/**
 * InsightFlow — Main Application Router & Entry Point
 */

const SAMPLES = {
  sales: {
    name: 'SalesQ4_2024.csv',
    cols: ['OrderID', 'Date', 'Product', 'Category', 'Region', 'Units', 'Revenue', 'Profit', 'Type'],
    data: [
      ['ORD-1001', '2024-10-03', 'Laptop Pro 16"', 'Electronics', 'North', '2', '2399', '720', 'Enterprise'],
      ['ORD-1002', '2024-10-05', 'Ergonomic Chair', 'Furniture', 'South', '5', '1250', '375', 'SMB'],
      ['ORD-1003', '2024-10-08', 'CRM Suite', 'SaaS', 'West', '12', '3600', '2880', 'Enterprise'],
      ['ORD-1004', '2024-10-12', 'Standing Desk', 'Furniture', 'East', '3', '1890', '567', 'SMB'],
      ['ORD-1005', '2024-10-15', 'Analytics Pro', 'SaaS', 'North', '8', '4800', '3840', 'Enterprise'],
      ['ORD-1006', '2024-10-18', '4K Monitor', 'Electronics', 'West', '6', '2940', '882', 'SMB'],
      ['ORD-1007', '2024-10-22', 'Cloud Storage', 'SaaS', 'South', '20', '6000', '4800', 'Enterprise'],
      ['ORD-1008', '2024-10-25', 'Wireless Mouse', 'Electronics', 'East', '15', '750', '225', 'SMB'],
      ['ORD-1009', '2024-11-02', 'Project Mgr SaaS', 'SaaS', 'North', '10', '5000', '4000', 'Enterprise'],
      ['ORD-1010', '2024-11-08', 'Conference Cam', 'Electronics', 'West', '8', '1600', '480', 'SMB'],
    ]
  },
  hr: {
    name: 'HR_Employees.csv',
    cols: ['EmpID', 'Name', 'Department', 'Role', 'Experience', 'Salary', 'Rating', 'City'],
    data: [
      ['E001', 'Alice', 'Engineering', 'Senior Dev', '5', '95000', '4.5', 'Mumbai'],
      ['E002', 'Bob', 'Marketing', 'Manager', '8', '85000', '4.2', 'Delhi'],
      ['E003', 'Charlie', 'Engineering', 'Junior Dev', '2', '55000', '3.8', 'Bangalore'],
      ['E004', 'Diana', 'HR', 'Recruiter', '3', '60000', '4.0', 'Mumbai'],
      ['E005', 'Eve', 'Engineering', 'Tech Lead', '10', '120000', '4.8', 'Bangalore'],
      ['E006', 'Frank', 'Sales', 'Executive', '4', '70000', '3.5', 'Delhi'],
      ['E007', 'Grace', 'Marketing', 'Analyst', '3', '65000', '4.1', 'Pune'],
      ['E008', 'Hank', 'Engineering', 'Senior Dev', '6', '100000', '4.4', 'Mumbai'],
    ]
  },
  finance: {
    name: 'Finance_Transactions.csv',
    cols: ['TxnID', 'Date', 'Type', 'Category', 'Amount', 'Status', 'Account', 'Region'],
    data: [
      ['TXN001', '2024-10-01', 'Credit', 'Revenue', '15000', 'Completed', 'Business', 'North'],
      ['TXN002', '2024-10-03', 'Debit', 'Expense', '3200', 'Completed', 'Operations', 'South'],
      ['TXN003', '2024-10-05', 'Credit', 'Revenue', '22000', 'Completed', 'Business', 'West'],
      ['TXN004', '2024-10-08', 'Debit', 'Salary', '45000', 'Completed', 'HR', 'North'],
      ['TXN005', '2024-10-10', 'Credit', 'Revenue', '18500', 'Pending', 'Business', 'East'],
      ['TXN006', '2024-10-12', 'Debit', 'Marketing', '8000', 'Completed', 'Marketing', 'South'],
      ['TXN007', '2024-10-15', 'Credit', 'Revenue', '31000', 'Completed', 'Business', 'West'],
      ['TXN008', '2024-10-18', 'Debit', 'Expense', '4500', 'Failed', 'Operations', 'North'],
    ]
  }
};

setInterval(() => {
  const el = document.getElementById('clk');
  if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}, 1000);

function enterApp() {
  if (typeof protectRoute === 'function' && !protectRoute('dashboard')) {
    return;
  }
  document.getElementById('landing').style.display = 'none';
  document.getElementById('app').classList.add('on');
  if (typeof checkAIStatus === 'function') checkAIStatus();
}

function goHome() {
  document.getElementById('landing').style.display = 'flex';
  document.getElementById('app').classList.remove('on');
}

