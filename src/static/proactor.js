/* ── Proactor JS ──────────────────────────────────────────────── */

(function () {
    "use strict";

    const API = "/api/proactor/analyze";

    // ── DOM refs ────────────────────────────────────────────────
    const $startDate   = document.getElementById("start-date");
    const $endDate     = document.getElementById("end-date");
    const $btnAnalyze  = document.getElementById("btn-analyze");
    const $btnThisWeek = document.getElementById("btn-this-week");
    const $btnNextWeek = document.getElementById("btn-next-week");

    const $emptyState   = document.getElementById("empty-state");
    const $loadingState = document.getElementById("loading-state");
    const $errorState   = document.getElementById("error-state");
    const $errorMessage = document.getElementById("error-message");

    const $summaryRow   = document.getElementById("summary-row");
    const $summaryCard  = document.getElementById("summary-card");
    const $healthBadge  = document.getElementById("health-badge");
    const $summaryTitle = document.getElementById("summary-title");
    const $summaryStats = document.getElementById("summary-stats");

    const $overlapsRow  = document.getElementById("overlaps-row");
    const $overlapCount = document.getElementById("overlap-count");
    const $overlapsList = document.getElementById("overlaps-list");

    const $b2bRow   = document.getElementById("b2b-row");
    const $b2bCount = document.getElementById("b2b-count");
    const $b2bList  = document.getElementById("b2b-list");

    const $dayloadRow  = document.getElementById("dayload-row");
    const $dayloadBody = document.getElementById("dayload-body");

    const $gapsRow      = document.getElementById("gaps-row");
    const $timelineBody = document.getElementById("timeline-body");

    // ── Date helpers ────────────────────────────────────────────
    function isoDate(d) { return d.toISOString().slice(0, 10); }

    function getMonday(d) {
        const dt = new Date(d);
        const day = dt.getDay();
        const diff = dt.getDate() - day + (day === 0 ? -6 : 1);
        dt.setDate(diff);
        return dt;
    }

    function setRange(startDate, endDate) {
        $startDate.value = isoDate(startDate);
        $endDate.value = isoDate(endDate);
    }

    function setThisWeek() {
        const mon = getMonday(new Date());
        const sun = new Date(mon);
        sun.setDate(mon.getDate() + 6);
        setRange(mon, sun);
        runAnalysis();
    }

    function setNextWeek() {
        const mon = getMonday(new Date());
        mon.setDate(mon.getDate() + 7);
        const sun = new Date(mon);
        sun.setDate(mon.getDate() + 6);
        setRange(mon, sun);
        runAnalysis();
    }

    function setToday() {
        const today = new Date();
        setRange(today, today);
        runAnalysis();
    }

    function setThisMonth() {
        const now = new Date();
        const first = new Date(now.getFullYear(), now.getMonth(), 1);
        const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        setRange(first, last);
        runAnalysis();
    }

    // ── Formatting helpers ──────────────────────────────────────
    function fmtTime(dtStr) {
        if (!dtStr) return "?";
        // "YYYY-MM-DD HH:MM:SS" or ISO
        const parts = dtStr.replace("T", " ").split(" ");
        return parts.length >= 2 ? parts[1].slice(0, 5) : dtStr;
    }

    function fmtDate(dtStr) {
        if (!dtStr) return "?";
        return dtStr.replace("T", " ").split(" ")[0];
    }

    function fmtDateShort(dateStr) {
        try {
            const d = new Date(dateStr + "T00:00:00");
            return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
        } catch { return dateStr; }
    }

    function severityClass(severity) {
        return severity === "high" ? "text-danger fw-bold" :
               severity === "medium" ? "text-warning" : "text-muted";
    }

    function gapKindBadge(kind) {
        if (kind === "short") return '<span class="badge bg-warning text-dark">tight</span>';
        if (kind === "idle_window") return '<span class="badge bg-info">open window</span>';
        return '<span class="badge bg-success">available</span>';
    }

    function calBadge(ev) {
        const name = ev.calendar_name || "Local";
        const color = ev.calendar_color || "var(--bs-primary)";
        return `<span class="badge proactor-cal-badge" style="background:${esc(color)}">${esc(name)}</span>`;
    }

    // ── UI states ───────────────────────────────────────────────
    function showEmpty() {
        $emptyState.classList.remove("d-none");
        $loadingState.classList.add("d-none");
        $errorState.classList.add("d-none");
        hideResults();
    }

    function showLoading() {
        $emptyState.classList.add("d-none");
        $loadingState.classList.remove("d-none");
        $errorState.classList.add("d-none");
        hideResults();
    }

    function showError(msg) {
        $emptyState.classList.add("d-none");
        $loadingState.classList.add("d-none");
        $errorState.classList.remove("d-none");
        $errorMessage.textContent = msg;
        hideResults();
    }

    function hideResults() {
        $summaryRow.classList.add("d-none");
        $overlapsRow.classList.add("d-none");
        $b2bRow.classList.add("d-none");
        $dayloadRow.classList.add("d-none");
        $gapsRow.classList.add("d-none");
    }

    function showResults() {
        $emptyState.classList.add("d-none");
        $loadingState.classList.add("d-none");
        $errorState.classList.add("d-none");
    }

    // ── Render ──────────────────────────────────────────────────
    function renderReport(data) {
        showResults();
        const s = data.summary || {};

        // Health badge
        const healthMap = {
            good: { label: "✓ Healthy", cls: "proactor-health-good" },
            fair: { label: "⚠ Fair", cls: "proactor-health-fair" },
            poor: { label: "✗ Issues", cls: "proactor-health-poor" },
        };
        const h = healthMap[s.health] || healthMap.good;
        $healthBadge.textContent = h.label;
        $healthBadge.className = "proactor-health-badge " + h.cls;

        // Summary stats
        $summaryTitle.textContent = `Schedule Analysis - ${data.start_date} to ${data.end_date}`;
        $summaryStats.innerHTML = [
            `<span><i class="bi bi-calendar-event me-1"></i>${s.total_events || 0} events</span>`,
            `<span><i class="bi bi-exclamation-triangle me-1"></i>${s.overlap_count || 0} overlaps</span>`,
            `<span><i class="bi bi-arrow-right-circle me-1"></i>${s.back_to_back_count || 0} back-to-back</span>`,
            `<span><i class="bi bi-graph-up me-1"></i>${s.overloaded_days || 0} overloaded days</span>`,
            `<span><i class="bi bi-clock me-1"></i>${s.free_slots || 0} free slots</span>`,
        ].join("");
        $summaryRow.classList.remove("d-none");

        // Overlaps
        if ((data.overlaps || []).length > 0) {
            $overlapCount.textContent = data.overlaps.length;
            $overlapsList.innerHTML = data.overlaps.map(o => `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>${esc(o.event_a.title)}</strong> ${calBadge(o.event_a)}
                            <span class="text-muted small">(${fmtDate(o.event_a.start_at)} ${fmtTime(o.event_a.start_at)}–${fmtTime(o.event_a.end_at)})</span>
                            <br>
                            <i class="bi bi-arrow-left-right text-danger mx-2"></i>
                            <strong>${esc(o.event_b.title)}</strong> ${calBadge(o.event_b)}
                            <span class="text-muted small">(${fmtTime(o.event_b.start_at)}–${fmtTime(o.event_b.end_at)})</span>
                        </div>
                        <span class="${severityClass(o.severity)}">${Math.round(o.overlap_minutes)} min overlap</span>
                    </div>
                </div>
            `).join("");
            $overlapsRow.classList.remove("d-none");
        } else {
            $overlapsRow.classList.add("d-none");
        }

        // Back-to-back
        if ((data.back_to_back || []).length > 0) {
            $b2bCount.textContent = data.back_to_back.length;
            $b2bList.innerHTML = data.back_to_back.map(b => `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>${esc(b.event_a.title)}</strong> ${calBadge(b.event_a)}
                            <span class="text-muted small">(${fmtDate(b.event_a.end_at)} ends ${fmtTime(b.event_a.end_at)})</span>
                            <i class="bi bi-arrow-right mx-2 text-warning"></i>
                            <strong>${esc(b.event_b.title)}</strong> ${calBadge(b.event_b)}
                            <span class="text-muted small">(starts ${fmtTime(b.event_b.start_at)})</span>
                        </div>
                        <span class="text-warning">${Math.round(b.gap_minutes)} min gap</span>
                    </div>
                </div>
            `).join("");
            $b2bRow.classList.remove("d-none");
        } else {
            $b2bRow.classList.add("d-none");
        }

        // Day load
        if ((data.day_load || []).length > 0) {
            $dayloadBody.innerHTML = data.day_load.map(d => {
                const cls = d.overloaded ? "table-danger" : "";
                const badge = d.overloaded
                    ? '<span class="badge bg-danger">overloaded</span>'
                    : '<span class="badge bg-success">ok</span>';
                return `<tr class="${cls}">
                    <td>${fmtDateShort(d.date)}</td>
                    <td>${d.event_count}</td>
                    <td>${d.total_hours.toFixed(1)}h</td>
                    <td>${badge}</td>
                </tr>`;
            }).join("");
            $dayloadRow.classList.remove("d-none");
        } else {
            $dayloadRow.classList.add("d-none");
        }

        // Day timelines (visual)
        const timelines = data.day_timelines || [];
        if (timelines.length > 0) {
            $timelineBody.innerHTML = timelines.map(day => {
                const barSegments = day.segments.map(seg => {
                    if (seg.type === "meeting") {
                        const bg = seg.calendar_color || "#495057";
                        const tip = `${esc(seg.title || "Meeting")}${seg.calendar_name ? " (" + esc(seg.calendar_name) + ")" : ""}\n${seg.start}–${seg.end} (${Math.round(seg.minutes)} min)`;
                        return `<div class="tl-seg tl-meeting" style="width:${seg.pct}%;background:${bg}" title="${tip}"></div>`;
                    }
                    const kindCls = seg.kind === "idle_window" ? "tl-open" : seg.kind === "short" ? "tl-tight" : "tl-avail";
                    const tip = `Free: ${seg.start}–${seg.end} (${Math.round(seg.minutes)} min)`;
                    return `<div class="tl-seg ${kindCls}" style="width:${seg.pct}%" title="${tip}"></div>`;
                }).join("");

                const freeH = (day.total_free_min / 60).toFixed(1);
                const busyH = (day.total_busy_min / 60).toFixed(1);

                return `
                    <div class="tl-row">
                        <div class="tl-label">
                            <span class="fw-bold">${fmtDateShort(day.date)}</span>
                            <span class="text-muted small d-block">${freeH}h free · ${busyH}h busy</span>
                        </div>
                        <div class="tl-bar-wrap">
                            <div class="tl-bar">${barSegments}</div>
                            <div class="tl-ticks">
                                <span class="tl-tick">${day.work_start}</span>
                                <span class="tl-tick tl-tick-end">${day.work_end}</span>
                            </div>
                        </div>
                    </div>`;
            }).join("");
            $gapsRow.classList.remove("d-none");
        } else {
            $gapsRow.classList.add("d-none");
        }
    }

    // ── Escape HTML ─────────────────────────────────────────────
    function esc(str) {
        const d = document.createElement("div");
        d.textContent = str || "";
        return d.innerHTML;
    }

    // ── API call ────────────────────────────────────────────────
    async function runAnalysis() {
        const start = $startDate.value;
        const end = $endDate.value;
        if (!start || !end) { showError("Please select both start and end dates."); return; }

        showLoading();
        try {
            const resp = await fetch(`${API}?start=${start}&end=${end}`);
            const data = await resp.json();
            if (!data.ok) { showError(data.error || "Analysis failed"); return; }
            renderReport(data);
        } catch (err) {
            showError("Network error: " + err.message);
        }
    }

    // ── Events ──────────────────────────────────────────────────
    $btnAnalyze.addEventListener("click", runAnalysis);
    $btnThisWeek.addEventListener("click", setThisWeek);
    $btnNextWeek.addEventListener("click", setNextWeek);

    // Quick-range buttons
    document.querySelectorAll("[data-range]").forEach(btn => {
        btn.addEventListener("click", () => {
            const r = btn.dataset.range;
            if (r === "today") setToday();
            else if (r === "week") setThisWeek();
            else if (r === "next-week") setNextWeek();
            else if (r === "month") setThisMonth();
        });
    });

    // Default to this week
    (function init() {
        const mon = getMonday(new Date());
        const sun = new Date(mon);
        sun.setDate(mon.getDate() + 6);
        setRange(mon, sun);
    })();

})();

