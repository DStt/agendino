/**
 * AgenDino Knowledge Base JS
 * Mind map visualisation, RAG Q&A, and semantic search.
 */
(function () {
    'use strict';

    const API = '/api/knowledge';
    let mindmapNetwork = null;
    let aiMindmapNetwork = null;

    /* ── Helpers ── */
    function show(el) { el && el.classList.remove('d-none'); }
    function hide(el) { el && el.classList.add('d-none'); }
    function $(id) { return document.getElementById(id); }

    async function api(path, opts = {}) {
        const res = await fetch(`${API}${path}`, {
            headers: { 'Content-Type': 'application/json' },
            ...opts,
        });
        return res.json();
    }

    /* ── Summary Filter State ── */
    let filterSummaries = [];       // all available summaries
    let activeFilterIds = null;     // null = all, array = specific IDs
    let filterOpen = false;

    function getActiveFilterIds() {
        return activeFilterIds;
    }

    async function loadFilterSummaries() {
        const loading = $('filter-loading');
        const list = $('filter-list');
        show(loading);
        hide(list);

        try {
            const data = await api('/summaries');
            if (data.ok && data.summaries && data.summaries.length > 0) {
                filterSummaries = data.summaries;
                renderFilterList(list);
                hide(loading);
                show(list);
            } else {
                hide(loading);
                list.innerHTML = '<p class="text-muted text-center small p-2 mb-0">No summaries available.</p>';
                show(list);
            }
        } catch (e) {
            hide(loading);
            list.innerHTML = `<p class="text-danger text-center small p-2 mb-0">Error: ${e.message}</p>`;
            show(list);
        }
    }

    function renderFilterList(container) {
        container.innerHTML = '';
        for (const s of filterSummaries) {
            const tags = (s.tags || []).filter(t => t.trim());
            const tagsHtml = tags.map(t => `<span class="badge bg-secondary me-1">${t.trim()}</span>`).join('');
            const isChecked = !activeFilterIds || activeFilterIds.includes(s.id);
            const div = document.createElement('div');
            div.className = 'ai-picker-item';
            div.innerHTML = `
                <input class="form-check-input mt-1 filter-summary-cb" type="checkbox"
                       value="${s.id}" id="filter-${s.id}" ${isChecked ? 'checked' : ''}>
                <label for="filter-${s.id}">
                    <span class="picker-title">${s.title}</span>
                    <small class="text-muted ms-1">${s.recording_name}</small>
                    ${tagsHtml ? `<div class="picker-tags">${tagsHtml}</div>` : ''}
                </label>
            `;
            container.appendChild(div);
        }
    }

    function getFilterCheckedIds() {
        const checked = document.querySelectorAll('#filter-list .filter-summary-cb:checked');
        return Array.from(checked).map(cb => parseInt(cb.value, 10));
    }

    function updateFilterStatusUI() {
        const badge = $('filter-active-badge');
        const statusText = $('filter-status-text');
        const total = filterSummaries.length;

        if (!activeFilterIds || activeFilterIds.length === total) {
            badge.style.display = 'none';
            statusText.textContent = 'All summaries';
        } else if (activeFilterIds.length === 0) {
            badge.style.display = 'inline';
            badge.textContent = '0';
            statusText.textContent = 'No summaries selected';
        } else {
            badge.style.display = 'inline';
            badge.textContent = `${activeFilterIds.length} / ${total}`;
            statusText.textContent = `${activeFilterIds.length} of ${total} selected`;
        }
    }

    function applyFilter() {
        const checkedIds = getFilterCheckedIds();
        const total = filterSummaries.length;

        if (checkedIds.length === 0 || checkedIds.length === total) {
            activeFilterIds = checkedIds.length === 0 ? [] : null;
        } else {
            activeFilterIds = checkedIds;
        }

        updateFilterStatusUI();

        // Refresh both mind map and close filter
        loadMindMap();
    }

    function toggleFilterPanel() {
        const body = $('summary-filter-body');
        const chevron = $('filter-chevron');
        filterOpen = !filterOpen;

        if (filterOpen) {
            show(body);
            chevron.className = 'bi bi-chevron-up';
            if (filterSummaries.length === 0) {
                loadFilterSummaries();
            }
        } else {
            hide(body);
            chevron.className = 'bi bi-chevron-down';
        }
    }

    /* ── Stats ── */
    async function loadStats() {
        try {
            const data = await api('/stats');
            if (data.ok) {
                $('stat-total').textContent = data.total_summaries;
                $('stat-loaded').textContent = data.loaded_count;
            }
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    }

    /* ── Load Summaries into Vector Store ── */
    async function loadSummaries() {
        const alertEl = $('load-alert');
        const btn = $('btn-load-summaries');
        hide(alertEl);
        btn.classList.add('loading');

        try {
            const data = await api('/load', { method: 'POST' });
            if (data.ok) {
                alertEl.className = 'alert alert-success';
                alertEl.innerHTML =
                    `<i class="bi bi-check-circle me-1"></i> Loaded <strong>${data.loaded}</strong> summaries ` +
                    `(${data.skipped} skipped). Total in store: <strong>${data.total_in_store}</strong>`;
                if (data.errors && data.errors.length > 0) {
                    alertEl.innerHTML += `<br><small class="text-muted">Errors: ${data.errors.join(', ')}</small>`;
                }
            } else {
                alertEl.className = 'alert alert-danger';
                alertEl.textContent = data.error || 'Failed to load summaries';
            }
            show(alertEl);
            await loadStats();
            await loadMindMap();
        } catch (e) {
            alertEl.className = 'alert alert-danger';
            alertEl.textContent = `Error: ${e.message}`;
            show(alertEl);
        } finally {
            btn.classList.remove('loading');
        }
    }

    /* ── Tag-based Mind Map ── */
    async function loadMindMap() {
        const container = $('mindmap-container');
        const emptyState = $('mindmap-empty');

        try {
            const ids = getActiveFilterIds();
            const body = ids ? JSON.stringify({ summary_ids: ids }) : '{}';
            const data = await api('/mindmap', { method: 'POST', body });
            if (!data.ok || !data.nodes || data.nodes.length === 0) {
                hide(container);
                show(emptyState);
                return;
            }
            show(container);
            hide(emptyState);
            renderMindMap(container, data.nodes, data.edges);
        } catch (e) {
            container.innerHTML = '<div class="text-center text-danger p-5">Failed to load mind map</div>';
        }
    }

    function renderMindMap(container, nodesData, edgesData) {
        const nodes = new vis.DataSet(nodesData.map(n => ({
            id: n.id,
            label: n.label,
            title: n.title,
            group: n.type,
            shape: n.type === 'tag' ? 'diamond' : 'dot',
            size: n.type === 'tag' ? 18 : 28,
            font: {
                size: n.type === 'tag' ? 12 : 14,
                face: 'Source Sans 3, sans-serif',
            },
            _meta: n,
        })));

        const edges = new vis.DataSet(edgesData.map((e, i) => ({
            id: `e_${i}`,
            from: e.from,
            to: e.to,
            color: { opacity: 0.35 },
            smooth: { type: 'continuous' },
        })));

        const options = {
            groups: {
                summary: {
                    color: { background: '#0d6efd', border: '#0a58ca', highlight: { background: '#3d8bfd', border: '#0a58ca' } },
                    font: { color: '#fff' },
                },
                tag: {
                    color: { background: '#ffc107', border: '#cc9a06', highlight: { background: '#ffcd39', border: '#cc9a06' } },
                    font: { color: '#000' },
                },
            },
            physics: {
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {
                    gravitationalConstant: -50,
                    centralGravity: 0.005,
                    springLength: 130,
                    springConstant: 0.08,
                    damping: 0.4,
                },
                stabilization: { iterations: 150 },
            },
            interaction: {
                hover: true,
                tooltipDelay: 150,
                navigationButtons: true,
                keyboard: true,
            },
        };

        if (mindmapNetwork) mindmapNetwork.destroy();
        mindmapNetwork = new vis.Network(container, { nodes, edges }, options);

        // Click on a summary node → show detail
        mindmapNetwork.on('doubleClick', function (params) {
            if (params.nodes.length === 0) return;
            const nodeId = params.nodes[0];
            const node = nodes.get(nodeId);
            if (node && node._meta && node._meta.type === 'summary') {
                showSummaryDetail(node._meta);
            }
        });
    }

    /* ── Summary Detail Modal ── */
    async function showSummaryDetail(meta) {
        const backdrop = $('summary-detail-backdrop');
        const nameEl = $('summary-detail-name');
        const tagsEl = $('summary-detail-tags');
        const contentEl = $('summary-detail-content');

        nameEl.textContent = meta.label || meta.recording_name || '';
        tagsEl.innerHTML = '';
        contentEl.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-info" role="status"></div></div>';
        show(backdrop);

        // Fetch the full summary from the dashboard API
        try {
            const data = await fetch(`/api/dashboard/summaries/${meta.recording_name}`).then(r => r.json());
            if (data.ok && data.summaries && data.summaries.length > 0) {
                const summary = data.summaries[0];
                nameEl.textContent = summary.title || meta.recording_name;

                if (summary.tags && summary.tags.length > 0) {
                    tagsEl.innerHTML = summary.tags
                        .map(t => `<span class="badge bg-secondary me-1">${t}</span>`)
                        .join('');
                }
                contentEl.innerHTML = marked.parse(summary.summary || '');
            } else {
                contentEl.innerHTML = '<p class="text-muted">Summary not found.</p>';
            }
        } catch (e) {
            contentEl.innerHTML = `<p class="text-danger">Failed to load summary: ${e.message}</p>`;
        }
    }

    /* ── AI Mind Map — Step 1: Summary Picker ── */
    let pickerSummaries = [];

    async function openAIPicker() {
        const backdrop = $('ai-picker-backdrop');
        const loading  = $('ai-picker-loading');
        const list     = $('ai-picker-list');
        const error    = $('ai-picker-error');

        show(backdrop);
        show(loading);
        hide(list);
        hide(error);
        $('ai-picker-generate').disabled = true;

        try {
            const data = await api('/summaries');
            if (!data.ok || !data.summaries || data.summaries.length === 0) {
                error.textContent = 'No summaries found. Create summaries from the Dashboard first.';
                show(error);
                hide(loading);
                return;
            }
            pickerSummaries = data.summaries;
            hide(loading);
            renderPickerList(list);
            show(list);
            updatePickerCount();
        } catch (e) {
            error.textContent = `Error: ${e.message}`;
            show(error);
            hide(loading);
        }
    }

    function renderPickerList(container) {
        container.innerHTML = '';
        for (const s of pickerSummaries) {
            const tags = (s.tags || []).filter(t => t.trim());
            const tagsHtml = tags.map(t => `<span class="badge bg-secondary me-1">${t.trim()}</span>`).join('');
            const div = document.createElement('div');
            div.className = 'ai-picker-item';
            div.innerHTML = `
                <input class="form-check-input mt-1" type="checkbox" value="${s.id}" id="pick-${s.id}" checked>
                <label for="pick-${s.id}">
                    <span class="picker-title">${s.title}</span>
                    <small class="text-muted ms-1">${s.recording_name}</small>
                    ${tagsHtml ? `<div class="picker-tags">${tagsHtml}</div>` : ''}
                </label>
            `;
            div.querySelector('input').addEventListener('change', updatePickerCount);
            container.appendChild(div);
        }
    }

    function updatePickerCount() {
        const checked = document.querySelectorAll('#ai-picker-list input[type=checkbox]:checked');
        $('ai-picker-count').textContent = checked.length;
        $('ai-picker-generate').disabled = checked.length === 0;
    }

    function getSelectedSummaryIds() {
        const checked = document.querySelectorAll('#ai-picker-list input[type=checkbox]:checked');
        return Array.from(checked).map(cb => parseInt(cb.value, 10));
    }

    /* ── AI Mind Map — Step 2: Generate & Render ── */
    async function generateAIMindMap() {
        const ids = getSelectedSummaryIds();
        hide($('ai-picker-backdrop'));

        const backdrop  = $('ai-mindmap-modal-backdrop');
        const loading   = $('ai-mindmap-loading');
        const container = $('ai-mindmap-container');
        const legend    = $('ai-mindmap-legend');
        const error     = $('ai-mindmap-error');

        show(backdrop);
        show(loading);
        hide(container);
        hide(legend);
        hide(error);

        try {
            const body = ids.length > 0 ? JSON.stringify({ summary_ids: ids }) : '{}';
            const data = await api('/mindmap/generate', { method: 'POST', body });
            if (!data.ok) {
                error.textContent = data.error || 'Failed to generate mind map';
                show(error);
                hide(loading);
                return;
            }
            hide(loading);
            show(container);
            show(legend);
            renderAIMindMap(container, data.mind_map);
        } catch (e) {
            error.textContent = `Error: ${e.message}`;
            show(error);
            hide(loading);
        }
    }

    function wrapLabel(text, maxLen) {
        if (!text || text.length <= maxLen) return text;
        const words = text.split(' ');
        const lines = [];
        let line = '';
        for (const w of words) {
            if (line && (line + ' ' + w).length > maxLen) {
                lines.push(line);
                line = w;
            } else {
                line = line ? line + ' ' + w : w;
            }
        }
        if (line) lines.push(line);
        return lines.join('\n');
    }

    function renderAIMindMap(container, mindMapData) {
        const nodesArr = [];
        const edgesArr = [];
        let nodeId = 0;

        // Central topic
        const centralId = `ai_${nodeId++}`;
        nodesArr.push({
            id: centralId,
            label: wrapLabel(mindMapData.central_topic || 'Knowledge Base', 18),
            shape: 'ellipse',
            size: 50,
            color: { background: '#dc3545', border: '#a71d2a', highlight: { background: '#e35d6a', border: '#a71d2a' } },
            font: { color: '#fff', size: 20, bold: true, face: 'Source Sans 3, sans-serif', multi: true },
            borderWidth: 3,
            shadow: { enabled: true, size: 8, x: 2, y: 2, color: 'rgba(0,0,0,0.15)' },
            level: 0,
        });

        // Branches
        const branchMap = {};
        const branchColors = [
            { bg: '#0d6efd', border: '#0a58ca', hl: '#3d8bfd' },
            { bg: '#6f42c1', border: '#59359a', hl: '#8c68cd' },
            { bg: '#d63384', border: '#ab296a', hl: '#de5c9d' },
            { bg: '#fd7e14', border: '#ca6510', hl: '#fd9843' },
            { bg: '#0dcaf0', border: '#0aa2c0', hl: '#3dd5f3' },
            { bg: '#20c997', border: '#1aa179', hl: '#4dd4ac' },
            { bg: '#6c757d', border: '#565e64', hl: '#868e96' },
        ];

        if (mindMapData.branches) {
            for (let bi = 0; bi < mindMapData.branches.length; bi++) {
                const branch = mindMapData.branches[bi];
                const branchId = branch.id || `ai_${nodeId++}`;
                branchMap[branch.id || branchId] = branchId;
                const pal = branchColors[bi % branchColors.length];

                nodesArr.push({
                    id: branchId,
                    label: wrapLabel(branch.label, 16),
                    shape: 'box',
                    color: { background: pal.bg, border: pal.border, highlight: { background: pal.hl, border: pal.border } },
                    font: { color: '#fff', size: 15, bold: true, face: 'Source Sans 3, sans-serif', multi: true },
                    borderWidth: 2,
                    margin: 10,
                    shadow: { enabled: true, size: 4, x: 1, y: 1, color: 'rgba(0,0,0,0.12)' },
                    level: 1,
                });
                edgesArr.push({
                    from: centralId, to: branchId,
                    width: 3,
                    color: { color: pal.bg, opacity: 0.7 },
                    smooth: { type: 'cubicBezier', roundness: 0.4 },
                });

                // Children (leaves)
                if (branch.children) {
                    for (const child of branch.children) {
                        const childId = child.id || `ai_${nodeId++}`;
                        const sourceHint = child.summary_ids && child.summary_ids.length
                            ? `\n\nSource summaries: ${child.summary_ids.join(', ')}`
                            : '';
                        nodesArr.push({
                            id: childId,
                            label: wrapLabel(child.label, 20),
                            shape: 'box',
                            color: { background: '#198754', border: '#146c43', highlight: { background: '#28a745', border: '#146c43' } },
                            font: { color: '#fff', size: 12, face: 'Source Sans 3, sans-serif', multi: true },
                            margin: 8,
                            borderWidth: 1,
                            title: child.label + sourceHint,
                            level: 2,
                        });
                        edgesArr.push({
                            from: branchId, to: childId,
                            width: 1.5,
                            color: { color: '#198754', opacity: 0.45 },
                            smooth: { type: 'cubicBezier', roundness: 0.3 },
                        });
                    }
                }
            }
        }

        // Cross-connections
        if (mindMapData.connections) {
            for (const conn of mindMapData.connections) {
                const fromId = branchMap[conn.from] || conn.from;
                const toId = branchMap[conn.to] || conn.to;
                // Only add if both nodes exist
                if (!nodesArr.find(n => n.id === fromId) || !nodesArr.find(n => n.id === toId)) continue;
                edgesArr.push({
                    from: fromId, to: toId,
                    dashes: [8, 6],
                    width: 2,
                    label: wrapLabel(conn.label || '', 14),
                    color: { color: '#ffc107', opacity: 0.7 },
                    font: { size: 10, color: '#997404', strokeWidth: 3, strokeColor: '#fff', face: 'Source Sans 3, sans-serif' },
                    smooth: { type: 'curvedCW', roundness: 0.25 },
                    arrows: { to: { enabled: false } },
                });
            }
        }

        const options = {
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'UD',
                    sortMethod: 'directed',
                    levelSeparation: 140,
                    nodeSpacing: 180,
                    treeSpacing: 220,
                    blockShifting: true,
                    edgeMinimization: true,
                    parentCentralization: true,
                },
            },
            physics: {
                enabled: false,
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                navigationButtons: true,
                keyboard: true,
                zoomView: true,
                dragView: true,
            },
            edges: {
                arrows: { to: { enabled: false } },
            },
        };

        if (aiMindmapNetwork) aiMindmapNetwork.destroy();
        aiMindmapNetwork = new vis.Network(
            container,
            { nodes: new vis.DataSet(nodesArr), edges: new vis.DataSet(edgesArr) },
            options,
        );

        // Auto-fit after stabilization
        aiMindmapNetwork.once('stabilizationIterationsDone', () => {
            aiMindmapNetwork.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
        });
        // Also fit immediately since physics is off
        setTimeout(() => {
            aiMindmapNetwork.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
        }, 100);
    }

    /* ── RAG Ask ── */
    async function askQuestion() {
        const query = $('rag-query-input').value.trim();
        if (!query) return;

        hide($('rag-answer'));
        hide($('rag-error'));
        show($('rag-loading'));

        try {
            const ids = getActiveFilterIds();
            const payload = { query, top_k: 5 };
            if (ids) payload.summary_ids = ids;

            const data = await api('/ask', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            hide($('rag-loading'));

            if (data.ok) {
                $('rag-answer-content').innerHTML = marked.parse(data.answer);

                const sourcesEl = $('rag-sources');
                sourcesEl.innerHTML = '';
                if (data.sources) {
                    for (const src of data.sources) {
                        const badge = document.createElement('span');
                        badge.className = 'badge bg-secondary me-2 mb-1 source-badge';
                        badge.textContent = src.title || src.recording_name;
                        if (src.distance !== null && src.distance !== undefined) {
                            const similarity = (1 - src.distance).toFixed(3);
                            badge.title = `Similarity: ${similarity}`;
                        }
                        sourcesEl.appendChild(badge);
                    }
                }
                show($('rag-answer'));
            } else {
                $('rag-error').textContent = data.error || 'Failed to get answer';
                show($('rag-error'));
            }
        } catch (e) {
            hide($('rag-loading'));
            $('rag-error').textContent = `Error: ${e.message}`;
            show($('rag-error'));
        }
    }

    /* ── Semantic Search ── */
    async function searchSummaries() {
        const query = $('search-input').value.trim();
        if (!query) return;

        hide($('search-results'));
        hide($('search-error'));
        show($('search-loading'));

        try {
            const ids = getActiveFilterIds();
            const payload = { query, top_k: 10 };
            if (ids) payload.summary_ids = ids;

            const data = await api('/search', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            hide($('search-loading'));

            if (data.ok) {
                const resultsEl = $('search-results');
                resultsEl.innerHTML = '';

                if (data.results && data.results.length > 0) {
                    for (const r of data.results) {
                        const meta = r.metadata || {};
                        const similarity = r.distance !== null && r.distance !== undefined
                            ? (1 - r.distance).toFixed(3)
                            : '—';

                        const tagsHtml = meta.tags
                            ? meta.tags.split(',')
                                .filter(t => t.trim())
                                .map(t => `<span class="badge bg-secondary me-1">${t.trim()}</span>`)
                                .join('')
                            : '';

                        const preview = (r.document || '').substring(0, 250).replace(/</g, '&lt;');

                        const card = document.createElement('div');
                        card.className = 'card mb-2 search-result-card';
                        card.innerHTML = `
                            <div class="card-body py-2 px-3">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div>
                                        <strong>${meta.title || meta.recording_name || 'Untitled'}</strong>
                                        <small class="text-muted ms-2">${meta.recording_name || ''}</small>
                                    </div>
                                    <span class="badge bg-primary">Score: ${similarity}</span>
                                </div>
                                ${tagsHtml ? `<div class="mt-1">${tagsHtml}</div>` : ''}
                                <p class="text-muted small mt-1 mb-0">${preview}…</p>
                            </div>
                        `;
                        resultsEl.appendChild(card);
                    }
                } else {
                    resultsEl.innerHTML = '<p class="text-muted text-center p-3">No results found.</p>';
                }
                show(resultsEl);
            } else {
                $('search-error').textContent = data.error || 'Search failed';
                show($('search-error'));
            }
        } catch (e) {
            hide($('search-loading'));
            $('search-error').textContent = `Error: ${e.message}`;
            show($('search-error'));
        }
    }

    /* ── Event Bindings ── */
    document.addEventListener('DOMContentLoaded', () => {
        // Initial load
        loadStats();
        loadMindMap();

        // Action buttons
        $('btn-load-summaries').addEventListener('click', loadSummaries);
        $('btn-refresh-map').addEventListener('click', loadMindMap);
        $('btn-ai-mindmap').addEventListener('click', openAIPicker);
        $('btn-ask').addEventListener('click', askQuestion);
        $('btn-search').addEventListener('click', searchSummaries);

        // Enter key support
        $('rag-query-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') askQuestion();
        });
        $('search-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') searchSummaries();
        });

        // Summary filter panel
        $('summary-filter-toggle').addEventListener('click', toggleFilterPanel);
        $('filter-select-all').addEventListener('click', () => {
            document.querySelectorAll('#filter-list .filter-summary-cb').forEach(cb => cb.checked = true);
        });
        $('filter-select-none').addEventListener('click', () => {
            document.querySelectorAll('#filter-list .filter-summary-cb').forEach(cb => cb.checked = false);
        });
        $('filter-apply').addEventListener('click', applyFilter);

        // AI Picker modal
        $('ai-picker-close').addEventListener('click', () => hide($('ai-picker-backdrop')));
        $('ai-picker-backdrop').addEventListener('click', e => {
            if (e.target === $('ai-picker-backdrop')) hide($('ai-picker-backdrop'));
        });
        $('ai-picker-select-all').addEventListener('click', () => {
            document.querySelectorAll('#ai-picker-list input[type=checkbox]').forEach(cb => cb.checked = true);
            updatePickerCount();
        });
        $('ai-picker-select-none').addEventListener('click', () => {
            document.querySelectorAll('#ai-picker-list input[type=checkbox]').forEach(cb => cb.checked = false);
            updatePickerCount();
        });
        $('ai-picker-generate').addEventListener('click', generateAIMindMap);

        // AI Mind Map modal close
        $('ai-mindmap-modal-close').addEventListener('click', () => {
            hide($('ai-mindmap-modal-backdrop'));
        });
        $('ai-mindmap-modal-backdrop').addEventListener('click', e => {
            if (e.target === $('ai-mindmap-modal-backdrop')) {
                hide($('ai-mindmap-modal-backdrop'));
            }
        });

        // Summary Detail modal close
        $('summary-detail-close').addEventListener('click', () => {
            hide($('summary-detail-backdrop'));
        });
        $('summary-detail-backdrop').addEventListener('click', e => {
            if (e.target === $('summary-detail-backdrop')) {
                hide($('summary-detail-backdrop'));
            }
        });
    });
})();

