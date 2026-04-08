/**
 * AgenDino Calendar JS
 * Monthly calendar with day detail, event CRUD, and daily recap.
 */

const CAL_API = "/api/calendar";

const $ = (sel) => document.querySelector(sel);
const show = (el) => { if (el) el.style.display = ""; el?.classList.remove("d-none"); };
const hide = (el) => { if (el) el.classList.add("d-none"); };

const MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
];

let currentYear, currentMonth;
let selectedDate = null;
let monthEvents = [];
let recapDates = [];  // date strings that have stored recaps
let monthRecordings = {};  // date_str → recording count (fetched per-day lazily)
let editingEventId = null;
let sharedCalendars = [];  // shared calendar objects from API
let editingCalendarId = null;
let dayRecordings = [];  // current day's recordings
let daySummaries = [];   // current day's summaries
let dayEvents = [];      // current day's events

function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function pad(n) { return String(n).padStart(2, "0"); }

function dateStr(y, m, d) { return `${y}-${pad(m)}-${pad(d)}`; }

function timeFromISO(isoStr) {
    if (!isoStr) return "";
    // isoStr could be "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS"
    const parts = isoStr.replace("T", " ").split(" ");
    if (parts.length < 2) return "";
    return parts[1].substring(0, 5);  // HH:MM
}

