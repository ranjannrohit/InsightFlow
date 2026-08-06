/**
 * InsightFlow — SQL Playground Query Engine
 */

function setSQL(q) {
  const el = document.getElementById('sqlInput');
  if (el) el.value = q;
}

async function runSQL() {
  const query = document.getElementById('sqlInput')?.value.trim();
  const box = document.getElementById('sqlResults');
  if (!box) return;
  if (!query) { box.innerHTML = '<span style="color:var(--amber)">Please enter a SQL query.</span>'; return; }
  box.innerHTML = '<span style="font-family:var(--fm);font-size:13px;color:var(--muted2)">Running query…</span>';

  try {
    const r = await authFetch(API_BASE + '/run-sql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const data = await r.json();
    if (data.error) { box.innerHTML = `<span style="color:var(--red)">Error: ${data.error}</span>`; return; }
    if (!data.rows || data.rows.length === 0) { box.innerHTML = '<span style="color:var(--muted2)">Query returned 0 rows.</span>'; return; }

    let html = `<div style="font-family:var(--fm);font-size:10px;color:var(--muted2);margin-bottom:12px">${data.row_count || data.rows.length} row(s) returned</div>`;
    html += '<div style="overflow-x:auto"><table class="dtbl"><thead><tr>';
    data.columns.forEach(col => html += `<th>${col}</th>`);
    html += '</tr></thead><tbody>';
    data.rows.forEach(row => {
      html += '<tr>';
      row.forEach(cell => html += `<td>${cell === '' || cell === null ? '—' : cell}</td>`);
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = '<span style="color:var(--red)">Backend query execution failed.</span>';
  }
}
