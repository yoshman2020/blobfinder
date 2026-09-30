// shm.js

// =====================
// 共有メモリ連携
// =====================

import { renderBlobList } from "./blob.js";
import { loadCameras, startStream, stopStream } from "./camera.js";
import { draw } from "./canvas.js";
import { renderPipeline } from "./pipeline.js";
import { updateCurrentSettingsDisplay } from "./settings.js";
import { setStatus, state } from "./state.js";

let _shmWs = null;
let _shmWsRetryTimer = null;

export function shmConnect() {
    if (_shmWs && _shmWs.readyState <= WebSocket.OPEN) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    _shmWs = new WebSocket(`${proto}//${location.host}/ws/shm_result`);

    _shmWs.onopen = () => {
        console.log("shm ws connected");
        if (_shmWsRetryTimer) { clearTimeout(_shmWsRetryTimer); _shmWsRetryTimer = null; }
        shmRefreshStatus();
    };

    _shmWs.onmessage = (ev) => {
        try { shmHandleResult(JSON.parse(ev.data)); } catch (e) { /* ignore */ }
    };

    _shmWs.onclose = () => {
        console.log("shm ws closed, retry in 3s");
        _shmWsRetryTimer = setTimeout(shmConnect, 3000);
    };

    _shmWs.onerror = () => { _shmWs.close(); };
}

export async function shmRefreshStatus() {
    try {
        const res = await fetch("/api/shm/status");
        if (!res.ok) return;
        const d = await res.json();
        document.getElementById("shm-streaming").textContent =
            d.camera_ready ? "📷 ストリーム中" : "📷 停止中";
        document.getElementById("shm-pipeline").textContent =
            d.pipeline_name ? `📋 ${d.pipeline_name}` : "📋 未選択";
        document.getElementById("shm-queue").textContent =
            `🗂 キュー: ${d.queue_length}/${d.queue_max}`;
    } catch (e) { /* ignore */ }
}

async function shmAutoStartStream() {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) return;
    await loadCameras();
    const sel = document.getElementById("cam-select");
    if (!sel || sel.options.length <= 1) return;
    sel.selectedIndex = 1;
    await startStream();
}

async function shmHandleResult(data) {
    if (data.event === "stream_start") { shmAutoStartStream(); return; }
    if (data.event === "pipeline_select") {
        state.pipeline = data.pipeline || [];
        state.currentSettingsName = data.pipeline_name || "";
        state.intermediateImages = [];
        state.selectedStep = null;
        updateCurrentSettingsDisplay();
        renderPipeline();
        shmSyncPipeline();
        shmRefreshStatus();
        return;
    }

    const panel = document.getElementById("shm-result");
    panel.style.display = "";

    const statusEl = document.getElementById("shm-result-status");
    const status = data.status || "?";
    const error = data.error;
    statusEl.textContent = error
        ? `❌ ${error}`
        : status === "ok" ? "✅ 処理完了"
            : status === "processing" ? "⏳ 処理中..."
                : status === "streaming" ? "📷 ストリーム中"
                    : `ℹ️ ${status}`;
    statusEl.style.color = error ? "#c00" : status === "ok" ? "#080" : "#555";

    // 撮影画像
    const capImg = document.getElementById("shm-capture-img");
    if (data.capture_b64) capImg.src = "data:image/jpeg;base64," + data.capture_b64;

    // 処理結果画像
    const resImg = document.getElementById("shm-result-img");
    if (data.result_b64) resImg.src = "data:image/jpeg;base64," + data.result_b64;

    // ブロブ数
    const blobEl = document.getElementById("shm-blob-count");
    if (Array.isArray(data.blobs)) {
        blobEl.textContent = `ブロブ: ${data.blobs.length} 件`;
        // メイン画面にも反映（共有メモリ指令が優先）
        if (data.status === "ok") {
            state.blobData = data.blobs;
            renderBlobList(state.blobData);
        }
    } else {
        blobEl.textContent = "";
    }

    // 撮影時刻
    document.getElementById("shm-captured-at").textContent =
        data.captured_at ? `撮影: ${data.captured_at}` : "";

    // メイン画面の処理結果画像も更新（共有メモリ指令優先）
    if (data.status === "ok") {
        await stopStream();
        if (data.image_id) {
            state.imageId = data.image_id;
            state.originalFilename = `shm_capture_${data.image_id.slice(0, 8)}`;
            state.processedImage = null;
            state.blobData = [];
        }
        if (data.capture_b64) {
            const capImg2 = new Image();
            capImg2.onload = () => { state.originalImage = capImg2; };
            capImg2.src = "data:image/jpeg;base64," + data.capture_b64;
        }
        if (data.result_b64) {
            const resImg2 = new Image();
            resImg2.onload = () => {
                state.processedImage = resImg2;
                state.showingOriginal = false;
                state.viewMode = "result";
                state.blobData = data.blobs || [];
                renderBlobList(state.blobData);
                draw();
                setStatus("", "");
            };
            resImg2.src = "data:image/jpeg;base64," + data.result_b64;
        }
    }

    shmRefreshStatus();
}

export async function shmSetQueueMax(val) {
    const n = parseInt(val);
    if (isNaN(n) || n < 1) return;
    await fetch("/api/shm/queue_max", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queue_max: n }),
    });
}

// pipeline が変わるたびに ShmController に同期する
export function shmSyncPipeline() {
    fetch("/api/shm/pipeline_sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline: state.pipeline, name: state.currentSettingsName || "" }),
    }).catch(() => { });
}