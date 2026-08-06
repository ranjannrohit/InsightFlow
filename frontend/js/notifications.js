/**
 * InsightFlow — Notifications System
 */

function loadNotifications() {
  const container = document.getElementById('notifications-c');
  if (!container) return;

  const mockNotifs = [
    { type: 'success', title: 'Dataset Upload Completed', desc: 'Dataset schema and numeric cleaning finished successfully.', time: '2 mins ago' },
    { type: 'info', title: 'AI Insights Ready', desc: 'Executive insights synthesized for 4 primary dimensions.', time: '10 mins ago' },
    { type: 'warn', title: 'Outliers Detected', desc: 'Statistical anomalies identified in target metric series.', time: '1 hour ago' }
  ];

  container.innerHTML = mockNotifs.map(n => `
    <div class="nf-card" style="display:flex;gap:14px;align-items:flex-start;background:var(--s1);border:1px solid var(--line2);padding:14px 18px;border-radius:8px;margin-bottom:10px">
      <div class="nf-icon ${n.type}">⚡</div>
      <div class="nf-body">
        <div class="nf-title" style="font-family:var(--ff);font-weight:600;color:var(--white);font-size:14px">${n.title}</div>
        <div class="nf-desc" style="font-size:13px;color:var(--muted);margin-top:2px">${n.desc}</div>
        <div class="nf-time" style="font-family:var(--fm);font-size:11px;color:var(--muted2);margin-top:6px">${n.time}</div>
      </div>
    </div>`).join('');
}