function escapeHtml(text) {
    return (text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatMarkdown(text) {
    return (text || "")
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

// ─── Month calendar ────────────────────────────────────────────

function eventsForDate(ds) {
    return monthEvents.filter(ev => {
        const startDate = ev.start_at.substring(0, 10);
        const endDate = ev.end_at.substring(0, 10);
        return ds >= startDate && ds <= endDate;
    });
}

function renderCalendar() {
    const body = $("#cal-body");
    body.innerHTML = "";

    // Determine first day of month and how many days
    const firstDay = new Date(currentYear, currentMonth - 1, 1);
    const lastDay = new Date(currentYear, currentMonth, 0);
    const daysInMonth = lastDay.getDate();
    const startWeekday = (firstDay.getDay() + 6) % 7; // Monday = 0

    // Previous month fill
    const prevLast = new Date(currentYear, currentMonth - 1, 0);
    const prevDays = prevLast.getDate();
    const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1;
    const prevYear = currentMonth === 1 ? currentYear - 1 : currentYear;
    for (let i = startWeekday - 1; i >= 0; i--) {
        const d = prevDays - i;
        const ds = dateStr(prevYear, prevMonth, d);
        body.appendChild(createDayCell(ds, d, true));
    }

    // Current month
    const today = todayStr();
    for (let d = 1; d <= daysInMonth; d++) {
        const ds = dateStr(currentYear, currentMonth, d);
        const cell = createDayCell(ds, d, false);
        if (ds === today) cell.classList.add("cal-today");
        if (ds === selectedDate) cell.classList.add("cal-selected");
        body.appendChild(cell);
    }

    // Next month fill
    const totalCells = startWeekday + daysInMonth;
    const remaining = (7 - (totalCells % 7)) % 7;
    const nextMonth = currentMonth === 12 ? 1 : currentMonth + 1;
    const nextYear = currentMonth === 12 ? currentYear + 1 : currentYear;
    for (let d = 1; d <= remaining; d++) {
        const ds = dateStr(nextYear, nextMonth, d);
        body.appendChild(createDayCell(ds, d, true));
    }

    $("#month-title").textContent = `${MONTH_NAMES[currentMonth - 1]} ${currentYear}`;
}

function createDayCell(ds, dayNum, isOther) {
    const div = document.createElement("div");
    div.className = `cal-day${isOther ? " cal-other-month" : ""}`;
    div.dataset.date = ds;

    const dayEvents = eventsForDate(ds);

    let chips = "";
    for (const ev of dayEvents.slice(0, 3)) {
        const t = timeFromISO(ev.start_at);
        const colorStyle = ev.calendar_color ? `border-left:3px solid ${ev.calendar_color};` : "";
        const cancelled = ev.status === "cancelled";
        const titleHtml = cancelled ? `<s>${t ? t + " " : ""}${escapeHtml(ev.title)}</s>` : `${t ? t + " " : ""}${escapeHtml(ev.title)}`;
        chips += `<span class="cal-event-chip${cancelled ? " cal-event-cancelled" : ""}" style="${colorStyle}">${titleHtml}</span>`;
    }
    if (dayEvents.length > 3) {
        chips += `<span class="cal-event-chip" style="background:transparent;color:var(--bs-secondary-color)">+${dayEvents.length - 3} more</span>`;
    }

    // Dots for summary/recording
    let dots = "";
    if (dayEvents.length > 0) dots += '<span class="cal-day-dot cal-dot-event"></span>';
    if (recapDates.includes(ds)) dots += '<span class="cal-day-dot cal-dot-recap" title="Has daily recap"></span>';

    div.innerHTML = `
        <div class="cal-day-number">${dayNum}${dots ? " " + dots : ""}</div>
        <div class="cal-day-events">${chips}</div>
    `;

    div.addEventListener("click", () => {
        // Remove old selection
        document.querySelectorAll(".cal-day.cal-selected").forEach(el => el.classList.remove("cal-selected"));
        div.classList.add("cal-selected");
        selectedDate = ds;
        loadDayDetail(ds);
    });

    return div;
}

async function loadMonth(year, month) {
    currentYear = year;
    currentMonth = month;

    try {
        const res = await fetch(`${CAL_API}/month/${year}/${month}`);
        const data = await res.json();
        monthEvents = data.ok ? data.events : [];
        recapDates = data.ok ? (data.recap_dates || []) : [];
        sharedCalendars = data.ok ? (data.shared_calendars || []) : [];
    } catch {
        monthEvents = [];
        recapDates = [];
        sharedCalendars = [];
    }
    renderCalendar();
    renderCalendarLegend();
}

// ─── Day detail ────────────────────────────────────────────────

async function loadDayDetail(ds) {
    const row = $("#day-detail-row");
    row.style.display = "";
    show($("#day-detail-loading"));
    hide($("#day-detail-content"));
    $("#day-detail-title").textContent = ds;

    // Hide the standalone recap panel when loading a new day
    $("#recap-row").style.display = "none";

    // Hide the detail viewer when loading a new day
    $("#detail-viewer-row").style.display = "none";

    try {
        const res = await fetch(`${CAL_API}/day-detail/${ds}`);
        const data = await res.json();

        hide($("#day-detail-loading"));
        if (!data.ok) return;

        dayEvents = data.events || [];
        dayRecordings = data.recordings || [];
        daySummaries = data.summaries || [];

        renderDayEvents(dayEvents);
        renderDayRecordings(dayRecordings);
        renderDaySummaries(daySummaries);
        renderStoredRecap(data.recap);
        updateRecapButton(data.recap);
        show($("#day-detail-content"));
    } catch (err) {
        hide($("#day-detail-loading"));
        $("#day-events-list").innerHTML = `<div class="alert alert-danger">Failed to load: ${err.message}</div>`;
        show($("#day-detail-content"));
    }
}

function renderDayEvents(events) {
    const container = $("#day-events-list");
    if (events.length === 0) {
        container.innerHTML = '<div class="empty-day-message">No events</div>';
        return;
    }
    container.innerHTML = events.map(ev => {
        const start = timeFromISO(ev.start_at);
        const end = timeFromISO(ev.end_at);
        const timeRange = start && end ? `${start} – ${end}` : "";
        const desc = ev.description ? `<div class="event-desc">${escapeHtml(ev.description)}</div>` : "";
        const location = ev.location ? `<small class="text-muted"><i class="bi bi-geo-alt me-1"></i>${escapeHtml(ev.location)}</small>` : "";
        const meetingUrl = ev.meeting_url ? `<a href="${escapeHtml(ev.meeting_url)}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="bi bi-camera-video me-1"></i>Join</a>` : "";

        // Linked recordings — show as expandable cards
        const linkedRecs = (ev.linked_recordings || []).map(lr => {
            const preview = lr.summary_text ? escapeHtml(lr.summary_text.substring(0, 120).replace(/\n/g, " ")) + (lr.summary_text.length > 120 ? "…" : "") : "";
            const tags = (lr.summary_tags || []).map(t =>
                `<span class="badge bg-secondary bg-opacity-25 text-body me-1" style="font-size:.7em">${escapeHtml(t)}</span>`
            ).join("");
            const summaryTitle = lr.summary_title ? escapeHtml(lr.summary_title) : "";
            const viewBtn = lr.has_summary
                ? `<button class="btn btn-sm btn-outline-info btn-view-linked-summary" data-recording-name="${escapeHtml(lr.name)}" title="View summary"><i class="bi bi-eye"></i></button>`
                : "";
            return `<div class="linked-rec-card">
                <div class="d-flex justify-content-between align-items-start">
                    <div style="min-width:0;flex:1">
                        <span class="badge bg-success-subtle text-success-emphasis me-1"><i class="bi bi-mic me-1"></i>${escapeHtml(lr.name)}</span>
                        <span class="badge bg-secondary-subtle text-secondary-emphasis" style="font-size:.65em">${lr.link_source}</span>
                        ${summaryTitle ? `<div class="linked-rec-title mt-1">${summaryTitle}</div>` : ""}
                        ${tags ? `<div class="mt-1">${tags}</div>` : ""}
                        ${preview ? `<div class="linked-rec-preview">${preview}</div>` : ""}
                    </div>
                    <div class="d-flex gap-1 ms-2 flex-shrink-0">
                        ${viewBtn}
                        <button class="btn btn-sm btn-outline-danger btn-unlink-rec" data-recording-id="${lr.recording_id}" data-event-id="${ev.id}" title="Unlink"><i class="bi bi-x-circle"></i></button>
                    </div>
                </div>
            </div>`;
        }).join("");

        const borderColor = ev.calendar_color ? `border-left:3px solid ${ev.calendar_color};` : "";
        const isShared = ev.shared_calendar_id != null;
        const isCancelled = ev.status === "cancelled";
        const isTentative = ev.status === "tentative";
        const statusBadge = isCancelled
            ? '<span class="badge bg-danger-subtle text-danger me-1"><i class="bi bi-x-circle me-1"></i>Cancelled</span>'
            : isTentative
                ? '<span class="badge bg-warning-subtle text-warning me-1"><i class="bi bi-question-circle me-1"></i>Tentative</span>'
                : "";
        const titleHtml = isCancelled
            ? `<s class="text-muted">${escapeHtml(ev.title)}</s>`
            : escapeHtml(ev.title);
        const calBadge = isShared ? (() => {
            const sc = sharedCalendars.find(c => c.id === ev.shared_calendar_id);
            return sc ? `<span class="badge me-1" style="background:${sc.color}22;color:${sc.color};border:1px solid ${sc.color}44"><i class="bi bi-cloud me-1"></i>${escapeHtml(sc.name)}</span>` : "";
        })() : "";

        return `<div class="day-event-card${isCancelled ? " day-event-cancelled" : ""}" data-event-id="${ev.id}" style="${borderColor}${isCancelled ? "opacity:.65;" : ""}">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <span class="event-time">${timeRange}</span>${calBadge}${statusBadge}
                    <div class="event-title">${titleHtml}</div>
                    ${desc}
                    ${location}
                </div>
                <div class="event-actions">
                    ${meetingUrl}
                    <button class="btn btn-sm btn-outline-success btn-link-rec" data-event-id="${ev.id}" title="Link recording">
                        <i class="bi bi-link-45deg"></i>
                    </button>
                    ${!isShared ? `<button class="btn btn-sm btn-outline-secondary btn-edit-event" data-event-id="${ev.id}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger btn-delete-event" data-event-id="${ev.id}" title="Delete">
                        <i class="bi bi-trash3"></i>
                    </button>` : ""}
                </div>
            </div>
            ${linkedRecs ? `<div class="linked-recs-section mt-2">${linkedRecs}</div>` : ""}
        </div>`;
    }).join("");
}

function renderDayRecordings(recordings) {
    const container = $("#day-recordings-list");
    if (recordings.length === 0) {
        container.innerHTML = '<div class="empty-day-message">No recordings</div>';
        return;
    }
    container.innerHTML = recordings.map(rec => {
        const badges = [];
        if (rec.has_transcript) badges.push('<span class="badge bg-success-subtle text-success-emphasis">Transcript</span>');
        if (rec.has_summary) badges.push('<span class="badge bg-info-subtle text-info-emphasis">Summary</span>');
        const title = rec.summary_title ? ` — ${escapeHtml(rec.summary_title)}` : "";
        const tags = (rec.summary_tags || []).map(t =>
            `<span class="badge bg-secondary bg-opacity-25 text-body me-1">${escapeHtml(t)}</span>`
        ).join("");

        const viewBtn = rec.has_summary
            ? `<button class="btn btn-sm btn-outline-info btn-view-rec-summary" data-recording-name="${escapeHtml(rec.name)}" title="View summary"><i class="bi bi-eye me-1"></i>View</button>`
            : "";

        return `<div class="day-recording-card ${rec.has_summary ? "day-recording-clickable" : ""}" data-recording-name="${escapeHtml(rec.name)}">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <span class="rec-name">${escapeHtml(rec.name)}</span>${title}
                    <div class="rec-meta">${badges.join(" ")} ${tags}</div>
                </div>
                <div class="d-flex gap-1">
                    ${viewBtn}
                </div>
            </div>
        </div>`;
    }).join("");
}

function renderDaySummaries(summaries) {
    const container = $("#day-summaries-list");
    if (summaries.length === 0) {
        container.innerHTML = '<div class="empty-day-message">No summaries</div>';
        return;
    }
    container.innerHTML = summaries.map(s => {
        const tags = (s.tags || []).filter(t => t).map(t =>
            `<span class="badge bg-secondary bg-opacity-25 text-body me-1">${escapeHtml(t)}</span>`
        ).join("");
        const preview = (s.summary || "").substring(0, 200).replace(/\n/g, " ");

        return `<div class="day-summary-card day-summary-clickable" data-recording-name="${escapeHtml(s.recording_name)}">
            <div class="d-flex justify-content-between align-items-start">
                <div style="min-width:0;flex:1">
                    <div class="summary-title">${escapeHtml(s.title || s.recording_name)}</div>
                    <div class="summary-tags">${tags}</div>
                    <div class="summary-preview">${escapeHtml(preview)}${(s.summary || "").length > 200 ? "…" : ""}</div>
                </div>
                <button class="btn btn-sm btn-outline-info btn-view-summary ms-2 flex-shrink-0" data-recording-name="${escapeHtml(s.recording_name)}" title="View full summary">
                    <i class="bi bi-eye me-1"></i>Read
                </button>
            </div>
        </div>`;
    }).join("");
}

// ─── Event CRUD ────────────────────────────────────────────────

const eventBackdrop = $("#event-modal-backdrop");
const eventForm = $("#event-form");
const eventModalTitle = $("#event-modal-title");
const eventFormError = $("#event-form-error");

function openEventModal(date, event) {
    editingEventId = event ? event.id : null;
    eventModalTitle.textContent = event ? "Edit Event" : "Add Event";
    hide(eventFormError);

    if (event) {
        $("#event-title").value = event.title || "";
        $("#event-start").value = (event.start_at || "").replace(" ", "T").substring(0, 16);
        $("#event-end").value = (event.end_at || "").replace(" ", "T").substring(0, 16);
        $("#event-description").value = event.description || "";
        $("#event-location").value = event.location || "";
        $("#event-meeting-url").value = event.meeting_url || "";
        $("#event-all-day").checked = event.is_all_day || false;
    } else {
        eventForm.reset();
        if (date) {
            $("#event-start").value = `${date}T09:00`;
            $("#event-end").value = `${date}T10:00`;
        }
    }
    show(eventBackdrop);
}

function closeEventModal() {
    hide(eventBackdrop);
    editingEventId = null;
}

if ($("#event-modal-close")) $("#event-modal-close").addEventListener("click", closeEventModal);
if ($("#event-cancel-btn")) $("#event-cancel-btn").addEventListener("click", closeEventModal);
if (eventBackdrop) eventBackdrop.addEventListener("click", (e) => { if (e.target === eventBackdrop) closeEventModal(); });

if (eventForm) {
    eventForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        hide(eventFormError);

        const body = {
            title: $("#event-title").value.trim(),
            start_at: $("#event-start").value.replace("T", " ") + ":00",
            end_at: $("#event-end").value.replace("T", " ") + ":00",
            description: $("#event-description").value.trim() || null,
            location: $("#event-location").value.trim() || null,
            meeting_url: $("#event-meeting-url").value.trim() || null,
            is_all_day: $("#event-all-day").checked,
        };

        const saveBtn = $("#event-save-btn");
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        try {
            let url, method;
            if (editingEventId) {
                url = `${CAL_API}/events/${editingEventId}`;
                method = "PATCH";
            } else {
                url = `${CAL_API}/events`;
                method = "POST";
            }

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (data.ok) {
                closeEventModal();
                await loadMonth(currentYear, currentMonth);
                if (selectedDate) await loadDayDetail(selectedDate);
            } else {
                eventFormError.textContent = data.error || "Failed to save event";
                show(eventFormError);
            }
        } catch (err) {
            eventFormError.textContent = `Error: ${err.message}`;
            show(eventFormError);
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Save';
        }
    });
}

// Edit event
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-edit-event");
    if (!btn) return;
    e.preventDefault();
    const eventId = parseInt(btn.dataset.eventId, 10);
    const ev = monthEvents.find(ev => ev.id === eventId);
    if (ev) openEventModal(null, ev);
});

