// blob.js

import { state } from "./state.js";
import { draw } from "./canvas.js";

let blobSortCol = null;
let blobSortAsc = true;

export function renderBlobList(blobs) {
    const section = document.getElementById("blob-section");
    const container = document.getElementById("blob-list");
    const countSpan = document.getElementById("blob-count");
    if (!blobs || blobs.length === 0) {
        section.style.display = "none";
        return;
    }
    section.style.display = "";
    countSpan.textContent = `(${blobs.length}件)`;
    const cols = ["id", "cx", "cy", "area", "circularity", "convexity", "inertia_ratio", "perimeter", "rect_long", "rect_short"];
    const heads = ["#", "X", "Y", "面積", "真円度", "凸度", "慣性比", "周囲長", "長辺", "短辺"];

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
        const sel = b.id === state.selectedBlobId ? " selected" : "";
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

export function sortBlobList(colIndex) {
    if (blobSortCol === colIndex) {
        blobSortAsc = !blobSortAsc;
    } else {
        blobSortCol = colIndex;
        blobSortAsc = true;
    }
    renderBlobList(state.blobData);
}

export function selectBlob(id) {
    state.selectedBlobId = state.selectedBlobId === id ? null : id;
    document.querySelectorAll(".blob-row").forEach((row) => {
        row.classList.toggle("selected", parseInt(row.dataset.id) === state.selectedBlobId);
    });
    draw();
}

export function saveBlobCsv() {
    if (!state.blobData.length) return;
    const cols = ["id", "cx", "cy", "area", "circularity", "convexity", "inertia_ratio", "perimeter", "rect_long", "rect_short"];
    const heads = ["#", "X", "Y", "面積", "真円度", "凸度", "慣性比", "周囲長", "長辺", "短辺"];
    const rows = [heads.join(",")];
    state.blobData.forEach((b) => {
        rows.push(cols.map((k) => (b[k] !== undefined ? b[k] : "")).join(","));
    });
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${state.originalFilename}_blobs.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
}
