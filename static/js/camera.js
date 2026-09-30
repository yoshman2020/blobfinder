// camera.js

import { renderBlobList } from "./blob.js";
import { draw, fitToWindow } from "./canvas.js";
import { loadImage } from "./image.js";
import { setStatus, state } from "./state.js";

const CAM_PARAM_LABELS = {
    width: "Width(px)", height: "Height(px)", fps: "FPS設定",
    brightness: "明るさ", contrast: "コントラスト", saturation: "彩度",
    hue: "色相", gain: "ゲイン", exposure: "露光",
    autofocus: "オートフォーカス", focus: "フォーカス", auto_exposure: "自動露光",
};
// チェックボックスで表示するパラメータ
const CAM_PARAM_CHECKBOX = new Set(["autofocus", "auto_exposure"]);

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
    const params = await res.json();
    const table = document.getElementById("cam-param-table");
    table.innerHTML = Object.entries(params)
        .map(([k, v]) => {
            const label = CAM_PARAM_LABELS[k] || k;
            const unavailable = v === null;
            if (CAM_PARAM_CHECKBOX.has(k)) {
                const checked = !unavailable && v > 0 ? "checked" : "";
                const dis = unavailable ? "disabled" : "";
                return (
                    `<tr><td style="font-size:11px;padding:2px 4px">${label}</td>` +
                    `<td><input type="checkbox" id="cparam-${k}" ${checked} ${dis}></td></tr>`
                );
            }
            const val = !unavailable ? v : "";
            const dis = unavailable ? "disabled" : "";
            return (
                `<tr><td style="font-size:11px;padding:2px 4px">${label}</td>` +
                `<td><input type="number" id="cparam-${k}" value="${val}"` +
                ` style="width:70px;font-size:11px;padding:1px 3px" step="any" ${dis}></td></tr>`
            );
        })
        .join("");
    document.getElementById("cam-params").style.display = "";
}

export async function applyCamParams() {
    setStatus("", "");
    const table = document.getElementById("cam-param-table");
    const params = {};
    table.querySelectorAll("input").forEach((inp) => {
        if (inp.disabled) return;
        const key = inp.id.replace("cparam-", "");
        if (inp.type === "checkbox") {
            params[key] = inp.checked ? 1 : 0;
        } else if (inp.value !== "") {
            params[key] = Number(inp.value);
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