// Delete event
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-delete-event");
    if (!btn) return;
    e.preventDefault();
    const eventId = parseInt(btn.dataset.eventId, 10);
    if (!confirm("Delete this event?")) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
        const res = await fetch(`${CAL_API}/events/${eventId}`, { method: "DELETE" });
        const data = await res.json();
        if (data.ok) {
            await loadMonth(currentYear, currentMonth);
            if (selectedDate) await loadDayDetail(selectedDate);
        }
    } catch (err) {
        console.error("Failed to delete event:", err);
    }
});

// ─── Daily Recap ───────────────────────────────────────────────

function renderRecapHtml(recap) {
    let html = "";

    if (recap.title) {
        html += `<h4>${escapeHtml(recap.title)}</h4>`;
    }

    if (recap.highlights && recap.highlights.length > 0) {
        html += `<h6 class="text-muted text-uppercase small fw-bold mt-3 mb-2"><i class="bi bi-star me-1"></i>Highlights</h6>`;
        html += `<ul class="recap-highlights">`;
        for (const h of recap.highlights) {
            html += `<li>${escapeHtml(h)}</li>`;
        }
        html += `</ul>`;
    }

    if (recap.recap) {
        html += `<h6 class="text-muted text-uppercase small fw-bold mt-3 mb-2"><i class="bi bi-journal-text me-1"></i>Full Recap</h6>`;
        html += `<div class="summary-content">${formatMarkdown(recap.recap)}</div>`;
    }

    if (recap.action_items && recap.action_items.length > 0) {
        html += `<h6 class="text-muted text-uppercase small fw-bold mt-3 mb-2"><i class="bi bi-check2-square me-1"></i>Action Items</h6>`;
        html += `<ul class="recap-action-items">`;
        for (const a of recap.action_items) {
            html += `<li>${escapeHtml(a)}</li>`;
        }
        html += `</ul>`;
    }

    if (recap.blockers && recap.blockers.length > 0) {
        html += `<h6 class="text-muted text-uppercase small fw-bold mt-3 mb-2"><i class="bi bi-exclamation-triangle me-1"></i>Blockers</h6>`;
        html += `<ul class="recap-blockers">`;
        for (const b of recap.blockers) {
            html += `<li>${escapeHtml(b)}</li>`;
        }
        html += `</ul>`;
    }

    if (!html) {
        html = '<div class="text-muted text-center p-3">No recap content generated.</div>';
    }

    return html;
}

