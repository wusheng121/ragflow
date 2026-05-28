import { api } from '../api.js';
import { formatDate, escapeHtml, showModal, showToast, nl2br } from '../utils.js';

let cardsCache = [];
let pageSubjects = [];

export async function renderKnowledgeCards(container) {
  container.innerHTML = '<div class="page-loading"><div class="loading-spinner"></div></div>';
  const [subjects, cards] = await Promise.all([api.getSubjects(), api.getKnowledgeCards()]);
  pageSubjects = subjects;
  cardsCache = cards;

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">知识卡片</h2>
    </div>
    <div class="filter-bar">
      <select class="form-select" id="filterSubject">
        <option value="">全部科目</option>
        ${subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('')}
      </select>
      <button class="btn btn-danger btn-sm" id="btnDeleteAllBySubject" hidden>删除本科目全部卡片</button>
      <span id="cardsCountHint" style="color:var(--text-muted);font-size:0.85rem;font-family:var(--font-mono);">共 ${cards.length} 张卡片 · 点击查看详情</span>
    </div>
    <div id="cardsContainer">
      ${renderCardsGrid(cards, subjects)}
    </div>
  `;

  const filterEl = document.getElementById('filterSubject');
  const deleteAllBtn = document.getElementById('btnDeleteAllBySubject');

  function updateBulkActions() {
    deleteAllBtn.hidden = !filterEl.value;
  }

  filterEl.addEventListener('change', async (e) => {
    const subjectId = e.target.value || undefined;
    const filtered = await api.getKnowledgeCards(subjectId);
    cardsCache = filtered;
    document.getElementById('cardsContainer').innerHTML = renderCardsGrid(filtered, subjects);
    updateCountHint(filtered.length);
    updateBulkActions();
    bindCardEvents(document.getElementById('cardsContainer'), subjects);
  });

  deleteAllBtn.addEventListener('click', async () => {
    const subjectId = filterEl.value;
    if (!subjectId) return;
    const subject = subjects.find((s) => s.id === subjectId);
    const name = subject?.name || '该科目';
    if (!confirm(`确定删除「${name}」下的全部 ${cardsCache.length} 张知识卡片吗？此操作不可恢复。`)) return;
    try {
      await api.deleteKnowledgeCardsBySubject(subjectId);
      cardsCache = [];
      document.getElementById('cardsContainer').innerHTML = renderCardsGrid([], subjects);
      updateCountHint(0);
      showToast('已删除本科目全部卡片', 'success');
    } catch (err) {
      showToast(err.message || '删除失败', 'error');
    }
  });

  updateBulkActions();
  bindCardEvents(document.getElementById('cardsContainer'), subjects);
}

function updateCountHint(count) {
  document.getElementById('cardsCountHint').textContent =
    `共 ${count} 张卡片 · 点击查看详情`;
}

function refreshGrid() {
  const filterEl = document.getElementById('filterSubject');
  const subjectId = filterEl?.value || '';
  document.getElementById('cardsContainer').innerHTML = renderCardsGrid(cardsCache, pageSubjects);
  updateCountHint(cardsCache.length);
  bindCardEvents(document.getElementById('cardsContainer'), pageSubjects);
  if (filterEl && subjectId) filterEl.value = subjectId;
  const deleteAllBtn = document.getElementById('btnDeleteAllBySubject');
  if (deleteAllBtn) deleteAllBtn.hidden = !subjectId;
}

function renderCardsGrid(cards, subjects) {
  if (!cards.length) {
    return `<div class="empty-state">
      <div class="empty-icon">★</div>
      <h3 class="empty-title">暂无知识卡片</h3>
      <p class="empty-desc">请先在科目管理中上传资料，由 AI 根据原文抽取术语并生成一句话解释与详细说明</p>
      <button class="btn btn-primary" id="gotoSubjects">前往科目管理</button>
    </div>`;
  }

  return `<div class="card-grid">${cards
    .map((c) => `<div class="knowledge-card" data-id="${c.id}">
        <button class="card-delete-btn" data-id="${c.id}" title="删除卡片" aria-label="删除卡片">&times;</button>
        <div class="concept-title">${escapeHtml(c.concept)}</div>
        <div class="concept-preview">${escapeHtml(c.summary)}</div>
        <div class="card-hint">点击查看详细解释 →</div>
      </div>`)
    .join('')}</div>`;
}

function bindCardEvents(container, subjects) {
  container.querySelector('#gotoSubjects')?.addEventListener('click', () => {
    window.dispatchEvent(new CustomEvent('navigate', { detail: 'subjects' }));
  });

  container.querySelectorAll('.card-delete-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      handleDeleteCard(btn.dataset.id);
    });
  });

  container.querySelectorAll('.knowledge-card').forEach((el) => {
    el.addEventListener('click', () => {
      const card = cardsCache.find((c) => c.id === el.dataset.id);
      if (card) openCardDetail(card, subjects);
    });
  });
}

async function handleDeleteCard(cardId) {
  try {
    await api.deleteKnowledgeCard(cardId);
    cardsCache = cardsCache.filter((c) => c.id !== cardId);
    refreshGrid();
    showToast('已删除知识卡片', 'success');
  } catch (err) {
    showToast(err.message || '删除失败', 'error');
  }
}

function openCardDetail(card, subjects) {
  const sub = subjects.find((s) => s.id === card.subjectId);

  const modal = document.getElementById('modal');
  modal.classList.add('modal-lg');

  const { close } = showModal({
    title: card.concept,
    body: `
      <div class="card-detail-modal">
        <div class="card-detail-section">
          <label class="form-label">所属科目</label>
          <p>${escapeHtml(sub?.name || '未知')}</p>
        </div>
        <div class="card-detail-section">
          <label class="form-label">简介</label>
          <p class="card-detail-text">${nl2br(card.summary)}</p>
        </div>
        <div class="card-detail-section">
          <label class="form-label">详细说明</label>
          <div class="card-detail-full">${nl2br(card.detail || '暂无详细说明')}</div>
        </div>
        <div class="card-detail-footer">
          <span>创建时间：${formatDate(card.createdAt)}</span>
        </div>
      </div>
    `,
    footer: `
      <button class="btn btn-danger" id="modalDeleteBtn">删除卡片</button>
      <button class="btn btn-secondary" id="modalCloseBtn">关闭</button>
    `,
    onClose: () => modal.classList.remove('modal-lg'),
  });

  document.getElementById('modalCloseBtn')?.addEventListener('click', close);
  document.getElementById('modalDeleteBtn')?.addEventListener('click', async () => {
    close();
    await handleDeleteCard(card.id);
  });
}
