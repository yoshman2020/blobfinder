// camera.js

import { renderBlobList } from "./blob.js";
import { draw, fitToWindow } from "./canvas.js";
import { loadImage } from "./image.js";
import { setStatus, state } from "./state.js";

let _fpsTimer = null;

export async function loadCameras() {
    setStatus("", "");
    const res = await fetch("/cameras");
    const data = await res.json();
    const sel = document.getElementById("cam-select");
    sel.innerHTML = "<option value=''>― カメラを選択 ―</option>";
    data.cameras.forEach((cam) => {
        const opt = document.createElement("option");
        opt.value = cam.uid;
        opt.textContent = `[${cam.index}] ${cam.name}`;
        sel.appendChild(opt);
    });
    if (data.cameras.length === 0)
        sel.innerHTML = "<option value=''>カメラなし</option>";
}

export async function startStream() {
    setStatus("", "");
    const uid = document.getElementById("cam-select").value;
    if (uid === "") return;

    // Open camera first
    const res = await fetch(`/camera/open/${uid}`, { method: "POST" });
    if (!res.ok) {
        setStatus("error", "カメラを開けませんでした");
        return;
    }

    // Now connect WebSocket
    const canvas = state.canvas;
    const img = new Image();
    let firstFrame = true;

    state.ws = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/camera/stream/ws`,
    );
    state.ws.binaryType = "arraybuffer";

    state.ws.onopen = async () => {
        console.log("WebSocket connected");
        document.getElementById("img-info").textContent = "streaming...";
        // カメラプロパティテーブルを読み込む
        await loadCamParamTable();
        // FPS表示タイマーを開始
        _fpsTimer = setInterval(async () => {
            const r = await fetch("/camera/fps");
            const d = await r.json();
            document.getElementById("cam-fps").textContent = d.fps + " fps";
        }, 1000);
    };

    state.ws.onerror = (e) => {
        console.error("WebSocket error:", e);
        setStatus("error", "ストリーミング接続エラー");
    };

    state.ws.onclose = () => {
        console.log("WebSocket disconnected");
        if (_fpsTimer) { clearInterval(_fpsTimer); _fpsTimer = null; }
        document.getElementById("img-info").textContent = "";
        document.getElementById("cam-fps").textContent = "";
        document.getElementById("cam-params").style.display = "none";
    };

    state.ws.onmessage = (event) => {
        const blob = new Blob([event.data], { type: "image/jpeg" });
        const url = URL.createObjectURL(blob);
        img.onload = () => {
            state.streamImage = img;
            // 初回フレームのみfitToWindow()を呼ぶ
            if (firstFrame) {
                firstFrame = false;
                fitToWindow();
            } else {
                draw(); // 毎フレーム描画
            }
            URL.revokeObjectURL(url);
        };
        img.src = url;
    };
}

export async function stopStream() {
    // FPSタイマーを停止
    if (_fpsTimer) {
        clearInterval(_fpsTimer);
        _fpsTimer = null;
    }

    // WebSocketを閉じる
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.close();
    }
    state.ws = null;

    // サーバー側でカメラを閉じる
    const res = await fetch("/camera/close", { method: "POST" });
    if (!res.ok) {
        setStatus("error", "カメラを閉じられませんでした");
        return;
    }
    // UI要素をクリア
    document.getElementById("img-info").textContent = "";
    document.getElementById("cam-fps").textContent = "";
    document.getElementById("cam-params").style.display = "none";

    // ストリーミング画像と元画像をリセット
    state.streamImage = null;
    state.originalImage = null;
    state.processedImage = null;

    // キャンバスをクリア
    const canvas = state.canvas;
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
}

export async function captureFrame() {
    setStatus("", "");
    const res = await fetch("/camera/capture", { method: "POST" });
    if (!res.ok) {
        setStatus("error", "キャプチャ失敗");
        return;
    }
    const data = await res.json();
    await stopStream();
    state.imageId = data.image_id;
    state.originalFilename = data.image_name.replace(/\.[^.]+$/, "");
    state.originalImage = await loadImage(data.image_url);
    state.processedImage = null;
    state.blobData = [];
    state.selectedBlobId = null;
    renderBlobList([]);
    state.showingOriginal = true;
    fitToWindow();
    setStatus("", "");
}

export async function loadCamParamTable() {
    const res = await fetch("/camera/params");
    if (!res.ok) return;
    const data = await res.json();
    const table = document.getElementById("cam-param-table");
    table.innerHTML = data.params
        .map((param) => renderCameraParam(param))
        .join("");
    document.getElementById("cam-params").style.display = "";
}

function renderCameraParam(param) {
    const key = param.key;
    const value = param.value;

    let control = "";

    switch (param.type) {

        case "number":
            control = `
                <input
                    type="number"
                    id="cparam-${key}"
                    value="${value ?? ""}"
                    min="${param.min ?? ""}"
                    max="${param.max ?? ""}"
                    step="${param.step ?? "any"}"
                    ${param.readonly ? "disabled" : ""}
                >
            `;
            break;

        case "range":
            control = `
                <div class="cam-range">
                    <input
                        type="range"
                        id="cparam-${key}"
                        value="${value ?? param.min}"
                        min="${param.min}"
                        max="${param.max}"
                        step="${param.step ?? 1}"
                        oninput="updateCameraRange('${key}', this.value)"
                    >
                    <input
                        type="number"
                        id="cparam-${key}-value"
                        value="${value ?? param.min}"
                        min="${param.min}"
                        max="${param.max}"
                        step="${param.step ?? 1}"
                        oninput="updateCameraRange('${key}', this.value)"
                    >
                    ${param.unit ? `<span>${param.unit}</span>` : ""}
                </div>
            `;
            break;

        case "select":
            control = `
                <select id="cparam-${key}">
                    ${(param.options || [])
                    .map(
                        (option) => `
                                <option
                                    value="${option.value}"
                                    ${String(option.value) === String(value) ? "selected" : ""}
                                >
                                    ${option.label}
                                </option>
                            `
                    )
                    .join("")}
                </select>
            `;
            break;

        case "checkbox":
            control = `
                <input
                    type="checkbox"
                    id="cparam-${key}"
                    ${value ? "checked" : ""}
                >
            `;
            break;
    }

    return `
        <tr>
            <td>${param.label || key}</td>
            <td>${control}</td>
        </tr>
    `;
}

window.updateCameraRange = function (key, value) {
    const range = document.getElementById(`cparam-${key}`);
    const number = document.getElementById(`cparam-${key}-value`);

    if (!range || !number) return;

    range.value = value;
    number.value = value;
};

export async function applyCamParams() {
    setStatus("", "");
    const params = {};
    document
        .querySelectorAll("#cam-param-table input, #cam-param-table select")
        .forEach((el) => {
            if (el.disabled) return;
            // rangeの連動用数値入力（-valueで終わるもの）は重複するためスキップする
            if (el.id.endsWith("-value")) return;
            const key = el.id.replace("cparam-", "");
            if (el.type === "checkbox") {
                params[key] = el.checked;
            } else if (el.type === "number") {
                params[key] = Number(el.value);
            } else if (el.type === "range") {
                params[key] = Number(el.value);
            } else if (el.tagName === "SELECT") {
                params[key] = el.value;
            }
        });
    const res = await fetch("/camera/params", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
    });
    if (!res.ok) {
        setStatus("error", "パラメータ適用失敗");
        return;
    }
    await loadCamParamTable();
    // パラメータ変更後に画面に反映させる
    fitToWindow();
}