function renderStoredRecap(recap) {
    const section = $("#day-stored-recap");
    const content = $("#day-recap-content");
    const updatedAt = $("#recap-updated-at");

    if (!recap) {
        hide(section);
        return;
    }

    content.innerHTML = renderRecapHtml(recap);
    if (recap.updated_at) {
        const dt = recap.updated_at.replace("T", " ").substring(0, 16);
        updatedAt.textContent = `Updated ${dt}`;
    } else {
        updatedAt.textContent = "";
    }
    show(section);
}

function updateRecapButton(recap) {
    const btn = $("#btn-daily-recap");
    if (!btn) return;
    if (recap) {
        btn.innerHTML = '<i class="bi bi-stars me-1"></i>Regenerate Recap';
        btn.classList.remove("btn-outline-warning");
        btn.classList.add("btn-outline-secondary");
    } else {
        btn.innerHTML = '<i class="bi bi-stars me-1"></i>Daily Recap';
        btn.classList.remove("btn-outline-secondary");
        btn.classList.add("btn-outline-warning");
    }
}

async function generateRecap(ds) {
    const row = $("#recap-row");
    row.style.display = "";
    show($("#recap-loading"));
    hide($("#recap-content"));
    hide($("#recap-error"));
    $("#recap-date").textContent = ds;

    try {
        const res = await fetch(`${CAL_API}/recap/${ds}`, { method: "POST" });
        const data = await res.json();

        hide($("#recap-loading"));
        if (!data.ok) {
            $("#recap-error").textContent = data.error;
            show($("#recap-error"));
            return;
        }

        const recap = data.recap || {};
        $("#recap-content").innerHTML = renderRecapHtml(recap);
        show($("#recap-content"));

        // Also refresh inline stored recap and month dots
        renderStoredRecap(recap);
        updateRecapButton(recap);
        await loadMonth(currentYear, currentMonth);
    } catch (err) {
        hide($("#recap-loading"));
        $("#recap-error").textContent = `Recap generation failed: ${err.message}`;
        show($("#recap-error"));
    }
}

