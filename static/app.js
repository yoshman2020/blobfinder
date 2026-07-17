let imageId = null;
let originalFilename = "result";
let folderImages = [];
let selectedFile = null;
let pipeline = [];
let currentSettingsName = ""; // 現在の設定名
let intermediateImages = [];
let selectedStep = null;
let showingOriginal = true;
let zoom = 1.0;
let offsetX = 0,
  offsetY = 0;
let dragging = false,
  lastX = 0,
  lastY = 0;
let canvas, ctx, menu;
let originalImage = null,
  processedImage = null;
let viewMode = "result";
let blobData = [];
let selectedBlobId = null;
let regionSelect = null; // {stepIndex, startX, startY, endX, endY} | null
let regionDragging = false;
let ws = null;
let streamImage = null; // ストリーミング中の現在フレーム
let _streamTimer = null;

const PROC_LABELS = {
  r: "R抽出",
  g: "G抽出",
  b: "B抽出",
  gray: "Gray変換",
  h: "H抽出",
  l: "L抽出",
  s: "S抽出",
  invert: "反転",
  resize: "リサイズ",
  equalize: "ヒストグラム平滑化",
  clahe: "適応ヒストグラム平滑化",
  gaussian: "平滑化",
  median: "メディアン",
  bilateral: "バイラテラル",
  threshold: "二値化",
  adaptive_threshold: "適応二値化",
  distance_transform: "距離変換",
  opening: "オープニング",
  closing: "クロージング",
  dilate: "膨張",
  erode: "縮小",
  morphology: "モルフォロジー勾配",
  top_hat: "トップハット",
  black_hat: "ブラックハット",
  sobel: "Sobel",
  laplacian: "Laplacian",
  scharr: "Scharr",
  canny: "Canny",
  fill_holes: "穴埋め",
  remove_border: "境界ブロブ除去",
  watershed: "ウォーターシェッド",
  blob: "ブロブ解析",
};

