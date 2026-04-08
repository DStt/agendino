/**
 * AgenDino Dashboard JS
 * Fetches recordings status from API and renders the table.
 * Device communication uses WebUSB via HiDockDevice (hidock-device.js).
 */

const API_URL = "/api/dashboard/recordings";
const TRANSCRIBE_URL = "/api/dashboard/transcribe";
const TRANSCRIPT_URL = "/api/dashboard/transcript";
const TRANSCRIPT_UPDATE_URL = "/api/dashboard/transcript";
const PROMPTS_URL = "/api/dashboard/prompts";
const SUMMARIZE_URL = "/api/dashboard/summarize";
const SUMMARIES_URL = "/api/dashboard/summaries";
const SHARE_DESTINATIONS_URL = "/api/dashboard/share/destinations";
const SHARE_SUMMARY_URL = "/api/dashboard/share/summary";
const AUDIO_URL = "/api/dashboard/audio";
const SUMMARY_UPDATE_URL = "/api/dashboard/summary";
const DELETE_RECORDING_URL = "/api/dashboard/recording";
const TASKS_GENERATE_URL = "/api/dashboard/tasks/generate";
const TASKS_URL = "/api/dashboard/tasks";
const UPLOAD_URL = "/api/dashboard/upload";
const RECORDING_UPDATE_URL = "/api/dashboard/recording";
const FOLDERS_URL = "/api/dashboard/folders";
const MOVE_RECORDING_URL = "/api/dashboard/recording";
const BULK_MOVE_URL = "/api/dashboard/recordings/move";
const LOGOUT_URL = "/api/auth/logout"
const LOGIN_PAGE_URL = "/login"

const $ = (sel) => document.querySelector(sel);
const show = (el) => el?.classList.remove("d-none");
const hide = (el) => el?.classList.add("d-none");

// ─── WebUSB device state ────────────────────────────────────────
let _cachedDeviceData = null; // { info, files, storage } from last device probe
let _currentFolder = null;   // null = "All", "/" = root only, "/path" = specific folder
let _allRecordings = [];     // all recordings from last fetch
let _allFolders = [];        // all folder paths from last fetch

function formatDuration(seconds) {
    if (seconds == null) return "—";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
}

function formatSize(bytes) {
    if (bytes == null) return "—";
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
}

function statusBadge(ok, yesIcon = "bi-check-circle-fill", noIcon = "bi-x-circle") {
    if (ok) {
        return `<span class="badge-status badge-yes"><i class="bi ${yesIcon}"></i></span>`;
    }
    return `<span class="badge-status badge-no"><i class="bi ${noIcon}"></i></span>`;
}

function actionButtons(rec) {
    const btns = [];
    if (rec.on_local) {
        btns.push(`<button class="btn btn-sm btn-outline-secondary btn-play-audio" data-name="${rec.name}" title="Play audio"><i class="bi bi-play-circle"></i></button>`);
        if (rec.has_transcript) {
            btns.push(`<button class="btn btn-sm btn-outline-success btn-view-transcript" data-name="${rec.name}" title="View transcript"><i class="bi bi-file-text"></i></button>`);
            if (rec.has_summary) {
                    btns.push(`<button class="btn btn-sm btn-outline-info btn-view-summary" data-name="${rec.name}" title="View summaries"><i class="bi bi-journal-text"></i></button>`);
            }
            btns.push(`<button class="btn btn-sm btn-outline-warning btn-summarize" data-name="${rec.name}" title="Summarize"><i class="bi bi-stars"></i></button>`);
        } else {
            btns.push(`<div class="btn-group btn-group-sm transcribe-split" style="position:relative">
                <button class="btn btn-outline-primary btn-transcribe" data-name="${rec.name}" data-engine="gemini" title="Transcribe with Gemini"><i class="bi bi-mic"></i></button>
                <button type="button" class="btn btn-outline-primary btn-transcribe-toggle" data-name="${rec.name}" title="Choose engine" style="padding-left:3px;padding-right:3px;border-left:0"><i class="bi bi-caret-down-fill" style="font-size:.55em"></i></button>
                <div class="transcribe-engine-menu d-none" style="position:absolute;top:100%;right:0;z-index:1050;min-width:160px;background:var(--bs-body-bg);border:1px solid var(--bs-border-color);border-radius:.375rem;box-shadow:0 .5rem 1rem rgba(0,0,0,.15);margin-top:2px">
                    <a href="#" class="btn-transcribe-engine d-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-body" data-name="${rec.name}" data-engine="gemini" style="font-size:.85rem"><i class="bi bi-cloud"></i> Gemini</a>
                    <a href="#" class="btn-transcribe-engine d-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-body" data-name="${rec.name}" data-engine="whisper" style="font-size:.85rem;border-top:1px solid var(--bs-border-color)"><i class="bi bi-pc-display"></i> Whisper (local)</a>
                </div>
            </div>`);
        }
    }
    if (rec.in_db) {
        btns.push(`<button class="btn btn-sm btn-outline-primary btn-move-recording" data-name="${rec.name}" title="Move to folder"><i class="bi bi-folder-symlink"></i></button>`);
    }
    if (rec.on_device || rec.on_local || rec.in_db) {
        btns.push(`<button class="btn btn-sm btn-outline-danger btn-delete-recording" data-name="${rec.name}" data-on-device="${rec.on_device}" data-on-local="${rec.on_local}" data-in-db="${rec.in_db}" title="Delete recording…"><i class="bi bi-trash3"></i></button>`);
    }
    return btns.join(" ") || '<span class="text-muted">—</span>';
}

function renderTags(tags) {
    if (!tags || tags.length === 0) return '<span class="text-muted">—</span>';
    return tags
        .map(t => `<span class="badge bg-secondary bg-opacity-25 text-body me-1 mb-1">${t}</span>`)
        .join("");
}

function fileTypeBadge(ext) {
    const colors = {
        hda: "bg-dark",
        mp3: "bg-success",
        wav: "bg-primary",
        m4a: "bg-info",
        ogg: "bg-warning text-dark",
        webm: "bg-secondary",
        flac: "bg-purple",
        aac: "bg-danger",
    };
    const cls = colors[ext] || "bg-secondary";
    return `<span class="badge ${cls}" style="font-size:.7rem">.${ext || "hda"}</span>`;
}

function renderRow(rec) {
    const dateStr = rec.date && rec.time ? `${rec.date} ${rec.time}` : (rec.date || "—");
    const dateCell = rec.in_db
        ? `<span class="editable-date" role="button" data-name="${rec.name}" data-recorded-at="${rec.recorded_at || ""}" title="Click to edit date/time">${dateStr} <i class="bi bi-pencil-square small text-muted"></i></span>`
        : dateStr;
    let titleStr;
    if (rec.db_title && rec.notion_url) {
        titleStr = `<a href="${rec.notion_url}" target="_blank" rel="noopener" class="text-decoration-none" title="Open in Notion">${rec.db_title} <i class="bi bi-box-arrow-up-right small text-muted"></i></a>`;
    } else {
        titleStr = rec.db_title || '<span class="text-muted">—</span>';
    }
    const titleCell = rec.summary_count > 1 ? `${titleStr} <span class="badge bg-info-subtle text-info-emphasis ms-1">v${rec.summary_count}</span>` : titleStr;
    return `<tr>
        <td class="text-center"><input type="checkbox" class="rec-checkbox" data-name="${rec.name}" ${!rec.in_db ? "disabled title=\"Not in DB\"" : ""}></td>
        <td class="fw-semibold">${rec.name}</td>
        <td>${dateCell}</td>
        <td>${formatDuration(rec.duration)}</td>
        <td>${formatSize(rec.size)}</td>
        <td class="text-center">${fileTypeBadge(rec.file_extension)}</td>
        <td class="text-center">${statusBadge(rec.on_device)}</td>
        <td class="text-center">${statusBadge(rec.on_local)}</td>
        <td class="text-center">${statusBadge(rec.in_db)}</td>
        <td>${titleCell}</td>
        <td>${renderTags(rec.db_tags)}</td>
        <td class="text-center text-nowrap">${actionButtons(rec)}</td>
    </tr>`;
}

/**
 * Try to probe an already-paired WebUSB HiDock device.
 * Returns { info, files, storage } or null on failure / no device.
 */
async function probeWebUSBDevice() {
    if (!HiDockDevice.isSupported()) return null;
    try {
        const devices = await HiDockDevice.getDevices();
        if (devices.length === 0) return null;
        const hidock = devices[0];
        await hidock.open();
        try {
            const info = await hidock.getDeviceInfo();
            const files = await hidock.listFiles();
            const storage = await hidock.getCardInfo();
            return { info, files, storage, hidock };
        } finally {
            await hidock.close();
        }
    } catch (e) {
        console.warn("WebUSB device probe failed:", e);
        return null;
    }
}

/**
 * Merge server-side recordings data with WebUSB device data.
 */
function mergeDeviceData(serverData, deviceData) {
    if (!deviceData || !deviceData.files) return serverData;

    const deviceMap = {};
    for (const f of deviceData.files) {
        const bare = HiDockDevice.bareName(f.name);
        deviceMap[bare] = f;
    }

    // Mark existing recordings as on_device
    const existingNames = new Set();
    for (const rec of serverData.recordings) {
        existingNames.add(rec.name);
        const devFile = deviceMap[rec.name];
        if (devFile) {
            rec.on_device = true;
            rec.recording_type = devFile.recording_type;
            if (!rec.duration && devFile.duration) rec.duration = devFile.duration;
            if (!rec.size && devFile.length) rec.size = devFile.length;
            if (!rec.date && devFile.create_date) {
                rec.date = devFile.create_date;
                rec.time = devFile.create_time;
            }
        }
    }

    // Add device-only recordings that aren't on server yet
    for (const [bare, devFile] of Object.entries(deviceMap)) {
        if (!existingNames.has(bare)) {
            serverData.recordings.push({
                name: bare,
                on_device: true,
                on_local: false,
                in_db: false,
                file_extension: "hda",
                duration: devFile.duration,
                size: devFile.length,
                date: devFile.create_date,
                time: devFile.create_time,
                recorded_at: null,
                recording_type: devFile.recording_type,
                db_label: null,
                db_id: null,
                db_title: null,
                db_tags: [],
                has_transcript: false,
                has_summary: false,
                summary_count: 0,
                notion_url: null,
                folder: "/",
            });
        }
    }

    // Update device section
    const info = deviceData.info;
    serverData.device = {
        connected: true,
        model: info ? `${info.model} (v${info.version}, S/N: ${info.serial})` : "HiDock",
    };
    serverData.counts.device = deviceData.files.length;

    if (deviceData.storage) {
        serverData.storage = {
            used: deviceData.storage.used,
            capacity: deviceData.storage.capacity,
            status: deviceData.storage.status,
        };
    }

    return serverData;
}

// ─── Folder helpers ─────────────────────────────────────────────

