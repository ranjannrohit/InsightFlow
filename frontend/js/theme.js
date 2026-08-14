/**
 * InsightFlow — Theme Management (Dark & Light Mode)
 * Default Theme: Light Mode (Warm Light Orange Atmosphere)
 */

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
    btn.innerHTML = next === 'dark' ? '☀️' : '🌙';
  });
}

(function initTheme() {
  const saved = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      btn.innerHTML = saved === 'dark' ? '☀️' : '🌙';
    });
  });
})();
