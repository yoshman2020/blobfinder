// canvas.js

import { state } from "./state.js";

export function draw() {
    let img;
    if (state.streamImage) {
        img = state.streamImage;
    } else {
        switch (state.viewMode) {
            case "original":
                img = state.originalImage;
                break;
            case "step":
                img = state.intermediateImages[state.selectedStep];
                break;
            default:
                img = state.processedImage || state.originalImage;
                break;
        }
    }
    if (!img || !img.complete) return;
    state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
    state.ctx.save();
    state.ctx.translate(state.offsetX, state.offsetY);
    state.ctx.scale(state.zoom, state.zoom);
    state.ctx.drawImage(img, 0, 0);
    // 選択中ブロブのハイライト
    if (state.selectedBlobId !== null && !state.showingOriginal) {
        const b = state.blobData.find((b) => b.id === state.selectedBlobId);
        if (b) {
            state.ctx.strokeStyle = "#ff0";
            state.ctx.lineWidth = 2 / state.zoom;
            state.ctx.beginPath();
            state.ctx.arc(b.cx, b.cy, 12 / state.zoom, 0, Math.PI * 2);
            state.ctx.stroke();
            state.ctx.strokeStyle = "#f00";
            state.ctx.lineWidth = 1 / state.zoom;
            state.ctx.beginPath();
            state.ctx.moveTo(b.cx - 16 / state.zoom, b.cy);
            state.ctx.lineTo(b.cx + 16 / state.zoom, b.cy);
            state.ctx.moveTo(b.cx, b.cy - 16 / state.zoom);
            state.ctx.lineTo(b.cx, b.cy + 16 / state.zoom);
            state.ctx.stroke();
        }
    }
    state.ctx.restore();
    // 領域選択矩形の表示
    if (state.regionSelect) {
        const r = state.regionSelect;
        const x1 = r.startX * state.zoom + state.offsetX;
        const y1 = r.startY * state.zoom + state.offsetY;
        const x2 = r.endX * state.zoom + state.offsetX;
        const y2 = r.endY * state.zoom + state.offsetY;
        state.ctx.save();
        state.ctx.strokeStyle = "#f90";
        state.ctx.lineWidth = 1.5;
        state.ctx.setLineDash([4, 3]);
        state.ctx.strokeRect(
            Math.min(x1, x2), Math.min(y1, y2),
            Math.abs(x2 - x1), Math.abs(y2 - y1),
        );
        state.ctx.fillStyle = "rgba(255,153,0,0.08)";
        state.ctx.fillRect(
            Math.min(x1, x2), Math.min(y1, y2),
            Math.abs(x2 - x1), Math.abs(y2 - y1),
        );
        state.ctx.restore();
    }
}

export function fitToWindow() {
    const img =
        state.streamImage ||
        (state.showingOriginal ? state.originalImage : state.processedImage || state.originalImage);
    if (!img || !img.naturalWidth) return;
    state.zoom = Math.min(
        state.canvas.width / img.naturalWidth,
        state.canvas.height / img.naturalHeight,
    );
    state.offsetX = (state.canvas.width - img.naturalWidth * state.zoom) / 2;
    state.offsetY = (state.canvas.height - img.naturalHeight * state.zoom) / 2;
    draw();
}

export function originalSize() {
    state.zoom = 1.0;
    state.offsetX = 0;
    state.offsetY = 0;
    draw();
}

export function zoomIn() {
    state.zoom *= 1.2;
    draw();
}

export function zoomOut() {
    state.zoom /= 1.2;
    draw();
}

export function toggleImage() {
    if (!state.processedImage) return;
    state.showingOriginal = !state.showingOriginal;
    if (state.viewMode === "original") {
        if (state.selectedStep !== null) state.viewMode = "step";
        else state.viewMode = "result";
    } else {
        state.viewMode = "original";
    }
    draw();
}

export function canvasToImage(cx, cy) {
    return { x: (cx - state.offsetX) / state.zoom, y: (cy - state.offsetY) / state.zoom };
}

export function updateImgInfo(e) {
    const rect = state.canvas.getBoundingClientRect();
    const img = state.showingOriginal ? state.originalImage : state.processedImage || state.originalImage;
    if (!img) return;
    const { x, y } = canvasToImage(e.clientX - rect.left, e.clientY - rect.top);
    const ix = Math.round(x), iy = Math.round(y);
    const w = img.naturalWidth, h = img.naturalHeight;
    let rgbStr = "";
    if (ix >= 0 && iy >= 0 && ix < w && iy < h) {
        const tmp = document.createElement("canvas");
        tmp.width = w; tmp.height = h;
        tmp.getContext("2d").drawImage(img, 0, 0);
        const px = tmp.getContext("2d").getImageData(ix, iy, 1, 1).data;
        rgbStr = `  R:${px[0]} G:${px[1]} B:${px[2]}`;
    }
    document.getElementById("img-info").textContent =
        `${w} x ${h}px  |  X:${ix} Y:${iy}${rgbStr}`;
}

export function startRegionSelect(stepIndex) {
    state.regionSelect = { stepIndex, startX: 0, startY: 0, endX: 0, endY: 0 };
    state.regionDragging = false;
    state.canvas.style.cursor = "crosshair";
}

export async function downloadImage() {
    const img =
        state.streamImage ||
        (state.showingOriginal ? state.originalImage : state.processedImage || state.originalImage);
    if (!img || !img.complete) return;
    const w = img.naturalWidth, h = img.naturalHeight;
    // 実際の画像解像度でオフスクリーンキャンバスを作成
    const offscreenCanvas = document.createElement("canvas");
    offscreenCanvas.width = w;
    offscreenCanvas.height = h;
    const offCtx = offscreenCanvas.getContext("2d");
    // ズームやオフセットなしで元の解像度で描画
    offCtx.drawImage(img, 0, 0, w, h);
    // キャンバスをPNGで保存
    offscreenCanvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${state.originalFilename || "image"}_${w}x${h}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, "image/png");
}
