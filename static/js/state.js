// state.js

export const state = {
    imageId: null,
    originalFilename: "result",

    folderImages: [],
    selectedFile: null,

    pipeline: [],
    currentSettingsName: "",

    intermediateImages: [],
    selectedStep: null,

    showingOriginal: true,
    viewMode: "result",

    zoom: 1.0,
    offsetX: 0,
    offsetY: 0,

    dragging: false,
    lastX: 0,
    lastY: 0,

    canvas: null,
    ctx: null,
    menu: null,

    originalImage: null,
    processedImage: null,

    blobData: [],
    selectedBlobId: null,

    regionSelect: null,
    regionDragging: false,

    ws: null,
    streamImage: null,
};

export function setStatus(type, msg) {
    const el = document.getElementById("status");
    el.textContent = msg;
    el.className = "status " + type;
    el.style.display = msg ? "block" : "none";
}