async function deleteRecap(ds) {
    if (!confirm("Delete the stored daily recap?")) return;

    try {
        const res = await fetch(`${CAL_API}/recap/${ds}`, { method: "DELETE" });
        const data = await res.json();
        if (data.ok) {
            renderStoredRecap(null);
            updateRecapButton(null);
            $("#recap-row").style.display = "none";
            await loadMonth(currentYear, currentMonth);
        }
    } catch (err) {
        console.error("Failed to delete recap:", err);
    }
}

// ─── Shared Calendars ──────────────────────────────────────────

function renderCalendarLegend() {
    const container = $("#shared-cal-legend");
    const items = $("#shared-cal-legend-items");
    if (!container || !items) return;

    if (sharedCalendars.length === 0) {
        hide(container);
        return;
    }

    let html = '<small class="text-muted fw-bold me-1"><i class="bi bi-circle-fill me-1" style="color:var(--bs-primary);font-size:.5rem"></i>Local</small>';
    for (const cal of sharedCalendars) {
        if (!cal.is_enabled) continue;
        html += `<small class="text-muted fw-bold me-1"><i class="bi bi-circle-fill me-1" style="color:${escapeHtml(cal.color)};font-size:.5rem"></i>${escapeHtml(cal.name)}</small>`;
    }
    items.innerHTML = html;
    show(container);
}

function renderSharedCalendarPanel() {
    const list = $("#shared-cal-list");
    if (!list) return;

    if (sharedCalendars.length === 0) {
        list.innerHTML = '<div class="text-center text-muted p-3">No shared calendars configured.</div>';
        return;
    }

    list.innerHTML = sharedCalendars.map(cal => {
        const statusIcon = cal.last_error
            ? `<span class="badge bg-danger-subtle text-danger" title="${escapeHtml(cal.last_error)}"><i class="bi bi-exclamation-triangle me-1"></i>Error</span>`
            : cal.last_synced_at
                ? `<span class="badge bg-success-subtle text-success"><i class="bi bi-check-circle me-1"></i>Synced</span>`
                : `<span class="badge bg-secondary-subtle text-secondary">Not synced</span>`;
        const lastSync = cal.last_synced_at ? `<small class="text-muted">Last: ${cal.last_synced_at.replace("T", " ").substring(0, 16)}</small>` : "";
        const enabledClass = cal.is_enabled ? "" : "opacity-50";

        return `<div class="shared-cal-item ${enabledClass}">
            <div class="d-flex justify-content-between align-items-center">
                <div class="d-flex align-items-center gap-2">
                    <span class="shared-cal-dot" style="background:${escapeHtml(cal.color)}"></span>
                    <div>
                        <div class="fw-bold">${escapeHtml(cal.name)}</div>
                        <div class="d-flex gap-2 align-items-center">
                            ${statusIcon}
                            <small class="text-muted">${cal.event_count || 0} events</small>
                            ${lastSync}
                        </div>
                    </div>
                </div>
                <div class="d-flex gap-1">
                    <button class="btn btn-sm btn-outline-success btn-sync-cal" data-cal-id="${cal.id}" title="Sync now">
                        <i class="bi bi-arrow-repeat"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-secondary btn-edit-cal" data-cal-id="${cal.id}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger btn-delete-cal" data-cal-id="${cal.id}" title="Delete">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </div>
        </div>`;
    }).join("");
}

