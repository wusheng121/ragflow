const STORAGE_PREFIX = 'ragflow_review_data';

function storageKey() {
  try {
    const raw = localStorage.getItem('ragflow_auth_user');
    if (raw) {
      const user = JSON.parse(raw);
      if (user?.id) return `${STORAGE_PREFIX}_${user.id}`;
    }
  } catch {
    /* ignore */
  }
  return STORAGE_PREFIX;
}

export function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function escapeHtml(str) {
  const el = document.createElement('div');
  el.textContent = str;
  return el.innerHTML;
}

export function nl2br(str) {
  return escapeHtml(str || '').replace(/\n/g, '<br>');
}

export function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { success: '\u2713', error: '\u2715', info: '\u2139' };
  toast.innerHTML = `<span>${icons[type] || '\u2139'}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

export function showModal({ title, body, footer, onClose }) {
  const overlay = document.getElementById('modalOverlay');
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = body;
  document.getElementById('modalFooter').innerHTML = footer || '';

  const close = () => {
    overlay.classList.remove('active');
    if (onClose) onClose();
  };

  document.getElementById('modalClose').onclick = close;
  overlay.onclick = (e) => {
    if (e.target === overlay) close();
  };

  overlay.classList.add('active');
  return { close };
}

export function getStore() {
  try {
    const raw = localStorage.getItem(storageKey());
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return getDefaultStore();
}

export function saveStore(data) {
  localStorage.setItem(storageKey(), JSON.stringify(data));
}

function getDefaultStore() {
  return {
    subjects: [],
    materials: [],
    knowledgeCards: [],
    practiceSessions: [],
    wrongAnswers: [],
  };
}

export function shuffleArray(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
