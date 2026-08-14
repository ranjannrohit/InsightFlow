/**
 * InsightFlow — Dashboard & Executive Analytics Engine
 */

window.cur = window.cur || null;
window._availableCols = window._availableCols || { numeric: [], categorical: [], all: [] };

async function renderDashboard(s) {
  cur = s;
  document.getElementById('dh').textContent = s.name.replace(/\.[^.]+$/, '');
  document.getElementById('ds').textContent = `${s.rows.toLocaleString()} records · ${s.columns} features · pipeline complete`;

  try {
    const chartData = await fetchChartData();
    _availableCols = chartData.available || { numeric: [], categorical: [], all: [] };

    if (chartData.domain) {
      document.getElementById('domainBadge').textContent = '⚡ AI DOMAIN: ' + chartData.domain.toUpperCase();
    }

    populateFilters();
    populateCustomWidgetSelects();
    if (typeof initVsStudioControls === 'function') initVsStudioControls();

    renderKPIs(chartData.kpis || []);

    if (chartData.line) renderLineChart(chartData.line);
    if (chartData.bar) renderBarChart(chartData.bar);
    if (chartData.donut) renderDonut(chartData.donut);

    if (typeof setSt === 'function') setSt('ok', 'Analysis complete');
  } catch (e) {
    console.error('Dashboard load error:', e);
    if (typeof setSt === 'function') setSt('error', 'Could not load charts');
  }

  fetchInsights();
}

function renderKPIs(kpis) {
  const container = document.getElementById('krow');
  if (!container) return;

  container.innerHTML = kpis.map((kpi, index) => `
    <div class="kpi" id="${kpi.id || 'kpi_' + index}">
      <div class="klbl">${kpi.title || kpi.label}</div>
      <div class="kval">${kpi.value}</div>
      <div class="kdelta ${kpi.up ? 'up' : 'dn'}">${kpi.delta}</div>
    </div>
  `).join('');
}

function populateFilters() {
  const lf = document.getElementById('lineFilter');
  if (lf && _availableCols.numeric.length) {
    lf.innerHTML = _availableCols.numeric.map(c => `<option value="${c}">${c}</option>`).join('');
  }

  const bf = document.getElementById('barFilter');
  if (bf) {
    const barCols = [..._availableCols.categorical, ..._availableCols.numeric];
    bf.innerHTML = barCols.map(c => `<option value="${c}">${c}</option>`).join('');
  }

  const df = document.getElementById('donutFilter');
  if (df) {
    const donutCols = _availableCols.categorical.length > 0 ? _availableCols.categorical : _availableCols.all;
    df.innerHTML = donutCols.map(c => `<option value="${c}">${c}</option>`).join('');
  }
}

function populateCustomWidgetSelects() {
  const cwX = document.getElementById('cwX');
  const cwY = document.getElementById('cwY');
  if (!cwX || !cwY || !_availableCols) return;

  const allCols = [..._availableCols.categorical, ..._availableCols.numeric];
  cwX.innerHTML = allCols.map(c => `<option value="${c}">${c}</option>`).join('');

  const numCols = _availableCols.numeric.length ? _availableCols.numeric : allCols;
  cwY.innerHTML = numCols.map(c => `<option value="${c}">${c}</option>`).join('');
}

async function onFilterChange(type) {
  const barCol = document.getElementById('barFilter')?.value;
  const lineCol = document.getElementById('lineFilter')?.value;
  const donutCol = document.getElementById('donutFilter')?.value;
  const barAgg = document.getElementById('barAgg')?.value || 'SUM';

  try {
    const data = await fetchChartData(
      type === 'bar' ? barCol : null,
      type === 'line' ? lineCol : null,
      type === 'donut' ? donutCol : null,
      barAgg
    );
    if (type === 'bar' && data.bar) renderBarChart(data.bar);
    if (type === 'line' && data.line) renderLineChart(data.line);
    if (type === 'donut' && data.donut) renderDonut(data.donut);
  } catch (e) {
    console.error('Filter error:', e);
  }
}

function applyDashboardPreset(preset) {
  if (!_availableCols) return;
  if (preset === 'overview') {
    populateFilters();
    onFilterChange('bar');
    onFilterChange('line');
    onFilterChange('donut');
  } else if (preset === 'trends' && _availableCols.numeric.length > 0) {
    document.getElementById('lineFilter').value = _availableCols.numeric[0];
    onFilterChange('line');
  } else if (preset === 'category' && _availableCols.categorical.length > 0) {
    document.getElementById('barFilter').value = _availableCols.categorical[0];
    document.getElementById('barAgg').value = 'COUNT';
    onFilterChange('bar');
  } else if (preset === 'metrics' && _availableCols.numeric.length > 1) {
    document.getElementById('barFilter').value = _availableCols.numeric[1];
    document.getElementById('barAgg').value = 'AVG';
    onFilterChange('bar');
  }
}
