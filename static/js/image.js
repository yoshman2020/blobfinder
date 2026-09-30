// image.js

import { renderBlobList } from "./blob.js";
import { captureFrame, startStream } from "./camera.js";
import { fitToWindow } from "./canvas.js";
import { runPipeline } from "./pipeline.js";
import { setStatus, state } from "./state.js";

export function loadImage(url) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.src = url + "?t=" + Date.now();
    });
}

export async function uploadImage(file) {
    try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch("/upload", { method: "POST", body: fd });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `アップロードエラー (${res.status})`);
        }
        const data = await res.json();
        state.imageId = data.image_id;
        state.originalFilename = (data.image_name || file.name).replace(/\.[^.]+$/, "");
        state.originalImage = await loadImage(data.image_url);
        state.processedImage = null;
        state.blobData = [];
        state.selectedBlobId = null;
        renderBlobList([]);
        state.showingOriginal = true;
        fitToWindow();
        setStatus("", "");
    } catch (e) {
        setStatus("error", "アップロードエラー: " + e.message);
    }
}

export function clearFolderSelection() {
    document.getElementById("folder-input").value = "";
    state.folderImages = [];
    state.selectedFile = null;
    const list = document.getElementById("image-list");
    if (list) {
        list.innerHTML = "";
        list.style.display = "none";
    }
}

export function clearFileSelection() {
    document.getElementById("file-input").value = "";
}

export async function selectSingleFile(input) {
    clearFolderSelection();
    if (input.files.length === 0) {
        document.getElementById("selected-file-name").textContent = "未選択";
        return;
    }
    document.getElementById("selected-file-name").textContent = input.files[0].name;
    await uploadImage(input.files[0]);
}

export function loadImageList(files) {
    clearFileSelection();
    state.folderImages = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (state.folderImages.length > 0) {
        const folderName = state.folderImages[0].webkitRelativePath.split("/")[0];
        document.getElementById("selected-folder-name").textContent =
            `${folderName} (${state.folderImages.length}枚)`;
    } else {
        document.getElementById("selected-folder-name").textContent = "未選択";
    }
    renderImageList();
}

export function renderImageList() {
    const container = document.getElementById("image-list");
    container.innerHTML = "";
    state.folderImages.forEach((file, index) => {
        const url = URL.createObjectURL(file);
        const div = document.createElement("div");
        div.className = "image-item";
        div.innerHTML = `
            <img src="${url}" width="40">
            <span>${file.name}</span>
        `;
        div.onclick = () => selectImage(index);
        container.appendChild(div);
    });
    container.style.display = state.folderImages.length > 0 ? "flex" : "none";
}

export async function selectImage(index) {
    state.selectedFile = state.folderImages[index];
    document
        .querySelectorAll(".image-item")
        .forEach((e, i) => e.classList.toggle("selected", i === index));
    await uploadImage(state.selectedFile);
    if (state.pipeline.length > 0) {
        await runPipeline();
    }
}

export async function saveResult() {
    if (state.streamImage) {
        // ストリーミング中なら自動キャプチャ
        await captureFrame();
        // キャプチャ後再度ストリーミング開始
        await startStream();
    }
    if (!state.imageId) return;
    const a = document.createElement("a");
    a.href = `/download/${state.imageId}`;
    a.download = `${state.originalFilename}_processed.png`;
    a.click();
}