// main.js

import { saveBlobCsv, selectBlob, sortBlobList } from "./blob.js";
import {
    applyCamParams,
    captureFrame,
    loadCameras, startStream, stopStream,
} from "./camera.js";
import {
    canvasToImage,
    downloadImage,
    draw, fitToWindow, originalSize,
    startRegionSelect,
    toggleImage,
    updateImgInfo,
    zoomIn, zoomOut,
} from "./canvas.js";
import { loadImageList, saveResult, selectSingleFile } from "./image.js";
import {
    addProc,
    previewStep,
    removeStep, renderPipeline,
    runPipeline,
    updateParam,
} from "./pipeline.js";
import {
    closePipelineDialog,
    deleteSettings,
    exportSettings, importSettings,
    loadPipelineList,
    loadSettingsList,
    saveSettings,
    selectPipelineToLoad,
    selectSettingsToLoad,
    showDeleteDialog,
    updateCurrentSettingsDisplay,
} from "./settings.js";
import { shmConnect, shmSetQueueMax, shmSyncPipeline } from "./shm.js";
import { state } from "./state.js";

// HTMLのonclick属性から呼ばれる関数をグローバルに公開
window.fitToWindow = fitToWindow;
window.originalSize = originalSize;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.toggleImage = toggleImage;
window.saveResult = saveResult;
window.selectSingleFile = selectSingleFile;
window.loadImageList = loadImageList;
window.addProc = addProc;
window.removeStep = removeStep;
window.updateParam = updateParam;
window.runPipeline = runPipeline;
window.previewStep = previewStep;
window.startRegionSelect = startRegionSelect;
window.sortBlobList = sortBlobList;
window.selectBlob = selectBlob;
window.saveBlobCsv = saveBlobCsv;
window.loadCameras = loadCameras;
window.startStream = startStream;
window.stopStream = stopStream;
window.captureFrame = captureFrame;
window.applyCamParams = applyCamParams;
window.saveSettings = saveSettings;
window.selectSettingsToLoad = selectSettingsToLoad;
window.loadSettingsList = loadSettingsList;
window.deleteSettings = deleteSettings;
window.exportSettings = exportSettings;
window.importSettings = importSettings;
window.closeSettingsDialog = () => document.getElementById("settings-dialog")?.remove();
window.loadPipelineList = loadPipelineList;
window.showDeleteDialog = showDeleteDialog;
window.selectPipelineToLoad = selectPipelineToLoad;
window.closePipelineDialog = closePipelineDialog;
window.shmSetQueueMax = shmSetQueueMax;

function showMyMenu(x, y) {
    const menu = state.menu;
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.style.display = "block";
}

function hideMyMenu() {
    state.menu.style.display = "none";
}

window.showMyMenu = showMyMenu;
window.hideMyMenu = hideMyMenu;

// addProc / removeStep / selectSettingsToLoad に shmSyncPipeline をフック
const _origAddProc = addProc;
window.addProc = function (...args) { _origAddProc(...args); shmSyncPipeline(); };

const _origRemoveStep = removeStep;
window.removeStep = function (...args) { _origRemoveStep(...args); shmSyncPipeline(); };

const _origSelectSettingsToLoad = selectSettingsToLoad;
window.selectSettingsToLoad = async function (...args) {
    await _origSelectSettingsToLoad(...args);
    shmSyncPipeline();
};

