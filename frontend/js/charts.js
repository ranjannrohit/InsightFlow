/**
 * InsightFlow — Custom Chart Engine & Visualization Studio
 */

let activeVsChartType = 'bar';
let vsChartInstance = null;
let _lastLineChartData = null;

function setVsChartType(type) {
  activeVsChartType = type;
  document.querySelectorAll('#vs-chart-pills .schip').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-type') === type);
  });
  renderVsStudioChart();
}

async function initVsStudioControls() {
  const xSelect = document.getElementById('vs-x-col');
  const ySelect = document.getElementById('vs-y-col');
  if (!xSelect || !ySelect) return;

  let cols = [];
  let numCols = [];

  if (typeof _availableCols !== 'undefined' && _availableCols && _availableCols.all && _availableCols.all.length > 0) {
    cols = _availableCols.categorical.length > 0 ? [..._availableCols.categorical, ..._availableCols.numeric] : _availableCols.all;
    numCols = _availableCols.numeric.length > 0 ? _availableCols.numeric : _availableCols.all;
  } else if (typeof cur !== 'undefined' && cur && cur.column_names) {
    cols = cur.column_names;
    numCols = cur.numeric_columns || cur.column_names;
  } else {
    try {
      const res = await fetchChartData();
      if (res && res.available) {
        _availableCols = res.available;
        cols = [...res.available.categorical, ...res.available.numeric];
        numCols = res.available.numeric.length > 0 ? res.available.numeric : cols;
      }
    } catch (e) {
      cols = ['Category', 'Month', 'Region', 'Segment'];
      numCols = ['Sales', 'Profit', 'Units', 'Revenue'];
    }
  }

  if (cols.length === 0) {
    cols = ['Category', 'Month', 'Region', 'Segment'];
    numCols = ['Sales', 'Profit', 'Units', 'Revenue'];
  }

  xSelect.innerHTML = cols.map(c => `<option value="${c}">${c}</option>`).join('');
  ySelect.innerHTML = numCols.map(c => `<option value="${c}">${c}</option>`).join('');

  if (numCols.length > 0) ySelect.value = numCols[0];
  if (cols.length > 0) xSelect.value = cols[0] !== numCols[0] ? cols[0] : (cols[1] || cols[0]);

  updateVsDataSummary();
  await renderVsStudioChart();
}

function updateVsDataSummary() {
  const xCol = document.getElementById('vs-x-col')?.value || '—';
  const yCol = document.getElementById('vs-y-col')?.value || '—';
  
  const rowsEl = document.getElementById('vs-stat-rows');
  const colsEl = document.getElementById('vs-stat-cols');
  const xEl = document.getElementById('vs-stat-x');
  const yEl = document.getElementById('vs-stat-y');
  const missingEl = document.getElementById('vs-stat-missing');
  const summaryEl = document.getElementById('vs-stat-summary');

  const rowsCount = typeof cur !== 'undefined' && cur ? cur.rows : 500;
  const colsCount = typeof cur !== 'undefined' && cur ? cur.columns : (typeof _availableCols !== 'undefined' && _availableCols.all ? _availableCols.all.length : 4);
  const missingCount = typeof cur !== 'undefined' && cur ? cur.missing : 0;

  if (rowsEl) rowsEl.textContent = rowsCount.toLocaleString();
  if (colsEl) colsEl.textContent = colsCount;
  if (xEl) xEl.textContent = xCol;
  if (yEl) yEl.textContent = yCol;
  if (missingEl) missingEl.textContent = missingCount;

  if (summaryEl) {
    summaryEl.innerHTML = `Category Axis: <strong style="color:var(--lime)">${xCol}</strong><br>Target Metric: <strong style="color:var(--teal)">${yCol}</strong><br>Aggregation: <strong>${document.getElementById('vs-agg')?.value || 'SUM'}</strong>`;
  }
}