function gv(v) {
  if (typeof protectRoute === 'function' && !protectRoute(v)) {
    return;
  }
  if (typeof closeMobileSidebar === 'function') closeMobileSidebar();
  document.querySelectorAll('.view').forEach(e => e.classList.remove('on'));
  document.querySelectorAll('.nv').forEach(e => e.classList.remove('on'));
  
  const viewEl = document.getElementById('v-' + v);
  if (viewEl) viewEl.classList.add('on');
  
  const navEl = document.getElementById('n-' + v);
  if (navEl) navEl.classList.add('on');

  const titleEl = document.getElementById('topPageName');
  if (titleEl && PAGE_TITLES[v]) titleEl.textContent = PAGE_TITLES[v];

  const main = document.querySelector('.main');
  if (main) main.scrollTop = 0;

  if (v === 'studio' && typeof initVsStudioControls === 'function') initVsStudioControls();
  if (v === 'data' && typeof loadDataTable === 'function') loadDataTable();
  if (v === 'eda' && typeof loadEDA === 'function') loadEDA();
  if (v === 'report' && typeof loadReport === 'function') loadReport();
  if (v === 'forecast' && typeof loadForecastView === 'function') loadForecastView();
  if (v === 'notifications' && typeof loadNotifications === 'function') loadNotifications();
}

function setSt(s, t) {
  const dot = document.getElementById('sdot'), txt = document.getElementById('stxt');
  if (!dot || !txt) return;
  dot.className = 'sdot' + (s === 'busy' ? ' busy' : '');
  dot.style.background = s === 'ok' ? 'var(--lime)' : s === 'busy' ? 'var(--amber)' : 'var(--muted)';
  txt.textContent = t;
}

function triggerFileUpload() {
  const el = document.getElementById('fileInput');
  if (el) {
    el.value = '';
    el.click();
  }
}

async function loadSample(key) {
  const s = SAMPLES[key] || SAMPLES.sales;
  enterApp();
  const fileBadge = document.getElementById('afile');
  if (fileBadge) fileBadge.textContent = s.name;
  gv('dashboard');
  setSt('busy', 'Processing...');

  const header = s.cols.join(',');
  const rows = s.data.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));
  const csv = [header, ...rows].join('\n');

  try {
    const data = await uploadToBackend(csv, s.name);
    if (data.error) { setSt('error', data.error); return; }
    cur = data.summary;
    cur.name = s.name;
    runPipeline(cur);
  } catch (e) {
    console.error('Sample load error:', e);
    setSt('error', 'Backend not running');
  }
}

async function handleUpload(input) {
  const file = input.files[0];
  if (!file) return;
  enterApp();
  const fileBadge = document.getElementById('afile');
  if (fileBadge) fileBadge.textContent = file.name;
  gv('dashboard');
  setSt('busy', 'Uploading...');

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await authFetch(API_BASE + '/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { setSt('error', data.error); alert('Error: ' + data.error); return; }
    cur = data.summary;
    cur.name = file.name;
    cur.preview = data.preview;
    runPipeline(cur);
  } catch (e) {
    setSt('error', 'Backend not running — start with: uvicorn main:app --reload');
  }
}

function runPipeline(summary) {
  const steps = [
    'Uploading dataset...',
    'Understanding schema...',
    'Cleaning data...',
    'Running analytics...',
    'Generating AI insights...',
    'Preparing report...',
    'Almost ready...'
  ];
  const STEP_DELAY = 400;
  const HOLD_AFTER = 300;
  let i = 0;

  const overlay = document.getElementById('dload');
  const statusEl = document.getElementById('lsStatus');
  const barFill = document.getElementById('lsBarFill');
  const items = overlay ? overlay.querySelectorAll('.ls-step-item') : [];

  if (overlay) {
    overlay.style.display = 'flex';
    overlay.classList.remove('ls-hidden');
  }
  const dcont = document.getElementById('dcont');
  if (dcont) dcont.style.display = 'none';
  setSt('busy', 'Processing...');

  items.forEach(el => el.classList.remove('active'));
  if (barFill) barFill.style.width = '0';

  function advance() {
    if (i < steps.length) {
      if (i > 0 && items[i - 1]) items[i - 1].classList.remove('active');
      if (items[i]) items[i].classList.add('active');

      if (statusEl) {
        statusEl.classList.add('ls-fade');
        setTimeout(() => {
          statusEl.textContent = steps[i];
          statusEl.classList.remove('ls-fade');
        }, 150);
      }

      if (barFill) barFill.style.width = ((i + 1) / steps.length * 100) + '%';
      i++;
      setTimeout(advance, STEP_DELAY);
    } else {
      setTimeout(() => {
        if (overlay) overlay.classList.add('ls-hidden');
        setTimeout(() => {
          if (overlay) {
            overlay.style.display = 'none';
            overlay.classList.remove('ls-hidden');
          }
          if (dcont) dcont.style.display = 'block';
          if (typeof renderDashboard === 'function') renderDashboard(summary);
        }, 500);
      }, HOLD_AFTER);
    }
  }
  setTimeout(advance, 200);
}

function handleGlobalSearch(query) {
  const q = query.toLowerCase().trim();
  if (!q) return;
  
  for (const [key, title] of Object.entries(PAGE_TITLES)) {
    if (title.toLowerCase().includes(q) || key.includes(q)) {
      gv(key);
      break;
    }
  }
}