// パラメータ型定義
const PARAM_DEFS = {
  clahe: [
    { key: "clip_limit", label: "Clip", type: "number", step: 0.1, min: 0.1 },
    { key: "tile", label: "Tile", type: "number", step: 1, min: 1 },
  ],
  gaussian: [
    { key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 },
  ],
  median: [{ key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 }],
  bilateral: [
    { key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 },
  ],
  threshold: [
    { key: "value", label: "閾値", type: "number", step: 1, min: 0, max: 255 },
  ],
  adaptive_threshold: [
    { key: "block", label: "Block", type: "number", step: 2, min: 3 },
    { key: "c", label: "C", type: "number", step: 1 },
    { key: "otsu", label: "大津の二値化", type: "checkbox" },
  ],
  distance_transform: [
    {
      key: "dist_type",
      label: "距離種類",
      type: "select",
      options: [
        { value: 1, label: "L1" },
        { value: 2, label: "L2" },
        { value: 3, label: "C" },
        { value: 4, label: "L1+L2" },
        { value: 5, label: "Fair" },
        { value: 6, label: "Welsch" },
        { value: 7, label: "Huber" },
      ],
    },
    {
      key: "mask_size",
      label: "マスクサイズ",
      type: "select",
      options: [
        { value: 3, label: "3" },
        { value: 5, label: "5" },
        { value: 0, label: "0" },
      ],
    },
  ],
  opening: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
  ],
  closing: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
  ],
  dilate: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
    { key: "iterations", label: "回数", type: "number", step: 1, min: 1 },
  ],
  erode: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
    { key: "iterations", label: "回数", type: "number", step: 1, min: 1 },
  ],
  morphology: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
  ],
  top_hat: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
  ],
  black_hat: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
  ],
  sobel: [
    { key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 },
    { key: "x", label: "X", type: "checkbox" },
    { key: "y", label: "Y", type: "checkbox" },
  ],
  laplacian: [
    { key: "kernel", label: "Kernel", type: "number", step: 2, min: 1 },
  ],
  scharr: [
    {
      key: "direction",
      label: "方向",
      type: "select",
      options: [
        { value: "x", label: "X" },
        { value: "y", label: "Y" },
      ],
    },
  ],
  canny: [
    { key: "low", label: "Low", type: "number", step: 1, min: 0 },
    { key: "high", label: "High", type: "number", step: 1, min: 0 },
  ],
  watershed: [
    { key: "kernel", label: "Kernel", type: "number", step: 1, min: 1 },
    {
      key: "opening_iterations",
      label: "オープニング回数",
      type: "number",
      step: 1,
      min: 0,
    },
    {
      key: "dilation_iterations",
      label: "膨張回数",
      type: "number",
      step: 1,
      min: 0,
    },
    {
      key: "distance_transform",
      label: "変換距離",
      type: "select",
      options: [
        { value: 3, label: "3" },
        { value: 5, label: "5" },
        { value: 0, label: "0" },
        { value: -1, label: "なし" },
      ],
    },
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
    {
      key: "min_circularity",
      label: "最小真円度",
      type: "number",
      step: 0.01,
      min: 0,
      max: 1,
    },
    { key: "filter_convexity", label: "凸度フィルタ", type: "checkbox" },
    {
      key: "min_convexity",
      label: "最小凸度",
      type: "number",
      step: 0.01,
      min: 0,
      max: 1,
    },
    { key: "filter_inertia", label: "慣性比フィルタ", type: "checkbox" },
    {
      key: "min_inertia",
      label: "最小慣性比",
      type: "number",
      step: 0.01,
      min: 0,
      max: 1,
    },
    { key: "filter_color", label: "色フィルタ", type: "checkbox" },
    {
      key: "blob_color",
      label: "Blob色(0=暗/255=明)",
      type: "number",
      step: 255,
      min: 0,
      max: 255,
    },
    { key: "filter_side", label: "辺長フィルタ", type: "checkbox" },
    {
      key: "min_long_side",
      label: "最小長辺",
      type: "number",
      step: 1,
      min: 0,
    },
    {
      key: "max_short_side",
      label: "最大短辺",
      type: "number",
      step: 1,
      min: 0,
    },
    { key: "filter_angle", label: "角度フィルタ", type: "checkbox" },
    {
      key: "min_angle",
      label: "最小角度",
      type: "number",
      step: 1,
      min: -180,
      max: 180,
    },
    {
      key: "max_angle",
      label: "最大角度",
      type: "number",
      step: 1,
      min: -180,
      max: 180,
    },
    { key: "filter_centroid", label: "重心XYフィルタ", type: "checkbox" },
    { key: "min_cx", label: "最小X", type: "number", step: 1, min: 0 },
    { key: "max_cx", label: "最大X", type: "number", step: 1, min: 0 },
    { key: "min_cy", label: "最小Y", type: "number", step: 1, min: 0 },
    { key: "max_cy", label: "最大Y", type: "number", step: 1, min: 0 },
    {
      key: "_select_region",
      label: "領域をマウスで選択",
      type: "region_select",
    },
  ],
};

function draw() {
  let img;
  if (streamImage) {
    img = streamImage;
  } else {
    switch (viewMode) {
      case "original":
        img = originalImage;
        break;
      case "step":
        img = intermediateImages[selectedStep];
        break;
      default:
        img = processedImage || originalImage;
        break;
    }
  }
  if (!img || !img.complete) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(offsetX, offsetY);
  ctx.scale(zoom, zoom);
  ctx.drawImage(img, 0, 0);
  // 選択中ブロブのハイライト
  if (selectedBlobId !== null && !showingOriginal) {
    const b = blobData.find((b) => b.id === selectedBlobId);
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
  // 領域選択矩形の表示
  if (regionSelect) {
    const r = regionSelect;
    const x1 = r.startX * zoom + offsetX;
    const y1 = r.startY * zoom + offsetY;
    const x2 = r.endX * zoom + offsetX;
    const y2 = r.endY * zoom + offsetY;
    ctx.save();
    ctx.strokeStyle = "#f90";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(
      Math.min(x1, x2),
      Math.min(y1, y2),
      Math.abs(x2 - x1),
      Math.abs(y2 - y1),
    );
    ctx.fillStyle = "rgba(255,153,0,0.08)";
    ctx.fillRect(
      Math.min(x1, x2),
      Math.min(y1, y2),
      Math.abs(x2 - x1),
      Math.abs(y2 - y1),
    );
    ctx.restore();
  }
}

function fitToWindow() {
  const img =
    streamImage ||
    (showingOriginal ? originalImage : processedImage || originalImage);
  if (!img || !img.naturalWidth) return;
  zoom = Math.min(
    canvas.width / img.naturalWidth,
    canvas.height / img.naturalHeight,
  );
  offsetX = (canvas.width - img.naturalWidth * zoom) / 2;
  offsetY = (canvas.height - img.naturalHeight * zoom) / 2;
  draw();
}

function originalSize() {
  zoom = 1.0;
  offsetX = 0;
  offsetY = 0;
  draw();
}

function zoomIn() {
  zoom *= 1.2;
  draw();
}
function zoomOut() {
  zoom /= 1.2;
  draw();
}

function toggleImage() {
  if (!processedImage) return;
  showingOriginal = !showingOriginal;
  if (viewMode === "original") {
    if (selectedStep !== null) viewMode = "step";
    else viewMode = "result";
  } else {
    viewMode = "original";
  }
  draw();
}

function loadImage(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.src = url + "?t=" + Date.now();
  });
}

