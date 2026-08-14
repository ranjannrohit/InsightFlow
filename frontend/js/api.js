/**
 * InsightFlow — API Client Services
 * Centralized API endpoints & fetch utilities
 */

window.API_BASE = window.API_BASE || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? "http://127.0.0.1:8000"
  : "https://insightflow-backend-dedb.onrender.com");

window.authFetch = async function authFetch(url, options = {}) {
  options = options || {};
  options.headers = options.headers || {};
  const token = typeof getAuthToken === 'function' ? getAuthToken() : (localStorage.getItem('auth_token') || '');
  if (token) {
    options.headers['Authorization'] = `Bearer ${token}`;
  }
  return fetch(url, options);
};

async function uploadToBackend(csvContent, filename) {
  const blob = new Blob([csvContent], { type: 'text/csv' });
  const file = new File([blob], filename, { type: 'text/csv' });
  const fd = new FormData();
  fd.append('file', file);
  const res = await authFetch(API_BASE + '/upload', { method: 'POST', body: fd });
  return await res.json();
}

async function fetchChartData(barCol, lineCol, donutCol, barAgg) {
  let url = API_BASE + '/chart-data';
  const params = [];
  if (barCol) params.push('bar_col=' + encodeURIComponent(barCol));
  if (lineCol) params.push('line_col=' + encodeURIComponent(lineCol));
  if (donutCol) params.push('donut_col=' + encodeURIComponent(donutCol));
  if (barAgg) params.push('agg=' + encodeURIComponent(barAgg));
  if (params.length) url += '?' + params.join('&');
  const r = await authFetch(url);
  return await r.json();
}

async function fetchInsights() {
  const box = document.getElementById('insBox');
  if (!box) return;
  box.innerHTML = `
    <div style="padding:20px;text-align:center">
      <div class="spin" style="margin:0 auto 12px"></div>
      <div class="ltxt">AI Agent analyzing dataset...</div>
    </div>`;
  try {
    const res = await authFetch(API_BASE + '/insights');
    const data = await res.json();
    if (data.error) {
      box.innerHTML = `<div style="padding:16px;color:var(--red);font-family:var(--fm);font-size:13px">${data.error}</div>`;
      return;
    }
    const tags = { ok: 'INSIGHT', warn: 'WARNING', bad: 'RISK' };
    const html = (data.insights || []).map((ins, i) => `
      <li class="ins-li" style="animation-delay:${i * 0.07}s">
        <span class="ins-n">0${i + 1}</span>
        <span class="ins-tag ${ins.tag}">${tags[ins.tag] || 'NOTE'}</span>
        <span>${ins.text}</span>
      </li>`).join('');
    box.innerHTML = `<ul class="ins-list">${html}</ul>`;
  } catch (e) {
    box.innerHTML = `<div style="padding:16px;color:var(--muted);font-family:var(--fm);font-size:13px">AI insights unavailable — start backend with uvicorn</div>`;
  }
}
