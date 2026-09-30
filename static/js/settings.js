// settings.js

import { renderPipeline } from "./pipeline.js";
import { setStatus, state } from "./state.js";

// ===== 現在の設定名表示を更新 =====

export function updateCurrentSettingsDisplay() {
    const display = document.getElementById("current-settings-name");
    if (display) {
        display.textContent = state.currentSettingsName
            ? `現在の設定: ${state.currentSettingsName}`
            : "";
    }
}

export async function saveSettings() {
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

export async function performSave(name, overwrite) {
    setStatus("processing", "設定を保存中...");
    try {
        const res = await fetch("/api/pipelines/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, pipeline: state.pipeline, overwrite }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "保存失敗");
        }
        const data = await res.json();
        // バックエンドから返された実際の名前を使用
        state.currentSettingsName = data.name;
        updateCurrentSettingsDisplay();
        setStatus("success", `保存完了: ${data.name}`);
        setTimeout(() => setStatus("", ""), 2000);
    } catch (e) {
        setStatus("error", "エラー: " + e.message);
    }
}

export async function selectSettingsToLoad(filename) {
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
        state.pipeline = data.pipeline;
        state.currentSettingsName = data.name;
        state.intermediateImages = [];
        state.selectedStep = null;
        state.viewMode = "original";
        updateCurrentSettingsDisplay();
        renderPipeline();
        setStatus("success", `読み込み完了: ${state.currentSettingsName}`);
        setTimeout(() => setStatus("", ""), 2000);
    } catch (e) {
        setStatus("error", "エラー: " + e.message);
    }
}

// ===== 設定読み込み =====

export async function loadSettingsList() {
    try {
        const res = await fetch("/api/pipelines/list");
        if (!res.ok) throw new Error("リスト取得失敗");
        const data = await res.json();
        showLoadDialog(data.pipelines);
    } catch (e) {
        setStatus("error", "エラー: " + e.message);
    }
}

export function closeSettingsDialog() {
    document.getElementById("settings-dialog")?.remove();
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

// ===== Pipeline読み込み =====

export async function loadPipelineList() {
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

export async function showDeleteDialog() {
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

export async function selectPipelineToLoad(filename) {
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
        state.pipeline = data.pipeline;
        state.currentSettingsName = data.name;
        state.intermediateImages = [];
        state.selectedStep = null;
        state.viewMode = "original";
        renderPipeline();
        setStatus("success", `読み込み完了: ${data.name}`);
        setTimeout(() => setStatus("", ""), 2000);
    } catch (e) {
        setStatus("error", "エラー: " + e.message);
    }
}

export function closePipelineDialog() {
    const dialog = document.getElementById("pipeline-dialog");
    if (dialog) dialog.remove();
}

// ===== 設定削除 =====

export async function deleteSettings(filename) {
    if (!confirm(`「${filename}」を削除してもよろしいですか？`)) {
        return;
    }

    setStatus("processing", "設定を削除中...");
    try {
        const res = await fetch(`/api/pipelines/${filename}`, { method: "DELETE" });
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

// ===== 設定エクスポート =====

export async function exportSettings() {
    const name = prompt("エクスポート時のファイル名を入力してください (拡張子なし):");
    if (!name) return;
    setStatus("processing", "設定をエクスポート中...");
    try {
        const safe_name = name.replace(/[^a-zA-Z0-9_]/g, "_");
        const data = {
            name: state.currentSettingsName || name,
            pipeline: state.pipeline,
            exported_at: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
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

export function importSettings() {
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
            const res = await fetch("/api/pipelines/import", { method: "POST", body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || "インポート失敗");
            }
            const data = await res.json();
            state.pipeline = data.pipeline;
            state.currentSettingsName = data.name;
            state.intermediateImages = [];
            state.selectedStep = null;
            state.viewMode = "original";
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