async function uploadImage(file) {
  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/upload", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `アップロードエラー (${res.status})`);
    }
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
    setStatus("", "");
  } catch (e) {
    setStatus("error", "アップロードエラー: " + e.message);
  }
}

function clearFolderSelection() {
  document.getElementById("folder-input").value = "";
  folderImages = [];
  selectedFile = null;

  const list = document.getElementById("image-list");
  if (list) list.innerHTML = "";
}

function clearFileSelection() {
  document.getElementById("file-input").value = "";
}

async function selectSingleFile(input) {
  clearFolderSelection();
  if (input.files.length === 0) {
    document.getElementById("selected-file-name").textContent = "未選択";
    return;
  }
  document.getElementById("selected-file-name").textContent =
    input.files[0].name;
  await uploadImage(input.files[0]);
}

function loadImageList(files) {
  clearFileSelection();
  folderImages = Array.from(files).filter((f) => f.type.startsWith("image/"));
  if (folderImages.length > 0) {
    const folderName = folderImages[0].webkitRelativePath.split("/")[0];
    document.getElementById("selected-folder-name").textContent =
      `${folderName} (${folderImages.length}枚)`;
  } else {
    document.getElementById("selected-folder-name").textContent = "未選択";
  }
  renderImageList();
}

function renderImageList() {
  const container = document.getElementById("image-list");
  container.innerHTML = "";
  folderImages.forEach((file, index) => {
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
}

async function selectImage(index) {
  selectedFile = folderImages[index];
  document
    .querySelectorAll(".image-item")
    .forEach((e, i) => e.classList.toggle("selected", i === index));
  await uploadImage(selectedFile);
  if (pipeline.length > 0) {
    await runPipeline();
  }
}

function setStatus(type, msg) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = "status " + type; // "", "processing", "error"
  el.style.display = msg ? "block" : "none";
}

async function runPipeline() {
  selectedStep = null;
  viewMode = "result";
  intermediateImages = [];
  if (!imageId || pipeline.length === 0) return;
  setStatus("processing", "処理中...");
  try {
    const res = await fetch(`/process/${imageId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipeline }),
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
    } else {
      setStatus("error", "処理に失敗しました");
    }
    if (data.intermediate_urls) {
      intermediateImages = await Promise.all(
        data.intermediate_urls.map((url) => loadImage(url)),
      );
    }
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
  console.log("pipeline", pipeline.length);
  console.log("intermediateImages", intermediateImages?.length);
  console.log("last index", pipeline.length - 1);
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
  const cols = [
    "id",
    "cx",
    "cy",
    "area",
    "circularity",
    "convexity",
    "inertia_ratio",
    "perimeter",
    "rect_long",
    "rect_short",
  ];
  const heads = [
    "#",
    "X",
    "Y",
    "面積",
    "真円度",
    "凸度",
    "慣性比",
    "周囲長",
    "長辺",
    "短辺",
  ];
  const rows = [heads.join(",")];
  blobData.forEach((b) => {
    rows.push(cols.map((k) => (b[k] !== undefined ? b[k] : "")).join(","));
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
  selectedStep = null;
  intermediateImages = [];
  renderPipeline();
}

function removeStep(index) {
  pipeline.splice(index, 1);
  selectedStep = null;
  intermediateImages = [];
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

function previewStep(index) {
  if (!intermediateImages[index]) return;
  selectedStep = index;
  viewMode = "step";
  draw();
  document
    .querySelectorAll(".pipeline-item")
    .forEach((e, idx) => e.classList.toggle("selected", idx === index));
}

let blobSortCol = null;
let blobSortAsc = true;

function renderBlobList(blobs) {
  const section = document.getElementById("blob-section");
  const container = document.getElementById("blob-list");
  const countSpan = document.getElementById("blob-count");
  if (!blobs || blobs.length === 0) {
    section.style.display = "none";
    return;
  }
  section.style.display = "";
  countSpan.textContent = `(${blobs.length}件)`;
  const cols = [
    "id",
    "cx",
    "cy",
    "area",
    "circularity",
    "convexity",
    "inertia_ratio",
    "perimeter",
    "rect_long",
    "rect_short",
  ];
  const heads = [
    "#",
    "X",
    "Y",
    "面積",
    "真円度",
    "凸度",
    "慣性比",
    "周囲長",
    "長辺",
    "短辺",
  ];

  let sorted = [...blobs];
  if (blobSortCol !== null) {
    sorted.sort((a, b) => {
      const va = a[cols[blobSortCol]] ?? 0;
      const vb = b[cols[blobSortCol]] ?? 0;
      return blobSortAsc ? va - vb : vb - va;
    });
  }

  const thHtml = heads
    .map((h, i) => {
      const arrow = blobSortCol === i ? (blobSortAsc ? " ▲" : " ▼") : "";
      return `<th onclick="sortBlobList(${i})" style="cursor:pointer">${h}${arrow}</th>`;
    })
    .join("");

  let html = `<table class="blob-table"><thead><tr>${thHtml}</tr></thead><tbody>`;
  sorted.forEach((b) => {
    const color = b.color
      ? `rgb(${b.color[2]},${b.color[1]},${b.color[0]})`
      : "#ccc";
    const sel = b.id === selectedBlobId ? " selected" : "";
    html += `<tr class="blob-row${sel}" data-id="${b.id}" onclick="selectBlob(${b.id})" style="--blob-color:${color}">`;
    cols.forEach((k) => {
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
  selectedBlobId = selectedBlobId === id ? null : id;
  document.querySelectorAll(".blob-row").forEach((row) => {
    row.classList.toggle(
      "selected",
      parseInt(row.dataset.id) === selectedBlobId,
    );
  });
  draw();
}

// ===== 設定保存 =====

async function saveSettings() {
  const settingsName = prompt("設定名を入力してください：");
  if (!settingsName) return;

  // 存在確認
  try {
    const checkRes = await fetch("/api/pipelines/check-exists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: settingsName }),
    });
    const checkData = await checkRes.json();

    if (checkData.exists) {
      // 既存ファイルがある場合、ダイアログを表示
      showSaveConflictDialog(settingsName);
    } else {
      // 存在しない場合、そのまま保存
      performSave(settingsName, false);
    }
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

function showSaveConflictDialog(name) {
  // 既に存在したら削除
  const existing = document.getElementById("save-conflict-dialog");
  if (existing) existing.remove();

  // オーバーレイを作成
  const overlay = document.createElement("div");
  overlay.className = "save-dialog-overlay";
  overlay.id = "save-conflict-overlay";

  // ダイアログを作成
  const dialog = document.createElement("div");
  dialog.className = "save-dialog";
  dialog.id = "save-conflict-dialog";
  dialog.innerHTML = `
    <h3>設定「${name}」は既に存在します</h3>
    <p>どのように保存しますか？</p>
    <div class="save-dialog-buttons">
      <button id="overwrite-btn" class="btn-primary">上書き保存</button>
      <button id="save-as-new-btn" class="btn-secondary">新規保存</button>
      <button id="cancel-btn" style="background: #f0f0f0; color: #333;">キャンセル</button>
    </div>
  `;

  document.body.appendChild(overlay);
  document.body.appendChild(dialog);

  // イベントリスナーを追加
  document.getElementById("overwrite-btn").addEventListener("click", () => {
    closeSaveConflictDialog();
    performSave(name, true);
  });

  document.getElementById("save-as-new-btn").addEventListener("click", () => {
    closeSaveConflictDialog();
    performSave(name, false);
  });

  document.getElementById("cancel-btn").addEventListener("click", () => {
    closeSaveConflictDialog();
  });

  // オーバーレイクリックでも閉じる
  overlay.addEventListener("click", () => {
    closeSaveConflictDialog();
  });
}

function closeSaveConflictDialog() {
  const dialog = document.getElementById("save-conflict-dialog");
  const overlay = document.getElementById("save-conflict-overlay");
  if (dialog) dialog.remove();
  if (overlay) overlay.remove();
}

async function performSave(name, overwrite) {
  setStatus("processing", "設定を保存中...");
  try {
    const res = await fetch("/api/pipelines/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        pipeline,
        overwrite
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "保存失敗");
    }
    const data = await res.json();

    // バックエンドから返された実際の名前を使用
    currentSettingsName = data.name;
    updateCurrentSettingsDisplay();

    setStatus("success", `保存完了: ${data.name}`);
    setTimeout(() => setStatus("", ""), 2000);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

async function selectSettingsToLoad(filename) {
  closeSettingsDialog();
  setStatus("processing", "設定を読み込み中...");
  try {
    const res = await fetch("/api/pipelines/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: filename }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "読み込み失敗");
    }
    const data = await res.json();
    pipeline = data.pipeline;
    currentSettingsName = data.name;
    intermediateImages = [];
    selectedStep = null;
    viewMode = "original";
    updateCurrentSettingsDisplay();
    renderPipeline();
    setStatus("success", `読み込み完了: ${currentSettingsName}`);
    setTimeout(() => setStatus("", ""), 2000);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}


// ===== 設定読み込み =====

async function loadSettingsList() {
  try {
    const res = await fetch("/api/pipelines/list");
    if (!res.ok) throw new Error("リスト取得失敗");

    const data = await res.json();
    showLoadDialog(data.pipelines);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

function closeSettingsDialog() {
  const dialog = document.getElementById("settings-dialog");
  if (dialog) dialog.remove();
}

async function loadPipelineList() {
  // 既存のダイアログがあれば閉じる
  closePipelineDialog();

  try {
    const res = await fetch("/api/pipelines/list");
    if (!res.ok) throw new Error("リスト取得失敗");

    const data = await res.json();
    showLoadDialog(data.pipelines);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

function showLoadDialog(pipelines) {
  closeSettingsDialog();

  const html = `
        <div class="settings-dialog">
            <h3>保存済み設定を読み込み</h3>
            <div class="settings-dialog-list">
                ${pipelines.length === 0
      ? '<div class="settings-dialog-empty">保存済み設定はありません</div>'
      : pipelines
        .map(
          (p) => `
                    <div class="settings-dialog-item">
                        <div class="settings-dialog-item-info" onclick="selectSettingsToLoad('${p.filename}')">
                            <div class="settings-dialog-item-name">${p.name}</div>
                            <div class="settings-dialog-item-meta">
                                ステップ数: ${p.steps} | ${p.saved_at}
                            </div>
                        </div>
                        <button class="btn-danger" onclick="deleteSettings('${p.filename}')">削除</button>
                    </div>
                `,
        )
        .join("")
    }
            </div>
            <div class="settings-dialog-buttons">
                <button onclick="closeSettingsDialog()">キャンセル</button>
            </div>
        </div>
        <div class="settings-dialog-overlay" onclick="closeSettingsDialog()"></div>
    `;

  const dialog = document.createElement("div");
  dialog.id = "settings-dialog";
  dialog.innerHTML = html;
  document.body.appendChild(dialog);
}

// ===== 設定削除 =====

async function deleteSettings(filename) {
  if (!confirm(`「${filename}」を削除してもよろしいですか？`)) {
    return;
  }

  setStatus("processing", "設定を削除中...");
  try {
    const res = await fetch(`/api/pipelines/${filename}`, {
      method: "DELETE",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "削除失敗");
    }

    setStatus("success", "削除完了");
    await loadSettingsList();
    setTimeout(() => setStatus("", ""), 2000);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

async function showDeleteDialog() {
  // 既存のダイアログがあれば閉じる
  closePipelineDialog();

  try {
    const res = await fetch("/api/pipelines/list");
    if (!res.ok) throw new Error("リスト取得失敗");

    const data = await res.json();

    const html = `
            <div style="position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); 
                        background:white; padding:20px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.2);
                        z-index:1000; max-height:80vh; overflow-y:auto; min-width:400px;">
                <h3>Pipeline削除</h3>
                <div style="max-height:400px; overflow-y:auto; margin-bottom:15px;">
                    ${data.pipelines.length === 0
        ? "<p>保存済みpipelineはありません</p>"
        : data.pipelines
          .map(
            (p, i) => `
                        <div style="padding:10px; margin:5px 0; border:1px solid #ddd; border-radius:4px; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <strong>${p.name}</strong>
                                <div style="font-size:12px; color:#666;">
                                    ステップ数: ${p.steps} | ${p.saved_at}
                                </div>
                            </div>
                            <button onclick="deletePipeline('${p.filename}')" 
                                    style="padding:6px 12px; background:#ff6b6b; color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px;">
                                削除
                            </button>
                        </div>
                    `,
          )
          .join("")
      }
                </div>
                <button onclick="closePipelineDialog()" style="padding:8px 16px; cursor:pointer;">閉じる</button>
            </div>
            <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;"
                 onclick="closePipelineDialog()"></div>
        `;

    const dialog = document.createElement("div");
    dialog.id = "pipeline-dialog";
    dialog.innerHTML = html;
    document.body.appendChild(dialog);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

async function selectPipelineToLoad(filename) {
  closePipelineDialog();
  setStatus("processing", "設定を読み込み中...");

  try {
    const res = await fetch("/api/pipelines/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: filename }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "読み込み失敗");
    }

    const data = await res.json();
    pipeline = data.pipeline;
    currentPipelineName = data.name;
    intermediateImages = [];
    selectedStep = null;
    viewMode = "original";
    renderPipeline();
    setStatus("success", `読み込み完了: ${data.name}`);
    setTimeout(() => setStatus("", ""), 2000);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

function closePipelineDialog() {
  const dialog = document.getElementById("pipeline-dialog");
  if (dialog) dialog.remove();
}

// ===== 設定エクスポート =====

async function exportSettings() {
  const name = prompt(
    "エクスポート時のファイル名を入力してください (拡張子なし):",
  );
  if (!name) return;

  setStatus("processing", "設定をエクスポート中...");
  try {
    const safe_name = name.replace(/[^a-zA-Z0-9_]/g, "_");
    const data = {
      name: currentSettingsName || name,
      pipeline: pipeline,
      exported_at: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safe_name}.json`;
    a.click();
    URL.revokeObjectURL(url);

    setStatus("success", "エクスポート完了");
    setTimeout(() => setStatus("", ""), 2000);
  } catch (e) {
    setStatus("error", "エラー: " + e.message);
  }
}

// ===== 設定インポート =====

function importSettings() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setStatus("processing", "設定をインポート中...");
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/pipelines/import", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "インポート失敗");
      }

      const data = await res.json();
      pipeline = data.pipeline;
      currentSettingsName = data.name;
      intermediateImages = [];
      selectedStep = null;
      viewMode = "original";
      updateCurrentSettingsDisplay();
      renderPipeline();
      setStatus("success", `インポート完了: ${data.name}`);
      setTimeout(() => setStatus("", ""), 2000);
    } catch (e) {
      setStatus("error", "エラー: " + e.message);
    }
  };
  input.click();
}

