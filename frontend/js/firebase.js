/**
 * InsightFlow — Firebase Authentication Manager Architecture
 * Modular foundation for Firebase Authentication, Firestore & Analytics.
 */

// Firebase Configuration Object (Replace with your project keys)
window.FirebaseConfig = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: ""
};

// Modular Firebase Auth Manager Interface
window.FirebaseAuthManager = {
  initialized: false,
  auth: None = null,
  googleProvider: None = null,

  /**
   * Initialize Firebase SDK if configuration keys are present.
   */
  async init() {
    if (this.initialized) return true;
    
    // If Firebase Web SDK CDN scripts are loaded and config keys exist:
    if (window.firebase && window.FirebaseConfig.apiKey) {
      try {
        if (!window.firebase.apps.length) {
          window.firebase.initializeApp(window.FirebaseConfig);
        }
        this.auth = window.firebase.auth();
        this.googleProvider = new window.firebase.auth.GoogleAuthProvider();
        this.googleProvider.addScope('email');
        this.googleProvider.addScope('profile');
        this.initialized = true;
        console.log("⚡ Firebase Auth Manager initialized successfully");
        return true;
      } catch (e) {
        console.warn("Firebase Init Notice:", e);
      }
    }
    return false;
  }
};

/**
 * Modular Placeholder / Wrapper Functions for Firebase Auth Integration
 */

// 1. Google OAuth Popup Login
async function loginWithGoogle() {
  console.log("🔒 initiating loginWithGoogle()...");
  const firebaseReady = await window.FirebaseAuthManager.init();
  
  if (firebaseReady && window.FirebaseAuthManager.auth && window.FirebaseAuthManager.googleProvider) {
    try {
      const result = await window.FirebaseAuthManager.auth.signInWithPopup(window.FirebaseAuthManager.googleProvider);
      const user = result.user;
      return {
        uid: user.uid,
        name: user.displayName || user.email.split('@')[0],
        email: user.email,
        photoURL: user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.displayName || user.email)}&background=4285f4&color=fff`,
        credits: 100,
        workspaceId: "ws_default",
        providerId: "google.com"
      };
    } catch (error) {
      console.error("Firebase Google Auth Error:", error);
      throw error;
    }
  }

  // Fallback to backend authentication architecture if Firebase SDK keys are pending
  if (typeof handleGoogleSignIn === 'function') {
    return await handleGoogleSignIn();
  }
}

// 2. Email + Password Login
async function loginWithEmail(email, password, remember = true) {
  console.log("🔒 initiating loginWithEmail()...", { email, remember });
  const firebaseReady = await window.FirebaseAuthManager.init();

  if (firebaseReady && window.FirebaseAuthManager.auth) {
    try {
      const userCredential = await window.FirebaseAuthManager.auth.signInWithEmailAndPassword(email, password);
      const user = userCredential.user;
      return {
        uid: user.uid,
        name: user.displayName || user.email.split('@')[0],
        email: user.email,
        photoURL: user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.email)}`,
        credits: 100,
        workspaceId: "ws_default",
        providerId: "password"
      };
    } catch (error) {
      console.error("Firebase Email Auth Error:", error);
      throw error;
    }
  }

  // Fallback to API endpoint handler
  if (typeof executeBackendLogin === 'function') {
    return await executeBackendLogin(email, password, remember);
  }
}

// 3. Email + Password Registration
async function signup(name, email, password) {
  console.log("🔒 initiating signup()...", { name, email });
  const firebaseReady = await window.FirebaseAuthManager.init();

  if (firebaseReady && window.FirebaseAuthManager.auth) {
    try {
      const userCredential = await window.FirebaseAuthManager.auth.createUserWithEmailAndPassword(email, password);
      const user = userCredential.user;
      if (name && user.updateProfile) {
        await user.updateProfile({ displayName: name });
      }
      return {
        uid: user.uid,
        name: name || user.email.split('@')[0],
        email: user.email,
        photoURL: `https://ui-avatars.com/api/?name=${encodeURIComponent(name || email)}`,
        credits: 100,
        workspaceId: "ws_default",
        providerId: "password"
      };
    } catch (error) {
      console.error("Firebase SignUp Error:", error);
      throw error;
    }
  }

  // Fallback to API endpoint handler
  if (typeof executeBackendSignUp === 'function') {
    return await executeBackendSignUp(name, email, password);
  }
}

// 4. Password Reset Link
async function forgotPassword(email) {
  console.log("🔒 initiating forgotPassword()...", email);
  const firebaseReady = await window.FirebaseAuthManager.init();

  if (firebaseReady && window.FirebaseAuthManager.auth) {
    try {
      await window.FirebaseAuthManager.auth.sendPasswordResetEmail(email);
      return { success: true, message: `Password reset email sent to ${email}` };
    } catch (error) {
      console.error("Firebase Reset Password Error:", error);
      throw error;
    }
  }

  // Fallback handler
  if (typeof executeBackendForgotPassword === 'function') {
    return await executeBackendForgotPassword(email);
  }
  return { success: true, message: `If an account exists for ${email}, a reset link has been dispatched.` };
}

// 5. Sign Out
async function logout() {
  console.log("🔒 initiating logout()...");
  const firebaseReady = await window.FirebaseAuthManager.init();

  if (firebaseReady && window.FirebaseAuthManager.auth) {
    try {
      await window.FirebaseAuthManager.auth.signOut();
    } catch (error) {
      console.warn("Firebase SignOut Notice:", error);
    }
  }

  if (typeof executeSessionLogout === 'function') {
    executeSessionLogout();
  }
}

// 6. Verify Auth Session / Listener
function verifySession(callback) {
  if (window.FirebaseAuthManager.auth) {
    window.FirebaseAuthManager.auth.onAuthStateChanged((user) => {
      if (user) {
        const sessionUser = {
          uid: user.uid,
          name: user.displayName || user.email.split('@')[0],
          email: user.email,
          photoURL: user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.email)}`,
          credits: 100,
          workspaceId: "ws_default",
          providerId: user.providerData?.[0]?.providerId || 'password'
        };
        if (callback) callback(sessionUser);
      } else {
        if (callback) callback(null);
      }
    });
  }
}