window.addEventListener("DOMContentLoaded", () => {
    updateCurrentSettingsDisplay();
    state.canvas = document.getElementById("canvas");
    state.ctx = state.canvas.getContext("2d");
    state.menu = document.getElementById("contextMenu");

    // 右クリックで画像保存
    state.canvas.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        showMyMenu(e.clientX, e.clientY);
    });

    const resizeCanvas = () => {
        const area = state.canvas.parentElement;
        state.canvas.width = area.clientWidth - 20;
        state.canvas.height = area.clientHeight - 60;
        draw();
    };
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    state.canvas.addEventListener("mousedown", (e) => {
        const rect = state.canvas.getBoundingClientRect();
        const pos = canvasToImage(e.clientX - rect.left, e.clientY - rect.top);
        if (state.regionSelect) {
            state.regionDragging = true;
            state.regionSelect.startX = pos.x;
            state.regionSelect.startY = pos.y;
            state.regionSelect.endX = pos.x;
            state.regionSelect.endY = pos.y;
        } else {
            state.dragging = true;
            state.lastX = e.clientX;
            state.lastY = e.clientY;
        }
    });

    state.canvas.addEventListener("mouseup", (e) => {
        if (state.regionDragging && state.regionSelect) {
            state.regionDragging = false;
            state.canvas.style.cursor = "grab";
            const si = state.regionSelect.stepIndex;
            const x1 = Math.round(Math.min(state.regionSelect.startX, state.regionSelect.endX));
            const x2 = Math.round(Math.max(state.regionSelect.startX, state.regionSelect.endX));
            const y1 = Math.round(Math.min(state.regionSelect.startY, state.regionSelect.endY));
            const y2 = Math.round(Math.max(state.regionSelect.startY, state.regionSelect.endY));
            state.pipeline[si].params.min_cx = x1;
            state.pipeline[si].params.max_cx = x2;
            state.pipeline[si].params.min_cy = y1;
            state.pipeline[si].params.max_cy = y2;
            state.pipeline[si].params.filter_centroid = true;
            state.regionSelect = null;
            renderPipeline();
        }
        state.dragging = false;
    });

    state.canvas.addEventListener("mouseleave", () => { state.dragging = false; });

    state.canvas.addEventListener("mousemove", (e) => {
        updateImgInfo(e);
        const rect = state.canvas.getBoundingClientRect();
        const pos = canvasToImage(e.clientX - rect.left, e.clientY - rect.top);
        if (state.regionDragging && state.regionSelect) {
            state.regionSelect.endX = pos.x;
            state.regionSelect.endY = pos.y;
            draw();
            return;
        }
        if (!state.dragging) return;
        state.offsetX += e.clientX - state.lastX;
        state.offsetY += e.clientY - state.lastY;
        state.lastX = e.clientX;
        state.lastY = e.clientY;
        draw();
    });

    state.canvas.addEventListener("wheel", (e) => {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
        const rect = state.canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        state.offsetX = mx - (mx - state.offsetX) * factor;
        state.offsetY = my - (my - state.offsetY) * factor;
        state.zoom *= factor;
        draw();
    }, { passive: false });

    new Sortable(document.getElementById("pipeline"), {
        animation: 150,
        handle: ".drag-handle",
        onEnd: (evt) => {
            const item = state.pipeline.splice(evt.oldIndex, 1)[0];
            state.pipeline.splice(evt.newIndex, 0, item);
            state.selectedStep = null;
            state.intermediateImages = [];
            renderPipeline();
        },
    });

    // パネルリサイズ
    const handle = document.getElementById("resize-handle");
    const panel = document.querySelector(".panel");
    let resizing = false, resizeStartX = 0, resizeStartW = 0;
    handle.addEventListener("mousedown", (e) => {
        resizing = true;
        resizeStartX = e.clientX;
        resizeStartW = panel.offsetWidth;
        handle.classList.add("dragging");
        e.preventDefault();
    });
    document.addEventListener("mousemove", (e) => {
        if (!resizing) return;
        const delta = resizeStartX - e.clientX;
        const newW = Math.max(200, Math.min(window.innerWidth - 200, resizeStartW + delta));
        panel.style.width = newW + "px";
        resizeCanvas();
    });
    document.addEventListener("mouseup", () => {
        if (!resizing) return;
        resizing = false;
        handle.classList.remove("dragging");
    });
    // 共有メモリ WebSocket 接続開始
    shmConnect();
});

// セクションの折りたたみ
document.querySelectorAll("section").forEach((section) => {
    const toggle = section.querySelector(".section-toggle");
    if (!toggle) return;
    toggle.addEventListener("click", () => section.classList.toggle("collapsed"));
});

// 「画像を保存」
document.getElementById("menuSave").addEventListener("click", () => {
    hideMyMenu();
    downloadImage();
});
// メニュー外をクリックしたら閉じる
document.addEventListener("click", () => { hideMyMenu(); });
// ESCでも閉じる
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideMyMenu();
});