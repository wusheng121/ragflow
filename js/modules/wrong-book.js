import { api } from '../api.js';
import { formatDate, escapeHtml, showToast } from '../utils.js';

export async function renderWrongBook(container) {
  container.innerHTML = '<div class="page-loading"><div class="loading-spinner"></div></div>';

  const [subjects, items] = await Promise.all([api.getSubjects(), api.getWrongBook()]);

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">错题本</h2>
      <span style="color:var(--text-muted);font-family:var(--font-mono);font-size:0.85rem;">${items.length} 道错题</span>
    </div>
    <div class="filter-bar">
      <select class="form-select" id="filterSubject">
        <option value="">全部科目</option>
        ${subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('')}
      </select>
    </div>
    <div id="wrongList">${renderWrongList(items, subjects)}</div>
  `;

  document.getElementById('filterSubject').addEventListener('change', async (e) => {
    const filtered = await api.getWrongBook(e.target.value || undefined);
    document.getElementById('wrongList').innerHTML = renderWrongList(filtered, subjects);
    bindDeleteEvents(container);
  });

  bindDeleteEvents(container);
}

function renderWrongList(items, subjects) {
  if (!items.length) {
    return `<div class="empty-state">
      <div class="empty-icon">&#9733;</div>
      <h3 class="empty-title">暂无错题</h3>
      <p class="empty-desc">继续保持，或者去做一些练习吧</p>
    </div>`;
  }

  return items.map((item) => {
    const sub = subjects.find((s) => s.id === item.subjectId);
    return `<div class="card" style="margin-bottom:16px;" data-id="${item.id}">
      <div class="card-header">
        <span class="badge badge-danger">${escapeHtml(sub?.name || '未知')}</span>
        <button class="btn btn-sm btn-danger btn-remove" data-id="${item.id}">移除</button>
      </div>
      <p style="font-size:1rem;color:var(--text-primary);margin-bottom:16px;">${escapeHtml(item.question)}</p>
      <div style="display:grid;gap:8px;font-size:0.9rem;">
        <div><span style="color:var(--danger);">你的答案：</span>${escapeHtml(item.userAnswer)}</div>
        <div><span style="color:var(--success);">正确答案：</span>${escapeHtml(item.correctAnswer)}</div>
      </div>
      <div style="margin-top:12px;font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);">${formatDate(item.createdAt)}</div>
    </div>`;
  }).join('');
}

function bindDeleteEvents(container) {
  container.querySelectorAll('.btn-remove').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api.deleteWrongItem(btn.dataset.id);
      showToast('已从错题本移除', 'success');
      renderWrongBook(container);
    });
  });
}
