'use strict';

// Sidebar toggle
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn  = document.getElementById('sidebarToggle');
  const closeBtn   = document.getElementById('sidebarCloseBtn');
  const sidebar    = document.getElementById('sidebar');
  const overlay    = document.getElementById('sidebarOverlay');

  function isMobile() { return window.innerWidth <= 768; }

  function openMobileSidebar() {
    sidebar.classList.add('mobile-open');
    overlay.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeMobileSidebar() {
    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('show');
    document.body.style.overflow = '';
  }

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      if (isMobile()) {
        sidebar.classList.contains('mobile-open') ? closeMobileSidebar() : openMobileSidebar();
      } else {
        sidebar.classList.toggle('collapsed');
        localStorage.setItem('sidebar_collapsed', sidebar.classList.contains('collapsed'));
      }
    });

    // Restore collapsed state on desktop
    if (localStorage.getItem('sidebar_collapsed') === 'true' && !isMobile()) {
      sidebar.classList.add('collapsed');
    }
  }

  // Close button inside sidebar (mobile)
  if (closeBtn) {
    closeBtn.addEventListener('click', closeMobileSidebar);
  }

  // Overlay click closes sidebar
  if (overlay) {
    overlay.addEventListener('click', closeMobileSidebar);
  }

  // Close on resize to desktop
  window.addEventListener('resize', () => {
    if (!isMobile()) {
      closeMobileSidebar();
    }
  });

  // Close when a nav link is clicked on mobile
  if (sidebar) {
    sidebar.querySelectorAll('.sidebar-link').forEach(link => {
      link.addEventListener('click', () => {
        if (isMobile()) closeMobileSidebar();
      });
    });
  }
});

// Toast notifications
function showToast(message, type = 'primary') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const id = 'toast_' + Date.now();
  const icons = { success: 'check-circle-fill', danger: 'exclamation-triangle-fill', warning: 'exclamation-circle-fill', info: 'info-circle-fill', primary: 'bell-fill' };
  const icon = icons[type] || icons.primary;
  const toast = document.createElement('div');
  toast.id = id;
  toast.className = `toast align-items-center text-white bg-${type} border-0 show`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `<div class="d-flex"><div class="toast-body"><i class="bi bi-${icon} me-2"></i>${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('${id}').remove()"></button></div>`;
  container.appendChild(toast);
  setTimeout(() => { const el = document.getElementById(id); if (el) el.remove(); }, 4000);
}

// Notifications
async function markNotifsRead() {
  await fetch('/api/notifications/read', { method: 'POST' });
  document.querySelectorAll('.badge.rounded-pill.bg-danger').forEach(el => el.remove());
  document.getElementById('notifDropdown')?.querySelectorAll('.dropdown-item-text').forEach(el => el.remove());
  showToast('All notifications marked as read', 'info');
}

// PWA Install
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = document.getElementById('installBtn');
  if (btn) btn.classList.remove('d-none');
});

window.addEventListener('appinstalled', () => {
  const btn = document.getElementById('installBtn');
  if (btn) btn.classList.add('d-none');
  deferredPrompt = null;
});

async function installPWA() {
  if (!deferredPrompt) { showToast('App is already installed or not available', 'info'); return; }
  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  if (outcome === 'accepted') showToast('App installed successfully!', 'success');
  deferredPrompt = null;
}

// Report content — delegated handler for all .report-btn buttons
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.report-btn');
  if (!btn) return;
  const contentType = btn.dataset.type || '';
  const contentId   = btn.dataset.id   || '';
  const contentTitle   = btn.dataset.title   || '';
  const contentSnippet = btn.dataset.snippet || '';
  if (typeof openReportModal === 'function') {
    openReportModal(contentType, contentId, contentTitle, contentSnippet);
  }
});

// Register Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW registration failed:', err));
  });
}
