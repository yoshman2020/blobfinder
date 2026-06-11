let imageId = null;
let originalFilename = "result";
let pipeline = [];
let showingOriginal = true;
let zoom = 1.0;
let offsetX = 0, offsetY = 0;
let dragging = false, lastX = 0, lastY = 0;
let canvas, ctx;
let originalImage = null, processedImage = null;
let blobData = [];
let selectedBlobId = null;

const PROC_LABELS = {
    r: "R抽出", g: "G抽出", b: "B抽出", gray: "Gray変換",
    h: "H抽出", l: "L抽出", s: "S抽出", invert: "反転",
    equalize: "ヒストグラム平滑化", clahe: "適応ヒストグラム平滑化",
    gaussian: "平滑化", median: "メディアン", bilateral: "バイラテラル",
    threshold: "二値化", adaptive_threshold: "適応二値化",
    opening: "オープニング", closing: "クロージング",
    dilate: "膨張", erode: "縮小", morphology: "モルフォロジー勾配",
    top_hat: "トップハット", black_hat: "ブラックハット",
    sobel: "Sobel", laplacian: "Laplacian", scharr: "Scharr", canny: "Canny",
    fill_holes: "穴埋め", remove_border: "境界ブロブ除去",
    watershed: "ウォーターシェッド", blob: "ブロブ解析",
};