function buildFolderTree(folders) {
    // Build a nested tree from flat folder paths
    const root = { name: "All", path: null, children: {}, count: 0 };
    const rootFolder = { name: "/", path: "/", children: {}, count: 0 };
    root.children["/"] = rootFolder;

    for (const folderPath of folders) {
        if (folderPath === "/") continue;
        const parts = folderPath.split("/").filter(p => p);
        let current = rootFolder;
        let built = "";
        for (const part of parts) {
            built += "/" + part;
            if (!current.children[part]) {
                current.children[part] = { name: part, path: built, children: {}, count: 0 };
            }
            current = current.children[part];
        }
    }
    return root;
}

function countRecordingsInFolder(recordings, folderPath) {
    if (folderPath === null) return recordings.length; // "All"
    return recordings.filter(r => {
        const rf = r.folder || "/";
        if (folderPath === "/") return rf === "/";
        return rf === folderPath || rf.startsWith(folderPath + "/");
    }).length;
}

function renderFolderTreeNode(node, recordings, level = 0) {
    const children = Object.values(node.children);
    const count = countRecordingsInFolder(recordings, node.path);
    const isActive = _currentFolder === node.path;
    const isRoot = node.path === null;
    const isRootDir = node.path === "/";
    const icon = isRoot ? "bi-collection" : (isActive ? "bi-folder2-open" : "bi-folder");
    const indent = level > 0 ? `padding-left: ${level * 1}rem` : "";

    let html = `<div class="folder-tree-item ${isActive ? 'active' : ''}" data-folder-path="${node.path}" style="${indent}">
        <i class="bi ${icon} folder-icon"></i>
        <span class="folder-name" title="${node.path || 'All recordings'}">${isRoot ? 'All' : node.name}</span>
        <span class="folder-count">${count}</span>`;

    if (!isRoot && !isRootDir) {
        html += `<span class="folder-actions">
            <button class="btn btn-rename-folder" data-folder-path="${node.path}" title="Rename"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-delete-folder" data-folder-path="${node.path}" title="Delete"><i class="bi bi-trash3"></i></button>
        </span>`;
    }
    html += `</div>`;

    if (children.length > 0) {
        html += `<div class="folder-tree-children">`;
        for (const child of children.sort((a, b) => a.name.localeCompare(b.name))) {
            html += renderFolderTreeNode(child, recordings, level + 1);
        }
        html += `</div>`;
    }
    return html;
}

function renderFolderTree(folders, recordings) {
    const treeEl = $("#folder-tree");
    if (!treeEl) return;

    // Ensure all recording folders appear in the tree
    const allFolders = new Set(folders);
    for (const rec of recordings) {
        if (rec.folder && rec.folder !== "/") allFolders.add(rec.folder);
    }

    const tree = buildFolderTree([...allFolders]);
    treeEl.innerHTML = renderFolderTreeNode(tree, recordings);
}

function renderBreadcrumb(folderPath) {
    const el = $("#folder-breadcrumb");
    if (!el) return;
    if (folderPath === null) {
        el.innerHTML = '<i class="bi bi-collection me-1"></i>All recordings';
        return;
    }
    if (folderPath === "/") {
        el.innerHTML = '<span class="breadcrumb-part" data-folder-path="null"><i class="bi bi-collection me-1"></i>All</span> / <strong>/</strong>';
        return;
    }
    const parts = folderPath.split("/").filter(p => p);
    let html = '<span class="breadcrumb-part" data-folder-path="null"><i class="bi bi-collection me-1"></i>All</span>';
    html += ' / <span class="breadcrumb-part" data-folder-path="/">/</span>';
    let built = "";
    for (let i = 0; i < parts.length; i++) {
        built += "/" + parts[i];
        if (i === parts.length - 1) {
            html += ` / <strong>${parts[i]}</strong>`;
        } else {
            html += ` / <span class="breadcrumb-part" data-folder-path="${built}">${parts[i]}</span>`;
        }
    }
    el.innerHTML = html;
}

function filterRecordingsByFolder(recordings, folderPath) {
    if (folderPath === null) return recordings;
    return recordings.filter(r => {
        const rf = r.folder || "/";
        if (folderPath === "/") return rf === "/";
        return rf === folderPath || rf.startsWith(folderPath + "/");
    });
}

function updateBulkActionsBar() {
    const bar = $("#bulk-actions-bar");
    const countEl = $("#bulk-selected-count");
    if (!bar || !countEl) return;
    const checked = document.querySelectorAll(".rec-checkbox:checked");
    if (checked.length > 0) {
        countEl.textContent = `${checked.length} selected`;
        show(bar);
    } else {
        hide(bar);
    }
}

function renderFilteredTable() {
    const table = $("#recordings-table");
    const tbody = $("#recordings-body");
    const emptyEl = $("#empty-state");

    const filtered = filterRecordingsByFolder(_allRecordings, _currentFolder);
    renderBreadcrumb(_currentFolder);

    if (filtered.length === 0) {
        hide(table);
        show(emptyEl);
        return;
    }

    tbody.innerHTML = filtered.map(renderRow).join("");
    show(table);
    hide(emptyEl);

    // Reset select-all
    const selectAll = $("#select-all-recordings");
    if (selectAll) selectAll.checked = false;
    hide($("#bulk-actions-bar"));
}

async function loadDashboard() {
    const loading = $("#loading");
    const table = $("#recordings-table");
    const tbody = $("#recordings-body");
    const errorEl = $("#error-alert");
    const emptyEl = $("#empty-state");

    show(loading);
    hide(table);
    hide(errorEl);
    hide(emptyEl);

    try {
        const [res, deviceData] = await Promise.all([
            fetch(API_URL),
            probeWebUSBDevice(),
        ]);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        let data = await res.json();

        // Merge device data if available
        if (deviceData) {
            _cachedDeviceData = deviceData;
            data = mergeDeviceData(data, deviceData);
        }

        // Store globally for folder filtering
        _allRecordings = data.recordings || [];
        _allFolders = data.folders || ["/"];

        // Update status cards
        $("#count-device").textContent = data.counts.device;
        $("#count-local").textContent = data.counts.local;
        $("#count-db").textContent = data.counts.db;

        if (data.device.connected) {
            $("#device-status").textContent = "Connected";
            $("#device-model").textContent = data.device.model || "HiDock";
            $("#device-status-card").className = "small-box text-bg-info";
        } else {
            $("#device-status").textContent = "Offline";
            $("#device-model").textContent = "No device found";
            $("#device-status-card").className = "small-box text-bg-secondary";
        }

        // Update storage info
        const storageEl = $("#storage-info");
        if (data.storage && data.storage.capacity) {
            $("#storage-used").textContent = formatSize(data.storage.used);
            $("#storage-capacity").textContent = formatSize(data.storage.capacity);
            const pct = Math.min(100, (data.storage.used / data.storage.capacity) * 100);
            const bar = $("#storage-bar");
            bar.style.width = `${pct.toFixed(1)}%`;
            bar.className = `progress-bar${pct > 90 ? " bg-danger" : pct > 70 ? " bg-warning" : " bg-light"}`;
            show(storageEl);
        } else {
            hide(storageEl);
        }

        // Render folder tree
        renderFolderTree(_allFolders, _allRecordings);

        // Render table (filtered by current folder)
        hide(loading);
        renderFilteredTable();
    } catch (err) {
        hide(loading);
        errorEl.textContent = `Failed to load recordings: ${err.message}`;
        show(errorEl);
    }
}

function showSyncOverlay() {
    const overlay = $("#sync-overlay");
    if (overlay) {
        show(overlay);
        return;
    }
    // Create overlay on first use
    const el = document.createElement("div");
    el.id = "sync-overlay";
    el.innerHTML = `
        <div class="sync-overlay-backdrop">
            <div class="spinner-border text-light" style="width:3rem;height:3rem" role="status"></div>
            <p class="text-light mt-3 mb-0 fw-semibold">Syncing from device…</p>
        </div>`;
    document.body.appendChild(el);
}

function hideSyncOverlay() {
    hide($("#sync-overlay"));
}