function openSharedCalModal(cal) {
    editingCalendarId = cal ? cal.id : null;
    const title = $("#shared-cal-modal-title");
    title.textContent = cal ? "Edit Shared Calendar" : "Add Shared Calendar";
    hide($("#shared-cal-form-error"));
    hide($("#shared-cal-form-info"));

    if (cal) {
        $("#shared-cal-name").value = cal.name || "";
        $("#shared-cal-url").value = cal.ical_url || "";
        $("#shared-cal-color").value = cal.color || "#0d6efd";
        $("#shared-cal-enabled").checked = cal.is_enabled !== false;
        $("#shared-cal-interval").value = cal.sync_interval_minutes || 30;
    } else {
        $("#shared-cal-form").reset();
        $("#shared-cal-color").value = "#0d6efd";
        $("#shared-cal-enabled").checked = true;
        $("#shared-cal-interval").value = 30;
    }
    show($("#shared-cal-modal-backdrop"));
}

function closeSharedCalModal() {
    hide($("#shared-cal-modal-backdrop"));
    editingCalendarId = null;
}

// Shared cal modal events
if ($("#shared-cal-modal-close")) $("#shared-cal-modal-close").addEventListener("click", closeSharedCalModal);
if ($("#shared-cal-cancel-btn")) $("#shared-cal-cancel-btn").addEventListener("click", closeSharedCalModal);
if ($("#shared-cal-modal-backdrop")) {
    $("#shared-cal-modal-backdrop").addEventListener("click", (e) => {
        if (e.target === $("#shared-cal-modal-backdrop")) closeSharedCalModal();
    });
}

// Shared cal form submit
if ($("#shared-cal-form")) {
    $("#shared-cal-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        hide($("#shared-cal-form-error"));
        hide($("#shared-cal-form-info"));

        const body = {
            name: $("#shared-cal-name").value.trim(),
            ical_url: $("#shared-cal-url").value.trim(),
            color: $("#shared-cal-color").value,
            is_enabled: $("#shared-cal-enabled").checked,
            sync_interval_minutes: parseInt($("#shared-cal-interval").value, 10) || 30,
        };

        const saveBtn = $("#shared-cal-save-btn");
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving…';

        try {
            let url, method;
            if (editingCalendarId) {
                url = `${CAL_API}/shared/${editingCalendarId}`;
                method = "PATCH";
            } else {
                url = `${CAL_API}/shared`;
                method = "POST";
            }

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (data.ok) {
                closeSharedCalModal();
                await loadMonth(currentYear, currentMonth);
                await refreshSharedCalPanel();
            } else {
                const errEl = $("#shared-cal-form-error");
                errEl.textContent = data.error || "Failed to save calendar";
                show(errEl);
            }
        } catch (err) {
            const errEl = $("#shared-cal-form-error");
            errEl.textContent = `Error: ${err.message}`;
            show(errEl);
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Save & Sync';
        }
    });
}

async function refreshSharedCalPanel() {
    try {
        const res = await fetch(`${CAL_API}/shared`);
        const data = await res.json();
        if (data.ok) {
            sharedCalendars = data.calendars || [];
            renderSharedCalendarPanel();
            renderCalendarLegend();
        }
    } catch {
        // ignore
    }
}

// Sync single calendar
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-sync-cal");
    if (!btn) return;
    e.preventDefault();
    const calId = parseInt(btn.dataset.calId, 10);
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
        const res = await fetch(`${CAL_API}/shared/${calId}/sync`, { method: "POST" });
        await res.json();
        await loadMonth(currentYear, currentMonth);
        await refreshSharedCalPanel();
        if (selectedDate) await loadDayDetail(selectedDate);
    } catch (err) {
        console.error("Sync failed:", err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-repeat"></i>';
    }
});

// Edit calendar
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-edit-cal");
    if (!btn) return;
    e.preventDefault();
    const calId = parseInt(btn.dataset.calId, 10);
    const cal = sharedCalendars.find(c => c.id === calId);
    if (cal) openSharedCalModal(cal);
});

// Delete calendar
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-delete-cal");
    if (!btn) return;
    e.preventDefault();
    const calId = parseInt(btn.dataset.calId, 10);
    const cal = sharedCalendars.find(c => c.id === calId);
    const name = cal ? cal.name : "this calendar";
    if (!confirm(`Delete "${name}" and all its synced events?`)) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
        const res = await fetch(`${CAL_API}/shared/${calId}`, { method: "DELETE" });
        const data = await res.json();
        if (data.ok) {
            await loadMonth(currentYear, currentMonth);
            await refreshSharedCalPanel();
            if (selectedDate) await loadDayDetail(selectedDate);
        }
    } catch (err) {
        console.error("Delete failed:", err);
    }
});

// ─── Link / Unlink Recordings ──────────────────────────────────

