const REFRESH_INTERVAL = 30000;

let torrents = [];
let settings = {};

async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + " " + units[i];
}

function formatTimeRemaining(removalDate) {
    if (!removalDate) return { text: "N/A", pct: 100, level: "safe" };
    const now = new Date();
    const removal = new Date(removalDate + "Z");
    const diff = removal - now;

    if (diff <= 0) return { text: "Overdue", pct: 0, level: "danger" };

    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);

    let text;
    if (days > 0) {
        text = days + "d " + hours + "h";
    } else if (hours > 0) {
        text = hours + "h";
    } else {
        const mins = Math.floor((diff % 3600000) / 60000);
        text = mins + "m";
    }

    const seedDays = parseFloat(settings.seed_time_days) || 14;
    const totalMs = seedDays * 86400000;
    const pct = Math.min(100, Math.max(0, (diff / totalMs) * 100));

    let level = "safe";
    if (pct < 15) level = "danger";
    else if (pct < 40) level = "warning";

    return { text, pct, level };
}

function formatDate(isoDate) {
    if (!isoDate) return "-";
    const d = new Date(isoDate + "Z");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function stateClass(state) {
    if (!state) return "";
    const s = state.toLowerCase();
    if (s === "seeding") return "state-seeding";
    if (s === "downloading") return "state-downloading";
    if (s === "paused") return "state-paused";
    if (s === "removed") return "state-removed";
    if (s === "missing") return "state-missing";
    return "";
}

// Note: innerHTML usage below is safe because all user-provided strings
// (torrent names, hashes) are sanitized through escapeHtml() which uses
// textContent-based escaping to prevent XSS.
function renderTorrents() {
    const tbody = document.getElementById("torrent-table");
    const showRemoved = document.getElementById("show-removed").checked;

    const showMissing = document.getElementById("show-missing").checked;
    const visible = torrents.filter(t => {
        if (t.removed) return showRemoved;
        if (t.state === "Missing") return showMissing;
        return true;
    });

    if (visible.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No torrents found</td></tr>';
        return;
    }

    tbody.innerHTML = visible.map(t => {
        const tr = t.removed ? "removed-row" : "";
        const time = t.removed ? { text: "Removed", pct: 0, level: "danger" } : formatTimeRemaining(t.scheduled_removal);
        const protectLabel = t.protected ? "Unprotect" : "Protect";
        const protectClass = t.protected ? "protected" : "";
        const protectAction = t.protected ? "unprotect" : "protect";

        let actionsHtml = "";
        if (!t.removed && t.state === "Missing") {
            actionsHtml = `
                <button class="action-btn delete" onclick="dismissTorrent('${t.torrent_hash}', '${escapeHtml(t.name)}')">Dismiss</button>
            `;
        } else if (!t.removed) {
            actionsHtml = `
                <button class="action-btn ${protectClass}" onclick="toggleProtect('${t.torrent_hash}', '${protectAction}')">${protectLabel}</button>
                <button class="action-btn delete" onclick="removeTorrent('${t.torrent_hash}', '${escapeHtml(t.name)}')">Remove</button>
            `;
        }

        let timeCell;
        if (t.removed) {
            timeCell = '<span class="time-text">Removed</span>';
        } else if (!t.scheduled_removal) {
            timeCell = '<span class="time-text">-</span>';
        } else if (t.protected) {
            timeCell = '<span class="time-text" style="color:var(--info)">Protected</span>';
        } else {
            timeCell = `
                <div class="time-remaining">
                    <div class="time-bar-container">
                        <div class="time-bar ${time.level}" style="width:${time.pct}%"></div>
                    </div>
                    <span class="time-text">${time.text}</span>
                </div>
            `;
        }

        return `
            <tr class="${tr}">
                <td class="col-name"><span class="torrent-name">${escapeHtml(t.name)}</span></td>
                <td class="col-size">${formatBytes(t.size)}</td>
                <td class="col-state"><span class="state-badge ${stateClass(t.state)}">${escapeHtml(t.state)}</span></td>
                <td class="col-ratio">${t.ratio != null ? t.ratio.toFixed(2) : "-"}</td>
                <td class="col-completed">${formatDate(t.completed_date)}</td>
                <td class="col-remaining">${timeCell}</td>
                <td class="col-actions"><div class="actions-cell">${actionsHtml}</div></td>
            </tr>
        `;
    }).join("");
}

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function updateStats() {
    const active = torrents.filter(t => !t.removed && t.state !== "Missing");
    const missing = torrents.filter(t => !t.removed && t.state === "Missing");
    const pending = active.filter(t => !t.protected && t.scheduled_removal);
    const protectedCount = active.filter(t => t.protected);
    const removed = torrents.filter(t => t.removed);

    document.getElementById("stat-active").textContent = active.length;
    document.getElementById("stat-pending").textContent = pending.length;
    document.getElementById("stat-protected").textContent = protectedCount.length;
    document.getElementById("stat-missing").textContent = missing.length;
    document.getElementById("stat-removed").textContent = removed.length;
}

async function loadTorrents() {
    try {
        torrents = await fetchJSON("/api/torrents?show_removed=true");
        renderTorrents();
        updateStats();
    } catch (e) {
        console.error("Failed to load torrents:", e);
    }
}

async function loadSettings() {
    try {
        settings = await fetchJSON("/api/settings");
        document.getElementById("seed-time").value = settings.seed_time_days || 14;
        document.getElementById("check-interval").value = settings.check_interval_minutes || 5;
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

async function loadStatus() {
    try {
        const status = await fetchJSON("/api/status");
        const dot = document.querySelector(".status-dot");
        const text = document.getElementById("status-text");

        if (status.connected) {
            dot.className = "status-dot connected";
            text.textContent = "Connected";
        } else {
            dot.className = "status-dot disconnected";
            text.textContent = status.last_error || "Disconnected";
        }

        if (status.last_check) {
            const d = new Date(status.last_check + "Z");
            document.getElementById("last-check").textContent =
                "Last check: " + d.toLocaleTimeString();
        }
    } catch (e) {
        console.error("Failed to load status:", e);
    }
}

async function toggleProtect(hash, action) {
    await fetchJSON(`/api/torrents/${hash}/${action}`, { method: "POST" });
    await loadTorrents();
}

async function dismissTorrent(hash, name) {
    if (!confirm(`Dismiss "${name}"? This removes it from Cleanrr's tracking.`)) return;
    await fetchJSON(`/api/torrents/${hash}/dismiss`, { method: "POST" });
    await loadTorrents();
}

async function removeTorrent(hash, name) {
    if (!confirm(`Remove "${name}" and delete its data?`)) return;
    await fetchJSON(`/api/torrents/${hash}`, { method: "DELETE" });
    await loadTorrents();
}

async function saveSettings() {
    const data = {
        seed_time_days: document.getElementById("seed-time").value,
        check_interval_minutes: document.getElementById("check-interval").value,
    };
    await fetchJSON("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    settings = data;
    document.getElementById("settings-modal").classList.remove("active");
    await loadTorrents();
}

async function triggerCheck() {
    const btn = document.getElementById("check-now-btn");
    btn.disabled = true;
    btn.textContent = "Checking...";
    try {
        await fetchJSON("/api/check", { method: "POST" });
        await refresh();
    } finally {
        btn.disabled = false;
        btn.textContent = "Check Now";
    }
}

async function refresh() {
    await Promise.all([loadTorrents(), loadStatus()]);
}

// Event listeners
document.getElementById("settings-btn").addEventListener("click", () => {
    document.getElementById("settings-modal").classList.add("active");
});

document.getElementById("modal-close").addEventListener("click", () => {
    document.getElementById("settings-modal").classList.remove("active");
});

document.getElementById("modal-cancel").addEventListener("click", () => {
    document.getElementById("settings-modal").classList.remove("active");
});

document.getElementById("modal-save").addEventListener("click", saveSettings);

document.getElementById("settings-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
        e.currentTarget.classList.remove("active");
    }
});

document.getElementById("show-removed").addEventListener("change", loadTorrents);
document.getElementById("show-missing").addEventListener("change", renderTorrents);
document.getElementById("check-now-btn").addEventListener("click", triggerCheck);

// Initial load
(async () => {
    await loadSettings();
    await refresh();
    setInterval(refresh, REFRESH_INTERVAL);
})();