// ===== 現在の設定名表示を更新 =====

function updateCurrentSettingsDisplay() {
  const display = document.getElementById("current-settings-name");
  if (display) {
    display.textContent = currentSettingsName
      ? `現在の設定: ${currentSettingsName}`
      : "";
  }
}

// =====================
// Camera
// =====================
let _fpsTimer = null;

const CAM_PARAM_LABELS = {
  width: "Width(px)",
  height: "Height(px)",
  fps: "FPS設定",
  brightness: "明るさ",
  contrast: "コントラスト",
  saturation: "彩度",
  hue: "色相",
  gain: "ゲイン",
  exposure: "露光",
  autofocus: "オートフォーカス",
  focus: "フォーカス",
  auto_exposure: "自動露光",
};
// チェックボックスで表示するパラメータ
const CAM_PARAM_CHECKBOX = new Set(["autofocus", "auto_exposure"]);

async function loadCameras() {
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

async function startStream() {
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
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  const img = new Image();
  let firstFrame = true;

  ws = new WebSocket(
    `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/camera/stream/ws`,
  );
  ws.binaryType = "arraybuffer";

  ws.onopen = async () => {
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

  ws.onerror = (e) => {
    console.error("WebSocket error:", e);
    setStatus("error", "ストリーミング接続エラー");
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
    clearInterval(_fpsTimer);
    document.getElementById("img-info").textContent = "";
    document.getElementById("cam-fps").textContent = "";
    document.getElementById("cam-params").style.display = "none";
  };

  ws.onmessage = (event) => {
    const blob = new Blob([event.data], { type: "image/jpeg" });
    const url = URL.createObjectURL(blob);
    img.onload = () => {
      streamImage = img;

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

async function stopStream() {
  // FPSタイマーを停止
  if (_fpsTimer) {
    clearInterval(_fpsTimer);
    _fpsTimer = null;
  }

  // WebSocketを閉じる
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
  }
  ws = null;

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
  streamImage = null;
  originalImage = null;
  processedImage = null;

  // キャンバスをクリア
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

async function captureFrame() {
  setStatus("", "");
  const res = await fetch("/camera/capture", { method: "POST" });
  if (!res.ok) {
    setStatus("error", "キャプチャ失敗");
    return;
  }
  const data = await res.json();
  await stopStream();
  imageId = data.image_id;
  originalFilename = data.image_name.replace(/\.[^.]+$/, "");
  originalImage = await loadImage(data.image_url);
  processedImage = null;
  blobData = [];
  selectedBlobId = null;
  renderBlobList([]);
  showingOriginal = true;
  fitToWindow();
  setStatus("", "");
}

async function loadCamParamTable() {
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

async function applyCamParams() {
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

function startRegionSelect(stepIndex) {
  regionSelect = { stepIndex, startX: 0, startY: 0, endX: 0, endY: 0 };
  regionDragging = false;
  canvas.style.cursor = "crosshair";
}

function canvasToImage(cx, cy) {
  return { x: (cx - offsetX) / zoom, y: (cy - offsetY) / zoom };
}

function updateImgInfo(e) {
  const rect = canvas.getBoundingClientRect();
  const img = showingOriginal ? originalImage : processedImage || originalImage;
  if (!img) return;
  const { x, y } = canvasToImage(e.clientX - rect.left, e.clientY - rect.top);
  const ix = Math.round(x),
    iy = Math.round(y);
  const w = img.naturalWidth,
    h = img.naturalHeight;
  let rgbStr = "";
  if (ix >= 0 && iy >= 0 && ix < w && iy < h) {
    const tmp = document.createElement("canvas");
    tmp.width = w;
    tmp.height = h;
    tmp.getContext("2d").drawImage(img, 0, 0);
    const px = tmp.getContext("2d").getImageData(ix, iy, 1, 1).data;
    rgbStr = `  R:${px[0]} G:${px[1]} B:${px[2]}`;
  }
  document.getElementById("img-info").textContent =
    `${w} x ${h}px  |  X:${ix} Y:${iy}${rgbStr}`;
}

function updateParam(index, key, value) {
  const def = (PARAM_DEFS[pipeline[index].type] || []).find(
    (d) => d.key === key,
  );
  if (def && def.type === "checkbox") {
    pipeline[index].params[key] = value === true || value === "true";
  } else if (def && def.type === "number") {
    pipeline[index].params[key] = Number(value);
  } else {
    pipeline[index].params[key] = value;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  updateCurrentSettingsDisplay();
  canvas = document.getElementById("canvas");
  ctx = canvas.getContext("2d");

  menu = document.getElementById("contextMenu");
  // 右クリックで画像保存
  canvas.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    showMyMenu(e.clientX, e.clientY);
  });

  const resizeCanvas = () => {
    const area = canvas.parentElement;
    canvas.width = area.clientWidth - 20;
    canvas.height = area.clientHeight - 60;
    draw();
  };
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  canvas.addEventListener("mousedown", (e) => {
    const rect = canvas.getBoundingClientRect();
    const pos = canvasToImage(e.clientX - rect.left, e.clientY - rect.top);
    if (regionSelect) {
      regionDragging = true;
      regionSelect.startX = pos.x;
      regionSelect.startY = pos.y;
      regionSelect.endX = pos.x;
      regionSelect.endY = pos.y;
    } else {
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
    }
  });
  canvas.addEventListener("mouseup", (e) => {
    if (regionDragging && regionSelect) {
      regionDragging = false;
      canvas.style.cursor = "grab";
      const si = regionSelect.stepIndex;
      const x1 = Math.round(Math.min(regionSelect.startX, regionSelect.endX));
      const x2 = Math.round(Math.max(regionSelect.startX, regionSelect.endX));
      const y1 = Math.round(Math.min(regionSelect.startY, regionSelect.endY));
      const y2 = Math.round(Math.max(regionSelect.startY, regionSelect.endY));
      pipeline[si].params.min_cx = x1;
      pipeline[si].params.max_cx = x2;
      pipeline[si].params.min_cy = y1;
      pipeline[si].params.max_cy = y2;
      pipeline[si].params.filter_centroid = true;
      regionSelect = null;
      renderPipeline();
    }
    dragging = false;
  });
  canvas.addEventListener("mouseleave", () => {
    dragging = false;
  });
  canvas.addEventListener("mousemove", (e) => {
    updateImgInfo(e);
    const rect = canvas.getBoundingClientRect();
    const pos = canvasToImage(e.clientX - rect.left, e.clientY - rect.top);
    if (regionDragging && regionSelect) {
      regionSelect.endX = pos.x;
      regionSelect.endY = pos.y;
      draw();
      return;
    }
    if (!dragging) return;
    offsetX += e.clientX - lastX;
    offsetY += e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    draw();
  });
  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      offsetX = mx - (mx - offsetX) * factor;
      offsetY = my - (my - offsetY) * factor;
      zoom *= factor;
      draw();
    },
    { passive: false },
  );

  new Sortable(document.getElementById("pipeline"), {
    animation: 150,
    handle: ".drag-handle",
    onEnd: (evt) => {
      const item = pipeline.splice(evt.oldIndex, 1)[0];
      pipeline.splice(evt.newIndex, 0, item);
      selectedStep = null;
      intermediateImages = [];
      renderPipeline();
    },
  });

  // パネルリサイズ
  const handle = document.getElementById("resize-handle");
  const panel = document.querySelector(".panel");
  let resizing = false;
  let resizeStartX = 0;
  let resizeStartW = 0;
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
    const newW = Math.max(
      200,
      Math.min(window.innerWidth - 200, resizeStartW + delta),
    );
    panel.style.width = newW + "px";
    resizeCanvas();
  });
  document.addEventListener("mouseup", () => {
    if (!resizing) return;
    resizing = false;
    handle.classList.remove("dragging");
  });
});

function showMyMenu(x, y) {
  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;
  menu.style.display = "block";
}

function hideMyMenu() {
  menu.style.display = "none";
}

// 「画像を保存」
document.getElementById("menuSave").addEventListener("click", () => {
  hideMyMenu();
  downloadImage();
});

// メニュー外をクリックしたら閉じる
document.addEventListener("click", () => {
  hideMyMenu();
});

// ESCでも閉じる
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    hideMyMenu();
  }
});

// 実装済み画像を正しいサイズで保存
async function downloadImage() {
  let img =
    streamImage ||
    (showingOriginal ? originalImage : processedImage || originalImage);

  if (!img || !img.complete) {
    return;
  }

  const w = img.naturalWidth;
  const h = img.naturalHeight;

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
    a.download = `${originalFilename || "image"}_${w}x${h}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, "image/png");
}
