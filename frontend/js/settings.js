/**
 * InsightFlow — User & Workspace Settings
 * Loads and saves settings from/to backend /api/users/me/settings
 */

function switchSettingsTab(tabName) {
  document.querySelectorAll('.st-tab').forEach(tab => {
    tab.classList.toggle('active', tab.getAttribute('data-tab') === tabName);
  });
  document.querySelectorAll('.st-section').forEach(sec => {
    sec.style.display = sec.id === `st-sec-${tabName}` ? 'block' : 'none';
  });
}

/**
 * Load settings from backend and populate form fields.
 */
async function loadSettings() {
  const token = typeof getAuthToken === 'function' ? getAuthToken() : localStorage.getItem('auth_token');
  if (!token) return;

  try {
    const res = await authFetch(API_BASE + '/api/users/me/settings');
    if (!res.ok) return;

    const data = await res.json();
    const settings = data.settings || {};

    // Populate theme
    const themeSelect = document.getElementById('st-theme');
    if (themeSelect && settings.theme) themeSelect.value = settings.theme;

    // Populate language
    const langSelect = document.getElementById('st-language');
    if (langSelect && settings.language) langSelect.value = settings.language;

    // Populate notification toggles
    const emailNotifToggle = document.getElementById('st-email-notif');
    if (emailNotifToggle) emailNotifToggle.checked = !!settings.email_notifications;

    const productToggle = document.getElementById('st-product-updates');
    if (productToggle) productToggle.checked = !!settings.product_updates;

  } catch (e) {
    console.warn('Settings load error:', e);
  }
}

/**
 * Save current settings form values to backend.
 */
async function saveSettings(showAlert = true) {
  const themeSelect = document.getElementById('st-theme');
  const langSelect = document.getElementById('st-language');
  const emailNotifToggle = document.getElementById('st-email-notif');
  const productToggle = document.getElementById('st-product-updates');

  const payload = {};
  if (themeSelect) payload.theme = themeSelect.value;
  if (langSelect) payload.language = langSelect.value;
  if (emailNotifToggle) payload.email_notifications = emailNotifToggle.checked ? 1 : 0;
  if (productToggle) payload.product_updates = productToggle.checked ? 1 : 0;

  try {
    const res = await authFetch(API_BASE + '/api/users/me/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      if (showAlert) {
        const alertEl = document.getElementById('st-save-alert');
        if (alertEl) {
          alertEl.textContent = 'Settings saved successfully.';
          alertEl.style.display = 'block';
          setTimeout(() => { alertEl.style.display = 'none'; }, 3000);
        }
      }
      // Apply theme if changed
      if (payload.theme && typeof applyTheme === 'function') {
        applyTheme(payload.theme);
      }
    }
  } catch (e) {
    console.warn('Settings save error:', e);
  }
}

/**
 * Load user credits and display in settings if credits element exists.
 */
async function loadCreditsInfo() {
  const token = typeof getAuthToken === 'function' ? getAuthToken() : localStorage.getItem('auth_token');
  if (!token) return;

  try {
    const res = await authFetch(API_BASE + '/api/credits');
    if (!res.ok) return;

    const data = await res.json();
    const balanceEl = document.getElementById('st-credits-balance');
    if (balanceEl) balanceEl.textContent = `${data.balance} / 100`;

    const txContainer = document.getElementById('st-credits-tx');
    if (txContainer && data.transactions) {
      txContainer.innerHTML = data.transactions.slice(0, 10).map(tx => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--line2);font-size:12px">
          <span style="color:var(--muted);font-family:var(--fm)">${tx.operation}</span>
          <span style="color:${tx.amount < 0 ? 'var(--amber)' : 'var(--lime)'}">
            ${tx.amount > 0 ? '+' : ''}${tx.amount}
          </span>
        </div>`).join('');
    }
  } catch (e) {
    console.warn('Credits load error:', e);
  }
}

/**
 * Save user profile info to backend PUT /api/user/profile
 */
async function saveUserProfile() {
  const btn = document.getElementById('st-profile-save-btn') || document.activeElement;
  if (btn && btn.disabled !== undefined) {
    btn.disabled = true;
    btn.textContent = 'Saving...';
  }

  const name = document.getElementById('st-profile-name')?.value;
  const email = document.getElementById('st-profile-email')?.value;
  const role = document.getElementById('st-profile-role')?.value;
  const organization = document.getElementById('st-profile-org')?.value;

  try {
    const res = await authFetch(API_BASE + '/api/user/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, role, organization })
    });
    const data = await res.json();
    if (res.ok) {
      const alertEl = document.getElementById('st-save-alert');
      if (alertEl) {
        alertEl.textContent = 'Profile saved successfully!';
        alertEl.style.display = 'block';
        setTimeout(() => { alertEl.style.display = 'none'; }, 3000);
      } else {
        alert('Profile saved successfully!');
      }
      if (data.user) {
        localStorage.setItem('insightflow_user', JSON.stringify(data.user));
        if (typeof updateUserUI === 'function') updateUserUI(data.user);
      }
    } else {
      alert('Failed to save profile: ' + (data.detail || 'Unknown error'));
    }
  } catch (e) {
    console.warn('Profile save error:', e);
    alert('Error saving profile.');
  } finally {
    if (btn && btn.disabled !== undefined) {
      btn.disabled = false;
      btn.textContent = 'Save Profile';
    }
  }
}

// Auto-load settings when settings view is entered
document.addEventListener('DOMContentLoaded', () => {
  // Observe settings view visibility
  const settingsSection = document.getElementById('v-settings');
  if (settingsSection) {
    const observer = new MutationObserver(() => {
      if (settingsSection.classList.contains('on')) {
        loadSettings();
        loadCreditsInfo();
      }
    });
    observer.observe(settingsSection, { attributes: true, attributeFilter: ['class'] });
  }
});
