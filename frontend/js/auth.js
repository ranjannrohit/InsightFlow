/**
 * InsightFlow — Authentication, Session Manager, User State & Route Guard
 */

// Global User Session Object
let currentUser = null;

/**
 * SESSION MANAGER — Token Storage & Session Persistence
 */
function getAuthToken() {
  return localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token') || '';
}

function setAuthToken(token, remember = true) {
  if (remember) {
    localStorage.setItem('auth_token', token);
    sessionStorage.removeItem('auth_token');
  } else {
    sessionStorage.setItem('auth_token', token);
    localStorage.removeItem('auth_token');
  }
}

function clearAuthToken() {
  localStorage.removeItem('auth_token');
  sessionStorage.removeItem('auth_token');
}

/**
 * USER STATE MANAGER — Synchronize user state across components
 */
function updateUserUI(user) {
  if (user) {
    currentUser = {
      uid: user.uid || user.id || 'usr_' + Date.now(),
      name: user.name || (user.email ? user.email.split('@')[0] : 'User'),
      email: user.email || '',
      photoURL: user.photoURL || user.profile_photo || '',
      credits: user.credits ?? 100,
      workspaceId: user.workspaceId || user.workspace_id || 'ws_default',
      providerId: user.providerId || user.login_provider || 'password'
    };
  } else {
    currentUser = null;
  }

  const sbAvatar = document.getElementById('sbAvatar');
  const sbName = document.getElementById('sbUserName');
  const sbEmail = document.getElementById('sbUserEmail');
  const sbCreditsText = document.getElementById('sbCreditsText');
  const sbCreditsFill = document.getElementById('sbCreditsFill');
  const sbCreditsSub = document.getElementById('sbCreditsSubText');
  const tnAvatar = document.getElementById('tnAvatar');
  const landingAuthBtn = document.getElementById('landingAuthBtn');

  if (currentUser) {
    const initials = currentUser.name
      ? currentUser.name.split(' ').map(p => p[0]).join('').toUpperCase().substring(0, 2)
      : 'IF';

    if (sbAvatar) {
      if (currentUser.photoURL) {
        sbAvatar.innerHTML = `<img src="${currentUser.photoURL}" style="width:100%;height:100%;border-radius:8px;object-fit:cover;">`;
      } else {
        sbAvatar.textContent = initials;
      }
    }
    if (tnAvatar) {
      if (currentUser.photoURL) {
        tnAvatar.innerHTML = `<img src="${currentUser.photoURL}" style="width:100%;height:100%;border-radius:8px;object-fit:cover;">`;
      } else {
        tnAvatar.textContent = initials;
      }
    }
    if (sbName) sbName.textContent = currentUser.name;
    if (sbEmail) sbEmail.textContent = currentUser.email;
    
    const credits = currentUser.credits ?? 100;
    if (sbCreditsText) sbCreditsText.textContent = `${credits} / 100`;
    if (sbCreditsFill) sbCreditsFill.style.width = `${Math.min(100, Math.max(0, credits))}%`;
    if (sbCreditsSub) sbCreditsSub.textContent = `${credits} / 100 Credits Remaining`;

    if (landingAuthBtn) {
      landingAuthBtn.textContent = currentUser.name ? currentUser.name.split(' ')[0] : 'Account';
      landingAuthBtn.onclick = () => enterApp();
    }
  } else {
    if (sbAvatar) sbAvatar.textContent = 'IF';
    if (tnAvatar) tnAvatar.textContent = 'IF';
    if (sbName) sbName.textContent = 'Guest User';
    if (sbEmail) sbEmail.textContent = 'guest@insightflow.ai';
    if (sbCreditsText) sbCreditsText.textContent = '100 / 100';
    if (sbCreditsFill) sbCreditsFill.style.width = '100%';
    if (sbCreditsSub) sbCreditsSub.textContent = '100 / 100 Credits Remaining';

    if (landingAuthBtn) {
      landingAuthBtn.textContent = 'Sign In';
      landingAuthBtn.onclick = () => showLoginPage('login');
    }
  }
}

/**
 * ROUTE GUARD — Protect application pages & allow seamless guest exploration
 */
