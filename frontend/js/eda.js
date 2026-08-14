/**
 * InsightFlow — Exploratory Data Analysis (EDA) Engine
 */

window._edaLoaded = window._edaLoaded || false;

function resetEDA() {
  window._edaLoaded = false;
}

async function loadEDA() {
  if (_edaLoaded) return;
  const el = document.getElementById('eda-c');
  if (!el) return;
  el.innerHTML = '<div class="load-box"><div class="spin"></div><div class="ltxt">Analyzing data...</div></div>';

  try {
    const r = await authFetch(API_BASE + '/eda');
    const d = await r.json();
    if (d.error) { el.innerHTML = `<div class="load-box"><div class="ltxt" style="color:var(--amber)">${d.error}</div></div>`; return; }
    _edaLoaded = true;
    const subEl = document.getElementById('eda-s');
    if (subEl) subEl.textContent = `${d.shape.rows.toLocaleString()} records · ${d.shape.columns} features`;

    let html = '';

    // Stats grid
    html += `<div class="egrid">
      <div class="estat"><div class="elbl">Rows</div><div class="eval">${d.shape.rows.toLocaleString()}</div><div class="esub">total records</div></div>
      <div class="estat"><div class="elbl">Columns</div><div class="eval">${d.shape.columns}</div><div class="esub">total features</div></div>
      <div class="estat"><div class="elbl">Missing</div><div class="eval">${d.missing}</div><div class="esub">missing values</div></div>
      <div class="estat"><div class="elbl">Duplicates</div><div class="eval">${d.duplicates}</div><div class="esub">duplicate rows</div></div>
      <div class="estat"><div class="elbl">Numeric</div><div class="eval">${d.numeric_columns.length}</div><div class="esub">numeric features</div></div>
      <div class="estat"><div class="elbl">Categorical</div><div class="eval">${d.categorical_columns.length}</div><div class="esub">text features</div></div>
    </div>`;

    // Quality + Column types grid
    html += '<div class="qgrid">';
    html += '<div class="cc"><div class="ct">✅ Data Quality</div>';
    [['Completeness', d.quality.completeness], ['Uniqueness', d.quality.uniqueness]].forEach(([l, n]) => {
      html += `<div style="margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;margin-bottom:5px">
          <span style="font-family:var(--fm);font-size:12px;color:var(--muted)">${l}</span>
          <span style="font-family:var(--ff);font-size:16px;color:var(--lime)">${n}%</span>
        </div>
        <div style="height:2px;background:var(--s3)"><div class="qb" data-w="${n}" style="height:100%;width:0;background:var(--lime);transition:width 1.1s cubic-bezier(.4,0,.2,1)"></div></div>
      </div>`;
    });
    html += '</div>';

    // Column types
    html += '<div class="cc"><div class="ct">📋 Column Types</div>';
    d.col_info.forEach(c => {
      const color = c.is_numeric ? 'var(--lime)' : 'var(--blue)';
      html += `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line)">
        <span style="font-family:var(--fm);font-size:12.5px;color:var(--muted)">${c.name}</span>
        <span style="font-family:var(--fm);font-size:12.5px;color:${color}">${c.dtype} <span style="color:var(--muted2);font-size:10px">(${c.nulls} nulls)</span></span>
      </div>`;
    });
    html += '</div></div>';

    // Numeric stats table
    if (Object.keys(d.num_stats).length > 0) {
      html += '<div class="corrbox"><div class="ct">📊 Numeric Statistics</div>';
      html += '<div style="overflow-x:auto"><table class="dtbl"><thead><tr>';
      html += '<th>Column</th><th>Mean</th><th>Median</th><th>Std</th><th>Min</th><th>Q25</th><th>Q75</th><th>Max</th></tr></thead><tbody>';
      for (const [col, s] of Object.entries(d.num_stats)) {
        html += `<tr style="animation-delay:0s"><td><strong style="color:var(--white)">${col}</strong></td>
          <td>${s.mean}</td><td>${s.median}</td><td>${s.std}</td><td>${s.min}</td><td>${s.q25}</td><td>${s.q75}</td><td>${s.max}</td></tr>`;
      }
      html += '</tbody></table></div></div>';
    }

    // Correlation matrix
    if (d.correlation && d.correlation.columns && d.correlation.columns.length >= 2) {
      const cols = d.correlation.columns;
      const matrix = d.correlation.matrix;
      html += '<div class="corrbox"><div class="ct">🔗 Correlation Matrix</div>';
      html += `<div style="display:grid;grid-template-columns:90px repeat(${cols.length},1fr);gap:3px">`;
      html += '<div></div>' + cols.map(h => `<div style="font-family:var(--fm);font-size:10px;color:var(--muted2);text-align:center;padding:4px;overflow:hidden;text-overflow:ellipsis" title="${h}">${h.length > 8 ? h.slice(0, 7) + '…' : h}</div>`).join('');
      matrix.forEach((row, ri) => {
        html += `<div style="font-family:var(--fm);font-size:11px;color:var(--muted);display:flex;align-items:center;overflow:hidden;text-overflow:ellipsis" title="${cols[ri]}">${cols[ri].length > 10 ? cols[ri].slice(0, 9) + '…' : cols[ri]}</div>`;
        row.forEach(v => {
          const n = Math.abs(v);
          const bg = n >= 0.99 ? 'var(--lime)' : n > .7 ? 'rgba(212,255,42,.45)' : n > .4 ? 'rgba(212,255,42,.2)' : n > .2 ? 'rgba(212,255,42,.08)' : 'var(--s3)';
          const tc = n > .6 ? 'var(--black)' : 'var(--muted)';
          html += `<div style="background:${bg};padding:6px;text-align:center;font-family:var(--fm);font-size:11px;color:${tc};border-radius:2px">${v.toFixed(2)}</div>`;
        });
      });
      html += '</div></div>';
    }

    el.innerHTML = html;
    setTimeout(() => document.querySelectorAll('.qb').forEach(b => b.style.width = b.dataset.w + '%'), 100);
  } catch (e) {
    el.innerHTML = '<div class="load-box"><div class="ltxt" style="color:var(--red)">Could not load EDA — is the backend running?</div></div>';
  }
}
