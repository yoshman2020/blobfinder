// pipeline.js

import { state, setStatus } from "./state.js";
import { draw, startRegionSelect } from "./canvas.js";
import { renderBlobList } from "./blob.js";
import { loadImage } from "./image.js";
import { captureFrame } from "./camera.js";

const PROC_LABELS = {
    r: "R抽出", g: "G抽出", b: "B抽出", gray: "Gray変換",
    h: "H抽出", l: "L抽出", s: "S抽出", invert: "反転", resize: "リサイズ",
    equalize: "ヒストグラム平滑化", clahe: "適応ヒストグラム平滑化",
    gaussian: "平滑化", median: "メディアン", bilateral: "バイラテラル",
    threshold: "二値化", adaptive_threshold: "適応二値化",
    distance_transform: "距離変換",
    opening: "オープニング", closing: "クロージング",
    dilate: "膨張", erode: "縮小", morphology: "モルフォロジー勾配",
    top_hat: "トップハット", black_hat: "ブラックハット",
    sobel: "Sobel", laplacian: "Laplacian", scharr: "Scharr", canny: "Canny",
    fill_holes: "穴埋め", remove_border: "境界ブロブ除去", watershed: "ウォーターシェッド",
    blob: "ブロブ解析",
};

const PARAM_DEFS = {
    clahe: [
        { key: "clip_limit", label: "Clip", type: "number", step: 0.1, min: 0.1 },
        { key: "tile", label: "Tile", type: "number", step: 1, min: 1 },
    ],
    gaussian: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    median: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    bilateral: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    threshold: [{ key: "value", label: "閾値", type: "number", step: 1, min: 0, max: 255 }],
    adaptive_threshold: [
        { key: "block", label: "Block", type: "number", step: 2, min: 3 },
        { key: "c", label: "C", type: "number", step: 1 },
        { key: "otsu", label: "大津の二値化", type: "checkbox" },
    ],
    distance_transform: [
        { key: "dist_type", label: "距離種類", type: "select", options: [{ value: 1, label: "L1" }, { value: 2, label: "L2" }, { value: 3, label: "C" }, { value: 4, label: "L1+L2" }, { value: 5, label: "Fair" }, { value: 6, label: "Welsch" }, { value: 7, label: "Huber" }] },
        { key: "mask_size", label: "マスクサイズ", type: "select", options: [{ value: 3, label: "3" }, { value: 5, label: "5" }, { value: 0, label: "0" }] },
    ],
    opening: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    closing: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    dilate: [
        { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
        { key: "iterations", label: "回数", type: "number", step: 1, min: 1 },
    ],
    erode: [
        { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
        { key: "iterations", label: "回数", type: "number", step: 1, min: 1 },
    ],
    morphology: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    top_hat: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    black_hat: [{ key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 }],
    sobel: [
        { key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 },
        { key: "x", label: "X", type: "checkbox" },
        { key: "y", label: "Y", type: "checkbox" },
    ],
    laplacian: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
    scharr: [{ key: "direction", label: "方向", type: "select", options: [{ value: "x", label: "X" }, { value: "y", label: "Y" }] }],
    canny: [
        { key: "low", label: "Low", type: "number", step: 1, min: 0 },
        { key: "high", label: "High", type: "number", step: 1, min: 0 },
    ],
    watershed: [
        { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
        { key: "opening_iterations", label: "オープニング回数", type: "number", step: 1, min: 0 },
        { key: "dilation_iterations", label: "膨張回数", type: "number", step: 1, min: 0 },
        { key: "distance_transform", label: "変換距離", type: "select", options: [{ value: 3, label: "3" }, { value: 5, label: "5" }, { value: 0, label: "0" }, { value: -1, label: "なし" }] },
    ],
    resize: [
        { key: "width", label: "W(px)", type: "number", step: 1, min: 0 },
        { key: "height", label: "H(px)", type: "number", step: 1, min: 0 },
        { key: "scale", label: "倍率", type: "number", step: 0.1, min: 0.1 },
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
        { key: "filter_centroid", label: "重心XYフィルタ", type: "checkbox" },
        { key: "min_cx", label: "最小X", type: "number", step: 1, min: 0 },
        { key: "max_cx", label: "最大X", type: "number", step: 1, min: 0 },
        { key: "min_cy", label: "最小Y", type: "number", step: 1, min: 0 },
        { key: "max_cy", label: "最大Y", type: "number", step: 1, min: 0 },
        { key: "_select_region", label: "領域をマウスで選択", type: "region_select" },
    ],
};

export function addProc(type, params = {}) {
    state.pipeline.push({ type, params: { ...params } });
    state.selectedStep = null;
    state.intermediateImages = [];
    renderPipeline();
}

export function removeStep(index) {
    state.pipeline.splice(index, 1);
    state.selectedStep = null;
    state.intermediateImages = [];
    renderPipeline();
}

export function renderPipeline() {
    const container = document.getElementById("pipeline");
    container.innerHTML = "";
    state.pipeline.forEach((step, i) => {
        const div = document.createElement("div");
        div.className = "pipeline-item";
        div.dataset.index = i;

        let paramsHtml = "";
        const defs = PARAM_DEFS[step.type] || [];
        if (defs.some((d) => d.type === "checkbox")) {
          paramsHtml = "<div>";
        }
        defs.forEach((def) => {
            const val = step.params[def.key] ?? "";
            if (def.type === "checkbox") {
                const checked = val ? "checked" : "";
                paramsHtml += `</div><div><label><input type="checkbox" ${checked}
                    onchange="updateParam(${i},'${def.key}',this.checked)">
                    ${def.label}</label> `;
            } else if (def.type === "select") {
                paramsHtml += `<label>${def.label}:
                    <select onchange="updateParam(${i},'${def.key}',this.value)">
                        ${def.options.map((opt) => `<option value="${opt.value}" ${opt.value === val ? "selected" : ""}>${opt.label}</option>`).join("")}
                    </select>
                </label> `;
            } else if (def.type === "region_select") {
                paramsHtml += `<button type="button" onclick="startRegionSelect(${i})" style="margin-top:4px;font-size:11px">📌 領域をマウスで選択</button>`;
            } else {
                paramsHtml += `<label>${def.label}:
                    <input type="number" value="${val}"
                        step="${def.step || 1}" min="${def.min ?? ""}" max="${def.max ?? ""}"
                        onchange="updateParam(${i},'${def.key}',this.value)">
                </label> `;
            }
        });
        if (defs.some((d) => d.type === "checkbox")) {
          paramsHtml += "</div>";
        }

        div.innerHTML = `<span class="drag-handle">☰</span>
            <b>${PROC_LABELS[step.type] || step.type}</b>
            <button class="btn-remove" onclick="removeStep(${i})">✕</button>
            <div class="params">${paramsHtml}</div>`;

        div.onclick = () => previewStep(i);
        container.appendChild(div);
    });
}

export function previewStep(index) {
    if (!state.intermediateImages[index]) return;
    state.selectedStep = index;
    state.viewMode = "step";
    draw();
    document
        .querySelectorAll(".pipeline-item")
        .forEach((e, idx) => e.classList.toggle("selected", idx === index));
}

export function updateParam(index, key, value) {
    const def = (PARAM_DEFS[state.pipeline[index].type] || []).find((d) => d.key === key);
    if (def && def.type === "checkbox") {
        state.pipeline[index].params[key] = value === true || value === "true";
    } else if (def && def.type === "number") {
        state.pipeline[index].params[key] = Number(value);
    } else {
        state.pipeline[index].params[key] = value;
    }
}

export async function runPipeline() {
    state.selectedStep = null;
    state.viewMode = "result";
    state.intermediateImages = [];
    if (state.pipeline.length === 0) return;
    if (!state.imageId) {
        // カメラオープン中なら自動キャプチャ
        const camSel = document.getElementById("cam-select");
        if (!camSel || camSel.value === "") return;
        await captureFrame();
        if (!state.imageId) return;
    }
    setStatus("processing", "処理中...");
    try {
        const res = await fetch(`/process/${state.imageId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pipeline: state.pipeline }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `サーバーエラー (${res.status})`);
        }
        const data = await res.json();
        if (data.result_url) {
            state.processedImage = await loadImage(data.result_url);
            state.showingOriginal = false;
            state.blobData = data.blobs || [];
            renderBlobList(state.blobData);
            draw();
            setStatus("", "");
        } else {
            setStatus("error", "処理に失敗しました");
        }
        if (data.intermediate_urls) {
            state.intermediateImages = await Promise.all(
                data.intermediate_urls.map((url) => loadImage(url)),
            );
        }
    } catch (e) {
        setStatus("error", "エラー: " + e.message);
    }
    console.log("pipeline", state.pipeline.length);
    console.log("intermediateImages", state.intermediateImages?.length);
    console.log("last index", state.pipeline.length - 1);
}