// パラメータ型定義
const PARAM_DEFS = {
    clahe: [
        { key: "clip_limit", label: "Clip", type: "number", step: 0.1, min: 0.1 },
        { key: "tile", label: "Tile", type: "number", step: 1, min: 1 }
    ],
    gaussian: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    median: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    bilateral: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    threshold: [{ key: "value", label: "閾値", type: "number", step: 1, min: 0, max: 255 }],
    adaptive_threshold: [
        { key: "block", label: "Block", type: "number", step: 2, min: 3 },
        { key: "c", label: "C", type: "number", step: 1 },
        { key: "otsu", label: "大津の二値化", type: "checkbox" }
    ],
    opening: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    closing: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    dilate: [
        { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
        { key: "iterations", label: "回数", type: "number", step: 1, min: 1 }
    ],
    erode: [
        { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
        { key: "iterations", label: "回数", type: "number", step: 1, min: 1 }
    ],
    morphology: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    top_hat: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    black_hat: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    sobel: [
        { key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 },
        { key: "x", label: "X", type: "checkbox" },
        { key: "y", label: "Y", type: "checkbox" }
    ],
    laplacian: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    scharr: [
        {
            key: "direction", label: "方向", type: "select", options: [
                { value: "x", label: "X" },
                { value: "y", label: "Y" },
            ]
        }
    ],
    canny: [
        { key: "low", label: "Low", type: "number", step: 1, min: 0 },
        { key: "high", label: "High", type: "number", step: 1, min: 0 }
    ],
    watershed: [
        { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
        { key: "opening_iterations", label: "オープニング回数", type: "number", step: 1, min: 1 },
        { key: "dilation_iterations", label: "膨張回数", type: "number", step: 1, min: 1 },
        {
            key: "distance_transform", label: "変換距離", type: "select", options: [
                { value: 3, label: "3" },
                { value: 5, label: "5" },
                { value: 0, label: "0" }
            ]
        }
    ],
    blob: [
        { key: "filter_area", label: "面積フィルタ", type: "checkbox" },
        { key: "min_area", label: "最小面積", type: "number", step: 1, min: 0 },
        { key: "max_area", label: "最大面積", type: "number", step: 1, min: 0 },
        { key: "filter_circularity", label: "真円度フィルタ", type: "checkbox" },
        { key: "min_circularity", label: "最小真円度", type: "number", step: 0.01, min: 0, max: 1 },
        { key: "filter_convexity", label: "凸度フィルタ", type: "checkbox" },
        { key: "min_convexity", label: "最小凸度", type: "number", step: 0.01, min: 0, max: 1 },
        { key: "filter_inertia", label: "慣性比フィルタ", type: "checkbox" },
        { key: "min_inertia", label: "最小慣性比", type: "number", step: 0.01, min: 0, max: 1 },
        { key: "filter_color", label: "色フィルタ", type: "checkbox" },
        { key: "blob_color", label: "Blob色(0=暗/255=明)", type: "number", step: 255, min: 0, max: 255 },
        { key: "filter_side", label: "辺長フィルタ", type: "checkbox" },
        { key: "min_long_side", label: "最小長辺", type: "number", step: 1, min: 0 },
        { key: "max_short_side", label: "最大短辺", type: "number", step: 1, min: 0 },
        { key: "filter_angle", label: "角度フィルタ", type: "checkbox" },
        { key: "min_angle", label: "最小角度", type: "number", step: 1, min: -180, max: 180 },
        { key: "max_angle", label: "最大角度", type: "number", step: 1, min: -180, max: 180 },
    ],
};

function draw() {
    const img = showingOriginal ? originalImage : (processedImage || originalImage);
    if (!img || !img.complete) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(zoom, zoom);
    ctx.drawImage(img, 0, 0);
    // 選択中ブロブのハイライト
    if (selectedBlobId !== null && !showingOriginal) {
        const b = blobData.find(b => b.id === selectedBlobId);
        if (b) {
            ctx.strokeStyle = "#ff0";
            ctx.lineWidth = 2 / zoom;
            ctx.beginPath();
            ctx.arc(b.cx, b.cy, 12 / zoom, 0, Math.PI * 2);
            ctx.stroke();
            ctx.strokeStyle = "#f00";
            ctx.lineWidth = 1 / zoom;
            ctx.beginPath();
            ctx.moveTo(b.cx - 16 / zoom, b.cy);
            ctx.lineTo(b.cx + 16 / zoom, b.cy);
            ctx.moveTo(b.cx, b.cy - 16 / zoom);
            ctx.lineTo(b.cx, b.cy + 16 / zoom);
            ctx.stroke();
        }
    }
    ctx.restore();
}

function fitToWindow() {
    const img = showingOriginal ? originalImage : (processedImage || originalImage);
    if (!img) return;
    zoom = Math.min(canvas.width / img.naturalWidth, canvas.height / img.naturalHeight);
    offsetX = (canvas.width - img.naturalWidth * zoom) / 2;
    offsetY = (canvas.height - img.naturalHeight * zoom) / 2;
    draw();
}

function originalSize() {
    zoom = 1.0;
    offsetX = 0; offsetY = 0;
    draw();
}

function zoomIn() { zoom *= 1.2; draw(); }
function zoomOut() { zoom /= 1.2; draw(); }

function toggleImage() {
    if (!processedImage) return;
    showingOriginal = !showingOriginal;
    draw();
}

function loadImage(url) {
    return new Promise(resolve => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.src = url + "?t=" + Date.now();
    });
}

async function uploadImage(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/upload", { method: "POST", body: fd });
    const data = await res.json();
    imageId = data.image_id;
    originalFilename = (data.image_name || file.name).replace(/\.[^.]+$/, "");
    originalImage = await loadImage(data.image_url);
    processedImage = null;
    blobData = [];
    selectedBlobId = null;
    renderBlobList([]);
    showingOriginal = true;
    fitToWindow();
}

function setStatus(type, msg) {
    const el = document.getElementById("status");
    el.textContent = msg;
    el.className = "status " + type; // "", "processing", "error"
    el.style.display = msg ? "block" : "none";
}

async function runPipeline() {
    if (!imageId || pipeline.length === 0) return;
    setStatus("processing", "処理中...");
    try {
        const res = await fetch(`/process/${imageId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pipeline })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `サーバーエラー (${res.status})`);
        }
        const data = await res.json();
        if (data.result_url) {
            processedImage = await loadImage(data.result_url);
            showingOriginal = false;
            blobData = data.blobs || [];
            renderBlobList(blobData);
            draw();
            setStatus("", "");
        }
        else {
            setStatus("error", "処理に失敗しました");
        }
    } catch (e) {
        setStatus("error", "エラー: " + e.message);
    }
}

function saveResult() {
    if (!imageId) return;
    const a = document.createElement("a");
    a.href = `/download/${imageId}`;
    a.download = `${originalFilename}_processed.png`;
    a.click();
}

function saveBlobCsv() {
    if (!blobData.length) return;
    const cols  = ["id", "cx", "cy", "area", "circularity", "convexity", "inertia_ratio", "perimeter", "rect_long", "rect_short"];
    const heads = ["#",  "X",  "Y",  "面積", "真円度",       "凸度",      "慣性比",        "周囲長",     "長辺",       "短辺"];
    const rows = [heads.join(",")];
    blobData.forEach(b => {
        rows.push(cols.map(k => b[k] !== undefined ? b[k] : "").join(","));
    });
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${originalFilename}_blobs.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
}

function addProc(type, params = {}) {
    pipeline.push({ type, params: { ...params } });
    renderPipeline();
}

function removeStep(index) {
    pipeline.splice(index, 1);
    renderPipeline();
}

function renderPipeline() {
    const container = document.getElementById("pipeline");
    container.innerHTML = "";
    pipeline.forEach((step, i) => {
        const div = document.createElement("div");
        div.className = "pipeline-item";
        div.dataset.index = i;

        let paramsHtml = "";
        const defs = PARAM_DEFS[step.type] || [];
        if (defs.some(d => d.type === "checkbox")) {
            paramsHtml = "<div>";
        }
        defs.forEach(def => {
            const val = step.params[def.key] ?? "";
            if (def.type === "checkbox") {
                const checked = val ? "checked" : "";
                paramsHtml += `</div><div><label><input type="checkbox" ${checked}
                    onchange="updateParam(${i},'${def.key}',this.checked)">
                    ${def.label}</label> `;
            } else if (def.type === "select") {
                paramsHtml += `<label>${def.label}:
                    <select onchange="updateParam(${i},'${def.key}',this.value)">
                        ${def.options.map(opt => `<option value="${opt.value}" ${opt.value === val ? "selected" : ""}>${opt.label}</option>`).join("")}
                    </select>
                </label> `;
            } else {
                paramsHtml += `<label>${def.label}:
                    <input type="number" value="${val}"
                        step="${def.step || 1}" min="${def.min ?? ""}" max="${def.max ?? ""}"
                        onchange="updateParam(${i},'${def.key}',this.value)">
                </label> `;
            }
        });
        if (defs.some(d => d.type === "checkbox")) {
            paramsHtml += "</div>";
        }

        div.innerHTML = `<span class="drag-handle">☰</span>
            <b>${PROC_LABELS[step.type] || step.type}</b>
            <button class="btn-remove" onclick="removeStep(${i})">✕</button>
            <div class="params">${paramsHtml}</div>`;
        container.appendChild(div);
    });
}

let blobSortCol = null;
let blobSortAsc = true;

function renderBlobList(blobs) {
    const section = document.getElementById("blob-section");
    const container = document.getElementById("blob-list");
    if (!blobs || blobs.length === 0) {
        section.style.display = "none";
        return;
    }
    section.style.display = "";
    const cols  = ["id", "cx", "cy", "area", "circularity", "convexity", "inertia_ratio", "perimeter", "rect_long", "rect_short"];
    const heads = ["#",  "X",  "Y",  "面積", "真円度",       "凸度",      "慣性比",        "周囲長",     "長辺",       "短辺"];

    let sorted = [...blobs];
    if (blobSortCol !== null) {
        sorted.sort((a, b) => {
            const va = a[cols[blobSortCol]] ?? 0;
            const vb = b[cols[blobSortCol]] ?? 0;
            return blobSortAsc ? va - vb : vb - va;
        });
    }

    const thHtml = heads.map((h, i) => {
        const arrow = blobSortCol === i ? (blobSortAsc ? " ▲" : " ▼") : "";
        return `<th onclick="sortBlobList(${i})" style="cursor:pointer">${h}${arrow}</th>`;
    }).join("");

    let html = `<table class="blob-table"><thead><tr>${thHtml}</tr></thead><tbody>`;
    sorted.forEach(b => {
        const color = b.color ? `rgb(${b.color[2]},${b.color[1]},${b.color[0]})` : "#ccc";
        const sel = b.id === selectedBlobId ? " selected" : "";
        html += `<tr class="blob-row${sel}" data-id="${b.id}" onclick="selectBlob(${b.id})" style="--blob-color:${color}">`;
        cols.forEach(k => {
            const v = b[k] !== undefined ? b[k] : "-";
            html += `<td>${typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(3)) : v}</td>`;
        });
        html += `</tr>`;
    });
    html += `</tbody></table>`;
    container.innerHTML = html;
}

function sortBlobList(colIndex) {
    if (blobSortCol === colIndex) {
        blobSortAsc = !blobSortAsc;
    } else {
        blobSortCol = colIndex;
        blobSortAsc = true;
    }
    renderBlobList(blobData);
}

function selectBlob(id) {
    selectedBlobId = (selectedBlobId === id) ? null : id;
    document.querySelectorAll(".blob-row").forEach(row => {
        row.classList.toggle("selected", parseInt(row.dataset.id) === selectedBlobId);
    });
    draw();
}

function updateParam(index, key, value) {
    const def = (PARAM_DEFS[pipeline[index].type] || []).find(d => d.key === key);
    if (def && def.type === "checkbox") {
        pipeline[index].params[key] = value === true || value === "true";
    } else if (def && def.type === "number") {
        pipeline[index].params[key] = Number(value);
    } else {
        pipeline[index].params[key] = value;
    }
}

window.addEventListener("DOMContentLoaded", () => {
    canvas = document.getElementById("canvas");
    ctx = canvas.getContext("2d");

    const resizeCanvas = () => {
        const area = canvas.parentElement;
        canvas.width = area.clientWidth - 20;
        canvas.height = area.clientHeight - 60;
        draw();
    };
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    canvas.addEventListener("mousedown", e => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
    canvas.addEventListener("mouseup", () => { dragging = false; });
    canvas.addEventListener("mouseleave", () => { dragging = false; });
    canvas.addEventListener("mousemove", e => {
        if (!dragging) return;
        offsetX += e.clientX - lastX;
        offsetY += e.clientY - lastY;
        lastX = e.clientX; lastY = e.clientY;
        draw();
    });
    canvas.addEventListener("wheel", e => {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        offsetX = mx - (mx - offsetX) * factor;
        offsetY = my - (my - offsetY) * factor;
        zoom *= factor;
        draw();
    }, { passive: false });

    new Sortable(document.getElementById("pipeline"), {
        animation: 150,
        handle: ".drag-handle",
        onEnd: evt => {
            const item = pipeline.splice(evt.oldIndex, 1)[0];
            pipeline.splice(evt.newIndex, 0, item);
            renderPipeline();
        }
    });
});
