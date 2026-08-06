/**
 * InsightFlow — Executive Reports Builder
 */

let _reportLoaded = false;

async function loadReport() {
  if (_reportLoaded) return;
  if (!cur) return;
  _reportLoaded = true;
  const el = document.getElementById('rep-c');
  if (!el) return;

  const s = cur;
  const completeness = ((1 - s.missing / Math.max(s.rows * s.columns, 1)) * 100).toFixed(1);

  el.innerHTML = `
  <div class="erow">
    <button class="ebtn" onclick="gv('chat')">🤖 Ask AI to expand →</button>
    <button class="ebtn" onclick="downloadReport()">↓ Download PDF</button>
  </div>
  <div class="rcard">
    <h3>📊 Executive Summary</h3>
    <p class="rp">Analysis of <strong>${s.name}</strong> reveals a dataset with <strong>${s.rows.toLocaleString()} records</strong> across <strong>${s.columns} features</strong>. The dataset contains <strong>${s.numeric_columns.length} numeric</strong> and <strong>${s.categorical_columns ? s.categorical_columns.length : s.columns - s.numeric_columns.length} categorical</strong> columns.</p>
  </div>
  <div class="rcard">
    <h3>🔍 Data Quality</h3>
    <p class="rp">
      Dataset completeness: <strong>${completeness}%</strong><br>
      Missing values: <strong>${s.missing}</strong> across the dataset<br>
      Duplicate rows: <strong>${s.duplicates}</strong> detected<br>
      Numeric columns: <strong>${s.numeric_columns.join(', ') || 'None'}</strong>
    </p>
  </div>
  <div class="rcard">
    <h3>💡 Recommendations</h3>
    <p class="rp">
      <strong>01.</strong> ${s.missing > 0 ? 'Address ' + s.missing + ' missing values through imputation or removal' : 'Dataset is complete — no missing values to handle'}<br><br>
      <strong>02.</strong> ${s.duplicates > 0 ? 'Review and remove ' + s.duplicates + ' duplicate rows' : 'No duplicate rows — data is unique'}<br><br>
      <strong>03.</strong> Use the <strong>Ask AI</strong> feature for deeper analysis of specific columns<br><br>
      <strong>04.</strong> Run SQL queries in the <strong>SQL Playground</strong> for custom aggregations
    </p>
  </div>`;
}

function downloadReport() {
  window.print();
}
