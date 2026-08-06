/**
 * InsightFlow — User & Workspace Settings
 */

function switchSettingsTab(tabName) {
  document.querySelectorAll('.st-tab').forEach(tab => {
    tab.classList.toggle('active', tab.getAttribute('data-tab') === tabName);
  });
  document.querySelectorAll('.st-section').forEach(sec => {
    sec.style.display = sec.id === `st-sec-${tabName}` ? 'block' : 'none';
  });
}
