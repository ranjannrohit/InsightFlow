/**
 * InsightFlow — AI Analyst Chat System
 */

async function checkAIStatus() {
  try {
    const r = await authFetch(API_BASE + '/status');
    const d = await r.json();
    const stxt = document.getElementById('stxt');
    if (d.ai_provider === 'groq') { if (stxt) stxt.textContent = 'Groq AI ready'; }
    else if (d.ai_provider === 'gemini') { if (stxt) stxt.textContent = 'Gemini AI ready'; }
    else { if (stxt) stxt.textContent = 'Local analysis mode'; }
  } catch (e) {
    console.log('Status check failed:', e);
  }
}

function qa(btn) {
  const t = btn.textContent.replace(/^[\p{Emoji}\s]+/u, '').trim();
  document.getElementById('cin').value = t;
  doChat();
}

async function doChat() {
  const inp = document.getElementById('cin');
  const q = inp.value.trim();
  if (!q) return;
  inp.value = '';
  addM('user', q);
  const el = addM('ai', '<span class="td"></span><span class="td"></span><span class="td"></span>', true);

  try {
    const r = await authFetch(API_BASE + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });
    const data = await r.json();

    if (data.error) {
      el.querySelector('.cbody').innerHTML = `<span style="color:var(--amber)">⚠ ${data.error}</span>`;
      return;
    }

    let html = data.answer
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code style="background:var(--black);padding:1px 6px;font-family:var(--fm);font-size:11px;color:var(--lime)">$1</code>')
      .replace(/^- (.*)/gm, '<br>• $1')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');

    if (data.table && data.table.rows && data.table.rows.length > 0) {
      html += `<div style="margin-top:16px">
    <div style="font-family:var(--fm);font-size:9px;color:var(--muted2);letter-spacing:1.5px;margin-bottom:8px">
      QUERY RESULT — ${data.table.rows.length} rows
      ${data.table.sql ? `<code style="font-size:9px;color:var(--muted);background:var(--s3);padding:2px 6px;margin-left:8px">${data.table.sql.substring(0, 80)}</code>` : ''}
    </div>
    <div style="overflow-x:auto;max-height:280px;overflow-y:auto;border:1px solid var(--line2);border-radius:6px">
      <table class="dtbl">
        <thead><tr>${data.table.columns.map(c => `<th>${c}</th>`).join('')}</tr></thead>
        <tbody>${data.table.rows.map(row => `<tr>${row.map(cell => `<td>${cell === '' ? '—' : cell}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  </div>`;
    }

    if (data.provider) {
      html += `<div style="margin-top:8px"><span class="provider-badge ${data.provider}">${data.provider.toUpperCase()}</span></div>`;
    }

    el.querySelector('.cbody').innerHTML = html;
  } catch (e) {
    el.querySelector('.cbody').innerHTML = `❌ <strong>Connection Error</strong><br><span style="color:var(--muted2);font-size:12px">Backend not running at <code style="color:var(--lime)">${API_BASE}</code></span>`;
  }
}

function addM(type, html, ret) {
  const w = document.getElementById('cmsgs'), d = document.createElement('div');
  if (!w) return null;
  d.className = 'cmsg' + (type === 'user' ? ' user' : '');
  d.innerHTML = `<div class="cav ${type === 'ai' ? 'ai' : 'u'}">${type === 'ai' ? 'IF' : 'U'}</div><div class="cbody">${html}</div>`;
  w.appendChild(d);
  w.scrollTop = w.scrollHeight;
  return ret ? d : null;
}
