/* ===================================================================
   Agent Efficiency Bench — UI Logic
   =================================================================== */
(() => {
  'use strict';

  /* --- State --- */
  const charts = {};
  let activeJobId = null;
  let pollTimer = null;

  /* --- DOM helpers --- */
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  /* --- Utility --- */
  function splitCSV(value) {
    return (value || '').split(',').map((s) => s.trim()).filter(Boolean);
  }

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
    }[ch]));
  }

  function formatNumber(value, opts = {}) {
    const { decimals = 2, unit = '', compact = false } = opts;
    if (value == null || value === '') return '—';
    const num = Number(value);
    if (!Number.isFinite(num)) return '—';
    if (compact && Math.abs(num) >= 1000) {
      return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(num) + (unit ? ` ${unit}` : '');
    }
    return num.toLocaleString('en', { minimumFractionDigits: 0, maximumFractionDigits: decimals }) + (unit ? ` ${unit}` : '');
  }

  function formatCurrency(value) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return '$' + Number(value).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }

  function formatPercent(value) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return (Number(value) * 100).toFixed(1) + '%';
  }

  function showToast(message, type = 'info') {
    const container = $('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 200ms';
      setTimeout(() => toast.remove(), 200);
    }, 4000);
  }

  /* --- Theme --- */
  function initTheme() {
    const stored = localStorage.getItem('aeb-theme');
    if (stored) {
      document.documentElement.setAttribute('data-theme', stored);
    }
    $('#theme-toggle').addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('aeb-theme', next);
      // Re-render charts with updated grid/text colors
      if (charts && Object.keys(charts).length) {
        refreshResults();
      }
    });
  }

  /* --- Form payload --- */
  function checkedValues(name) {
    return Array.from($$(`input[name="${name}"]:checked`)).map((el) => el.value);
  }

  function formPayload() {
    const form = $('#run-form');
    const fd = new FormData(form);
    const categories = splitCSV(fd.get('categories'));
    const limit = Number(fd.get('limit'));
    return {
      tasks_path: fd.get('tasks_path'),
      output_root: fd.get('output_root'),
      models: splitCSV(fd.get('models')),
      categories: categories.length ? categories : [null],
      scaffolds: checkedValues('scaffolds'),
      web_search: checkedValues('web_search').map((v) => v === 'true'),
      limit: Number.isFinite(limit) && limit > 0 ? limit : null,
      n_trials: Number(fd.get('n_trials') || 1),
      max_completion_tokens: Number(fd.get('max_completion_tokens') || 256),
      group_by: splitCSV(fd.get('group_by') || 'category,model,scaffold'),
      dry_run: Boolean(fd.get('dry_run')),
    };
  }

  function updateCombinationCount() {
    const payload = formPayload();
    const count =
      payload.models.length *
      payload.scaffolds.length *
      payload.categories.length *
      payload.web_search.length;
    const el = $('#combination-count');
    el.textContent = `${count} combination${count !== 1 ? 's' : ''}`;
    el.hidden = false;
  }

  /* --- API calls --- */
  async function apiFetch(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function refreshOptions() {
    try {
      const options = await apiFetch('/api/options');
      renderOptions(options);
      await refreshCatalog();
    } catch (err) {
      showToast(`Failed to load options: ${err.message}`, 'error');
    }
  }

  function renderOptions(options) {
    const el = $('#options-body');
    const scaffoldTags = options.scaffolds.map((s) => `<span class="tag">${escapeHTML(s)}</span>`).join('');
    const groupTags = options.group_by_dimensions.map((g) => `<span class="tag">${escapeHTML(g)}</span>`).join('');
    const modelTags = (options.example_models || []).map((m) => `<span class="tag">${escapeHTML(m)}</span>`).join('');
    el.innerHTML = `
      <div class="option-label">Scaffolds</div>
      <div class="option-row">${scaffoldTags}</div>
      <div class="option-label">Group by dimensions</div>
      <div class="option-row">${groupTags}</div>
      <div class="option-label">Example models</div>
      <div class="option-row">${modelTags}</div>
    `;
  }

  async function refreshCatalog() {
    const tasksPath = $('[name="tasks_path"]').value;
    const el = $('#catalog');
    el.innerHTML = '<p class="empty-state">Loading catalog…</p>';
    try {
      const data = await apiFetch(`/api/catalog?tasks_path=${encodeURIComponent(tasksPath)}`);
      renderCatalog(data);
    } catch (err) {
      el.innerHTML = `<p class="empty-state">Error: ${escapeHTML(err.message)}</p>`;
    }
  }

  function renderCatalog(data) {
    const el = $('#catalog');
    const totalEl = $('#catalog-total');
    totalEl.textContent = `${data.total_tasks} tasks`;
    totalEl.hidden = false;

    const catTags = Object.entries(data.categories || {})
      .map(([k, v]) => `<span class="tag">${escapeHTML(k)}: ${v}</span>`).join('');
    const srcTags = Object.entries(data.sources || {})
      .map(([k, v]) => `<span class="tag">${escapeHTML(k)}: ${v}</span>`).join('');
    const horizonTags = Object.entries(data.horizons || {})
      .map(([k, v]) => `<span class="tag">${escapeHTML(k)}: ${v}</span>`).join('');

    el.innerHTML = `
      <div class="catalog-row">
        <span class="catalog-label">Total tasks</span>
        <span class="catalog-value">${data.total_tasks}</span>
      </div>
      <div class="catalog-row">
        <span class="catalog-label">External search</span>
        <span class="catalog-value">${data.requires_external_search}</span>
      </div>
      <div style="margin-top:.75rem">
        <div class="option-label">Categories</div>
        <div class="catalog-tags">${catTags || '<span class="tag">none</span>'}</div>
      </div>
      <div style="margin-top:.75rem">
        <div class="option-label">Sources</div>
        <div class="catalog-tags">${srcTags || '<span class="tag">none</span>'}</div>
      </div>
      <div style="margin-top:.75rem">
        <div class="option-label">Horizons</div>
        <div class="catalog-tags">${horizonTags || '<span class="tag">none</span>'}</div>
      </div>
    `;
  }

  /* --- Run submission --- */
  async function submitRun(event) {
    event.preventDefault();
    const payload = formPayload();

    if (!payload.models.length) {
      showToast('At least one model is required', 'error');
      return;
    }
    if (!payload.scaffolds.length) {
      showToast('At least one scaffold must be selected', 'error');
      return;
    }
    if (!payload.web_search.length) {
      showToast('At least one web search mode must be selected', 'error');
      return;
    }

    // Show payload
    const pw = $('#payload-wrap');
    pw.hidden = false;
    $('#request-preview').textContent = JSON.stringify(payload, null, 2);

    const btn = $('#submit-btn');
    btn.disabled = true;
    btn.textContent = 'Starting…';

    try {
      const job = await apiFetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      activeJobId = job.job_id;
      renderStatus(job);
      $('#results-section').hidden = true;

      if (job.status === 'dry_run') {
        showToast('Dry run completed — no execution started', 'info');
        btn.disabled = false;
        btn.textContent = 'Start run';
      } else {
        showToast('Run started', 'success');
        btn.disabled = false;
        btn.textContent = 'Start run';
        startPolling();
      }
    } catch (err) {
      showToast(`Failed to start run: ${err.message}`, 'error');
      btn.disabled = false;
      btn.textContent = 'Start run';
    }
  }

  /* --- Polling --- */
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(refreshRun, 1500);
    refreshRun();
  }

  async function refreshRun() {
    if (!activeJobId) return;
    try {
      const job = await apiFetch(`/api/runs/${activeJobId}`);
      renderStatus(job);
      if (job.status === 'completed' || job.status === 'failed') {
        clearInterval(pollTimer);
        pollTimer = null;
        if (job.status === 'completed') {
          showToast('Run completed!', 'success');
          await refreshResults();
        } else {
          showToast('Run failed — see status for details', 'error');
        }
      }
    } catch (err) {
      showToast(`Status poll failed: ${err.message}`, 'error');
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  /* --- Status rendering --- */
  function statusBadgeClass(status) {
    const map = {
      queued: 'badge-muted',
      running: 'badge-info',
      completed: 'badge-success',
      failed: 'badge-danger',
      dry_run: 'badge-warning',
    };
    return map[status] || 'badge-muted';
  }

  function renderStatus(job) {
    const el = $('#status');
    const badge = $('#status-badge');
    badge.textContent = job.status;
    badge.className = `badge ${statusBadgeClass(job.status)}`;
    badge.hidden = false;

    const pct = job.total_combinations > 0
      ? Math.round((job.completed_combinations / job.total_combinations) * 100)
      : 0;

    let html = `
      <div class="status-meta">
        <span>Job: <code>${escapeHTML(job.job_id)}</code></span>
        <span>${job.completed_combinations} / ${job.total_combinations} combinations</span>
        <span>${pct}%</span>
      </div>
      <div class="progress-bar"><div class="progress-bar-fill" style="width:${pct}%"></div></div>
    `;

    if (job.telemetry_paths && job.telemetry_paths.length) {
      html += `<div class="status-meta" style="margin-top:.75rem"><span>Telemetry: <code>${escapeHTML(job.telemetry_paths.join(', '))}</code></span></div>`;
    }

    if (job.error) {
      html += `<div class="error-box">${escapeHTML(job.error)}</div>`;
    }

    el.innerHTML = html;
  }

  /* --- Results rendering --- */
  async function refreshResults() {
    if (!activeJobId) return;
    try {
      const payload = await apiFetch(`/api/runs/${activeJobId}/results`);
      const rows = payload.chart_rows || [];
      $('#results-section').hidden = false;
      renderMetricCards(rows);
      renderCharts(rows);
      renderTable(rows);
    } catch (err) {
      showToast(`Failed to load results: ${err.message}`, 'error');
    }
  }

  function aggregateMetric(rows, key) {
    if (!rows.length) return null;
    const values = rows.map((r) => Number(r[key])).filter((v) => Number.isFinite(v));
    if (!values.length) return null;
    return values.reduce((a, b) => a + b, 0);
  }

  function avgMetric(rows, key) {
    if (!rows.length) return null;
    const values = rows.map((r) => Number(r[key])).filter((v) => Number.isFinite(v));
    if (!values.length) return null;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  function renderMetricCards(rows) {
    const el = $('#metric-cards');
    if (!rows.length) {
      el.innerHTML = '';
      return;
    }
    const cards = [
      { label: 'Total runs', value: formatNumber(aggregateMetric(rows, 'total_runs'), { decimals: 0 }) },
      { label: 'Avg success', value: formatPercent(avgMetric(rows, 'success_rate')) },
      { label: 'Total cost', value: formatCurrency(aggregateMetric(rows, 'total_cost')) },
      { label: 'Avg p50 latency', value: formatNumber(avgMetric(rows, 'p50_latency_seconds'), { decimals: 1, unit: 's' }) },
      { label: 'Total tokens', value: formatNumber(aggregateMetric(rows, 'total_tokens'), { decimals: 0, compact: true }) },
      { label: 'Cost / success', value: formatCurrency(avgMetric(rows, 'cost_per_success')) },
    ];
    el.innerHTML = cards.map((c) => `
      <div class="metric-card">
        <div class="metric-label">${escapeHTML(c.label)}</div>
        <div class="metric-value">${escapeHTML(c.value)}</div>
      </div>
    `).join('');
  }

  /* --- Charts --- */
  function chartTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    return {
      grid: isDark ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.06)',
      text: isDark ? '#a0aec0' : '#475569',
      bar: isDark ? '#818cf8' : '#6366f1',
    };
  }

  function renderCharts(rows) {
    drawBar('success-chart', rows, 'success_rate', 'Success rate', (v) => v, 'percent');
    drawBar('cost-chart', rows, 'total_cost', 'Total cost (USD)', (v) => v, 'currency');
    drawBar('latency-chart', rows, 'p50_latency_seconds', 'p50 latency (seconds)');
    drawBar('tokens-chart', rows, 'total_tokens', 'Total tokens');
  }

  function drawBar(canvasId, rows, metric, label, _transform, fmt) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') return;
    if (charts[canvasId]) charts[canvasId].destroy();

    const theme = chartTheme();
    const labels = rows.map((r) => r.group || '—');
    const data = rows.map((r) => Number(r[metric] ?? 0));

    const tickCallback = fmt === 'percent'
      ? (v) => (v * 100).toFixed(0) + '%'
      : fmt === 'currency'
        ? (v) => '$' + v.toFixed(2)
        : undefined;

    charts[canvasId] = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label,
          data,
          backgroundColor: theme.bar,
          borderRadius: 4,
          maxBarThickness: 48,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: tickCallback ? { label: (ctx) => `${label}: ${tickCallback(ctx.parsed.y)}` } : {},
          },
        },
        scales: {
          x: {
            ticks: { color: theme.text, maxRotation: 45, minRotation: 0, autoSkip: false },
            grid: { display: false },
          },
          y: {
            ticks: { color: theme.text, callback: tickCallback },
            grid: { color: theme.grid },
            beginAtZero: true,
          },
        },
      },
    });
  }

  /* --- Table --- */
  function renderTable(rows) {
    const el = $('#summary-table');
    if (!rows.length) {
      el.innerHTML = '<p class="empty-state">No results yet.</p>';
      return;
    }
    const columns = [
      { key: 'group', label: 'Group' },
      { key: 'total_runs', label: 'Runs', numeric: true, fmt: (v) => formatNumber(v, { decimals: 0 }) },
      { key: 'success_rate', label: 'Success', numeric: true, fmt: (v) => formatPercent(v) },
      { key: 'mean_quality', label: 'Quality', numeric: true, fmt: (v) => formatNumber(v, { decimals: 2 }) },
      { key: 'total_cost', label: 'Cost', numeric: true, fmt: (v) => formatCurrency(v) },
      { key: 'p50_latency_seconds', label: 'p50 (s)', numeric: true, fmt: (v) => formatNumber(v, { decimals: 1 }) },
      { key: 'total_tokens', label: 'Tokens', numeric: true, fmt: (v) => formatNumber(v, { decimals: 0, compact: true }) },
      { key: 'cost_per_success', label: 'Cost/success', numeric: true, fmt: (v) => formatCurrency(v) },
    ];

    const visible = columns.filter((c) => rows.some((r) => r[c.key] != null && r[c.key] !== ''));

    el.innerHTML = `
      <table>
        <thead>
          <tr>${visible.map((c) => `<th${c.numeric ? ' style="text-align:right"' : ''}>${escapeHTML(c.label)}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              ${visible.map((c) => {
                const val = c.fmt ? c.fmt(row[c.key]) : escapeHTML(row[c.key] ?? '');
                return `<td${c.numeric ? ' class="numeric"' : ''}>${val}</td>`;
              }).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  /* --- Init --- */
  function init() {
    initTheme();
    $('#run-form').addEventListener('submit', submitRun);
    $('#refresh-options').addEventListener('click', refreshOptions);

    // Update combination count when form changes
    $$('#run-form input').forEach((el) => {
      el.addEventListener('input', updateCombinationCount);
      el.addEventListener('change', updateCombinationCount);
    });

    // Refresh catalog when tasks_path changes (debounced)
    let debounceTimer;
    $('[name="tasks_path"]').addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(refreshCatalog, 400);
    });

    updateCombinationCount();
    refreshOptions();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