// Show link-recording dropdown when clicking the link button on an event
document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-link-rec");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const eventId = parseInt(btn.dataset.eventId, 10);
    const ev = dayEvents.find(ev => ev.id === eventId);
    if (!ev) return;

    // Remove any existing dropdown
    document.querySelectorAll(".link-rec-dropdown").forEach(el => el.remove());

    // Determine which recordings are not yet linked to this event
    const linkedIds = new Set((ev.linked_recordings || []).map(lr => lr.recording_id));
    const available = dayRecordings.filter(r => !linkedIds.has(r.recording_id));

    if (available.length === 0) {
        // Nothing to link
        const dd = document.createElement("div");
        dd.className = "link-rec-dropdown";
        dd.innerHTML = '<div class="link-rec-empty">No unlinked recordings for this day</div>';
        btn.parentElement.style.position = "relative";
        btn.parentElement.appendChild(dd);
        setTimeout(() => dd.remove(), 2500);
        return;
    }

    const dd = document.createElement("div");
    dd.className = "link-rec-dropdown";
    dd.innerHTML = `<div class="link-rec-header">Link a recording</div>` +
        available.map(r => {
            const t = r.summary_title ? ` — ${escapeHtml(r.summary_title)}` : "";
            return `<div class="link-rec-item" data-recording-id="${r.recording_id}" data-event-id="${eventId}">
                <i class="bi bi-mic me-1 text-success"></i>${escapeHtml(r.name)}${t}
            </div>`;
        }).join("");

    btn.parentElement.style.position = "relative";
    btn.parentElement.appendChild(dd);

    // Close dropdown on outside click
    const closeDropdown = (ev2) => {
        if (!dd.contains(ev2.target) && ev2.target !== btn) {
            dd.remove();
            document.removeEventListener("click", closeDropdown);
        }
    };
    setTimeout(() => document.addEventListener("click", closeDropdown), 10);
});

// Handle clicking a recording in the link dropdown
document.addEventListener("click", async (e) => {
    const item = e.target.closest(".link-rec-item");
    if (!item) return;
    e.preventDefault();
    const recordingId = parseInt(item.dataset.recordingId, 10);
    const eventId = parseInt(item.dataset.eventId, 10);

    item.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Linking…';

    try {
        const res = await fetch(`${CAL_API}/link`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ recording_id: recordingId, event_id: eventId }),
        });
        const data = await res.json();
        if (data.ok) {
            // Remove dropdown and refresh day detail
            document.querySelectorAll(".link-rec-dropdown").forEach(el => el.remove());
            if (selectedDate) await loadDayDetail(selectedDate);
        }
    } catch (err) {
        console.error("Failed to link recording:", err);
    }
});

// Unlink recording from event
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-unlink-rec");
    if (!btn) return;
    e.preventDefault();
    const recordingId = parseInt(btn.dataset.recordingId, 10);
    const eventId = parseInt(btn.dataset.eventId, 10);

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
        const res = await fetch(`${CAL_API}/link`, {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ recording_id: recordingId, event_id: eventId }),
        });
        const data = await res.json();
        if (data.ok && selectedDate) {
            await loadDayDetail(selectedDate);
        }
    } catch (err) {
        console.error("Failed to unlink recording:", err);
    }
});

// ─── Detail Viewer (view summary / recording inline) ───────────

function openDetailViewer(title, recordingName, tags, summaryHtml) {
    const row = $("#detail-viewer-row");
    row.style.display = "";
    $("#detail-viewer-title").textContent = title || "Summary";
    $("#detail-viewer-rec-name").textContent = recordingName || "";
    const tagsHtml = (tags || []).filter(t => t).map(t =>
        `<span class="badge bg-secondary bg-opacity-25 text-body me-1">${escapeHtml(t)}</span>`
    ).join("");
    $("#detail-viewer-tags").innerHTML = tagsHtml;
    $("#detail-viewer-content").innerHTML = summaryHtml;
    row.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeDetailViewer() {
    $("#detail-viewer-row").style.display = "none";
}

// View summary from summary card
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-view-summary") || e.target.closest(".day-summary-clickable");
    if (!btn) return;
    e.preventDefault();
    const recName = btn.dataset.recordingName;
    if (!recName) return;

    // Find summary in cached day summaries
    const s = daySummaries.find(s => s.recording_name === recName);
    if (s && s.summary) {
        openDetailViewer(s.title || s.recording_name, s.recording_name, s.tags, formatMarkdown(s.summary));
        return;
    }

    // Fallback: fetch from API
    try {
        const res = await fetch(`/api/dashboard/summary/${encodeURIComponent(recName)}`);
        const data = await res.json();
        if (data.ok && data.summaries && data.summaries.length > 0) {
            const latest = data.summaries[0];
            openDetailViewer(latest.title || recName, recName, latest.tags, formatMarkdown(latest.summary));
        }
    } catch (err) {
        console.error("Failed to load summary:", err);
    }
});