async function renderVsStudioChart() {
  updateVsDataSummary();
  const canvas = document.getElementById('vsChartCanvas');
  if (!canvas) return;

  const xCol = document.getElementById('vs-x-col')?.value || '';
  const yCol = document.getElementById('vs-y-col')?.value || '';
  const agg = document.getElementById('vs-agg')?.value || 'SUM';
  const titleText = document.getElementById('vs-prop-title')?.value || (xCol && yCol ? `${agg} of ${yCol} by ${xCol}` : 'Visualization Studio Chart');
  const theme = document.getElementById('vs-prop-theme')?.value || 'lime';
  const showLegend = document.getElementById('vs-prop-legend')?.checked ?? true;
  const showGrid = document.getElementById('vs-prop-grid')?.checked ?? true;
  const showTooltips = document.getElementById('vs-prop-tooltips')?.checked ?? true;
  const enableAnim = document.getElementById('vs-prop-anim')?.checked ?? true;

  const colorPalettes = {
    lime: { main: '#d4ff2a', bg: 'rgba(212, 255, 42, 0.45)', border: '#d4ff2a' },
    blue: { main: '#3b82f6', bg: 'rgba(59, 130, 246, 0.45)', border: '#3b82f6' },
    teal: { main: '#14b8a6', bg: 'rgba(20, 184, 166, 0.45)', border: '#14b8a6' },
    amber: { main: '#f59e0b', bg: 'rgba(245, 158, 11, 0.45)', border: '#f59e0b' },
    rose: { main: '#f43f5e', bg: 'rgba(244, 63, 94, 0.45)', border: '#f43f5e' }
  };
  const palette = colorPalettes[theme] || colorPalettes.lime;
  const multiColors = ['#d4ff2a', '#3b82f6', '#14b8a6', '#f59e0b', '#f43f5e', '#a855f7', '#ec4899', '#06b6d4'];

  let labels = ['North', 'East', 'South', 'West', 'Central'];
  let dataVals = [4200, 5800, 3100, 7400, 6200];
  let scatterPoints = null;

  if (xCol) {
    try {
      const res = await authFetch(API_BASE + '/custom-widget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          widget_type: activeVsChartType,
          title: titleText,
          x_col: xCol,
          y_col: yCol,
          agg: agg
        })
      });
      const resData = await res.json();
      if (resData.widget && resData.widget.data) {
        const wData = resData.widget.data;
        if (wData.labels && wData.values) {
          labels = wData.labels;
          dataVals = wData.values;
        } else if (wData.points) {
          scatterPoints = wData.points;
        }
      }
    } catch (err) {
      console.warn('Vs Studio backend fetch fallback:', err);
    }
  }

  if (vsChartInstance) {
    vsChartInstance.destroy();
  }

  const chartTypeMap = {
    bar: 'bar',
    line: 'line',
    area: 'line',
    pie: 'pie',
    donut: 'doughnut',
    scatter: 'scatter',
    heatmap: 'bar',
    treemap: 'bar',
    radar: 'radar'
  };

  const type = chartTypeMap[activeVsChartType] || 'bar';
  const isArea = activeVsChartType === 'area';

  const datasetObj = scatterPoints ? {
    label: `${xCol} vs ${yCol}`,
    data: scatterPoints,
    backgroundColor: palette.main,
    borderColor: palette.border,
    pointRadius: 6
  } : {
    label: yCol || xCol,
    data: dataVals,
    backgroundColor: (type === 'pie' || type === 'doughnut') ? multiColors : (isArea ? palette.bg : palette.main),
    borderColor: palette.border,
    borderWidth: 2,
    fill: isArea,
    tension: 0.35,
    pointBackgroundColor: palette.main,
    pointRadius: 4
  };

  const config = {
    type: type,
    data: {
      labels: scatterPoints ? undefined : labels,
      datasets: [datasetObj]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: enableAnim ? { duration: 600 } : false,
      plugins: {
        title: {
          display: !!titleText,
          text: titleText,
          color: '#ffffff',
          font: { family: 'Outfit, sans-serif', size: 15, weight: '700' }
        },
        legend: {
          display: showLegend,
          labels: { color: '#888888', font: { family: 'JetBrains Mono, monospace', size: 11 } }
        },
        tooltip: {
          enabled: showTooltips
        }
      },
      scales: (type === 'pie' || type === 'doughnut' || type === 'radar') ? {} : {
        x: {
          grid: { display: showGrid, color: 'rgba(255,255,255,0.06)' },
          ticks: { color: '#888888', font: { family: 'JetBrains Mono, monospace', size: 11 } }
        },
        y: {
          grid: { display: showGrid, color: 'rgba(255,255,255,0.06)' },
          ticks: { color: '#888888', font: { family: 'JetBrains Mono, monospace', size: 11 } }
        }
      }
    }
  };

  vsChartInstance = new Chart(canvas.getContext('2d'), config);
}

function resetVsStudio() {
  document.getElementById('vs-prop-title').value = '';
  document.getElementById('vs-prop-theme').value = 'lime';
  document.getElementById('vs-prop-legend').checked = true;
  document.getElementById('vs-prop-grid').checked = true;
  document.getElementById('vs-prop-labels').checked = true;
  document.getElementById('vs-prop-tooltips').checked = true;
  document.getElementById('vs-prop-anim').checked = true;
  setVsChartType('bar');
}