document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();

    // ─── Folder tree click handler ──────────────────────────────
    document.addEventListener("click", (e) => {
        // Folder tree item click (navigate)
        const folderItem = e.target.closest(".folder-tree-item");
        if (folderItem && !e.target.closest(".folder-actions")) {
            e.preventDefault();
            const path = folderItem.dataset.folderPath;
            _currentFolder = path === "null" ? null : path;
            renderFolderTree(_allFolders, _allRecordings);
            renderFilteredTable();
            return;
        }

        // Breadcrumb click
        const bcPart = e.target.closest(".breadcrumb-part");
        if (bcPart) {
            e.preventDefault();
            const path = bcPart.dataset.folderPath;
            _currentFolder = path === "null" ? null : path;
            renderFolderTree(_allFolders, _allRecordings);
            renderFilteredTable();
            return;
        }
    });

    // ─── Select-all checkbox ─────────────────────────────────────
    document.addEventListener("change", (e) => {
        if (e.target.id === "select-all-recordings") {
            const checked = e.target.checked;
            document.querySelectorAll(".rec-checkbox:not(:disabled)").forEach(cb => cb.checked = checked);
            updateBulkActionsBar();
            return;
        }
        if (e.target.classList.contains("rec-checkbox")) {
            updateBulkActionsBar();
            // Update select-all state
            const all = document.querySelectorAll(".rec-checkbox:not(:disabled)");
            const allChecked = document.querySelectorAll(".rec-checkbox:checked");
            const selectAll = $("#select-all-recordings");
            if (selectAll) selectAll.checked = all.length > 0 && all.length === allChecked.length;
        }
    });

    // ─── Create Folder ───────────────────────────────────────────
    const createFolderBtn = $("#btn-create-folder");
    const folderModalBackdrop = $("#folder-modal-backdrop");
    const folderModalClose = $("#folder-modal-close");
    const folderModalCancel = $("#folder-modal-cancel");
    const folderPathInput = $("#folder-path-input");
    const folderModalConfirm = $("#folder-modal-confirm");
    const folderModalFeedback = $("#folder-modal-feedback");
    const folderModalTitle = $("#folder-modal-title");
    let _folderModalMode = "create"; // "create" or "rename"
    let _folderRenameOldPath = null;

    function openFolderModal(mode = "create", oldPath = null) {
        _folderModalMode = mode;
        _folderRenameOldPath = oldPath;
        if (mode === "rename") {
            folderModalTitle.innerHTML = '<i class="bi bi-pencil me-2"></i>Rename Folder';
            folderModalConfirm.innerHTML = '<i class="bi bi-check-lg me-1"></i>Rename';
            folderPathInput.value = oldPath || "";
        } else {
            folderModalTitle.innerHTML = '<i class="bi bi-folder-plus me-2"></i>New Folder';
            folderModalConfirm.innerHTML = '<i class="bi bi-check-lg me-1"></i>Create';
            // Pre-fill with current folder as parent
            const base = _currentFolder && _currentFolder !== "/" ? _currentFolder + "/" : "/";
            folderPathInput.value = base;
        }
        hide(folderModalFeedback);
        show(folderModalBackdrop);
        folderPathInput.focus();
    }

    function closeFolderModal() {
        hide(folderModalBackdrop);
    }

    if (createFolderBtn) createFolderBtn.addEventListener("click", (e) => { e.preventDefault(); openFolderModal("create"); });
    if (folderModalClose) folderModalClose.addEventListener("click", closeFolderModal);
    if (folderModalCancel) folderModalCancel.addEventListener("click", closeFolderModal);
    if (folderModalBackdrop) folderModalBackdrop.addEventListener("click", (e) => { if (e.target === folderModalBackdrop) closeFolderModal(); });

    if (folderModalConfirm) {
        folderModalConfirm.addEventListener("click", async () => {
            const path = (folderPathInput.value || "").trim();
            if (!path || path === "/") {
                folderModalFeedback.className = "small mt-2 text-danger";
                folderModalFeedback.textContent = "Please enter a valid folder path";
                show(folderModalFeedback);
                return;
            }

            folderModalConfirm.disabled = true;
            folderModalConfirm.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            try {
                if (_folderModalMode === "rename" && _folderRenameOldPath) {
                    const res = await fetch(`${FOLDERS_URL}/rename`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ old_path: _folderRenameOldPath, new_path: path }),
                    });
                    const data = await res.json();
                    if (data.ok) {
                        _currentFolder = data.new_path;
                        closeFolderModal();
                        await loadDashboard();
                    } else {
                        folderModalFeedback.className = "small mt-2 text-danger";
                        folderModalFeedback.textContent = data.error;
                        show(folderModalFeedback);
                    }
                } else {
                    // "Create" — just add it to the tree. The folder is implicit.
                    const res = await fetch(FOLDERS_URL, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ path }),
                    });
                    const data = await res.json();
                    if (data.ok) {
                        // Add folder to local list and re-render
                        if (!_allFolders.includes(data.path)) _allFolders.push(data.path);
                        _currentFolder = data.path;
                        renderFolderTree(_allFolders, _allRecordings);
                        renderFilteredTable();
                        closeFolderModal();
                    } else {
                        folderModalFeedback.className = "small mt-2 text-danger";
                        folderModalFeedback.textContent = data.error;
                        show(folderModalFeedback);
                    }
                }
            } catch (err) {
                folderModalFeedback.className = "small mt-2 text-danger";
                folderModalFeedback.textContent = `Failed: ${err.message}`;
                show(folderModalFeedback);
            } finally {
                folderModalConfirm.disabled = false;
                folderModalConfirm.innerHTML = _folderModalMode === "rename"
                    ? '<i class="bi bi-check-lg me-1"></i>Rename'
                    : '<i class="bi bi-check-lg me-1"></i>Create';
            }
        });
    }

    // Enter key in folder path input
    if (folderPathInput) {
        folderPathInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                folderModalConfirm?.click();
            }
        });
    }

    // ─── Rename / Delete folder buttons ──────────────────────────
    document.addEventListener("click", async (e) => {
        const renameBtn = e.target.closest(".btn-rename-folder");
        if (renameBtn) {
            e.preventDefault();
            e.stopPropagation();
            openFolderModal("rename", renameBtn.dataset.folderPath);
            return;
        }

        const deleteBtn = e.target.closest(".btn-delete-folder");
        if (deleteBtn) {
            e.preventDefault();
            e.stopPropagation();
            const path = deleteBtn.dataset.folderPath;
            const count = countRecordingsInFolder(_allRecordings, path);
            const msg = count > 0
                ? `Delete folder "${path}"? ${count} recording(s) will be moved to root (/).`
                : `Delete empty folder "${path}"?`;
            if (!confirm(msg)) return;

            try {
                const res = await fetch(FOLDERS_URL, {
                    method: "DELETE",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path, move_to: "/" }),
                });
                const data = await res.json();
                if (data.ok) {
                    if (_currentFolder === path) _currentFolder = null;
                    await loadDashboard();
                }
            } catch (err) {
                console.error("Failed to delete folder:", err);
            }
        }
    });

    // ─── Move-to-Folder modal ────────────────────────────────────
    const moveFolderBackdrop = $("#move-folder-modal-backdrop");
    const moveFolderClose = $("#move-folder-modal-close");
    const moveFolderCancel = $("#move-folder-cancel");
    const moveFolderConfirm = $("#move-folder-confirm");
    const moveFolderTree = $("#move-folder-tree");
    const moveFolderPathInput = $("#move-folder-path-input");
    const moveFolderRecName = $("#move-folder-recording-name");
    const moveFolderFeedback = $("#move-folder-feedback");
    let _moveRecordingNames = [];  // names to move
    let _selectedMoveFolder = "/";

    function renderMoveFolderTree() {
        const allFolders = new Set(_allFolders);
        for (const rec of _allRecordings) {
            if (rec.folder && rec.folder !== "/") allFolders.add(rec.folder);
        }
        const sorted = [...allFolders].sort();

        let html = "";
        for (const f of sorted) {
            const label = f === "/" ? "/ (root)" : f;
            const isSelected = f === _selectedMoveFolder;
            html += `<div class="move-folder-item ${isSelected ? 'selected' : ''}" data-path="${f}">
                <i class="bi ${f === "/" ? "bi-folder" : "bi-folder"} folder-icon"></i>
                <span>${label}</span>
            </div>`;
        }
        if (moveFolderTree) moveFolderTree.innerHTML = html;
    }

    function openMoveFolderModal(names) {
        _moveRecordingNames = names;
        _selectedMoveFolder = "/";
        if (moveFolderRecName) {
            moveFolderRecName.textContent = names.length === 1
                ? `Moving: ${names[0]}`
                : `Moving ${names.length} recording(s)`;
        }
        if (moveFolderPathInput) moveFolderPathInput.value = "";
        hide(moveFolderFeedback);
        renderMoveFolderTree();
        show(moveFolderBackdrop);
    }

    function closeMoveFolderModal() {
        hide(moveFolderBackdrop);
        _moveRecordingNames = [];
    }

    if (moveFolderClose) moveFolderClose.addEventListener("click", closeMoveFolderModal);
    if (moveFolderCancel) moveFolderCancel.addEventListener("click", closeMoveFolderModal);
    if (moveFolderBackdrop) moveFolderBackdrop.addEventListener("click", (e) => { if (e.target === moveFolderBackdrop) closeMoveFolderModal(); });

    // Click on folder item in move modal
    document.addEventListener("click", (e) => {
        const item = e.target.closest(".move-folder-item");
        if (!item || !moveFolderBackdrop || moveFolderBackdrop.classList.contains("d-none")) return;
        e.preventDefault();
        _selectedMoveFolder = item.dataset.path;
        if (moveFolderPathInput) moveFolderPathInput.value = "";
        moveFolderTree.querySelectorAll(".move-folder-item").forEach(el => el.classList.remove("selected"));
        item.classList.add("selected");
    });

    if (moveFolderConfirm) {
        moveFolderConfirm.addEventListener("click", async () => {
            const customPath = (moveFolderPathInput?.value || "").trim();
            const targetFolder = customPath || _selectedMoveFolder || "/";

            if (_moveRecordingNames.length === 0) return;

            moveFolderConfirm.disabled = true;
            moveFolderConfirm.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            hide(moveFolderFeedback);

            try {
                let res;
                if (_moveRecordingNames.length === 1) {
                    res = await fetch(`${MOVE_RECORDING_URL}/${encodeURIComponent(_moveRecordingNames[0])}/move`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ folder: targetFolder }),
                    });
                } else {
                    res = await fetch(BULK_MOVE_URL, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ names: _moveRecordingNames, folder: targetFolder }),
                    });
                }
                const data = await res.json();
                if (data.ok) {
                    closeMoveFolderModal();
                    await loadDashboard();
                } else {
                    moveFolderFeedback.className = "small mt-2 text-danger";
                    moveFolderFeedback.textContent = data.error;
                    show(moveFolderFeedback);
                }
            } catch (err) {
                moveFolderFeedback.className = "small mt-2 text-danger";
                moveFolderFeedback.textContent = `Move failed: ${err.message}`;
                show(moveFolderFeedback);
            } finally {
                moveFolderConfirm.disabled = false;
                moveFolderConfirm.innerHTML = '<i class="bi bi-folder-symlink me-1"></i>Move';
            }
        });
    }

    // Bulk move button
    const bulkMoveBtn = $("#btn-bulk-move");
    if (bulkMoveBtn) {
        bulkMoveBtn.addEventListener("click", (e) => {
            e.preventDefault();
            const checked = document.querySelectorAll(".rec-checkbox:checked");
            const names = Array.from(checked).map(cb => cb.dataset.name);
            if (names.length > 0) openMoveFolderModal(names);
        });
    }

    // Move single recording via right-click context or a dedicated button (we add a move button in action buttons area)
    // We'll handle the "move" action from action buttons below

    const refreshBtn = $("#btn-refresh");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", (e) => {
            e.preventDefault();
            refreshBtn.querySelector("i").classList.add("spin");
            loadDashboard().finally(() => {
                setTimeout(() => refreshBtn.querySelector("i").classList.remove("spin"), 600);
            });
        });
    }

    const logoutBtn = $("#btn-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", (e) => {
            e.preventDefault();
            fetch(LOGOUT_URL, { method: "POST" }).then(() => {
                window.location.href = LOGIN_PAGE_URL;
            }).catch(err => {
                alert("Logout failed: " + err.message);
            });

        });
    }

    const syncBtn = $("#btn-sync");
    if (syncBtn) {
        syncBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            const icon = syncBtn.querySelector("i");
            const alert = $("#sync-alert");

            icon.classList.add("spin");
            syncBtn.classList.add("disabled");
            hide(alert);
            showSyncOverlay();

            try {
                if (!HiDockDevice.isSupported()) throw new Error("WebUSB not supported in this browser");
                const devices = await HiDockDevice.getDevices();
                if (devices.length === 0) throw new Error("No paired HiDock device found. Click 'Connect Device' first.");
                const hidock = devices[0];
                await hidock.open();

                let files;
                try {
                    files = await hidock.listFiles();
                } catch (listErr) {
                    await hidock.close();
                    throw listErr;
                }

                if (files.length === 0) {
                    await hidock.close();
                    alert.className = "alert alert-info";
                    alert.innerHTML = `<i class="bi bi-info-circle me-1"></i> No files on device to sync.`;
                    show(alert);
                    await loadDashboard();
                    return;
                }

                // Pre-fetch existing recordings to skip already-synced files
                const statusRes = await fetch(API_URL);
                const statusData = await statusRes.json();
                const existingNames = new Set(
                    (statusData.recordings || [])
                        .filter(r => r.on_local && r.in_db)
                        .map(r => r.name)
                );

                const synced = [];
                const skipped = [];
                const errors = [];
                for (const f of files) {
                    try {
                        if (existingNames.has(HiDockDevice.bareName(f.name))) {
                            skipped.push(f.name);
                            continue;
                        }

                        const data = await hidock.downloadFile(f.name, f.length);
                        const blob = new Blob([data], { type: "audio/mpeg" });
                        const form = new FormData();
                        form.append("file", blob, f.name);
                        form.append("label", HiDockDevice.bareName(f.name));
                        const res = await fetch(UPLOAD_URL, { method: "POST", body: form });
                        const result = await res.json();
                        if (result.ok) {
                            synced.push(f.name);
                        } else if (result.error && result.error.toLowerCase().includes("already exists")) {
                            skipped.push(f.name);
                        } else {
                            errors.push(`${f.name}: ${result.error}`);
                        }
                    } catch (fileErr) {
                        errors.push(`${f.name}: ${fileErr.message}`);
                    }
                }

                await hidock.close();

                if (synced.length > 0) {
                    const list = synced.map(n => `<li>${n}</li>`).join("");
                    alert.className = "alert alert-success";
                    let msg = `<i class="bi bi-check-circle me-1"></i> Synced ${synced.length} file(s) from device.<ul class="mb-0 mt-1">${list}</ul>`;
                    if (skipped.length > 0) {
                        msg += `<br><small class="text-muted">Skipped ${skipped.length} already-synced file(s).</small>`;
                    }
                    if (errors.length > 0) {
                        msg += `<br><small class="text-muted">Warnings: ${errors.join("; ")}</small>`;
                    }
                    alert.innerHTML = msg;
                } else if (skipped.length > 0 && errors.length === 0) {
                    alert.className = "alert alert-info";
                    alert.innerHTML = `<i class="bi bi-info-circle me-1"></i> All ${skipped.length} file(s) already synced — nothing new to download.`;
                } else if (errors.length > 0) {
                    alert.className = "alert alert-danger";
                    let msg = `<i class="bi bi-exclamation-triangle me-1"></i> Sync failed: ${errors.join("; ")}`;
                    if (skipped.length > 0) {
                        msg += `<br><small class="text-muted">Skipped ${skipped.length} already-synced file(s).</small>`;
                    }
                    alert.innerHTML = msg;
                } else {
                    alert.className = "alert alert-info";
                    alert.innerHTML = `<i class="bi bi-info-circle me-1"></i> No new files to sync.`;
                }
                show(alert);
                await loadDashboard();
            } catch (err) {
                alert.className = "alert alert-danger";
                alert.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> Sync failed: ${err.message}`;
                show(alert);
            } finally {
                hideSyncOverlay();
                icon.classList.remove("spin");
                syncBtn.classList.remove("disabled");
            }
        });
    }

    // --- Connect Device (WebUSB pairing) ---
    const connectBtn = $("#btn-connect-device");
    const navConnect = $("#nav-connect-device");
    const navSync = $("#nav-sync-device");

    // Hide WebUSB buttons if not supported
    if (!window.HiDockDevice || !HiDockDevice.isSupported()) {
        if (navConnect) hide(navConnect);
        if (navSync) hide(navSync);
    }

    if (connectBtn && window.HiDockDevice && HiDockDevice.isSupported()) {
        connectBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            try {
                await HiDockDevice.requestDevice();
                await loadDashboard();
            } catch (err) {
                if (err.name !== "NotFoundError") { // user cancelled picker
                    console.error("Connect device failed:", err);
                }
            }
        });
    }

    // --- Upload modal ---
    const uploadBtn = $("#btn-upload");
    const uploadBackdrop = $("#upload-modal-backdrop");
    const uploadClose = $("#upload-modal-close");
    const uploadCancel = $("#upload-cancel-btn");
    const uploadFileInput = $("#upload-file-input");
    const uploadLabelInput = $("#upload-label-input");
    const uploadSubmitBtn = $("#upload-submit-btn");
    const uploadFormSection = $("#upload-form-section");
    const uploadProgress = $("#upload-progress");
    const uploadResult = $("#upload-result");

    function openUploadModal() {
        if (uploadFileInput) uploadFileInput.value = "";
        if (uploadLabelInput) uploadLabelInput.value = "";
        if (uploadSubmitBtn) uploadSubmitBtn.disabled = true;
        show(uploadFormSection);
        hide(uploadProgress);
        hide(uploadResult);
        show(uploadBackdrop);
    }

    function closeUploadModal() {
        hide(uploadBackdrop);
    }

    if (uploadBtn) {
        uploadBtn.addEventListener("click", (e) => {
            e.preventDefault();
            openUploadModal();
        });
    }
    if (uploadClose) uploadClose.addEventListener("click", closeUploadModal);
    if (uploadCancel) uploadCancel.addEventListener("click", closeUploadModal);
    if (uploadBackdrop) {
        uploadBackdrop.addEventListener("click", (e) => {
            if (e.target === uploadBackdrop) closeUploadModal();
        });
    }

    if (uploadFileInput) {
        uploadFileInput.addEventListener("change", () => {
            if (uploadSubmitBtn) {
                uploadSubmitBtn.disabled = !uploadFileInput.files || uploadFileInput.files.length === 0;
            }
        });
    }

    if (uploadSubmitBtn) {
        uploadSubmitBtn.addEventListener("click", async () => {
            if (!uploadFileInput.files || uploadFileInput.files.length === 0) return;

            const file = uploadFileInput.files[0];
            const label = uploadLabelInput ? uploadLabelInput.value.trim() : "";

            hide(uploadFormSection);
            show(uploadProgress);
            hide(uploadResult);

            const formData = new FormData();
            formData.append("file", file);
            formData.append("label", label);

            try {
                const res = await fetch(UPLOAD_URL, { method: "POST", body: formData });
                const data = await res.json();

                hide(uploadProgress);
                if (data.ok) {
                    uploadResult.className = "alert alert-success mt-3";
                    uploadResult.innerHTML = `<i class="bi bi-check-circle me-1"></i>${data.message}`;
                    show(uploadResult);
                    setTimeout(async () => {
                        closeUploadModal();
                        await loadDashboard();
                    }, 1200);
                } else {
                    uploadResult.className = "alert alert-danger mt-3";
                    uploadResult.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>${data.error}`;
                    show(uploadResult);
                    show(uploadFormSection);
                }
            } catch (err) {
                hide(uploadProgress);
                uploadResult.className = "alert alert-danger mt-3";
                uploadResult.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>Upload failed: ${err.message}`;
                show(uploadResult);
                show(uploadFormSection);
            }
        });
    }

    // --- Audio player modal ---
    const audioBackdrop = $("#audio-modal-backdrop");
    const audioClose = $("#audio-modal-close");
    const audioName = $("#audio-modal-name");
    const audioPlayer = $("#audio-player");

    function openAudioModal(name) {
        audioName.textContent = name;
        audioPlayer.src = `${AUDIO_URL}/${encodeURIComponent(name)}`;
        show(audioBackdrop);
        audioPlayer.play().catch(() => {});
    }

    function closeAudioModal() {
        if (audioPlayer) {
            audioPlayer.pause();
            audioPlayer.src = "";
        }
        hide(audioBackdrop);
    }

    if (audioClose) {
        audioClose.addEventListener("click", closeAudioModal);
    }
    if (audioBackdrop) {
        audioBackdrop.addEventListener("click", (e) => {
            if (e.target === audioBackdrop) closeAudioModal();
        });
    }

    document.addEventListener("click", (e) => {
        const playBtn = e.target.closest(".btn-play-audio");
        if (playBtn) {
            e.preventDefault();
            openAudioModal(playBtn.dataset.name);
        }

        // Move single recording button
        const moveBtn = e.target.closest(".btn-move-recording");
        if (moveBtn) {
            e.preventDefault();
            openMoveFolderModal([moveBtn.dataset.name]);
        }
    });

    // --- Transcript modal ---
    const modalBackdrop = $("#transcript-modal-backdrop");
    const modalClose = $("#transcript-modal-close");
    const modalName = $("#transcript-modal-name");
    const modalLoading = $("#transcript-loading");
    const modalContent = $("#transcript-content");
    const transcriptEditor = $("#transcript-editor");
    const transcriptEditToggle = $("#transcript-edit-toggle");
    const transcriptSaveBtn = $("#transcript-save-btn");
    const transcriptSaveFeedback = $("#transcript-save-feedback");
    const transcriptSpeakerEditor = $("#transcript-speaker-editor");
    const transcriptSpeakerList = $("#transcript-speaker-list");
    const transcriptApplySpeakersBtn = $("#transcript-apply-speakers-btn");
    const transcriptResetSpeakersBtn = $("#transcript-reset-speakers-btn");
    const transcriptAudioPlayer = $("#transcript-audio-player");
    const transcriptAudio = $("#transcript-audio");
    const modalError = $("#transcript-error");
    let currentTranscriptName = null;

    function extractSpeakerNames(transcript) {
        // Match speaker names at start of line, optionally preceded by timestamp [HH:MM]
        // Matches: "[00:01] Speaker 1:", "Speaker 1:", "[0:12] John:", "John:", etc.
        const speakerRegex = /^[\s]*(?:\[\d{1,2}:\d{2}\]\s*)?([A-Za-z0-9\s\(\)]+?):/gm;
        const names = [];
        const seen = new Set();
        let match;
        while ((match = speakerRegex.exec(transcript || "")) !== null) {
            const name = (match[1] || "").trim();
            if (name && !seen.has(name) && name.length > 0) {
                seen.add(name);
                names.push(name);
            }
        }
        return names;
    }

    function applySpeakerRenamesToTranscript(transcript, renames) {
        return (transcript || "").split("\n").map((line) => {
            // Try to match optional timestamp and speaker name at start: "[00:01] Speaker 1:" or "John:"
            const match = line.match(/^(\s*)(\[\d{1,2}:\d{2}\]\s*)?([A-Za-z0-9\s\(\)]+?):/);
            if (!match) return line;

            const indent = match[1] || "";
            const timestamp = match[2] || "";
            const originalSpeaker = match[3].trim();
            const newSpeaker = renames[originalSpeaker];

            if (!newSpeaker) return line;

            // Replace speaker name while preserving indentation, timestamp, and everything after colon
            return `${indent}${timestamp}${newSpeaker}:${line.slice(match[0].length)}`;
        }).join("\n");
    }

    function renderSpeakerEditor(transcript) {
        const speakers = extractSpeakerNames(transcript);
        if (!transcriptSpeakerEditor || !transcriptSpeakerList) return;

        if (speakers.length === 0) {
            transcriptSpeakerList.innerHTML = '<p class="text-muted small mb-0">No speakers found in transcript. Speakers should be formatted like "Speaker 1:" or "John:" at the start of a line.</p>';
            show(transcriptSpeakerEditor);
            return;
        }

        transcriptSpeakerList.innerHTML = speakers.map((name) => `
            <div class="row g-2 align-items-center mb-2">
                <div class="col-md-5">
                    <span class="small text-muted">${escapeHtml(name)}</span>
                </div>
                <div class="col-md-7">
                    <input
                        type="text"
                        class="form-control form-control-sm transcript-speaker-input"
                        data-original="${escapeHtml(name)}"
                        value="${escapeHtml(name)}"
                        placeholder="Speaker name"
                    />
                </div>
            </div>
        `).join("");
        show(transcriptSpeakerEditor);
    }

     function openTranscriptModal(name) {
         currentTranscriptName = name;
         modalName.textContent = name;
         show(modalLoading);
         hide(modalContent);
         hide(transcriptEditor);
         hide(transcriptSaveBtn);
         hide(transcriptSpeakerEditor);
         hide(transcriptSaveFeedback);
         hide(transcriptAudioPlayer);
         transcriptEditToggle.innerHTML = '<i class="bi bi-pencil-square"></i> Edit';
         transcriptEditToggle.disabled = true;
         hide(modalError);
         show(modalBackdrop);
     }

    function closeTranscriptModal() {
        currentTranscriptName = null;
        hide(modalBackdrop);
    }

    function showTranscriptPreview(transcript) {
         modalContent.innerHTML = formatTranscript(transcript || "");
         transcriptEditor.value = transcript || "";
         show(modalContent);
         show(transcriptAudioPlayer);
         if (currentTranscriptName && transcriptAudio) {
             transcriptAudio.src = `${AUDIO_URL}/${encodeURIComponent(currentTranscriptName)}`;
         }
         hide(transcriptEditor);
         hide(transcriptSaveBtn);
         hide(transcriptSpeakerEditor);
         transcriptEditToggle.innerHTML = '<i class="bi bi-pencil-square"></i> Edit';
         transcriptEditToggle.disabled = false;
     }

    function showTranscriptEditor() {
        hide(modalContent);
        show(transcriptEditor);
        show(transcriptSaveBtn);
        renderSpeakerEditor(transcriptEditor.value);
        transcriptEditToggle.innerHTML = '<i class="bi bi-eye"></i> Preview';
        transcriptEditor.focus();
    }

    if (modalClose) {
        modalClose.addEventListener("click", closeTranscriptModal);
    }
    if (modalBackdrop) {
        modalBackdrop.addEventListener("click", (e) => {
            if (e.target === modalBackdrop) closeTranscriptModal();
        });
    }

    // Transcribe engine dropdown toggle
    document.addEventListener("click", (e) => {
        const toggleBtn = e.target.closest(".btn-transcribe-toggle");
        if (toggleBtn) {
            e.preventDefault();
            e.stopPropagation();
            // Close any other open menus first
            document.querySelectorAll(".transcribe-engine-menu").forEach(m => m.classList.add("d-none"));
            const menu = toggleBtn.parentElement.querySelector(".transcribe-engine-menu");
            if (menu) menu.classList.toggle("d-none");
            return;
        }
        // Close all open menus on outside click
        document.querySelectorAll(".transcribe-engine-menu").forEach(m => m.classList.add("d-none"));
    });

    // Start transcription helper
    async function startTranscription(name, engine, triggerBtn) {
        const engineLabel = engine === "whisper" ? "Whisper (local)" : "Gemini AI";

        if (triggerBtn) {
            triggerBtn.disabled = true;
            triggerBtn._origHTML = triggerBtn._origHTML || triggerBtn.innerHTML;
            triggerBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
        }

        openTranscriptModal(name);
        modalLoading.querySelector("p").textContent = `Transcribing with ${engineLabel}… this may take a moment.`;

        try {
            const res = await fetch(`${TRANSCRIBE_URL}/${encodeURIComponent(name)}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ engine }),
            });
            const data = await res.json();

            hide(modalLoading);
            if (data.ok) {
                showTranscriptPreview(data.transcript);
                await loadDashboard();
            } else {
                modalError.textContent = data.error;
                show(modalError);
            }
        } catch (err) {
            hide(modalLoading);
            modalError.textContent = `Transcription failed: ${err.message}`;
            show(modalError);
        } finally {
            if (triggerBtn) {
                triggerBtn.disabled = false;
                triggerBtn.innerHTML = triggerBtn._origHTML;
            }
        }
    }

    // Transcribe button (main button — default engine) & engine menu item
    document.addEventListener("click", async (e) => {
        // Engine menu item clicked
        const engineItem = e.target.closest(".btn-transcribe-engine");
        if (engineItem) {
            e.preventDefault();
            const name = engineItem.dataset.name;
            const engine = engineItem.dataset.engine || "gemini";
            // Close menu
            document.querySelectorAll(".transcribe-engine-menu").forEach(m => m.classList.add("d-none"));
            // Find the main button for spinner
            const group = engineItem.closest(".transcribe-split");
            const mainBtn = group ? group.querySelector(".btn-transcribe") : null;
            await startTranscription(name, engine, mainBtn);
            return;
        }

        const transcribeBtn = e.target.closest(".btn-transcribe");
        if (transcribeBtn) {
            e.preventDefault();
            const name = transcribeBtn.dataset.name;
            const engine = transcribeBtn.dataset.engine || "gemini";
            await startTranscription(name, engine, transcribeBtn);
        }

        const viewBtn = e.target.closest(".btn-view-transcript");
        if (viewBtn) {
            e.preventDefault();
            const name = viewBtn.dataset.name;
            openTranscriptModal(name);

            try {
                const res = await fetch(`${TRANSCRIPT_URL}/${encodeURIComponent(name)}`);
                const data = await res.json();

                hide(modalLoading);
                if (data.ok) {
                    showTranscriptPreview(data.transcript);
                } else {
                    modalError.textContent = data.error;
                    show(modalError);
                }
            } catch (err) {
                hide(modalLoading);
                modalError.textContent = `Failed to load transcript: ${err.message}`;
                show(modalError);
            }
        }

        // --- View summary ---
        const viewSummaryBtn = e.target.closest(".btn-view-summary");
        if (viewSummaryBtn) {
            e.preventDefault();
            const name = viewSummaryBtn.dataset.name;
            openSummaryModal(name);

            try {
                const res = await fetch(`${SUMMARIES_URL}/${encodeURIComponent(name)}`);
                const data = await res.json();

                hide(summaryLoading);
                if (data.ok) {
                    summaryContent.innerHTML = renderSummaryVersions(data.summaries || []);
                    show(summaryContent);
                } else {
                    summaryError.textContent = data.error;
                    show(summaryError);
                }
            } catch (err) {
                hide(summaryLoading);
                summaryError.textContent = `Failed to load summary: ${err.message}`;
                show(summaryError);
            }
        }

        // --- Summarize button → open prompt picker ---
        const summarizeBtn = e.target.closest(".btn-summarize");
        if (summarizeBtn) {
            e.preventDefault();
            const name = summarizeBtn.dataset.name;
            openPromptPicker(name);
        }
    });

    if (transcriptEditToggle) {
        transcriptEditToggle.addEventListener("click", (e) => {
            e.preventDefault();
            hide(transcriptSaveFeedback);
            if (transcriptEditor.classList.contains("d-none")) {
                showTranscriptEditor();
            } else {
                showTranscriptPreview(transcriptEditor.value);
            }
        });
    }

    if (transcriptSaveBtn) {
        transcriptSaveBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            if (!currentTranscriptName) return;

            transcriptSaveBtn.disabled = true;
            transcriptSaveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
            hide(transcriptSaveFeedback);

            try {
                const res = await fetch(`${TRANSCRIPT_UPDATE_URL}/${encodeURIComponent(currentTranscriptName)}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ transcript: transcriptEditor.value }),
                });
                const data = await res.json();

                if (data.ok) {
                    transcriptSaveFeedback.className = "small mt-2 text-success";
                    transcriptSaveFeedback.textContent = "Transcript saved";
                    show(transcriptSaveFeedback);
                    showTranscriptPreview(transcriptEditor.value);
                    await loadDashboard();
                } else {
                    transcriptSaveFeedback.className = "small mt-2 text-danger";
                    transcriptSaveFeedback.textContent = data.error;
                    show(transcriptSaveFeedback);
                }
            } catch (err) {
                transcriptSaveFeedback.className = "small mt-2 text-danger";
                transcriptSaveFeedback.textContent = `Save failed: ${err.message}`;
                show(transcriptSaveFeedback);
            } finally {
                transcriptSaveBtn.disabled = false;
                transcriptSaveBtn.innerHTML = '<i class="bi bi-check-lg"></i> Save';
            }
        });
    }

    if (transcriptApplySpeakersBtn) {
        transcriptApplySpeakersBtn.addEventListener("click", (e) => {
            e.preventDefault();
            if (!transcriptSpeakerList || !transcriptEditor) return;

            const inputs = Array.from(transcriptSpeakerList.querySelectorAll(".transcript-speaker-input"));
            const renames = {};
            for (const input of inputs) {
                const original = (input.dataset.original || "").trim();
                const nextName = (input.value || "").trim();
                if (original && nextName && nextName !== original) {
                    renames[original] = nextName;
                }
            }

            if (Object.keys(renames).length === 0) {
                transcriptSaveFeedback.className = "small mt-2 text-muted";
                transcriptSaveFeedback.textContent = "No speaker changes to apply";
                show(transcriptSaveFeedback);
                return;
            }

            // Apply renames to transcript
            const oldTranscript = transcriptEditor.value;
            const newTranscript = applySpeakerRenamesToTranscript(oldTranscript, renames);
            transcriptEditor.value = newTranscript;

            // Re-render speaker editor with updated names
            renderSpeakerEditor(newTranscript);

            // Show feedback
            transcriptSaveFeedback.className = "small mt-2 text-success";
            transcriptSaveFeedback.textContent = `✓ Applied ${Object.keys(renames).length} speaker rename(s)`;
            show(transcriptSaveFeedback);

            // Scroll editor to top to show changes
            transcriptEditor.scrollTop = 0;
        });
    }

    if (transcriptResetSpeakersBtn) {
        transcriptResetSpeakersBtn.addEventListener("click", (e) => {
            e.preventDefault();
            if (!transcriptSpeakerList) return;

            const inputs = Array.from(transcriptSpeakerList.querySelectorAll(".transcript-speaker-input"));
            for (const input of inputs) {
                const original = input.dataset.original || "";
                input.value = original;
            }

            transcriptSaveFeedback.className = "small mt-2 text-info";
            transcriptSaveFeedback.textContent = "Speaker names reset";
            show(transcriptSaveFeedback);
        });
    }

    function escapeHtml(text) {
        return (text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatTranscript(text) {
        // Convert plain text transcript to HTML with basic formatting
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>")
            .replace(/\[(\d{1,2}:\d{2})\]/g, '<span class="transcript-timestamp">[$1]</span>')
            .replace(/(Speaker \d+|[A-Z][a-z]+):/g, '<strong>$1:</strong>');
    }

    function formatMarkdown(text) {
        // Basic markdown-to-HTML: headings, bold, italic, lists, line breaks
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/^### (.+)$/gm, '<h5>$1</h5>')
            .replace(/^## (.+)$/gm, '<h4>$1</h4>')
            .replace(/^# (.+)$/gm, '<h3>$1</h3>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
            .replace(/(<\/ul>\s*<ul>)/g, '')
            .replace(/\n/g, "<br>");
    }

    // --- Summary modal ---
    const summaryBackdrop = $("#summary-modal-backdrop");
    const summaryClose = $("#summary-modal-close");
    const summaryName = $("#summary-modal-name");
    const summaryLoading = $("#summary-loading");
    const summaryContent = $("#summary-content");
    const summaryError = $("#summary-error");
    let currentSummaryName = null;

    function renderSummaryVersions(summaries) {
        return summaries.map((s) => {
            const tags = (s.tags || []).join(", ");
            const created = s.created_at ? new Date(s.created_at).toLocaleString() : "";
            const notionLink = s.notion_url
                ? `<a href="${escapeHtml(s.notion_url)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-success"><i class="bi bi-box-arrow-up-right me-1"></i>Open</a>`
                : "";

            return `<div class="card mb-3" data-summary-id="${s.id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <strong>Version ${s.version}</strong>
                        <small class="text-muted ms-2">${escapeHtml(created)}</small>
                    </div>
                    <div class="d-flex gap-2">
                        ${notionLink}
                        <button class="btn btn-sm btn-outline-purple btn-view-tasks" data-summary-id="${s.id}" data-name="${escapeHtml(currentSummaryName || "")}">
                            <i class="bi bi-list-task"></i> Tasks
                        </button>
                        <button class="btn btn-sm btn-outline-primary btn-share-summary" data-summary-id="${s.id}" data-name="${escapeHtml(currentSummaryName || "")}">
                            <i class="bi bi-share"></i> Share
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row g-2 mb-2">
                        <div class="col-md-6">
                            <label class="form-label small mb-1">Title</label>
                            <input type="text" class="form-control form-control-sm summary-title-input" value="${escapeHtml(s.title || "")}" />
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small mb-1">Tags (comma separated)</label>
                            <input type="text" class="form-control form-control-sm summary-tags-input" value="${escapeHtml(tags)}" />
                        </div>
                    </div>
                    <div class="mb-3">
                        <button class="btn btn-sm btn-outline-secondary btn-save-summary-meta" data-summary-id="${s.id}">
                            <i class="bi bi-check-lg"></i> Save metadata
                        </button>
                        <span class="small ms-2 d-none summary-save-feedback"></span>
                    </div>
                    <div class="mb-2">
                        <button class="btn btn-sm btn-outline-secondary btn-toggle-summary-edit" data-summary-id="${s.id}">
                            <i class="bi bi-pencil-square"></i> Edit summary
                        </button>
                        <button class="btn btn-sm btn-success d-none btn-save-summary-content" data-summary-id="${s.id}">
                            <i class="bi bi-check-lg"></i> Save summary
                        </button>
                        <span class="small ms-2 d-none summary-content-feedback"></span>
                    </div>
                    <div class="summary-content summary-markdown-preview">${formatMarkdown(s.summary || "")}</div>
                    <textarea class="form-control d-none summary-content-editor" rows="12">${escapeHtml(s.summary || "")}</textarea>
                </div>
            </div>`;
        }).join("");
    }

    function openSummaryModal(name) {
        currentSummaryName = name;
        summaryName.textContent = name;
        show(summaryLoading);
        hide(summaryContent);
        hide(summaryError);
        show(summaryBackdrop);
    }

    function closeSummaryModal() {
        hide(summaryBackdrop);
    }

    if (summaryClose) {
        summaryClose.addEventListener("click", closeSummaryModal);
    }
    if (summaryBackdrop) {
        summaryBackdrop.addEventListener("click", (e) => {
            if (e.target === summaryBackdrop) closeSummaryModal();
        });
    }

    // --- Prompt picker modal ---
    const promptBackdrop = $("#prompt-picker-backdrop");
    const promptClose = $("#prompt-picker-close");
    const promptName = $("#prompt-picker-name");
    const promptList = $("#prompt-list");
    const promptLoading = $("#prompt-loading");
    const promptError = $("#prompt-picker-error");
    let currentSummarizeName = null;

    function closePromptPicker() {
        hide(promptBackdrop);
    }

    if (promptClose) {
        promptClose.addEventListener("click", closePromptPicker);
    }
    if (promptBackdrop) {
        promptBackdrop.addEventListener("click", (e) => {
            if (e.target === promptBackdrop) closePromptPicker();
        });
    }

    async function openPromptPicker(name) {
        currentSummarizeName = name;
        promptName.textContent = name;
        show(promptLoading);
        hide(promptList);
        hide(promptError);
        show(promptBackdrop);

        try {
            const res = await fetch(PROMPTS_URL);
            const data = await res.json();

            hide(promptLoading);
            if (!data.ok || data.prompts.length === 0) {
                promptError.textContent = "No system prompts found.";
                show(promptError);
                return;
            }

            const dataPrompts = data.prompts;
            const langs = [...new Set(dataPrompts.map(p => p.language))];
            
            let html = `
                <div class="mb-3">
                    <label class="form-label text-muted small fw-bold">Language</label>
                    <select class="form-select" id="prompt-lang-select">
                        <option value="">Select language...</option>
                        ${langs.map(l => `<option value="${l}">${l.toUpperCase()}</option>`).join('')}
                    </select>
                </div>
                <div class="mb-3 d-none" id="prompt-type-container">
                    <label class="form-label text-muted small fw-bold">Type</label>
                    <select class="form-select" id="prompt-type-select">
                        <option value="">Select type...</option>
                    </select>
                </div>
                <div class="mb-3 d-none" id="prompt-file-container">
                    <label class="form-label text-muted small fw-bold">Prompt</label>
                    <div id="prompt-buttons-container"></div>
                </div>
            `;
            promptList.innerHTML = html;
            show(promptList);

            // Add event listeners
            const langSelect = promptList.querySelector('#prompt-lang-select');
            const typeContainer = promptList.querySelector('#prompt-type-container');
            const typeSelect = promptList.querySelector('#prompt-type-select');
            const fileContainer = promptList.querySelector('#prompt-file-container');
            const btnContainer = promptList.querySelector('#prompt-buttons-container');

            langSelect.addEventListener('change', () => {
                const lang = langSelect.value;
                if (!lang) {
                    hide(typeContainer);
                    hide(fileContainer);
                    return;
                }
                const types = [...new Set(dataPrompts.filter(p => p.language === lang).map(p => p.category))];
                typeSelect.innerHTML = `<option value="">Select type...</option>` + 
                    types.map(t => `<option value="${t}">${t}</option>`).join('');
                show(typeContainer);
                hide(fileContainer);
            });

            typeSelect.addEventListener('change', () => {
                const lang = langSelect.value;
                const type = typeSelect.value;
                if (!lang || !type) {
                    hide(fileContainer);
                    return;
                }
                const prompts = dataPrompts.filter(p => p.language === lang && p.category === type);
                
                let btns = '';
                for (const p of prompts) {
                     btns += `<button class="btn btn-outline-secondary btn-sm me-2 mb-2 btn-select-prompt" data-prompt-id="${p.id}">
                        <i class="bi bi-file-earmark-text me-1"></i>${p.label.split(' / ')[1] || p.label}
                    </button>`;
                }
                btnContainer.innerHTML = btns;
                show(fileContainer);
            });
        } catch (err) {
            hide(promptLoading);
            promptError.textContent = `Failed to load prompts: ${err.message}`;
            show(promptError);
        }
    }

    // Handle prompt selection → trigger summarization
    document.addEventListener("click", async (e) => {
        const selectBtn = e.target.closest(".btn-select-prompt");
        if (!selectBtn || !currentSummarizeName) return;

        e.preventDefault();
        const promptId = selectBtn.dataset.promptId;

        // Disable all prompt buttons while working
        promptList.querySelectorAll(".btn-select-prompt").forEach(b => b.disabled = true);
        selectBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';

        closePromptPicker();
        openSummaryModal(currentSummarizeName);
        summaryLoading.querySelector("p").textContent = "Generating summary with Gemini AI… this may take a moment.";

        try {
            const res = await fetch(`${SUMMARIZE_URL}/${encodeURIComponent(currentSummarizeName)}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt_id: promptId }),
            });
            const data = await res.json();

            hide(summaryLoading);
            if (data.ok) {
                const summariesRes = await fetch(`${SUMMARIES_URL}/${encodeURIComponent(currentSummarizeName)}`);
                const summariesData = await summariesRes.json();
                if (summariesData.ok) {
                    summaryContent.innerHTML = renderSummaryVersions(summariesData.summaries || []);
                } else {
                    summaryContent.innerHTML = formatMarkdown(data.summary);
                }
                show(summaryContent);
                await loadDashboard();
            } else {
                summaryError.textContent = data.error;
                show(summaryError);
            }
        } catch (err) {
            hide(summaryLoading);
            summaryError.textContent = `Summarization failed: ${err.message}`;
            show(summaryError);
        }
    });

    // --- Share modal ---
    const shareBackdrop = $("#share-modal-backdrop");
    const shareClose = $("#share-modal-close");
    const shareName = $("#share-modal-name");
    const shareLoading = $("#share-loading");
    const shareDestinations = $("#share-destinations");
    const sharePublishing = $("#share-publishing");
    const shareSuccess = $("#share-success");
    const shareSuccessMsg = $("#share-success-msg");
    const shareSuccessLink = $("#share-success-link");
    const shareError = $("#share-error");
    let currentShareName = null;
    let currentShareSummaryId = null;

    function openShareModal(name, summaryId) {
        currentShareName = name;
        currentShareSummaryId = summaryId;
        shareName.textContent = name;
        show(shareLoading);
        hide(shareDestinations);
        hide(sharePublishing);
        hide(shareSuccess);
        hide(shareError);
        show(shareBackdrop);
    }

    function closeShareModal() {
        hide(shareBackdrop);
    }

    if (shareClose) {
        shareClose.addEventListener("click", closeShareModal);
    }
    if (shareBackdrop) {
        shareBackdrop.addEventListener("click", (e) => {
            if (e.target === shareBackdrop) closeShareModal();
        });
    }

    // Open share modal from a specific summary card.
    document.addEventListener("click", async (e) => {
        const shareBtn = e.target.closest(".btn-share-summary");
        if (!shareBtn) return;
        e.preventDefault();
        const name = shareBtn.dataset.name;
        const summaryId = parseInt(shareBtn.dataset.summaryId, 10);
        if (!summaryId) return;
        openShareModal(name, summaryId);

        try {
            const res = await fetch(SHARE_DESTINATIONS_URL);
            const data = await res.json();

            hide(shareLoading);
            if (!data.ok || data.destinations.length === 0) {
                shareError.textContent = "No publish destinations configured. Set NOTION_API_KEY and NOTION_DATABASE_ID in your .env file.";
                show(shareError);
                return;
            }

            let html = '<div class="d-flex flex-wrap gap-2 justify-content-center">';
            for (const dest of data.destinations) {
                html += `<button class="btn btn-outline-success btn-lg btn-select-destination" data-dest="${dest.id}">
                    <i class="bi ${dest.icon} me-2"></i>${dest.label}
                </button>`;
            }
            html += '</div>';
            shareDestinations.innerHTML = html;
            show(shareDestinations);
        } catch (err) {
            hide(shareLoading);
            shareError.textContent = `Failed to load destinations: ${err.message}`;
            show(shareError);
        }
    });

    // Handle destination selection → publish
    document.addEventListener("click", async (e) => {
        const destBtn = e.target.closest(".btn-select-destination");
        if (!destBtn || !currentShareName || !currentShareSummaryId) return;
        e.preventDefault();

        const destination = destBtn.dataset.dest;

        // Show publishing state
        hide(shareDestinations);
        hide(shareError);
        show(sharePublishing);

        try {
            const res = await fetch(`${SHARE_SUMMARY_URL}/${encodeURIComponent(currentShareSummaryId)}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ destination }),
            });
            const data = await res.json();

            hide(sharePublishing);
            if (data.ok) {
                shareSuccessMsg.textContent = `Published to ${destination.charAt(0).toUpperCase() + destination.slice(1)} successfully!`;
                if (data.url) {
                    shareSuccessLink.href = data.url;
                    shareSuccessLink.textContent = `Open in ${destination.charAt(0).toUpperCase() + destination.slice(1)}`;
                    show(shareSuccessLink);
                } else {
                    hide(shareSuccessLink);
                }
                show(shareSuccess);
                // Refresh dashboard so the Notion link appears on the title
                await loadDashboard();
            } else {
                shareError.textContent = data.error;
                show(shareError);
            }
        } catch (err) {
            hide(sharePublishing);
            shareError.textContent = `Publish failed: ${err.message}`;
            show(shareError);
        }
    });

    // Save metadata for a specific summary version.
    document.addEventListener("click", async (e) => {
        const saveBtn = e.target.closest(".btn-save-summary-meta");
        if (!saveBtn) return;
        e.preventDefault();

        const summaryId = parseInt(saveBtn.dataset.summaryId, 10);
        const card = saveBtn.closest(".card[data-summary-id]");
        if (!summaryId || !card) return;

        const titleInput = card.querySelector(".summary-title-input");
        const tagsInput = card.querySelector(".summary-tags-input");
        const feedback = card.querySelector(".summary-save-feedback");
        if (!titleInput || !tagsInput || !feedback) return;

        const title = titleInput.value.trim();
        const tags = tagsInput.value
            .split(",")
            .map((t) => t.trim())
            .filter((t) => t);

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
        hide(feedback);

        try {
            const res = await fetch(`${SUMMARY_UPDATE_URL}/${encodeURIComponent(summaryId)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, tags }),
            });
            const data = await res.json();

            if (data.ok) {
                feedback.className = "small ms-2 text-success summary-save-feedback";
                feedback.textContent = "Saved";
                show(feedback);
                await loadDashboard();
            } else {
                feedback.className = "small ms-2 text-danger summary-save-feedback";
                feedback.textContent = data.error;
                show(feedback);
            }
        } catch (err) {
            feedback.className = "small ms-2 text-danger summary-save-feedback";
            feedback.textContent = `Save failed: ${err.message}`;
            show(feedback);
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="bi bi-check-lg"></i> Save metadata';
        }
    });

    // Toggle summary markdown editing mode.
    document.addEventListener("click", (e) => {
        const editBtn = e.target.closest(".btn-toggle-summary-edit");
        if (!editBtn) return;
        e.preventDefault();

        const card = editBtn.closest(".card[data-summary-id]");
        if (!card) return;
        const preview = card.querySelector(".summary-markdown-preview");
        const editor = card.querySelector(".summary-content-editor");
        const saveBtn = card.querySelector(".btn-save-summary-content");
        const feedback = card.querySelector(".summary-content-feedback");
        if (!preview || !editor || !saveBtn || !feedback) return;

        hide(feedback);
        if (editor.classList.contains("d-none")) {
            hide(preview);
            show(editor);
            show(saveBtn);
            editBtn.innerHTML = '<i class="bi bi-eye"></i> Preview';
            editor.focus();
        } else {
            preview.innerHTML = formatMarkdown(editor.value);
            show(preview);
            hide(editor);
            hide(saveBtn);
            editBtn.innerHTML = '<i class="bi bi-pencil-square"></i> Edit summary';
        }
    });

    // Save markdown content for a specific summary version.
    document.addEventListener("click", async (e) => {
        const saveBtn = e.target.closest(".btn-save-summary-content");
        if (!saveBtn) return;
        e.preventDefault();

        const summaryId = parseInt(saveBtn.dataset.summaryId, 10);
        const card = saveBtn.closest(".card[data-summary-id]");
        if (!summaryId || !card) return;

        const editor = card.querySelector(".summary-content-editor");
        const feedback = card.querySelector(".summary-content-feedback");
        if (!editor || !feedback) return;

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
        hide(feedback);

        try {
            const res = await fetch(`${SUMMARY_UPDATE_URL}/${encodeURIComponent(summaryId)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ summary: editor.value }),
            });
            const data = await res.json();

            if (data.ok) {
                feedback.className = "small ms-2 text-success summary-content-feedback";
                feedback.textContent = "Saved";
                show(feedback);
                await loadDashboard();
            } else {
                feedback.className = "small ms-2 text-danger summary-content-feedback";
                feedback.textContent = data.error;
                show(feedback);
            }
        } catch (err) {
            feedback.className = "small ms-2 text-danger summary-content-feedback";
            feedback.textContent = `Save failed: ${err.message}`;
            show(feedback);
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="bi bi-check-lg"></i> Save summary';
        }
    });


    // --- Tasks modal ---
    const tasksBackdrop = $("#tasks-modal-backdrop");
    const tasksClose = $("#tasks-modal-close");
    const tasksModalName = $("#tasks-modal-name");
    const tasksLoading = $("#tasks-loading");
    const tasksContent = $("#tasks-content");
    const tasksEmpty = $("#tasks-empty");
    const tasksError = $("#tasks-error");
    let currentTasksSummaryId = null;
    let currentTasksSummaryName = null;

    function openTasksModal(summaryId, name) {
        currentTasksSummaryId = summaryId;
        currentTasksSummaryName = name || "";
        tasksModalName.textContent = name || `Summary #${summaryId}`;
        show(tasksLoading);
        hide(tasksContent);
        hide(tasksEmpty);
        hide(tasksError);
        show(tasksBackdrop);
    }

    function closeTasksModal() {
        hide(tasksBackdrop);
        currentTasksSummaryId = null;
    }

    if (tasksClose) {
        tasksClose.addEventListener("click", closeTasksModal);
    }
    if (tasksBackdrop) {
        tasksBackdrop.addEventListener("click", (e) => {
            if (e.target === tasksBackdrop) closeTasksModal();
        });
    }

    function renderTaskCard(task, isSubtask = false) {
        const doneClass = task.status === "done" ? "task-done" : "";
        const cardClass = isSubtask ? "subtask-card" : "task-card";
        const statusClass = task.status === "done" ? "task-status-done" : "task-status-open";
        const statusLabel = task.status === "done" ? "Done" : "Open";
        const toggleStatus = task.status === "done" ? "open" : "done";
        const toggleIcon = task.status === "done" ? "bi-arrow-counterclockwise" : "bi-check-lg";
        const toggleTitle = task.status === "done" ? "Reopen" : "Mark done";

        let subtasksHtml = "";
        if (!isSubtask && task.subtasks && task.subtasks.length > 0) {
            subtasksHtml = `<div class="subtask-list">${task.subtasks.map(s => renderTaskCard(s, true)).join("")}</div>`;
        }

        return `<div class="${cardClass} ${doneClass}" data-task-id="${task.id}">
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <div class="task-title">${escapeHtml(task.title)}</div>
                    ${task.description ? `<div class="task-description">${escapeHtml(task.description)}</div>` : ""}
                </div>
                <div class="d-flex align-items-center gap-2 ms-2 task-actions">
                    <span class="task-status-badge ${statusClass}">${statusLabel}</span>
                    <button class="btn btn-sm btn-outline-secondary btn-toggle-task-status" data-task-id="${task.id}" data-status="${toggleStatus}" title="${toggleTitle}">
                        <i class="bi ${toggleIcon}"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger btn-delete-task" data-task-id="${task.id}" title="Delete task">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
            </div>
            ${subtasksHtml}
        </div>`;
    }

    function renderTasksList(tasks, summaryId) {
        let html = `<div class="tasks-header">
            <span class="text-muted small">${tasks.length} task(s)</span>
            <button class="btn btn-sm btn-outline-warning btn-regenerate-tasks" data-summary-id="${summaryId}">
                <i class="bi bi-stars me-1"></i>Regenerate
            </button>
        </div>`;
        html += tasks.map(t => renderTaskCard(t)).join("");
        return html;
    }

    async function loadTasks(summaryId) {
        try {
            const res = await fetch(`${TASKS_URL}/${encodeURIComponent(summaryId)}`);
            const data = await res.json();
            hide(tasksLoading);

            if (data.ok && data.tasks && data.tasks.length > 0) {
                tasksContent.innerHTML = renderTasksList(data.tasks, summaryId);
                show(tasksContent);
                hide(tasksEmpty);
            } else {
                hide(tasksContent);
                show(tasksEmpty);
            }
        } catch (err) {
            hide(tasksLoading);
            tasksError.textContent = `Failed to load tasks: ${err.message}`;
            show(tasksError);
        }
    }

    async function generateTasks(summaryId) {
        show(tasksLoading);
        hide(tasksContent);
        hide(tasksEmpty);
        hide(tasksError);
        tasksLoading.querySelector("p").textContent = "Generating tasks with AI… this may take a moment.";

        try {
            const res = await fetch(TASKS_GENERATE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ summary_id: summaryId }),
            });
            const data = await res.json();
            hide(tasksLoading);

            if (data.ok && data.tasks && data.tasks.length > 0) {
                tasksContent.innerHTML = renderTasksList(data.tasks, summaryId);
                show(tasksContent);
                hide(tasksEmpty);
            } else if (data.ok) {
                hide(tasksContent);
                show(tasksEmpty);
            } else {
                tasksError.textContent = data.error || "Task generation failed";
                show(tasksError);
            }
        } catch (err) {
            hide(tasksLoading);
            tasksError.textContent = `Task generation failed: ${err.message}`;
            show(tasksError);
        }
    }

    // Open tasks modal from summary card
    document.addEventListener("click", async (e) => {
        const tasksBtn = e.target.closest(".btn-view-tasks");
        if (!tasksBtn) return;
        e.preventDefault();
        const summaryId = parseInt(tasksBtn.dataset.summaryId, 10);
        const name = tasksBtn.dataset.name || "";
        if (!summaryId) return;

        openTasksModal(summaryId, name);
        await loadTasks(summaryId);
    });

    // Generate tasks from empty state button
    document.addEventListener("click", async (e) => {
        if (e.target.closest("#tasks-generate-btn-empty")) {
            e.preventDefault();
            if (currentTasksSummaryId) {
                await generateTasks(currentTasksSummaryId);
            }
        }
    });

    // Regenerate tasks button
    document.addEventListener("click", async (e) => {
        const regenBtn = e.target.closest(".btn-regenerate-tasks");
        if (!regenBtn) return;
        e.preventDefault();
        const summaryId = parseInt(regenBtn.dataset.summaryId, 10);
        if (!summaryId) return;

        if (!confirm("This will replace all existing tasks for this summary. Continue?")) return;
        await generateTasks(summaryId);
    });

    // Toggle task status
    document.addEventListener("click", async (e) => {
        const toggleBtn = e.target.closest(".btn-toggle-task-status");
        if (!toggleBtn) return;
        e.preventDefault();
        const taskId = parseInt(toggleBtn.dataset.taskId, 10);
        const newStatus = toggleBtn.dataset.status;
        if (!taskId) return;

        toggleBtn.disabled = true;
        toggleBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';

        try {
            const res = await fetch(`${TASKS_URL}/${encodeURIComponent(taskId)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus }),
            });
            const data = await res.json();

            if (data.ok && currentTasksSummaryId) {
                await loadTasks(currentTasksSummaryId);
            }
        } catch (err) {
            console.error("Failed to update task status:", err);
        }
    });

    // Delete task
    document.addEventListener("click", async (e) => {
        const delBtn = e.target.closest(".btn-delete-task");
        if (!delBtn) return;
        e.preventDefault();
        const taskId = parseInt(delBtn.dataset.taskId, 10);
        if (!taskId) return;

        delBtn.disabled = true;
        delBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';

        try {
            const res = await fetch(`${TASKS_URL}/${encodeURIComponent(taskId)}`, {
                method: "DELETE",
            });
            const data = await res.json();

            if (data.ok && currentTasksSummaryId) {
                await loadTasks(currentTasksSummaryId);
            }
        } catch (err) {
            console.error("Failed to delete task:", err);
        }
    });


    // --- Delete recording modal (local file + DB record) ---
    const delRecBackdrop = $("#delete-rec-modal-backdrop");
    const delRecClose = $("#delete-rec-modal-close");
    const delRecCancel = $("#delete-rec-modal-cancel");
    const delRecName = $("#delete-rec-modal-name");
    const delRecConfirm = $("#delete-rec-modal-confirm");
    const delRecActions = $("#delete-rec-modal-actions");
    const delRecProgress = $("#delete-rec-modal-progress");
    const delRecResult = $("#delete-rec-modal-result");
    const delRecChkDevice = $("#delete-rec-chk-device");
    const delRecChkLocal = $("#delete-rec-chk-local");
    const delRecChkDb = $("#delete-rec-chk-db");
    let currentDelRecName = null;

    function openDeleteRecModal(name, onDevice, onLocal, inDb) {
        currentDelRecName = name;
        delRecName.textContent = name;
        show(delRecActions);
        hide(delRecProgress);
        hide(delRecResult);

        // Show/hide & pre-check options based on what exists
        const deviceRow = delRecChkDevice.closest(".form-check");
        if (onDevice) {
            show(deviceRow);
            delRecChkDevice.checked = false;
            delRecChkDevice.disabled = false;
        } else {
            hide(deviceRow);
            delRecChkDevice.checked = false;
        }

        const localRow = delRecChkLocal.closest(".form-check");
        if (onLocal) {
            show(localRow);
            delRecChkLocal.checked = true;
            delRecChkLocal.disabled = false;
        } else {
            hide(localRow);
            delRecChkLocal.checked = false;
        }

        const dbRow = delRecChkDb.closest(".form-check");
        if (inDb) {
            show(dbRow);
            delRecChkDb.checked = true;
            delRecChkDb.disabled = false;
        } else {
            hide(dbRow);
            delRecChkDb.checked = false;
        }

        updateDelRecConfirmState();
        show(delRecBackdrop);
    }

    function closeDeleteRecModal() {
        hide(delRecBackdrop);
        currentDelRecName = null;
    }

    function updateDelRecConfirmState() {
        if (delRecConfirm) {
            const anyChecked = delRecChkDevice.checked || delRecChkLocal.checked || delRecChkDb.checked;
            delRecConfirm.disabled = !anyChecked;
        }
    }

    if (delRecClose) delRecClose.addEventListener("click", closeDeleteRecModal);
    if (delRecCancel) delRecCancel.addEventListener("click", closeDeleteRecModal);
    if (delRecBackdrop) {
        delRecBackdrop.addEventListener("click", (e) => {
            if (e.target === delRecBackdrop) closeDeleteRecModal();
        });
    }
    if (delRecChkDevice) delRecChkDevice.addEventListener("change", updateDelRecConfirmState);
    if (delRecChkLocal) delRecChkLocal.addEventListener("change", updateDelRecConfirmState);
    if (delRecChkDb) delRecChkDb.addEventListener("change", updateDelRecConfirmState);

    // Open delete-recording modal on btn-delete-recording click
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".btn-delete-recording");
        if (!btn) return;
        e.preventDefault();
        openDeleteRecModal(
            btn.dataset.name,
            btn.dataset.onDevice === "true",
            btn.dataset.onLocal === "true",
            btn.dataset.inDb === "true",
        );
    });

    // Confirm delete recording
    if (delRecConfirm) {
        delRecConfirm.addEventListener("click", async () => {
            if (!currentDelRecName) return;

            hide(delRecActions);
            show(delRecProgress);
            hide(delRecResult);

            const deleteDevice = delRecChkDevice.checked;
            const deleteLocal = delRecChkLocal.checked;
            const deleteDb = delRecChkDb.checked;

            // --- Step 1: Delete from device via WebUSB (browser-side) ---
            if (deleteDevice && HiDockDevice.isSupported()) {
                try {
                    const devices = await HiDockDevice.getDevices();
                    if (devices.length > 0) {
                        const hidock = devices[0];
                        await hidock.open();
                        try {
                            const hdaName = `${currentDelRecName}.hda`;
                            await hidock.deleteFile(hdaName);
                        } finally {
                            await hidock.close();
                        }
                    }
                } catch (devErr) {
                    console.warn("Device delete failed:", devErr);
                    // Continue with server-side deletion anyway
                }
            }

            // --- Step 2: Delete local / DB via server ---
            if (deleteLocal || deleteDb) {
                const body = {
                    delete_device: false, // Already handled via WebUSB above
                    delete_local: deleteLocal,
                    delete_db: deleteDb,
                };

                try {
                    const res = await fetch(`${DELETE_RECORDING_URL}/${encodeURIComponent(currentDelRecName)}`, {
                        method: "DELETE",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body),
                    });
                    const data = await res.json();

                    hide(delRecProgress);
                    if (data.ok) {
                        let sources = [...(data.deleted || [])];
                        if (deleteDevice) sources.unshift("device");
                        delRecResult.className = "mt-3 alert alert-success";
                        let msg = `<i class="bi bi-check-circle me-1"></i>Deleted '${currentDelRecName}' from: ${sources.join(", ")}`;
                        if (data.warnings && data.warnings.length > 0) {
                            msg += `<br><small class="text-muted">${data.warnings.join("; ")}</small>`;
                        }
                        delRecResult.innerHTML = msg;
                        show(delRecResult);
                        setTimeout(async () => {
                            closeDeleteRecModal();
                            await loadDashboard();
                        }, 1200);
                    } else {
                        delRecResult.className = "mt-3 alert alert-danger";
                        delRecResult.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>${data.error}`;
                        show(delRecResult);
                        show(delRecActions);
                    }
                } catch (err) {
                    hide(delRecProgress);
                    delRecResult.className = "mt-3 alert alert-danger";
                    delRecResult.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>Delete failed: ${err.message}`;
                    show(delRecResult);
                    show(delRecActions);
                }
            } else {
                // Device-only deletion
                hide(delRecProgress);
                delRecResult.className = "mt-3 alert alert-success";
                delRecResult.innerHTML = `<i class="bi bi-check-circle me-1"></i>Deleted '${currentDelRecName}' from device`;
                show(delRecResult);
                setTimeout(async () => {
                    closeDeleteRecModal();
                    await loadDashboard();
                }, 1200);
            }
        });
    }

    // --- Edit recording datetime (inline popover) ---
    let activeDateEditor = null;

    function closeDateEditor() {
        if (activeDateEditor) {
            activeDateEditor.remove();
            activeDateEditor = null;
        }
    }

    document.addEventListener("click", (e) => {
        const dateEl = e.target.closest(".editable-date");
        if (!dateEl) {
            // Close if clicking outside
            if (activeDateEditor && !e.target.closest(".date-editor-popover")) {
                closeDateEditor();
            }
            return;
        }
        e.preventDefault();
        closeDateEditor();

        const name = dateEl.dataset.name;
        const currentRecordedAt = dateEl.dataset.recordedAt || "";

        // Parse existing value into date and time parts for the inputs
        let dateVal = "";
        let timeVal = "";
        if (currentRecordedAt) {
            const parts = currentRecordedAt.split(" ");
            dateVal = parts[0] || "";
            timeVal = (parts[1] || "").substring(0, 5); // HH:MM
        } else {
            // Try to parse from display text
            const text = dateEl.textContent.trim();
            const match = text.match(/(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/);
            if (match) {
                dateVal = match[1];
                timeVal = match[2];
            }
        }

        const popover = document.createElement("div");
        popover.className = "date-editor-popover";
        popover.innerHTML = `
            <div class="date-editor-inner">
                <div class="mb-2">
                    <label class="form-label small mb-1">Date</label>
                    <input type="date" class="form-control form-control-sm" id="date-editor-date" value="${dateVal}">
                </div>
                <div class="mb-2">
                    <label class="form-label small mb-1">Time</label>
                    <input type="time" class="form-control form-control-sm" id="date-editor-time" value="${timeVal}" step="1">
                </div>
                <div class="d-flex gap-2 justify-content-end">
                    <button class="btn btn-sm btn-outline-secondary" id="date-editor-cancel">Cancel</button>
                    <button class="btn btn-sm btn-primary" id="date-editor-save">
                        <i class="bi bi-check-lg"></i> Save
                    </button>
                </div>
                <div id="date-editor-feedback" class="small mt-1 d-none"></div>
            </div>
        `;

        // Position it near the clicked element
        const rect = dateEl.getBoundingClientRect();
        popover.style.position = "fixed";
        popover.style.top = `${rect.bottom + 4}px`;
        popover.style.left = `${rect.left}px`;
        popover.style.zIndex = "9999";
        document.body.appendChild(popover);
        activeDateEditor = popover;

        popover.querySelector("#date-editor-cancel").addEventListener("click", closeDateEditor);

        popover.querySelector("#date-editor-save").addEventListener("click", async () => {
            const newDate = popover.querySelector("#date-editor-date").value;
            const newTime = popover.querySelector("#date-editor-time").value || "00:00";
            const feedback = popover.querySelector("#date-editor-feedback");

            if (!newDate) {
                feedback.className = "small mt-1 text-danger";
                feedback.textContent = "Date is required";
                show(feedback);
                return;
            }

            const recorded_at = `${newDate} ${newTime}`;
            const saveBtn = popover.querySelector("#date-editor-save");
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            try {
                const res = await fetch(`${RECORDING_UPDATE_URL}/${encodeURIComponent(name)}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ recorded_at }),
                });
                const data = await res.json();

                if (data.ok) {
                    closeDateEditor();
                    await loadDashboard();
                } else {
                    feedback.className = "small mt-1 text-danger";
                    feedback.textContent = data.error;
                    show(feedback);
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="bi bi-check-lg"></i> Save';
                }
            } catch (err) {
                feedback.className = "small mt-1 text-danger";
                feedback.textContent = `Failed: ${err.message}`;
                show(feedback);
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="bi bi-check-lg"></i> Save';
            }
        });
    });

    // Close date editor on Escape
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && activeDateEditor) {
            closeDateEditor();
        }
    });
});
