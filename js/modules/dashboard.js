import { api } from '../api.js';
import { formatDate, escapeHtml } from '../utils.js';

export async function renderDashboard(container) {
  container.innerHTML = '<div class="page-loading"><div class="loading-spinner"></div><div class="page-loading-text">\u52a0\u8f7d\u4e2d...</div></div>';

  const [stats, subjects, history] = await Promise.all([
    api.getStats(),
    api.getSubjects(),
    api.getHistory(),
  ]);

  const recentHistory = history.slice(0, 5);
  const accuracy = history.length
    ? Math.round(
        (history.reduce((s, h) => s + h.score, 0) / history.reduce((s, h) => s + h.total, 0)) * 100
      )
    : 0;

  container.innerHTML = `
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">${stats.subjectCount}</div>
        <div class="stat-label">\u79d1\u76ee\u603b\u6570</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.cardCount}</div>
        <div class="stat-label">\u77e5\u8bc6\u5361\u7247</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.sessionCount}</div>
        <div class="stat-label">\u7ec3\u4e60\u6b21\u6570</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${accuracy}%</div>
        <div class="stat-label">\u603b\u6b63\u786e\u7387</div>
      </div>
    </div>

    <div class="section-header">
      <h2 class="section-title">\u5feb\u901f\u5f00\u59cb</h2>
    </div>
    <div class="card-grid" style="margin-bottom:32px;">
      <div class="card" style="cursor:pointer;" data-action="goto" data-page="subjects">
        <h3 style="margin-bottom:8px;color:var(--accent-primary);">\u65b0\u5efa\u79d1\u76ee</h3>
        <p>\u521b\u5efa\u5b66\u4e60\u79d1\u76ee\u5e76\u4e0a\u4f20\u590d\u4e60\u8d44\u6599</p>
      </div>
      <div class="card" style="cursor:pointer;" data-action="goto" data-page="knowledge-cards">
        <h3 style="margin-bottom:8px;color:var(--accent-primary);">\u6d4f\u89c8\u5361\u7247</h3>
        <p>\u67e5\u770b\u4ece\u8d44\u6599\u4e2d\u62bd\u53d6\u7684\u4e13\u6709\u540d\u8bcd\u4e0e\u672f\u8bed</p>
      </div>
      <div class="card" style="cursor:pointer;" data-action="goto" data-page="chat">
        <h3 style="margin-bottom:8px;color:var(--accent-primary);">\u667a\u80fd\u95ee\u7b54</h3>
        <p>\u5411 AI \u52a9\u624b\u63d0\u95ee\uff0c\u7ed3\u5408\u77e5\u8bc6\u5361\u7247\u89e3\u7b54\u590d\u4e60\u96be\u70b9</p>
      </div>
      <div class="card" style="cursor:pointer;" data-action="goto" data-page="practice">
        <h3 style="margin-bottom:8px;color:var(--accent-primary);">\u5f00\u59cb\u7ec3\u4e60</h3>
        <p>\u57fa\u4e8e\u77e5\u8bc6\u5361\u7247\u8fdb\u884c\u62bd\u67e5\u7ec3\u4e60</p>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h3 class="card-title">\u6700\u8fd1\u7ec3\u4e60</h3>
        <button class="btn btn-sm btn-secondary" data-action="goto" data-page="history">\u67e5\u770b\u5168\u90e8</button>
      </div>
      ${
        recentHistory.length
          ? `<table class="data-table">
              <thead><tr><th>\u79d1\u76ee</th><th>\u5f97\u5206</th><th>\u65f6\u95f4</th></tr></thead>
              <tbody>${recentHistory
                .map((h) => {
                  const sub = subjects.find((s) => s.id === h.subjectId);
                  return `<tr>
                    <td>${escapeHtml(sub?.name || '\u672a\u77e5\u79d1\u76ee')}</td>
                    <td><span class="badge ${h.score / h.total >= 0.6 ? 'badge-success' : 'badge-warning'}">${h.score}/${h.total}</span></td>
                    <td>${formatDate(h.createdAt)}</td>
                  </tr>`;
                })
                .join('')}</tbody>
            </table>`
          : `<div class="empty-state" style="padding:32px;">
              <p class="empty-desc">\u6682\u65e0\u7ec3\u4e60\u8bb0\u5f55\uff0c\u53bb\u5f00\u59cb\u7b2c\u4e00\u6b21\u7ec3\u4e60\u5427</p>
            </div>`
      }
    </div>
  `;

  container.querySelectorAll('[data-action="goto"]').forEach((el) => {
    el.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('navigate', { detail: el.dataset.page }));
    });
  });
}
