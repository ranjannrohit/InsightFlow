/**
 * InsightFlow — Executive Reports Builder
 * Generates, lists, and downloads real reports via backend API.
 */

window._reportLoaded = window._reportLoaded || false;
window._reportsList = window._reportsList || [];

async function loadReport() {
  if (typeof generateAllReports === 'function') {
    generateAllReports();
  }
  // Also load persisted reports list
  await loadReportsList();
}

async function loadReportsList() {
  const token = typeof getAuthToken === 'function' ? getAuthToken() : localStorage.getItem('auth_token');
  if (!token) return;

  try {
    const res = await authFetch(API_BASE + '/api/reports');
    if (res.ok) {
      const data = await res.json();
      window._reportsList = data.reports || [];
      renderReportsList(window._reportsList);
    }
  } catch (e) {
    console.warn('Reports list load error:', e);
  }
}

function renderReportsList(reports) {
  const container = document.getElementById('reports-history-list');
  if (!container) return;

  if (!reports || reports.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:24px;color:var(--muted);font-family:var(--fm);font-size:13px">
        No reports generated yet. Generate your first report above.
      </div>`;
    return;
  }

  const typeLabels = {
    executive: 'Executive Summary',
    business: 'Business Insights',
    forecast: 'Forecast Report',
    cleaning: 'Cleaning Report'
  };

  container.innerHTML = reports.map(r => `
    <div style="display:flex;justify-content:space-between;align-items:center;background:var(--s1);border:1px solid var(--line2);padding:12px 16px;border-radius:8px;margin-bottom:8px">
      <div>
        <div style="font-family:var(--ff);font-weight:600;color:var(--white);font-size:13px">${r.title}</div>
        <div style="font-family:var(--fm);font-size:11px;color:var(--muted);margin-top:2px">
          ${typeLabels[r.type] || r.type} · ${formatTimeAgo ? formatTimeAgo(r.created_at) : r.created_at}
        </div>
      </div>
      <div style="display:flex;gap:8px">
        <button onclick="viewReport('${r.id}')" style="background:var(--s2);border:1px solid var(--line2);color:var(--muted);padding:4px 10px;border-radius:4px;cursor:pointer;font-family:var(--fm);font-size:11px">View</button>
        <button onclick="downloadReportPDF('${r.id}')" style="background:rgba(212,255,42,0.1);border:1px solid rgba(212,255,42,0.2);color:var(--lime);padding:4px 10px;border-radius:4px;cursor:pointer;font-family:var(--fm);font-size:11px">PDF</button>
      </div>
    </div>`).join('');
}

async function generateReport(type = 'executive') {
  const btn = document.getElementById('generateReportBtn') || document.activeElement;
  if (btn && btn.disabled !== undefined) {
    btn.disabled = true;
    btn.textContent = 'Generating...';
  }

  try {
    const res = await authFetch(API_BASE + '/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, title: null })
    });
    const data = await res.json();

    if (!res.ok) {
      const msg = data.detail?.message || data.detail || 'Report generation failed';
      alert('Error: ' + msg);
      return null;
    }

    // Refresh the reports list
    await loadReportsList();
    return data;
  } catch (e) {
    console.error('Generate report error:', e);
    alert('Report generation failed — is the backend running?');
    return null;
  } finally {
    if (btn && btn.disabled !== undefined) {
      btn.disabled = false;
      btn.textContent = 'Generate Report';
    }
  }
}

async function viewReport(reportId) {
  try {
    const res = await authFetch(API_BASE + `/api/reports/${reportId}`);
    if (!res.ok) throw new Error('Not found');
    const data = await res.json();
    const report = data.report;
    const content = report.content || {};

    const modal = document.getElementById('report-modal');
    const modalContent = document.getElementById('report-modal-content');
    if (modal && modalContent) {
      modalContent.innerHTML = `
        <h2 style="font-family:var(--ff);font-weight:700;color:var(--white);font-size:20px;margin-bottom:16px">${report.title}</h2>
        ${content.executive_summary ? `<div style="background:var(--s2);border:1px solid var(--line2);padding:16px;border-radius:8px;margin-bottom:16px;font-size:14px;color:var(--muted);line-height:1.6">${content.executive_summary}</div>` : ''}
        ${(content.key_findings || []).length > 0 ? `
          <div style="margin-bottom:16px">
            <div style="font-family:var(--fm);font-size:11px;color:var(--muted2);letter-spacing:1.5px;margin-bottom:8px">KEY FINDINGS</div>
            ${content.key_findings.map(f => `<div style="padding:8px 0;border-bottom:1px solid var(--line2);font-size:13px;color:var(--white)">• ${f}</div>`).join('')}
          </div>` : ''}
        ${(content.strategic_recommendations || []).length > 0 ? `
          <div>
            <div style="font-family:var(--fm);font-size:11px;color:var(--muted2);letter-spacing:1.5px;margin-bottom:8px">RECOMMENDATIONS</div>
            ${content.strategic_recommendations.map(r => `<div style="padding:8px 0;border-bottom:1px solid var(--line2);font-size:13px;color:var(--lime)">→ ${r}</div>`).join('')}
          </div>` : ''}`;
      modal.classList.add('on');
    } else {
      // Fallback: alert summary
      alert(content.executive_summary || 'Report loaded — no modal found.');
    }
  } catch (e) {
    alert('Could not load report.');
  }
}

async function downloadReportPDF(reportId) {
  try {
    const res = await authFetch(API_BASE + `/api/reports/${reportId}/download`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Download failed');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `insightflow_report_${reportId.slice(0, 8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('PDF download error: ' + e.message);
  }
}

function downloadReport() {
  // Legacy function — use window.print() as fallback
  window.print();
}
