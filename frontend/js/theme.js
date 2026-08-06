/**
 * InsightFlow — Theme Management (Dark & Light Mode)
 */

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
    btn.innerHTML = next === 'dark' ? '🌙' : '☀️';
  });
}

(function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      btn.innerHTML = saved === 'dark' ? '🌙' : '☀️';
    });
  });
})();
