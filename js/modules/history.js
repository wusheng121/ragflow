import { api } from '../api.js';
import { formatDate, escapeHtml } from '../utils.js';

export async function renderHistory(container) {
  container.innerHTML = '<div class="page-loading"><div class="loading-spinner"></div></div>';

  const [subjects, sessions] = await Promise.all([api.getSubjects(), api.getHistory()]);

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">练习历史</h2>
      <span style="color:var(--text-muted);font-family:var(--font-mono);font-size:0.85rem;">${sessions.length} 次练习</span>
    </div>
    ${sessions.length
        ? `<div class="card">
            <table class="data-table">
              <thead>
                <tr>
                  <th>科目</th>
                  <th>得分</th>
                  <th>正确率</th>
                  <th>用时</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                ${sessions.map((s) => {
                  const sub = subjects.find((x) => x.id === s.subjectId);
                  const pct = Math.round((s.score / s.total) * 100);
                  const badge = pct >= 80 ? 'badge-success' : pct >= 60 ? 'badge-warning' : 'badge-danger';
                  return `<tr>
                    <td>${escapeHtml(sub?.name || '未知科目')}</td>
                    <td>${s.score} / ${s.total}</td>
                    <td><span class="badge ${badge}">${pct}%</span></td>
                    <td>${s.duration}s</td>
                    <td>${formatDate(s.createdAt)}</td>
                  </tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>`
        : `<div class="empty-state">
            <div class="empty-icon">&#9733;</div>
            <h3 class="empty-title">暂无练习记录</h3>
            <p class="empty-desc">完成第一次练习后，记录将显示在这里</p>
            <button class="btn btn-primary" id="gotoPractice">开始练习</button>
          </div>`}
  `;

  document.getElementById('gotoPractice')?.addEventListener('click', () => {
    window.dispatchEvent(new CustomEvent('navigate', { detail: 'practice' }));
  });
}
