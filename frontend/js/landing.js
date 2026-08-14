/**
 * InsightFlow — World-Class Interactive Landing Page Script
 * landing.js
 */

(function initLandingInteractions() {
  // 1. Sticky Navbar shrink on scroll
  const nav = document.getElementById('lNav');
  if (nav) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 40) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    });
  }

  // 2. Desktop 3D Mouse Parallax for Hero Dashboard
  const container = document.getElementById('hero3DContainer');
  const card = document.getElementById('hero3DCard');
  if (container && card && window.innerWidth > 768) {
    container.addEventListener('mousemove', (e) => {
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `perspective(1200px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg) translate3d(${x * 12}px, ${y * 12}px, 0)`;
      card.style.transition = 'transform 0.1s ease-out';
    });

    container.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1200px) rotateY(0deg) rotateX(0deg) translate3d(0, 0, 0)';
      card.style.transition = 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
    });
  }

  // 3. Scroll Reveal via IntersectionObserver
  const observerOptions = {
    root: null,
    rootMargin: '0px 0px -50px 0px',
    threshold: 0.12
  };

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry, idx) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.classList.add('in-view');
        }, idx * 80);
      }
    });
  }, observerOptions);

  document.querySelectorAll('.l-bento-card, .l-tcard, .l-pcard, .l-timeline-step, .l-faq-item, .l-reveal-item').forEach((el) => {
    el.classList.add('l-reveal');
    revealObserver.observe(el);
  });
})();

// 3. Switch Live Product Preview Tabs
function switchPreviewTab(tabKey, btnEl) {
  document.querySelectorAll('.l-ptab').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.l-ptab-pane').forEach(pane => pane.classList.remove('active'));

  if (btnEl) btnEl.classList.add('active');
  const pane = document.getElementById('ptab-' + tabKey);
  if (pane) pane.classList.add('active');
}

// 4. Toggle FAQ Accordions
function toggleFAQ(el) {
  const item = el.closest('.l-faq-item');
  if (!item) return;

  const isOpen = item.classList.contains('active');
  document.querySelectorAll('.l-faq-item').forEach(i => i.classList.remove('active'));

  if (!isOpen) {
    item.classList.add('active');
  }
}

// 5. Dynamic Hero Showcase Number Counter & Live Text Cycler
(function initHeroShowcaseAnimator() {
  const v1 = document.getElementById('hkpiVal1');
  const v2 = document.getElementById('hkpiVal2');
  const v3 = document.getElementById('hkpiVal3');
  const l1 = document.getElementById('hkpiLbl1');
  const l2 = document.getElementById('hkpiLbl2');
  const l3 = document.getElementById('hkpiLbl3');
  const s1 = document.getElementById('hkpiSub1');
  const s2 = document.getElementById('hkpiSub2');
  const s3 = document.getElementById('hkpiSub3');
  const aiDesc = document.getElementById('hfloatAiDesc');
  const anomalyDesc = document.getElementById('hfloatAnomalyDesc');
  const chartTitle = document.getElementById('hkpiChartTitle');

  if (!v1 || !v2 || !v3) return;

  const sets = [
    {
      l1: 'TOTAL REVENUE', target1: 84200, prefix1: '$', suffix1: '', s1: '↑ +24.8% vs last month',
      l2: 'ACTIVE CUSTOMERS', target2: 1204, prefix2: '', suffix2: '', s2: '↑ +1.2% ML score',
      l3: 'PROFIT MARGIN', target3: 21050, prefix3: '$', suffix3: '', s3: '↑ +18.4% optimal',
      ai: '"Q4 revenue projected to exceed target by +18.4%"',
      anomaly: 'Spike in Enterprise renewals (+340% YoY)',
      chart: 'Revenue Forecast (Prophet ML Model)'
    },
    {
      l1: 'ACTIVE USERS', target1: 342890, prefix1: '', suffix1: '', s1: '↑ +18.2% active DAU',
      l2: 'CUSTOMER CAC', target2: 42.50, prefix2: '$', suffix2: '', s2: '↓ -$6.80 optimized',
      l3: 'RETENTION RATE', target3: 94.6, prefix3: '', suffix3: '%', s3: '↑ +3.4% high benchmark',
      ai: '"Viral growth loop detected in North America cohort"',
      anomaly: 'Paid Ad ROI increased to 4.2x (+120% YoY)',
      chart: 'User Growth Trend (Cluster Neural Net)'
    },
    {
      l1: 'QUERY SPEED', target1: 12, prefix1: '', suffix1: 'ms', s1: '⚡ 10x faster execution',
      l2: 'DATA ACCURACY', target2: 99.98, prefix2: '', suffix2: '%', s3: '✓ Zero null anomalies',
      l3: 'COST SAVINGS', target3: 84200, prefix3: '$', suffix3: '', s3: '↑ +42% efficiency win',
      ai: '"Autonomous agent cleaned 1.2M rows in 0.4s"',
      anomaly: 'Sanitation completed: Zero duplicate records',
      chart: 'Query Response Latency (Low-Latency Cache)'
    }
  ];

  let currentIdx = 0;

  function animateValue(el, start, end, duration, prefix = '', suffix = '') {
    if (!el) return;
    const startTime = performance.now();
    const isFloat = end % 1 !== 0 || end < 10;

    function update(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * ease;

      if (isFloat) {
        el.textContent = prefix + current.toFixed(2) + suffix;
      } else {
        el.textContent = prefix + Math.floor(current).toLocaleString('en-US') + suffix;
      }

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }
    requestAnimationFrame(update);
  }

  function applySet(set) {
    if (l1) l1.textContent = set.l1;
    if (l2) l2.textContent = set.l2;
    if (l3) l3.textContent = set.l3;
    if (s1) s1.textContent = set.s1;
    if (s2) s2.textContent = set.s2;
    if (s3) s3.textContent = set.s3;
    if (aiDesc) aiDesc.textContent = set.ai;
    if (anomalyDesc) anomalyDesc.textContent = set.anomaly;
    if (chartTitle) chartTitle.textContent = set.chart;

    animateValue(v1, 0, set.target1, 1400, set.prefix1, set.suffix1);
    animateValue(v2, 0, set.target2, 1400, set.prefix2, set.suffix2);
    animateValue(v3, 0, set.target3, 1400, set.prefix3, set.suffix3);
  }

  // Initial animation
  applySet(sets[0]);

  // Cycle every 4.5 seconds
  setInterval(() => {
    currentIdx = (currentIdx + 1) % sets.length;
    applySet(sets[currentIdx]);
  }, 4500);
})();
