/**
 * InsightFlow — Utilities & Animations
 */

function showAlert(elementId, msg, isError = true) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.style.display = 'block';
  el.style.background = isError ? 'rgba(244,63,94,0.15)' : 'rgba(212,255,42,0.15)';
  el.style.border = `1px solid ${isError ? 'var(--red)' : 'var(--lime)'}`;
  el.style.color = isError ? '#fecdd3' : 'var(--lime)';
  el.textContent = msg;
}

function formatCurrency(val) {
  if (typeof val !== 'number') val = parseFloat(val) || 0;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
}

// ═══ CANVAS PARTICLE ANIMATION ═══
(function initParticleCanvas() {
  window.addEventListener('load', () => {
    const canvas = document.getElementById('pcvs');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    const particles = Array.from({ length: 45 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 1.5 + 0.5,
      alpha: Math.random() * 0.5 + 0.1
    }));

    function loop() {
      ctx.clearRect(0, 0, width, height);
      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.fillStyle = `rgba(212, 255, 42, ${p.alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      });
      requestAnimationFrame(loop);
    }
    loop();
  });
})();

// ═══ TYPEWRITER ANIMATION FOR LANDING PAGE ═══
(function initTypewriter() {
  const phrases = [
    "Autonomous Business Intelligence Agent",
    "Turn Raw CSVs into Executive Dashboards",
    "Predict Trends & Discover Anomalies",
    "Ask Questions in Natural English"
  ];
  let pIdx = 0;
  let charIdx = 0;
  let isDeleting = false;

  function typeStep() {
    const el = document.getElementById('typewriterSubheading');
    if (!el) return;
    const current = phrases[pIdx];

    if (isDeleting) {
      charIdx--;
      el.textContent = current.substring(0, charIdx);
    } else {
      charIdx++;
      el.textContent = current.substring(0, charIdx);
    }

    let delay = isDeleting ? 40 : 80;

    if (!isDeleting && charIdx === current.length) {
      delay = 2000;
      isDeleting = true;
    } else if (isDeleting && charIdx === 0) {
      isDeleting = false;
      pIdx = (pIdx + 1) % phrases.length;
      delay = 500;
    }

    setTimeout(typeStep, delay);
  }

  window.addEventListener('DOMContentLoaded', () => {
    setTimeout(typeStep, 600);
  });
})();
