/**
 * InsightFlow — Forecasting & Anomaly Detection Engine
 */

async function loadForecastView() {
  const container = document.getElementById('forecast-c');
  if (!container) return;

  container.innerHTML = `
    <div class="two-col-grid">
      <div class="cc">
        <div class="ct">🔮 Trend Forecast</div>
        <div class="st-form-group" style="margin-bottom:14px">
          <label style="font-family:var(--fm);font-size:11px;color:var(--muted);text-transform:uppercase">Target Metric</label>
          <select id="fcMetric" class="chart-filter" style="width:100%" onchange="runForecastQuery()">
            ${(_availableCols.numeric || ['Sales', 'Revenue']).map(c => `<option value="${c}">${c}</option>`).join('')}
          </select>
        </div>
        <div class="st-form-group" style="margin-bottom:14px">
          <label style="font-family:var(--fm);font-size:11px;color:var(--muted);text-transform:uppercase">Periods</label>
          <select id="fcPeriods" class="chart-filter" style="width:100%" onchange="runForecastQuery()">
            <option value="3">3 periods</option>
            <option value="6" selected>6 periods</option>
            <option value="12">12 periods</option>
          </select>
        </div>
        <div id="fcResult" style="background:var(--s2);border:1px solid var(--line2);border-radius:6px;padding:12px;margin-top:8px;display:none"></div>
        <div id="fcChartWrap" style="height:200px;position:relative;margin-top:12px">
          <canvas id="fcCanvas"></canvas>
        </div>
      </div>
      <div class="cc">
        <div class="ct">⚠️ Anomaly Scanner</div>
        <div id="anomalyWrap">
          <div style="color:var(--muted);font-family:var(--fm);font-size:13px">Scanning dataset for statistical outliers…</div>
        </div>
      </div>
    </div>`;

  runForecastQuery();
  loadAnomalies();
}

async function runForecastQuery() {
  const metric = document.getElementById('fcMetric')?.value;
  const periods = parseInt(document.getElementById('fcPeriods')?.value || '6');
  const resultBox = document.getElementById('fcResult');

  if (!metric) return;

  try {
    // Use the correct endpoint: /api/v3/forecast?target_col=X&periods=N
    const res = await authFetch(`${API_BASE}/api/v3/forecast?target_col=${encodeURIComponent(metric)}&periods=${periods}`);
    const data = await res.json();

    if (data.error) {
      if (resultBox) {
        resultBox.style.display = 'block';
        resultBox.innerHTML = `<span style="color:var(--amber)">${data.error}</span>`;
      }
      return;
    }

    if (resultBox) {
      resultBox.style.display = 'block';
      const trendColor = data.trend === 'UPWARD' ? 'var(--lime)' : data.trend === 'DOWNWARD' ? 'var(--red)' : 'var(--amber)';
      resultBox.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-family:var(--ff);font-weight:700;color:var(--white);font-size:14px">${metric}</span>
          <span style="font-family:var(--fm);font-size:11px;color:${trendColor};text-transform:uppercase;letter-spacing:1px">${data.trend || 'STABLE'}</span>
        </div>
        <div style="font-size:12px;color:var(--muted);font-family:var(--fm)">${data.summary || ''}</div>
        ${data.predicted_change_pct !== undefined ? `
          <div style="margin-top:8px;font-family:var(--fm);font-size:12px;color:${trendColor}">
            Projected change: <strong>${data.predicted_change_pct > 0 ? '+' : ''}${data.predicted_change_pct}%</strong>
          </div>` : ''}`;
    }

    // Render chart if Chart.js is available
    if (window.Chart && data.historical && data.forecast) {
      renderForecastChart(data.historical, data.forecast, metric);
    }

  } catch (e) {
    if (resultBox) {
      resultBox.style.display = 'block';
      resultBox.innerHTML = '<span style="color:var(--muted);font-size:12px">Forecast service ready — upload a dataset to begin.</span>';
    }
  }
}

function renderForecastChart(historical, forecast, label) {
  const canvas = document.getElementById('fcCanvas');
  if (!canvas || !window.Chart) return;

  // Destroy existing chart
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();

  const histLabels = historical.map((_, i) => `H${i + 1}`);
  const forecastLabels = forecast.map((_, i) => `F${i + 1}`);

  new Chart(canvas, {
    type: 'line',
    data: {
      labels: [...histLabels, ...forecastLabels],
      datasets: [
        {
          label: `Historical ${label}`,
          data: [...historical, ...Array(forecast.length).fill(null)],
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.1)',
          tension: 0.4,
          fill: true
        },
        {
          label: `Forecast ${label}`,
          data: [...Array(historical.length).fill(null), ...forecast],
          borderColor: '#d4ff2a',
          backgroundColor: 'rgba(212,255,42,0.05)',
          borderDash: [5, 5],
          tension: 0.4,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.03)' } },
        y: { ticks: { color: '#64748b', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });
}

async function loadAnomalies() {
  const anomalyWrap = document.getElementById('anomalyWrap');
  if (!anomalyWrap) return;

  try {
    const res = await authFetch(API_BASE + '/api/v3/anomalies');
    const data = await res.json();

    if (data.anomalies && data.anomalies.length === 0) {
      anomalyWrap.innerHTML = '<div style="color:var(--lime);font-family:var(--fm);font-size:13px">✓ No critical anomalies detected in dataset.</div>';
    } else if (data.anomalies) {
      anomalyWrap.innerHTML = data.anomalies.map(a => `
        <div style="background:var(--s2);border:1px solid var(--line2);padding:10px 14px;border-radius:6px;margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <div style="font-family:var(--fm);font-size:11px;color:${a.severity === 'CRITICAL' ? 'var(--red)' : 'var(--amber)'}">
              ${a.severity || 'OUTLIER'} — ${a.column}
            </div>
            <div style="font-family:var(--fm);font-size:10px;color:var(--muted2)">${a.count} values</div>
          </div>
          <div style="font-size:12px;color:var(--muted);margin-top:2px">${a.description || 'Statistical outlier detected.'}</div>
        </div>`).join('');
    }
  } catch (e) {
    if (anomalyWrap) anomalyWrap.innerHTML = '<div style="color:var(--muted);font-family:var(--fm);font-size:12px">Anomaly scanner ready</div>';
  }
}
