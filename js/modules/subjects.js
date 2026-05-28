import { api } from '../api.js';
import { formatDate, formatFileSize, escapeHtml, showToast, showModal } from '../utils.js';

export async function renderSubjects(container) {
  container.innerHTML = '<div class="page-loading"><div class="loading-spinner"></div></div>';
  const subjects = await api.getSubjects();

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">\u79d1\u76ee\u7ba1\u7406</h2>
      <button class="btn btn-primary" id="btnNewSubject">+ \u65b0\u5efa\u79d1\u76ee</button>
    </div>
    ${subjects.length
        ? `<div class="card-grid" id="subjectGrid">${subjects.map(renderSubjectCard).join('')}</div>`
        : `<div class="empty-state">
            <div class="empty-icon">&#128218;</div>
            <h3 class="empty-title">\u8fd8\u6ca1\u6709\u79d1\u76ee</h3>
            <p class="empty-desc">\u521b\u5efa\u7b2c\u4e00\u4e2a\u79d1\u76ee\uff0c\u4e0a\u4f20\u8d44\u6599\u5f00\u59cb\u667a\u80fd\u590d\u4e60</p>
            <button class="btn btn-primary" id="btnNewSubjectEmpty">+ \u65b0\u5efa\u79d1\u76ee</button>
          </div>`}
  `;

  container.querySelector('#btnNewSubject')?.addEventListener('click', openCreateModal);
  container.querySelector('#btnNewSubjectEmpty')?.addEventListener('click', openCreateModal);
  bindSubjectEvents(container);
}

function renderSubjectCard(s) {
  return `
    <div class="subject-card" data-id="${s.id}">
      <div class="subject-card-header">
        <div>
          <div class="subject-name">${escapeHtml(s.name)}</div>
          <div class="subject-desc">${escapeHtml(s.description || '\u6682\u65e0\u63cf\u8ff0')}</div>
        </div>
        <button class="btn btn-sm btn-danger btn-delete" data-id="${s.id}" title="\u5220\u9664">&#128465;</button>
      </div>
      <div class="subject-meta">
        <span class="meta-item">&#128196; ${s.materialCount} \u4efd\u8d44\u6599</span>
        <span class="meta-item">&#129504; ${s.cardCount} \u5f20\u5361\u7247</span>
      </div>
      <div class="subject-meta" style="border:none;padding-top:8px;">
        <span class="meta-item">&#128336; ${formatDate(s.createdAt)}</span>
      </div>
    </div>
  `;
}

function bindSubjectEvents(container) {
  container.querySelectorAll('.subject-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.btn-delete')) return;
      openSubjectDetail(card.dataset.id);
    });
  });

  container.querySelectorAll('.btn-delete').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('\u786e\u5b9a\u5220\u9664\u8be5\u79d1\u76ee\u53ca\u6240\u6709\u5173\u8054\u6570\u636e\uff1f')) return;
      await api.deleteSubject(btn.dataset.id);
      showToast('\u79d1\u76ee\u5df2\u5220\u9664', 'success');
      renderSubjects(container);
    });
  });
}

function openCreateModal() {
  showModal({
    title: '\u65b0\u5efa\u79d1\u76ee',
    body: `
      <div class="form-group">
        <label class="form-label">\u79d1\u76ee\u540d\u79f0 *</label>
        <input class="form-input" id="subjectName" placeholder="\u4f8b\u5982\uff1a\u64cd\u4f5c\u7cfb\u7edf\u3001\u7ebf\u6027\u4ee3\u6570">
      </div>
      <div class="form-group">
        <label class="form-label">\u63cf\u8ff0</label>
        <textarea class="form-textarea" id="subjectDesc" placeholder="\u7b80\u8981\u63cf\u8ff0\u8be5\u79d1\u76ee\u7684\u590d\u4e60\u8303\u56f4"></textarea>
      </div>
    `,
    footer: `
      <button class="btn btn-secondary" id="modalCancel">\u53d6\u6d88</button>
      <button class="btn btn-primary" id="modalConfirm">\u521b\u5efa</button>
    `,
  });

  document.getElementById('modalCancel').onclick = () =>
    document.getElementById('modalOverlay').classList.remove('active');

  document.getElementById('modalConfirm').onclick = async () => {
    const name = document.getElementById('subjectName').value.trim();
    if (!name) {
      showToast('\u8bf7\u8f93\u5165\u79d1\u76ee\u540d\u79f0', 'error');
      return;
    }
    const description = document.getElementById('subjectDesc').value.trim();
    const subject = await api.createSubject({ name, description });
    document.getElementById('modalOverlay').classList.remove('active');
    showToast('\u79d1\u76ee\u300c' + name + '\u300d\u521b\u5efa\u6210\u529f', 'success');
    openSubjectDetail(subject.id);
  };
}

function renderUploadedMaterials(materials) {
  return materials.map((m) => `
    <div class="file-item" data-material-id="${m.id}">
      <span class="file-info"><span>&#128196;</span><span class="file-name">${escapeHtml(m.name)}</span></span>
      <span class="file-size">${formatFileSize(m.size)}</span>
      <button class="btn btn-sm btn-danger btn-delete-material" data-id="${m.id}" title="\u5220\u9664\u8d44\u6599">&times;</button>
    </div>`).join('');
}

function clampExtractCount(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return 10;
  return Math.max(1, Math.min(50, Math.floor(n)));
}

async function openSubjectDetail(subjectId) {
  const [subjects, materials] = await Promise.all([
    api.getSubjects(),
    api.getMaterials(subjectId),
  ]);
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return;

  let pendingFiles = [];
  let uploadedMaterials = [...materials];

  showModal({
    title: subject.name,
    body: `
      <p style="margin-bottom:20px;color:var(--text-muted);">${escapeHtml(subject.description || '')}</p>
      <div class="form-group">
        <label class="form-label">\u4e0a\u4f20\u8d44\u6599</label>
        <div class="upload-zone" id="uploadZone">
          <div class="upload-icon">&#128193;</div>
          <p class="upload-text">\u62d6\u62fd\u6587\u4ef6\u5230\u6b64\u5904\uff0c\u6216\u70b9\u51fb\u9009\u62e9</p>
          <p class="upload-hint">\u652f\u6301 PDF / PPT / PPTX / DOC / DOCX / TXT / MD</p>
          <input type="file" id="fileInput" multiple accept=".pdf,.ppt,.pptx,.doc,.docx,.txt,.md" hidden>
        </div>
        <div class="file-list" id="fileList"></div>
      </div>
      <div id="uploadedMaterialsSection" style="margin-top:20px;" ${uploadedMaterials.length ? '' : 'hidden'}>
        <label class="form-label" id="uploadedMaterialsLabel">\u5df2\u4e0a\u4f20 (${uploadedMaterials.length})</label>
        <div id="uploadedMaterialsList">${renderUploadedMaterials(uploadedMaterials)}</div>
      </div>
      <div class="form-group" style="margin-top:20px;">
        <label class="form-label" for="extractCount">\u672c\u6b21\u751f\u6210\u5361\u7247\u6570\u91cf</label>
        <input class="form-input" type="number" id="extractCount" min="1" max="50" value="10" style="max-width:120px;">
        <p class="upload-hint" style="margin-top:6px;">\u6700\u591a 50 \u5f20\uff0c\u6309\u91cd\u8981\u6027\u62bd\u53d6\u4e13\u4e1a\u672f\u8bed</p>
      </div>
    `,
    footer: `
      <div id="uploadProgressPanel" class="extract-progress-panel" hidden>
        <div class="extract-progress-header">
          <span id="uploadProgressMessage">\u51c6\u5907\u4e0a\u4f20\u2026</span>
          <span id="uploadProgressPercent" class="progress-text">0%</span>
        </div>
        <div class="progress-bar extract-progress-bar">
          <div class="progress-fill" id="uploadProgressFill" style="width:0%;"></div>
        </div>
      </div>
      <div id="extractProgressPanel" class="extract-progress-panel" hidden>
        <div class="extract-progress-header">
          <span id="extractProgressMessage">\u51c6\u5907\u62bd\u53d6\u2026</span>
          <span id="extractProgressPercent" class="progress-text">0%</span>
        </div>
        <div class="progress-bar extract-progress-bar">
          <div class="progress-fill" id="extractProgressFill" style="width:0%;"></div>
        </div>
      </div>
      <div class="modal-footer-actions">
        <button class="btn btn-secondary" id="modalCancel">\u5173\u95ed</button>
        <button class="btn btn-secondary" id="btnExtract" ${uploadedMaterials.length ? '' : 'disabled'}>\u62bd\u53d6\u4e13\u6709\u540d\u8bcd\u4e0e\u672f\u8bed</button>
        <button class="btn btn-primary" id="btnUpload">\u4e0a\u4f20\u8d44\u6599</button>
      </div>
    `,
  });

  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('fileInput');
  const fileList = document.getElementById('fileList');
  const btnExtract = document.getElementById('btnExtract');
  const uploadedSection = document.getElementById('uploadedMaterialsSection');
  const uploadedList = document.getElementById('uploadedMaterialsList');
  const uploadedLabel = document.getElementById('uploadedMaterialsLabel');

  function refreshUploadedMaterials() {
    if (uploadedMaterials.length) {
      uploadedSection.hidden = false;
      uploadedLabel.textContent = `\u5df2\u4e0a\u4f20 (${uploadedMaterials.length})`;
      uploadedList.innerHTML = renderUploadedMaterials(uploadedMaterials);
      btnExtract.disabled = false;
      bindMaterialDeleteButtons();
    } else {
      uploadedSection.hidden = true;
      uploadedList.innerHTML = '';
      btnExtract.disabled = true;
    }
  }

  function bindMaterialDeleteButtons() {
    uploadedList.querySelectorAll('.btn-delete-material').forEach((btn) => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const materialId = btn.dataset.id;
        const item = uploadedMaterials.find((m) => m.id === materialId);
        if (!item) return;
        if (!confirm('\u786e\u5b9a\u5220\u9664\u8d44\u6599\u300c' + item.name + '\u300d\u5417\uff1f')) return;
        try {
          await api.deleteMaterial(subjectId, materialId);
          uploadedMaterials = uploadedMaterials.filter((m) => m.id !== materialId);
          refreshUploadedMaterials();
          showToast('\u8d44\u6599\u5df2\u5220\u9664', 'success');
        } catch (err) {
          showToast(err.message || '\u5220\u9664\u5931\u8d25', 'error');
        }
      };
    });
  }

  bindMaterialDeleteButtons();

  zone.onclick = () => input.click();
  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('dragover'); };
  zone.ondragleave = () => zone.classList.remove('dragover');
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    addFiles([...e.dataTransfer.files]);
  };
  input.onchange = () => { addFiles([...input.files]); input.value = ''; };

  function renderPendingList() {
    fileList.innerHTML = pendingFiles.map((f, i) => `<div class="file-item">
          <span class="file-info"><span>&#128196;</span><span class="file-name">${escapeHtml(f.name)}</span></span>
          <button class="btn btn-sm btn-danger" data-idx="${i}">&times;</button>
        </div>`).join('');
    fileList.querySelectorAll('button').forEach((btn) => {
      btn.onclick = () => { pendingFiles.splice(Number(btn.dataset.idx), 1); renderPendingList(); };
    });
  }

  function addFiles(files) { pendingFiles.push(...files); renderPendingList(); }

  document.getElementById('modalCancel').onclick = () =>
    document.getElementById('modalOverlay').classList.remove('active');

  document.getElementById('btnUpload').onclick = async () => {
    if (!pendingFiles.length) {
      showToast('\u8bf7\u9009\u62e9\u8981\u4e0a\u4f20\u7684\u6587\u4ef6', 'error');
      return;
    }

    const uploadBtn = document.getElementById('btnUpload');
    const extractBtn = document.getElementById('btnExtract');
    const cancelBtn = document.getElementById('modalCancel');
    const uploadPanel = document.getElementById('uploadProgressPanel');
    const uploadFill = document.getElementById('uploadProgressFill');
    const uploadMsg = document.getElementById('uploadProgressMessage');
    const uploadPct = document.getElementById('uploadProgressPercent');
    const extractPanel = document.getElementById('extractProgressPanel');

    const setUploadProgress = (percent, message) => {
      const p = Math.max(0, Math.min(100, percent));
      uploadFill.style.width = `${p}%`;
      uploadPct.textContent = `${p}%`;
      if (message) uploadMsg.textContent = message;
    };

    uploadBtn.disabled = true;
    extractBtn.disabled = true;
    cancelBtn.disabled = true;
    extractPanel.hidden = true;
    uploadPanel.hidden = false;
    setUploadProgress(0, '\u51c6\u5907\u4e0a\u4f20\u2026');

    try {
      const added = await api.uploadMaterials(subjectId, pendingFiles, setUploadProgress);
      uploadedMaterials = [...added, ...uploadedMaterials];
      pendingFiles = [];
      renderPendingList();
      refreshUploadedMaterials();
      showToast('\u8d44\u6599\u4e0a\u4f20\u6210\u529f', 'success');
    } catch (err) {
      showToast(err.message || '\u4e0a\u4f20\u5931\u8d25', 'error');
    } finally {
      uploadBtn.disabled = false;
      extractBtn.disabled = uploadedMaterials.length === 0;
      cancelBtn.disabled = false;
      uploadPanel.hidden = true;
      setUploadProgress(0, '');
    }
  };

  document.getElementById('extractCount').addEventListener('change', (e) => {
    e.target.value = clampExtractCount(e.target.value);
  });

  btnExtract.onclick = async () => {
    const uploadBtn = document.getElementById('btnUpload');
    const cancelBtn = document.getElementById('modalCancel');
    const uploadPanel = document.getElementById('uploadProgressPanel');
    const panel = document.getElementById('extractProgressPanel');
    const fill = document.getElementById('extractProgressFill');
    const msgEl = document.getElementById('extractProgressMessage');
    const pctEl = document.getElementById('extractProgressPercent');
    const extractCount = clampExtractCount(document.getElementById('extractCount').value);
    document.getElementById('extractCount').value = extractCount;

    const setProgress = (percent, message) => {
      const p = Math.max(0, Math.min(100, percent));
      fill.style.width = `${p}%`;
      pctEl.textContent = `${p}%`;
      if (message) msgEl.textContent = message;
    };

    btnExtract.disabled = true;
    uploadBtn.disabled = true;
    cancelBtn.disabled = true;
    uploadPanel.hidden = true;
    panel.hidden = false;
    setProgress(0, '\u51c6\u5907\u62bd\u53d6\u2026');

    try {
      const cards = await api.extractConcepts(subjectId, setProgress, extractCount);
      setProgress(100, `\u5b8c\u6210\uff0c\u5171\u62bd\u53d6 ${cards.length} \u4e2a\u672f\u8bed`);
      showToast('\u5df2\u4ece\u8d44\u6599\u4e2d\u62bd\u53d6 ' + cards.length + ' \u4e2a\u4e13\u6709\u540d\u8bcd/\u672f\u8bed', 'success');
      document.getElementById('modalOverlay').classList.remove('active');
      window.dispatchEvent(new CustomEvent('navigate', { detail: 'knowledge-cards' }));
    } catch (err) {
      showToast(err.message || '\u62bd\u53d6\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5', 'error');
    } finally {
      btnExtract.disabled = uploadedMaterials.length === 0;
      uploadBtn.disabled = false;
      cancelBtn.disabled = false;
      panel.hidden = true;
      setProgress(0, '');
    }
  };
}