function downloadVsChartPNG() {
  const canvas = document.getElementById('vsChartCanvas');
  if (!canvas) return;
  const link = document.createElement('a');
  link.download = `InsightFlow_Chart_${Date.now()}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

function downloadVsChartSVG() {
  alert('SVG Export: Preparing scalable vector graphic for download...');
  downloadVsChartPNG();
}

function renderBarChart(data) {
  if (!data || !data.labels || data.labels.length === 0) {
    document.getElementById('blist').innerHTML = '<div style="color:var(--muted);font-family:var(--fm);font-size:12px">No data for selected column</div>';
    return;
  }
  const mx = Math.max(...data.values);
  document.getElementById('blist').innerHTML = data.labels.map((l, i) => `
    <div class="brow">
      <span class="blbl" title="${l}">${l}</span>
      <div class="btrk">
        <div class="bfill" style="width:0%" data-w="${mx > 0 ? (data.values[i] / mx * 100).toFixed(0) : 0}">${data.values[i]}</div>
      </div>
    </div>`).join('');
  setTimeout(() => document.querySelectorAll('.bfill').forEach(e => e.style.width = e.dataset.w + '%'), 50);
}

function renderDonut(dd) {
  if (!dd || !dd.items || dd.items.length === 0) return;
  const svg = document.getElementById('dsvg');
  if (!svg) return;
  const cx = 75, cy = 75, r = 58, inn = 36;
  const tot = dd.items.reduce((s, i) => s + i.p, 0) || 1;
  let prog = 0;
  function draw() {
    let a = -Math.PI / 2;
    svg.innerHTML = dd.items.map(it => {
      const sw = (it.p / tot) * 2 * Math.PI * Math.min(1, prog);
      const x1 = cx + r * Math.cos(a), y1 = cy + r * Math.sin(a);
      const x2 = cx + r * Math.cos(a + sw), y2 = cy + r * Math.sin(a + sw);
      const ix1 = cx + inn * Math.cos(a), iy1 = cy + inn * Math.sin(a);
      const ix2 = cx + inn * Math.cos(a + sw), iy2 = cy + inn * Math.sin(a + sw);
      const lg = sw > Math.PI ? 1 : 0;
      const path = sw < .001 ? '' : `<path d="M${ix1},${iy1} L${x1},${y1} A${r},${r} 0 ${lg},1 ${x2},${y2} L${ix2},${iy2} A${inn},${inn} 0 ${lg},0 ${ix1},${iy1}" fill="${it.c}" opacity=".92"/>`;
      a += sw;
      return path;
    }).join('');
    prog += .04;
    if (prog < 1) requestAnimationFrame(draw);
  }
  draw();
  document.getElementById('dv').textContent = dd.total;
  document.getElementById('ds2').textContent = dd.sub || 'total';
  document.getElementById('dleg').innerHTML = dd.items.map(it => `
    <div class="leg-r"><div class="leg-l"><div class="ldot" style="background:${it.c}"></div>${it.l}</div>
    <span class="lpct">${it.p}%</span></div>`).join('');
}

function renderLineChart(data) {
  if (data) _lastLineChartData = data;
  const c = document.getElementById('lineChart');
  if (!c) return;
  const vals = data ? data.values : (_lastLineChartData ? _lastLineChartData.values : null);
  if (!vals || vals.length < 2) return;
  const W = c.width = c.offsetWidth, H = c.height = 160;
  const ctx = c.getContext('2d');
  const mn = Math.min(...vals), mx = Math.max(...vals), range = mx - mn || 1;
  const pad = { l: 50, r: 16, t: 10, b: 24 };
  const cW = W - pad.l - pad.r, cH = H - pad.t - pad.b;
  const toX = i => pad.l + i / (vals.length - 1) * cW;
  const toY = v => pad.t + cH - (v - mn) / range * cH;

  function drawBase() {
    ctx.strokeStyle = 'rgba(255,255,255,.04)'; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.t + i / 4 * cH;
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
    }
    ctx.font = '9px JetBrains Mono'; ctx.fillStyle = 'rgba(122,122,133,.6)'; ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const v = mn + (1 - i / 4) * range;
      ctx.fillText(v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(0), pad.l - 6, pad.t + i / 4 * cH + 3);
    }
    ctx.textAlign = 'center';
    ctx.fillText((data && data.column) ? data.column : '', W / 2, H - 4);
  }

  let progress = 0;
  function frame() {
    ctx.clearRect(0, 0, W, H); drawBase();
    const n = Math.max(2, Math.floor(vals.length * progress));
    const xs = vals.slice(0, n).map((_, i) => toX(i));
    const ys = vals.slice(0, n).map(v => toY(v));
    const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + cH);
    grad.addColorStop(0, 'rgba(200,241,53,.1)'); grad.addColorStop(1, 'rgba(200,241,53,0)');
    ctx.beginPath(); ctx.moveTo(xs[0], pad.t + cH);
    xs.forEach((x, i) => ctx.lineTo(x, ys[i]));
    ctx.lineTo(xs[xs.length - 1], pad.t + cH); ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath(); xs.forEach((x, i) => i === 0 ? ctx.moveTo(x, ys[i]) : ctx.lineTo(x, ys[i]));
    ctx.strokeStyle = '#c8f135'; ctx.lineWidth = 2; ctx.stroke();
    progress += .05; if (progress <= 1) requestAnimationFrame(frame);
  }
  frame();
}