function routeGuard(targetView = 'dashboard', allowGuest = false) {
  const token = getAuthToken();
  if (!token && !currentUser) {
    if (allowGuest) {
      updateUserUI({
        uid: 'guest_user',
        name: 'Guest User',
        email: 'guest@insightflow.ai',
        credits: 100,
        photoURL: ''
      });
      return true;
    }
    showLoginPage('login');
    return false;
  }
  return true;
}

function protectRoute(targetView) {
  return routeGuard(targetView, false);
}

/**
 * AUTH SESSION VERIFICATION — Startup session check
 */
async function checkAuthSession() {
  const token = getAuthToken();
  if (!token) {
    updateUserUI(null);
    return false;
  }
  try {
    const res = await authFetch(API_BASE + '/api/auth/me');
    if (res.ok) {
      const data = await res.json();
      updateUserUI(data.user);
      return true;
    } else {
      clearAuthToken();
      updateUserUI(null);
      return false;
    }
  } catch (e) {
    console.warn('Session check network notice:', e);
    return false;
  }
}

/**
 * AUTH UI NAVIGATION HANDLERS
 */
function switchAuthView(mode) {
  const loginView = document.getElementById('auth-login-view');
  const signupView = document.getElementById('auth-signup-view');
  const loginAlert = document.getElementById('auth-login-alert');
  const signupAlert = document.getElementById('auth-signup-alert');

  if (loginAlert) loginAlert.style.display = 'none';
  if (signupAlert) signupAlert.style.display = 'none';

  if (mode === 'signup') {
    if (loginView) loginView.style.display = 'none';
    if (signupView) signupView.style.display = 'block';
  } else {
    if (signupView) signupView.style.display = 'none';
    if (loginView) loginView.style.display = 'block';
  }
}

function showLoginPage(mode = 'login') {
  const lp = document.getElementById('login-page');
  if (lp) {
    switchAuthView(mode);
    lp.classList.add('on');
  } else {
    if (mode === 'signup') {
      window.location.href = 'signup.html';
    } else if (mode === 'forgot') {
      window.location.href = 'forgot-password.html';
    } else {
      window.location.href = 'login.html';
    }
  }
}

function hideLoginPage() {
  const lp = document.getElementById('login-page');
  if (lp) lp.classList.remove('on');
}

/**
 * FORM ACTION HANDLERS & BACKEND FALLBACKS
 */
async function handleEmailLogin(e) {
  if (e) e.preventDefault();
  const email = document.getElementById('login-email')?.value.trim();
  const password = document.getElementById('login-password')?.value;
  const remember = document.getElementById('login-remember')?.checked ?? true;
  const btn = document.getElementById('login-btn');

  if (!email || !password) {
    showAlert('auth-login-alert', 'Please fill in all fields');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Authenticating...';
  }

  try {
    const userSession = await loginWithEmail(email, password, remember);
    updateUserUI(userSession);
    hideLoginPage();
    enterApp();
    checkOnboardingWelcome();
  } catch (err) {
    showAlert('auth-login-alert', err.message || 'Login failed. Please check credentials.');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Sign In';
    }
  }
}

async function executeBackendLogin(email, password, remember) {
  const res = await fetch(API_BASE + '/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, remember_me: remember })
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Login failed. Please check credentials.');
  }
  setAuthToken(data.token, remember);
  return data.user;
}

async function handleEmailSignUp(e) {
  if (e) e.preventDefault();
  const name = document.getElementById('signup-name')?.value.trim();
  const email = document.getElementById('signup-email')?.value.trim();
  const password = document.getElementById('signup-password')?.value;
  const confirmPassword = document.getElementById('signup-confirm-password')?.value;
  const btn = document.getElementById('signup-btn');

  if (!name || !email || !password || !confirmPassword) {
    showAlert('auth-signup-alert', 'Please fill in all required fields');
    return;
  }

  if (password !== confirmPassword) {
    showAlert('auth-signup-alert', 'Passwords do not match');
    return;
  }

  if (password.length < 6) {
    showAlert('auth-signup-alert', 'Password must be at least 6 characters');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Creating Account...';
  }

  try {
    const userSession = await signup(name, email, password);
    updateUserUI(userSession);
    hideLoginPage();
    enterApp();
    checkOnboardingWelcome();
  } catch (err) {
    showAlert('auth-signup-alert', err.message || 'Sign up failed. Email may already exist.');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Create Account';
    }
  }
}