// View summary from recording card
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-view-rec-summary");
    if (!btn) return;
    e.preventDefault();
    const recName = btn.dataset.recordingName;
    if (!recName) return;

    // Find in day summaries
    const s = daySummaries.find(s => s.recording_name === recName);
    if (s && s.summary) {
        openDetailViewer(s.title || s.recording_name, s.recording_name, s.tags, formatMarkdown(s.summary));
        return;
    }

    // Fallback: fetch from API
    try {
        const res = await fetch(`/api/dashboard/summary/${encodeURIComponent(recName)}`);
        const data = await res.json();
        if (data.ok && data.summaries && data.summaries.length > 0) {
            const latest = data.summaries[0];
            openDetailViewer(latest.title || recName, recName, latest.tags, formatMarkdown(latest.summary));
        }
    } catch (err) {
        console.error("Failed to load summary:", err);
    }
});

// View summary from linked recording inside an event card
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-view-linked-summary");
    if (!btn) return;
    e.preventDefault();
    const recName = btn.dataset.recordingName;
    if (!recName) return;

    // Search linked recordings in day events
    for (const ev of dayEvents) {
        for (const lr of (ev.linked_recordings || [])) {
            if (lr.name === recName && lr.summary_text) {
                openDetailViewer(lr.summary_title || lr.name, lr.name, lr.summary_tags, formatMarkdown(lr.summary_text));
                return;
            }
        }
    }

    // Fallback: fetch from API
    try {
        const res = await fetch(`/api/dashboard/summary/${encodeURIComponent(recName)}`);
        const data = await res.json();
        if (data.ok && data.summaries && data.summaries.length > 0) {
            const latest = data.summaries[0];
            openDetailViewer(latest.title || recName, recName, latest.tags, formatMarkdown(latest.summary));
        }
    } catch (err) {
        console.error("Failed to load summary:", err);
    }
});

// ─── Init ──────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    const today = new Date();
    currentYear = today.getFullYear();
    currentMonth = today.getMonth() + 1;
    loadMonth(currentYear, currentMonth);

    // Nav buttons
    $("#btn-prev-month")?.addEventListener("click", () => {
        if (currentMonth === 1) { currentMonth = 12; currentYear--; }
        else { currentMonth--; }
        loadMonth(currentYear, currentMonth);
    });

    $("#btn-next-month")?.addEventListener("click", () => {
        if (currentMonth === 12) { currentMonth = 1; currentYear++; }
        else { currentMonth++; }
        loadMonth(currentYear, currentMonth);
    });

    $("#btn-today")?.addEventListener("click", (e) => {
        e.preventDefault();
        const today = new Date();
        currentYear = today.getFullYear();
        currentMonth = today.getMonth() + 1;
        selectedDate = todayStr();
        loadMonth(currentYear, currentMonth).then(() => loadDayDetail(selectedDate));
    });

    // Close day detail
    $("#btn-close-detail")?.addEventListener("click", () => {
        $("#day-detail-row").style.display = "none";
        closeDetailViewer();
        $("#recap-row").style.display = "none";
        selectedDate = null;
        document.querySelectorAll(".cal-day.cal-selected").forEach(el => el.classList.remove("cal-selected"));
    });

    // Add event button
    $("#btn-add-event")?.addEventListener("click", () => {
        openEventModal(selectedDate || todayStr(), null);
    });

    // Daily recap button (generate or regenerate)
    $("#btn-daily-recap")?.addEventListener("click", () => {
        if (selectedDate) generateRecap(selectedDate);
    });

    // Regenerate recap from inline stored recap
    $("#btn-regenerate-recap")?.addEventListener("click", () => {
        if (selectedDate) generateRecap(selectedDate);
    });

    // Delete recap from inline stored recap
    $("#btn-delete-recap")?.addEventListener("click", () => {
        if (selectedDate) deleteRecap(selectedDate);
    });

    // Close recap
    $("#btn-close-recap")?.addEventListener("click", () => {
        $("#recap-row").style.display = "none";
    });

    // Close detail viewer
    $("#btn-close-viewer")?.addEventListener("click", () => {
        closeDetailViewer();
    });

    // ─── Shared Calendar buttons ────────────────────────────────

    // Toggle shared calendar panel
    $("#btn-manage-calendars")?.addEventListener("click", (e) => {
        e.preventDefault();
        const panel = $("#shared-cal-panel");
        if (panel.classList.contains("d-none")) {
            refreshSharedCalPanel();
            show(panel);
        } else {
            hide(panel);
        }
    });

    // Close shared calendar panel
    $("#btn-close-shared-panel")?.addEventListener("click", () => {
        hide($("#shared-cal-panel"));
    });

    // Add calendar button
    $("#btn-add-shared-cal")?.addEventListener("click", () => {
        openSharedCalModal(null);
    });

    // Sync all calendars
    $("#btn-sync-all-calendars")?.addEventListener("click", async () => {
        const btn = $("#btn-sync-all-calendars");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Syncing…';

        try {
            const res = await fetch(`${CAL_API}/shared/sync-all`, { method: "POST" });
            await res.json();
            await loadMonth(currentYear, currentMonth);
            await refreshSharedCalPanel();
            if (selectedDate) await loadDayDetail(selectedDate);
        } catch (err) {
            console.error("Sync all failed:", err);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Sync All';
        }
    });
});

