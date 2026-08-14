/**
 * InsightFlow — Sidebar & Workspace Navigation
 */

const PAGE_TITLES = {
  dashboard: 'Dashboard',
  eda: 'Exploratory Data Analysis',
  data: 'Data Table',
  cleaning: 'Data Cleaning Log',
  report: 'Executive Reports',
  chat: 'Ask AI',
  sql: 'SQL Playground',
  agentic: 'Agent Execution Timeline',
  forecast: 'Forecasting & Anomalies',
  segmentation: 'Recommendations & RFM',
  rootcause: 'Root Cause Engine',
  export: 'Export Center',
  notifications: 'Notifications',
  settings: 'Settings',
  history: 'History',
  tutorial: 'Visualization Tutorial',
  studio: 'Visualization Studio'
};

function toggleMobileSidebar() {
  const aside = document.querySelector('.aside');
  if (!aside) return;
  if (aside.classList.contains('mobile-open')) {
    closeMobileSidebar();
  } else {
    openMobileSidebar();
  }
}

function openMobileSidebar() {
  const aside = document.querySelector('.aside');
  const backdrop = document.getElementById('asideBackdrop');
  if (aside) aside.classList.add('mobile-open');
  if (backdrop) backdrop.classList.add('active');
}

function closeMobileSidebar() {
  const aside = document.querySelector('.aside');
  const backdrop = document.getElementById('asideBackdrop');
  if (aside) aside.classList.remove('mobile-open');
  if (backdrop) backdrop.classList.remove('active');
}

function toggleSidebarCollapse() {
  const app = document.getElementById('app');
  if (!app) return;
  app.classList.toggle('sidebar-collapsed');
  const isCollapsed = app.classList.contains('sidebar-collapsed');
  localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false');

  const chk = document.getElementById('stCompactNav');
  if (chk) chk.checked = isCollapsed;

  // Trigger window resize so canvas / SVG charts adapt seamlessly
  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, 260);
}

function initSidebarState() {
  if (localStorage.getItem('sidebar_collapsed') === 'true') {
    const applyCollapse = () => {
      const app = document.getElementById('app');
      if (app) {
        app.classList.add('sidebar-collapsed');
        const chk = document.getElementById('stCompactNav');
        if (chk) chk.checked = true;
      }
    };
    if (document.readyState === 'loading') {
      window.addEventListener('DOMContentLoaded', applyCollapse);
    } else {
      applyCollapse();
    }
  }
}

initSidebarState();