async function executeBackendSignUp(name, email, password) {
  const res = await fetch(API_BASE + '/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password, confirm_password: password })
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Sign up failed. Email may already exist.');
  }
  setAuthToken(data.token, true);
  return data.user;
}

async function handleGoogleSignIn() {
  try {
    let googleEmail = prompt("Enter your Google Account email to continue with Google:", currentUser ? currentUser.email : "user@gmail.com");
    if (!googleEmail) return;
    
    const loginView = document.getElementById('auth-login-view');
    const signupView = document.getElementById('auth-signup-view');
    const loadingCard = document.getElementById('auth-google-loading');
    const loadingText = document.getElementById('auth-loading-text');

    if (loginView) loginView.style.display = 'none';
    if (signupView) signupView.style.display = 'none';
    if (loadingCard) loadingCard.classList.add('on');
    if (loadingText) loadingText.textContent = 'Connecting your Google Account...';

    await new Promise(r => setTimeout(r, 600));
    if (loadingText) loadingText.textContent = 'Preparing your workspace...';
    await new Promise(r => setTimeout(r, 500));

    const googleName = googleEmail.split('@')[0].replace('.', ' ').replace(/^./, str => str.toUpperCase());
    const googleId = "google_id_" + Math.abs(googleEmail.split('').reduce((a,b)=>{a=((a<<5)-a)+b.charCodeAt(0);return a&a},0));
    const photo = `https://ui-avatars.com/api/?name=${encodeURIComponent(googleName)}&background=4285f4&color=fff&bold=true`;

    const res = await fetch(API_BASE + '/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: googleEmail,
        name: googleName,
        google_id: googleId,
        profile_photo: photo,
        remember_me: true
      })
    });
    const data = await res.json();
    if (!res.ok) {
      if (loadingCard) loadingCard.classList.remove('on');
      if (loginView) loginView.style.display = 'block';
      alert('Google Sign-In Error: ' + (data.detail || 'Could not authenticate with Google.'));
      return;
    }

    setAuthToken(data.token, true);
    updateUserUI(data.user);
    if (loadingCard) loadingCard.classList.remove('on');
    hideLoginPage();
    enterApp();
    checkOnboardingWelcome();
  } catch (err) {
    const loadingCard = document.getElementById('auth-google-loading');
    const loginView = document.getElementById('auth-login-view');
    if (loadingCard) loadingCard.classList.remove('on');
    if (loginView) loginView.style.display = 'block';
    alert('Google Sign-In connection error');
  }
}

async function handleForgotPassword(e) {
  if (e) e.preventDefault();
  const emailInput = document.getElementById('forgot-email');
  const alertBox = document.getElementById('auth-forgot-alert');
  const btn = document.getElementById('forgot-btn');
  const email = emailInput?.value.trim();

  if (!email) {
    showAlert('auth-forgot-alert', 'Please enter your account email address');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Sending Link...';
  }

  try {
    const res = await forgotPassword(email);
    if (alertBox) {
      alertBox.style.display = 'block';
      alertBox.style.background = 'rgba(212, 255, 42, 0.1)';
      alertBox.style.border = '1px solid rgba(212, 255, 42, 0.3)';
      alertBox.style.color = 'var(--lime)';
      alertBox.textContent = res.message || 'Password reset link sent to your email.';
    }
  } catch (err) {
    showAlert('auth-forgot-alert', err.message || 'Could not send reset link.');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Send Reset Link';
    }
  }
}

function checkOnboardingWelcome() {
  if (!localStorage.getItem('has_seen_onboarding')) {
    setTimeout(() => {
      const modal = document.getElementById('onboarding-modal');
      if (modal) modal.classList.add('on');
    }, 400);
  }
}

function closeOnboardingModal() {
  localStorage.setItem('has_seen_onboarding', 'true');
  const modal = document.getElementById('onboarding-modal');
  if (modal) modal.classList.remove('on');
}

function executeSessionLogout() {
  clearAuthToken();
  updateUserUI(null);
  if (typeof goHome === 'function') goHome();
  showLoginPage('login');
}

async function handleLogout(e) {
  if (e) e.stopPropagation();
  try {
    await authFetch(API_BASE + '/api/auth/logout', { method: 'POST' });
  } catch (err) {
    console.warn('Logout notice:', err);
  } finally {
    logout();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  checkAuthSession();
});
