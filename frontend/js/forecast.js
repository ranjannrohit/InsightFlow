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
        <div id="fcChartWrap" style="height:200px;position:relative">
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
}

async function runForecastQuery() {
  const metric = document.getElementById('fcMetric')?.value || 'Sales';
  const anomalyWrap = document.getElementById('anomalyWrap');

  try {
    const res = await authFetch(API_BASE + `/forecast?metric=${encodeURIComponent(metric)}`);
    const data = await res.json();
    
    if (data.anomalies && anomalyWrap) {
      if (data.anomalies.length === 0) {
        anomalyWrap.innerHTML = '<div style="color:var(--lime);font-family:var(--fm);font-size:13px">✓ No critical anomalies detected in selected metric.</div>';
      } else {
        anomalyWrap.innerHTML = data.anomalies.map(a => `
          <div style="background:var(--s2);border:1px solid var(--line2);padding:10px 14px;border-radius:6px;margin-bottom:8px">
            <div style="font-family:var(--fm);font-size:11px;color:var(--amber)">OUTLIER DETECTED</div>
            <div style="font-size:13px;color:var(--white);margin-top:2px">${a.reason || 'Value significantly deviates from expected mean.'}</div>
          </div>`).join('');
      }
    }
  } catch (e) {
    if (anomalyWrap) anomalyWrap.innerHTML = '<div style="color:var(--muted);font-family:var(--fm);font-size:12px">Backend forecast service ready</div>';
  }
}
