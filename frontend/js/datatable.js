/**
 * InsightFlow — Interactive Data Table Renderer
 */

window._tableLoaded = window._tableLoaded || false;
window._sortDir = window._sortDir || {};

function resetDataTable() {
  window._tableLoaded = false;
}

async function loadDataTable() {
  if (_tableLoaded) return;
  const el = document.getElementById('data-c');
  if (!el) return;
  el.innerHTML = '<div class="load-box"><div class="spin"></div><div class="ltxt">Loading data...</div></div>';

  try {
    const r = await authFetch(API_BASE + '/data?limit=500');
    const d = await r.json();
    if (d.error) { el.innerHTML = `<div class="load-box"><div class="ltxt" style="color:var(--amber)">${d.error}</div></div>`; return; }
    _tableLoaded = true;

    const cols = d.columns;
    const rows = d.rows;

    el.innerHTML = `
    <div class="tbar">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <span class="ttag">${d.total_rows.toLocaleString()} ROWS</span>
        <span class="ttag">${cols.length} COLS</span>
        <span class="ttag g">✓ LOADED</span>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <input class="tsrch" placeholder="🔍 search..." oninput="filterTable(this.value)">
        <button onclick="window.open(API_BASE+'/download','_blank')" style="background:var(--lime);color:var(--black);border:none;padding:9px 18px;font-family:var(--ff);font-size:14px;letter-spacing:1px;cursor:pointer;border-radius:var(--radius-sm)">↓ CSV</button>
      </div>
    </div>
    <div class="twrap">
      <div class="thead-row">
        <span style="font-family:var(--ff);font-size:15px;letter-spacing:1px;font-weight:600">DATA TABLE</span>
        <span class="tmeta" id="tCount">Showing ${d.showing} of ${d.total_rows}</span>
      </div>
      <div style="overflow-x:auto;max-height:520px;overflow-y:auto">
        <table class="dtbl" id="mainTable">
          <thead style="position:sticky;top:0;z-index:2">
            <tr>${cols.map((c, i) => `<th onclick="sortTable(${i})">${c} ↕</th>`).join('')}</tr>
          </thead>
          <tbody id="tb">
            ${rows.map((row, ri) => `
              <tr style="animation-delay:${Math.min(ri * .015, .3)}s">
                ${cols.map(c => {
                  const v = row[c];
                  return `<td>${v === '' || v === null || v === undefined ? '<span style="color:var(--muted2);font-style:italic;font-size:12px">null</span>' : v}</td>`;
                }).join('')}
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
  } catch (e) {
    el.innerHTML = '<div class="load-box"><div class="ltxt" style="color:var(--red)">Backend offline</div></div>';
  }
}

function filterTable(q) {
  const rows = document.querySelectorAll('#tb tr');
  let v = 0;
  rows.forEach(r => {
    const show = r.textContent.toLowerCase().includes(q.toLowerCase());
    r.style.display = show ? '' : 'none';
    if (show) v++;
  });
  const el = document.getElementById('tCount');
  if (el) el.textContent = `Showing ${v} rows${q ? ' (filtered)' : ''}`;
}

function sortTable(ci) {
  const tb = document.getElementById('tb');
  if (!tb) return;
  const rows = Array.from(tb.querySelectorAll('tr'));
  _sortDir[ci] = !_sortDir[ci];
  rows.sort((a, b) => {
    const av = a.cells[ci]?.textContent.trim() || '';
    const bv = b.cells[ci]?.textContent.trim() || '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return _sortDir[ci] ? an - bn : bn - an;
    return _sortDir[ci] ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(r => tb.appendChild(r));
}
