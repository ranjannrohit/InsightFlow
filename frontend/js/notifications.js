/**
 * InsightFlow — Notifications System
 * Fetches real notifications from /api/notifications backend endpoint.
 */

async function loadNotifications() {
  const container = document.getElementById('notifications-c');
  if (!container) return;

  const token = typeof getAuthToken === 'function' ? getAuthToken() : localStorage.getItem('auth_token');
  if (!token) {
    container.innerHTML = `
      <div style="text-align:center;padding:40px;color:var(--muted);font-family:var(--fm);font-size:13px">
        <div style="font-size:32px;margin-bottom:12px">🔔</div>
        Sign in to view your notifications.
      </div>`;
    return;
  }

  container.innerHTML = `
    <div style="padding:20px;text-align:center">
      <div class="spin" style="margin:0 auto 12px"></div>
      <div class="ltxt">Loading notifications...</div>
    </div>`;

  try {
    const res = await authFetch(API_BASE + '/api/notifications');
    if (!res.ok) {
      throw new Error('Failed to load notifications');
    }
    const data = await res.json();
    const notifications = data.notifications || [];
    const unreadCount = data.unread_count || 0;

    // Update unread badges if elements exist
    const badge = document.getElementById('notif-badge');
    if (badge) {
      badge.textContent = unreadCount > 0 ? unreadCount : '';
      badge.style.display = unreadCount > 0 ? 'block' : 'none';
    }
    const ntBadge = document.getElementById('ntBadgeCount');
    if (ntBadge) {
      ntBadge.textContent = `${unreadCount} UNREAD`;
      if (unreadCount === 0) {
        ntBadge.style.borderColor = 'var(--line2)';
        ntBadge.style.color = 'var(--muted)';
        ntBadge.style.background = 'transparent';
      } else {
        ntBadge.style.borderColor = 'rgba(212,255,42,0.3)';
        ntBadge.style.color = 'var(--lime)';
        ntBadge.style.background = 'rgba(212,255,42,0.1)';
      }
    }

    if (notifications.length === 0) {
      container.innerHTML = `
        <div style="text-align:center;padding:40px;color:var(--muted);font-family:var(--fm);font-size:13px">
          <div style="font-size:32px;margin-bottom:12px">✓</div>
          No notifications yet. Start by uploading a dataset!
        </div>`;
      return;
    }

    // Header with mark-all-read button
    const headerHtml = unreadCount > 0 ? `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <div style="font-family:var(--fm);font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px">
          ${unreadCount} unread
        </div>
        <button onclick="markAllNotificationsRead()" style="background:transparent;border:1px solid var(--line2);color:var(--muted);padding:4px 12px;border-radius:4px;cursor:pointer;font-family:var(--fm);font-size:11px;">
          Mark All Read
        </button>
      </div>` : '';

    const iconMap = {
      success: '✓',
      info: '⚡',
      warn: '⚠',
      error: '✕'
    };

    const html = notifications.map(n => {
      const isUnread = !n.read;
      const timeAgo = formatTimeAgo(n.created_at);
      const icon = iconMap[n.type] || '⚡';
      return `
        <div class="nf-card" id="notif-${n.id}" style="
          display:flex;gap:14px;align-items:flex-start;
          background:${isUnread ? 'var(--s2)' : 'var(--s1)'};
          border:1px solid ${isUnread ? 'rgba(212,255,42,0.15)' : 'var(--line2)'};
          padding:14px 18px;border-radius:8px;margin-bottom:10px;
          cursor:pointer;transition:opacity 0.2s;
          ${isUnread ? 'box-shadow:0 0 0 1px rgba(212,255,42,0.05)' : ''}
        " onclick="markNotificationRead('${n.id}')">
          <div class="nf-icon ${n.type}" style="flex-shrink:0;width:32px;height:32px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:14px;
            background:${n.type === 'success' ? 'rgba(212,255,42,0.1)' : n.type === 'warn' ? 'rgba(245,158,11,0.1)' : 'rgba(59,130,246,0.1)'};">
            ${icon}
          </div>
          <div class="nf-body" style="flex:1;min-width:0">
            <div class="nf-title" style="font-family:var(--ff);font-weight:${isUnread ? '700' : '600'};color:var(--white);font-size:14px">${n.title}</div>
            <div class="nf-desc" style="font-size:13px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${n.message || ''}</div>
            <div class="nf-time" style="font-family:var(--fm);font-size:11px;color:var(--muted2);margin-top:6px">${timeAgo}</div>
          </div>
          ${isUnread ? '<div style="width:6px;height:6px;border-radius:50%;background:var(--lime);flex-shrink:0;margin-top:4px"></div>' : ''}
        </div>`;
    }).join('');

    container.innerHTML = headerHtml + html;
  } catch (e) {
    container.innerHTML = `
      <div style="padding:16px;color:var(--muted);font-family:var(--fm);font-size:13px">
        Could not load notifications — backend may be offline.
      </div>`;
  }
}

async function markNotificationRead(notifId) {
  try {
    await authFetch(API_BASE + `/api/notifications/${notifId}/read`, { method: 'PUT' });
    const card = document.getElementById(`notif-${notifId}`);
    if (card) {
      card.style.background = 'var(--s1)';
      card.style.border = '1px solid var(--line2)';
      card.style.boxShadow = 'none';
      const dot = card.querySelector('div[style*="border-radius:50%"]');
      if (dot) dot.remove();
    }
    // Reload to update unread count
    setTimeout(() => loadNotifications(), 300);
  } catch (e) {
    console.warn('Mark read failed:', e);
  }
}

async function markAllNotificationsRead() {
  try {
    await authFetch(API_BASE + '/api/notifications/read-all', { method: 'PUT' });
    loadNotifications();
  } catch (e) {
    console.warn('Mark all read failed:', e);
  }
}

function formatTimeAgo(isoString) {
  if (!isoString) return '';
  try {
    const date = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'));
    const diffMs = Date.now() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin} min${diffMin === 1 ? '' : 's'} ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`;
    const diffDay = Math.floor(diffHr / 24);
    return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`;
  } catch (e) {
    return '';
  }
}
