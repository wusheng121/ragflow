import { api, checkApiHealth, getAuthUser, isLoggedIn, logout } from './api.js';
import { renderChat, persistChatState } from './modules/chat.js';
import { renderDashboard } from './modules/dashboard.js';
import { renderSubjects } from './modules/subjects.js';
import { renderKnowledgeCards } from './modules/knowledge-cards.js';
import { renderPractice } from './modules/practice.js';
import { renderWrongBook } from './modules/wrong-book.js';
import { renderHistory } from './modules/history.js';

const PAGE_TITLES = {
  dashboard: '仪表盘',
  subjects: '科目管理',
  'knowledge-cards': '知识卡片',
  chat: '智能问答',
  practice: '练习抽查',
  'wrong-book': '错题本',
  history: '练习历史',
};

const pages = {
  dashboard: renderDashboard,
  subjects: renderSubjects,
  'knowledge-cards': renderKnowledgeCards,
  chat: renderChat,
  practice: renderPractice,
  'wrong-book': renderWrongBook,
  history: renderHistory,
};

/** Pages whose DOM is kept in memory when switching tabs (chat history, quiz progress, etc.) */
const KEEP_ALIVE_PAGES = new Set(['chat', 'practice']);
const pageRoots = {};

async function navigate(page) {
  if (!pages[page]) return;

  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.page === page);
  });

  document.getElementById('pageTitle').textContent = PAGE_TITLES[page];

  const container = document.getElementById('pageContent');

  // Always snapshot chat before any route change (avoids empty overwrite on other pages)
  persistChatState();

  // Detach cached keep-alive roots (preserve their DOM in memory)
  for (const el of Object.values(pageRoots)) {
    if (el?.parentNode === container) {
      el.remove();
    }
  }

  if (KEEP_ALIVE_PAGES.has(page)) {
    // Remove non-cached page markup (e.g. dashboard rendered directly into #pageContent)
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    if (!pageRoots[page]) {
      pageRoots[page] = document.createElement('div');
      pageRoots[page].className = `page-root page-${page}`;
    }
    container.appendChild(pageRoots[page]);
    await pages[page](pageRoots[page]);
  } else {
    container.replaceChildren();
    await pages[page](container);
  }

  document.getElementById('sidebar').classList.remove('open');
}

function initNavigation() {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', () => navigate(item.dataset.page));
  });

  window.addEventListener('navigate', (e) => navigate(e.detail));

  document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });

  document.getElementById('logoutBtn').addEventListener('click', () => logout());
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = '/';
    return false;
  }
  return true;
}

function showAccount() {
  const user = getAuthUser();
  const emailEl = document.getElementById('accountEmail');
  if (emailEl && user) {
    emailEl.textContent = user.email || user.username || '';
  }
}

async function init() {
  if (!requireAuth()) return;

  initNavigation();
  showAccount();

  const online = await checkApiHealth();
  const statusEl = document.getElementById('apiStatus');
  if (!online) {
    statusEl.textContent = '后端未连接';
    statusEl.parentElement.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    statusEl.parentElement.style.color = 'var(--danger, #ef4444)';
  } else {
    try {
      const me = await api.fetchMe();
      const emailEl = document.getElementById('accountEmail');
      if (emailEl && me?.email) {
        emailEl.textContent = me.email;
      }
      statusEl.textContent = 'API 已连接';
      statusEl.parentElement.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      statusEl.parentElement.style.color = 'var(--success)';
    } catch {
      logout();
      return;
    }
  }

  await navigate('dashboard');
}

init();

export { navigate };
