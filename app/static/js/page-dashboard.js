const USER_KEY = 'rag_review_current_user';
const TOKEN_KEY = 'rag_review_token';
let currentPracticeQuestion = '';
const SUPPORTED_UPLOAD_EXTENSIONS = new Set(['pdf', 'pptx', 'docx', 'txt', 'md']);
let currentReferences = [];
let cachedSubjects = [];
const ACTIVE_SUBJECT_KEY = 'rag_review_active_subject';

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch {
    return null;
  }
}

function readSubjectIdFromUrl() {
  const value = new URLSearchParams(window.location.search).get('subject_id');
  return value ? Number(value) : 0;
}

function saveUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function saveSession(auth) {
  localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
  localStorage.setItem(TOKEN_KEY, auth.access_token);
}

function loadToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function clearUser() {
  localStorage.removeItem(USER_KEY);
}

function clearSession() {
  clearUser();
  localStorage.removeItem(TOKEN_KEY);
}

function getActiveSubjectId() {
  return readSubjectIdFromUrl() || Number(localStorage.getItem(ACTIVE_SUBJECT_KEY) || 0);
}

function saveActiveSubject(id) {
  if (!id) {
    localStorage.removeItem(ACTIVE_SUBJECT_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_SUBJECT_KEY, String(id));
}

function buildSubjectUrl(subjectId) {
  const url = new URL(window.location.href);
  if (subjectId) {
    url.searchParams.set('subject_id', String(subjectId));
  } else {
    url.searchParams.delete('subject_id');
  }
  return url.pathname + (url.searchParams.toString() ? `?${url.searchParams.toString()}` : '');
}

function syncSubjectControls(subjectId) {
  const scopeSelect = $('#study-scope');
  const studySubjectSelect = $('#study-subject-select');
  const materialSubjectSelect = $('#material-subject-select');

  if (scopeSelect) scopeSelect.value = subjectId ? 'subject' : 'material';
  if (studySubjectSelect) studySubjectSelect.value = subjectId ? String(subjectId) : '';
  if (materialSubjectSelect) materialSubjectSelect.value = subjectId ? String(subjectId) : '';
}

function renderSidebarSubjects(subjects) {
  const host = $('#sidebar-subject-list');
  if (!host) return;
  const activeId = getActiveSubjectId();
  host.innerHTML = `
    <button type="button" class="subject-card ${activeId ? '' : 'active'}" data-subject-mode="all">
      <span class="subject-card-name">全部文件</span>
      <span class="subject-card-meta">默认按文件操作</span>
    </button>
    ${subjects.length ? subjects.map((item) => `
      <button type="button" class="subject-card ${activeId === item.id ? 'active' : ''}" data-subject-id="${item.id}">
        <span class="subject-card-name">${escapeHtml(item.name)}</span>
        <span class="subject-card-meta">${item.materials_count ?? 0} 份资料</span>
      </button>
    `).join('') : '<div class="small">暂无学科，请先新建。</div>'}
    <a class="subject-create-card" href="/materials#subject-form">＋ 新建学科</a>
  `;

  host.onclick = (event) => {
    const target = event.target.closest('[data-subject-id], [data-subject-mode]');
    if (!target) return;
    if (target.dataset.subjectMode === 'all') {
      saveActiveSubject(0);
      window.location.href = buildSubjectUrl(0);
      return;
    }
    const subjectId = Number(target.dataset.subjectId || 0);
    if (!subjectId) return;
    saveActiveSubject(subjectId);
    window.location.href = buildSubjectUrl(subjectId);
  };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function api(path, options = {}) {
  const token = loadToken();
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = data?.detail || data?.message || data || '请求失败';
    if (response.status === 401) {
      clearSession();
      if (!['/login', '/register'].includes(location.pathname)) {
        location.href = '/login';
      }
    }
    throw new Error(Array.isArray(message) ? message.join(', ') : message);
  }
  return data;
}

function setNotice(message, kind = 'info') {
  const box = ensureNoticeBox();
  if (!box) return;
  box.className = `notice ${kind}`;
  box.textContent = message;
  box.classList.remove('hidden');
}

function ensureNoticeBox() {
  let box = $('#auth-message');
  if (box) return box;
  const host = $('.page-content') || document.body;
  box = document.createElement('div');
  box.id = 'auth-message';
  box.className = 'notice hidden';
  box.setAttribute('role', 'status');
  box.setAttribute('aria-live', 'polite');
  host.prepend(box);
  return box;
}

function renderUser(user) {
  const dashboard = $('#dashboard');
  const currentUserName = $('#current-user-name');
  const currentUserLevel = $('#current-user-level');
  if (!user) {
    dashboard?.classList.add('hidden');
    currentUserName && (currentUserName.textContent = '未登录');
    currentUserLevel && (currentUserLevel.textContent = '');
    return;
  }
  dashboard?.classList.remove('hidden');
  currentUserName && (currentUserName.textContent = user.name);
  currentUserLevel && (currentUserLevel.textContent = `水平：${user.level || 'beginner'}`);
}

function activateAuthTab(tab) {
  const loginForm = $('#login-form');
  const registerForm = $('#register-form');
  $all('[data-auth-tab]').forEach((btn) => btn.classList.toggle('active', btn.dataset.authTab === tab));
  if (tab === 'login') {
    loginForm?.classList.remove('hidden');
    registerForm?.classList.add('hidden');
  } else {
    loginForm?.classList.add('hidden');
    registerForm?.classList.remove('hidden');
  }
}

function currentUserId() {
  return loadUser()?.id || null;
}

function currentUserLevel() {
  return loadUser()?.level || 'beginner';
}

function ensureLoggedIn() {
  const user = loadUser();
  if (!user || !loadToken()) {
    setNotice('请先登录后再使用资料、练习和错题本功能。', 'warning');
    if (!['/login', '/register'].includes(location.pathname)) {
      location.href = '/login';
    }
    return false;
  }
  return true;
}

function setSelectOptions(select, items) {
  if (!select) return;
  select.innerHTML = items.length
    ? items.map((item) => `<option value="${item.id}">${escapeHtml(item.title)} (#${item.id})</option>`).join('')
    : '<option value="">暂无资料</option>';
}

function setSubjectOptions(select, items) {
  if (!select) return;
  const placeholder = '<option value="">按文件</option>';
  select.innerHTML = items.length
    ? `${placeholder}${items.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}（${item.materials_count ?? 0} 份资料）</option>`).join('')}`
    : `${placeholder}<option value="">暂无学科，请先创建</option>`;
}

async function refreshSubjects() {
  const subjects = await api('/api/v1/subjects');
  cachedSubjects = subjects;
  setSubjectOptions($('#material-subject-select'), subjects);
  setSubjectOptions($('#study-subject-select'), subjects);
  const activeId = getActiveSubjectId();
  renderSidebarSubjects(subjects);
  syncSubjectControls(activeId);
}

function selectedStudyScope() {
  return String($('#study-scope')?.value || 'material');
}

function selectedStudySubjectId() {
  return Number($('#study-subject-select')?.value || 0);
}

async function refreshMaterials() {
  const materials = await api('/api/v1/materials');
  const activeSubjectId = getActiveSubjectId();
  const scopedMaterials = activeSubjectId ? materials.filter((item) => Number(item.subject_id || 0) === activeSubjectId) : materials;
  const select = $('#material-select');
  setSelectOptions(select, scopedMaterials);

  const list = $('#materials-list');
  if (!list) return;
  list.innerHTML = scopedMaterials.length
    ? scopedMaterials.map((m) => `
      <div class="item-card">
        <div class="item-title">${escapeHtml(m.title)}</div>
        <div class="muted">来源：${escapeHtml(m.source_name)} · ID：${m.id} · 学科：${m.subject_id ?? '-'} · 用户：${m.user_id ?? '-'}</div>
        <div class="item-actions">
          <button type="button" class="button small-btn ghost" data-use-material="${m.id}">用于练习</button>
          <button type="button" class="button small-btn ghost" data-view-material="${m.id}">查看内容</button>
        </div>
      </div>`).join('')
    : '<div class="empty-state">当前范围暂无资料，请先上传课件，或切换到“全部文件”。</div>';

  $all('[data-use-material]', list).forEach((btn) => {
    btn.addEventListener('click', () => {
      if (select) select.value = btn.dataset.useMaterial;
    });
  });

  $all('[data-view-material]', list).forEach((btn) => {
    btn.addEventListener('click', async () => {
      const materialId = Number(btn.dataset.viewMaterial || 0);
      if (!materialId) return;
      const detail = await api(`/api/v1/materials/${materialId}`);
      const box = $('#material-detail');
      if (!box) return;
      box.innerHTML = `
        <div class="item-card">
          <div class="item-title">${escapeHtml(detail.title)}（${escapeHtml(detail.source_name)}）</div>
          <div class="item-text">${escapeHtml(String(detail.content || '').slice(0, 1200))}${String(detail.content || '').length > 1200 ? '...' : ''}</div>
        </div>`;
    });
  });
}

async function refreshMistakes() {
  const mistakes = await api('/api/v1/mistakes');
  const list = $('#mistakes-list');
  if (!list) return;
  list.innerHTML = mistakes.length
    ? mistakes.map((m) => `
      <div class="item-card" data-mistake-id="${m.id}">
        <div class="item-title">${escapeHtml(m.material_title || `材料 #${m.material_id}`)} · ${escapeHtml(m.concept)}</div>
        <div class="muted">状态：${escapeHtml(m.status)} · 复习次数：${m.review_count} · 用户：${m.user_id ?? '-'}</div>
        <div class="stack gap-8">
          <label class="field"><span>原因</span><input class="input mistake-reason" value="${escapeHtml(m.reason)}"></label>
          <label class="field"><span>我的备注</span><textarea class="textarea mistake-note" rows="2">${escapeHtml(m.user_note)}</textarea></label>
          <div class="split-row">
            <select class="input mistake-status">
              ${['open', 'reviewing', 'mastered'].map((s) => `<option value="${s}" ${m.status === s ? 'selected' : ''}>${s}</option>`).join('')}
            </select>
            <button type="button" class="button small-btn ghost" data-review-mistake="${m.id}">标记复习</button>
            <button type="button" class="button small-btn primary" data-save-mistake="${m.id}">保存</button>
          </div>
        </div>
      </div>`).join('')
    : '<div class="empty-state">错题本为空，去完成一次练习吧。</div>';

  $all('[data-save-mistake]', list).forEach((btn) => {
    btn.addEventListener('click', async () => {
      const card = btn.closest('[data-mistake-id]');
      const id = btn.dataset.saveMistake;
      const payload = {
        reason: $('.mistake-reason', card)?.value || '',
        user_note: $('.mistake-note', card)?.value || '',
        status: $('.mistake-status', card)?.value || 'open',
      };
      await api(`/api/v1/mistakes/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      await refreshMistakes();
      setNotice('错题已保存。', 'success');
    });
  });

  $all('[data-review-mistake]', list).forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/api/v1/mistakes/${btn.dataset.reviewMistake}/review`, { method: 'POST', body: '{}' });
      await refreshMistakes();
      setNotice('已记录一次复习。', 'success');
    });
  });
}

async function refreshHistory() {
  const attempts = await api('/api/v1/attempts?limit=30');
  const list = $('#history-list');
  if (!list) return;
  list.innerHTML = attempts.length
    ? attempts.map((a) => `
      <div class="item-card">
        <div class="item-title">${escapeHtml(a.material_title || `材料 #${a.material_id}`)} · ${escapeHtml(a.concept || '综合练习')}</div>
        <div class="muted">分数：${a.score} · ${a.is_correct ? '正确' : '待复习'} · ${new Date(a.created_at).toLocaleString()}</div>
        <div class="item-text">${escapeHtml(a.feedback)}</div>
      </div>`).join('')
    : '<div class="empty-state">暂无练习历史。</div>';
}

function renderFlashcards(cards) {
  const box = $('#flashcard-result');
  if (!box) return;
  box.innerHTML = cards.length
    ? cards.map((card, idx) => `
      <div class="item-card">
        <div class="item-title">${idx + 1}. ${escapeHtml(card.concept)}</div>
        <div class="item-text"><strong>解释：</strong>${escapeHtml(card.explanation)}</div>
        ${card.example ? `<div class="item-text"><strong>例子：</strong>${escapeHtml(card.example)}</div>` : ''}
      </div>`).join('')
    : '<div class="empty-state">未生成任何知识卡片。</div>';
}

function renderQuestion(question, refs, basisPoints = []) {
  currentPracticeQuestion = question || '';
  currentReferences = refs || [];
  const box = $('#question-result');
  if (!box) return;
  box.innerHTML = `
    <div class="item-card">
      <div class="item-title">系统生成的问题</div>
      <div class="item-text">${escapeHtml(question)}</div>
    </div>
    <div class="item-card">
      <div class="item-title">参考证据</div>
      <ol>${(refs || []).map((ref) => `<li>${escapeHtml(ref)}</li>`).join('')}</ol>
    </div>`;
  if (basisPoints.length) {
    box.insertAdjacentHTML('beforeend', `
      <div class="item-card">
        <div class="item-title">评分依据</div>
        <ol>${basisPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join('')}</ol>
      </div>`);
  }
}

function renderAnswer(result) {
  const box = $('#answer-result');
  if (!box) return;
  box.innerHTML = `
    <div class="item-card">
      <div class="item-title">评分结果：${result.score}</div>
      <div class="muted">${result.is_correct ? '已达标' : '需要复习'}</div>
      <div class="item-text">${escapeHtml(result.feedback)}</div>
      <div class="item-text"><strong>纠正：</strong>${escapeHtml(result.correction)}</div>
      ${result.basis_points?.length ? `<div class="item-text"><strong>评分依据：</strong><ul>${result.basis_points.map((p) => `<li>${escapeHtml(p)}</li>`).join('')}</ul></div>` : ''}
    </div>`;
}

async function bindAuth() {
  const loginForm = $('#login-form');
  const registerForm = $('#register-form');
  const logoutBtn = $('#logout-btn');

  $all('[data-auth-tab]').forEach((btn) => btn.addEventListener('click', () => activateAuthTab(btn.dataset.authTab)));

  loginForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(loginForm);
    const name = String(form.get('name') || '').trim();
    const password = String(form.get('password') || '').trim();
    if (!name) return setNotice('请输入用户名。', 'warning');
    if (!password) return setNotice('请输入密码。', 'warning');
    const auth = await api('/api/v1/users/login', { method: 'POST', body: JSON.stringify({ name, password }) });
    saveSession(auth);
    renderUser(auth.user);
    setNotice(`欢迎回来，${auth.user.name}！`, 'success');
    await refreshAll();
  });

  registerForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(registerForm);
    const payload = {
      name: String(form.get('name') || '').trim(),
      level: String(form.get('level') || 'beginner'),
      email: String(form.get('email') || '').trim() || undefined,
      password: String(form.get('password') || '').trim() || undefined,
    };
    if (!payload.name) return setNotice('请输入用户名。', 'warning');
    if (!payload.password) return setNotice('请输入密码。', 'warning');
    const auth = await api('/api/v1/users/register', { method: 'POST', body: JSON.stringify(payload) });
    saveSession(auth);
    renderUser(auth.user);
    setNotice(`注册成功，已切换到用户 ${auth.user.name}。`, 'success');
    await refreshAll();
  });

  logoutBtn?.addEventListener('click', () => {
    clearSession();
    renderUser(null);
    setNotice('已退出登录。', 'info');
    $('#dashboard')?.classList.add('hidden');
  });
}

async function bindMaterials() {
  const uploadForm = $('#upload-form');
  const uploadSubmit = $('#upload-submit');
  const manualForm = $('#manual-material-form');
  const manualSubmit = $('#manual-material-submit');
  const subjectForm = $('#subject-form');
  const subjectSubmit = $('#subject-submit');
  const refreshBtn = $('#refresh-materials');
  refreshBtn?.addEventListener('click', async () => {
    await refreshMaterials();
    setNotice('资料列表已刷新。', 'info');
  });

  uploadForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!ensureLoggedIn()) return;
    const fileInput = uploadForm.querySelector('input[name="file"]');
    const files = fileInput?.files || [];
    const title = String(new FormData(uploadForm).get('title') || '').trim();
    if (!title) return setNotice('请输入资料标题。', 'warning');
    const activeSubjectId = getActiveSubjectId();
    const subjectId = Number($('#material-subject-select')?.value || activeSubjectId || 0);
    const createNew = $('#create-subject-checkbox')?.checked;
    const newSubjectName = String($('#new-subject-name')?.value || '').trim();
    let targetSubjectId = subjectId || 0;

    // If user requested to create a new subject for these files, create it first
    if (createNew) {
      if (!newSubjectName) return setNotice('请输入新学科名称或取消新建选项。', 'warning');
      try {
        const created = await api('/api/v1/subjects', { method: 'POST', body: JSON.stringify({ name: newSubjectName, description: '' }) });
        targetSubjectId = created.id;
        saveActiveSubject(targetSubjectId);
        syncSubjectControls(targetSubjectId);
      } catch (err) {
        return setNotice(err.message || '创建学科失败，上传已取消。', 'warning');
      }
    }
    if (!files.length) return setNotice('请选择要上传的文件。', 'warning');

    const progressWrap = $('#upload-progress-wrap');
    const progressBar = $('#upload-progress-bar');
    const progressText = $('#upload-progress-text');
    progressWrap?.classList.remove('hidden');
    progressBar && (progressBar.style.width = '0%');
    progressText && (progressText.textContent = '准备上传...');
    if (uploadSubmit) {
      uploadSubmit.disabled = true;
      uploadSubmit.textContent = '上传中...';
    }

    // 顺序上传每个文件，显示整体进度
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const extension = String((file.name || '').split('.').pop() || '').toLowerCase();
      if (!SUPPORTED_UPLOAD_EXTENSIONS.has(extension)) {
        setNotice(`文件 ${file.name} 格式不支持，跳过。`, 'warning');
        continue;
      }

      const fd = new FormData();
      // 将标题与文件名结合，避免多个文件使用相同标题导致混淆
      fd.append('title', `${title} - ${file.name}`);
      fd.append('file', file);
      if (targetSubjectId) fd.append('subject_id', String(targetSubjectId));

      try {
        await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open('POST', '/api/v1/materials/upload');
          const token = loadToken();
          if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
          xhr.upload.onprogress = (event) => {
            if (!event.lengthComputable) return;
            const filePercent = event.loaded / event.total;
            const overall = Math.round(((i + filePercent) / files.length) * 100);
            if (progressBar) progressBar.style.width = `${overall}%`;
            if (progressText) progressText.textContent = `上传 ${i + 1}/${files.length}：${file.name} (${overall}%)`;
          };
          xhr.onload = async () => {
            try {
              const data = xhr.responseText ? JSON.parse(xhr.responseText) : {};
              if (xhr.status >= 200 && xhr.status < 300) {
                setNotice(`已上传 ${file.name}。`, 'info');
                await refreshMaterials();
                resolve(data);
              } else {
                reject(new Error(data.detail || `上传 ${file.name} 失败`));
              }
            } catch (err) {
              reject(err);
            }
          };
          xhr.onerror = () => reject(new Error(`上传 ${file.name} 失败，请检查网络或文件格式`));
          xhr.send(fd);
        });
      } catch (err) {
        setNotice(err.message || `上传 ${file.name} 遇到错误。`, 'warning');
      }
    }

    // 完成全部文件上传
    uploadForm.reset();
    if (progressBar) progressBar.style.width = '100%';
    if (progressText) progressText.textContent = '全部上传完成，正在刷新...';
    setTimeout(() => progressWrap?.classList.add('hidden'), 800);
    if (uploadSubmit) {
      uploadSubmit.disabled = false;
      uploadSubmit.textContent = '上传并入库';
    }
    await refreshSubjects();
  });

  manualForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!ensureLoggedIn()) return;
    const formData = new FormData(manualForm);
    const title = String(formData.get('manual-title') || '').trim();
    const content = String(formData.get('manual-content') || '').trim();
    const subjectId = Number($('#material-subject-select')?.value || 0);
    if (!title) return setNotice('请输入资料标题。', 'warning');
    if (!content) return setNotice('请输入资料内容。', 'warning');

    manualSubmit && (manualSubmit.disabled = true);
    manualSubmit && (manualSubmit.textContent = '保存中...');
    try {
      await api('/api/v1/materials', {
        method: 'POST',
        body: JSON.stringify({ title, content, source_name: 'manual', subject_id: subjectId || null }),
      });
      setNotice('文字资料已保存。', 'success');
      manualForm.reset();
      await refreshMaterials();
    } catch (error) {
      setNotice(error.message || '保存失败。', 'warning');
    } finally {
      manualSubmit && (manualSubmit.disabled = false);
      manualSubmit && (manualSubmit.textContent = '保存文字资料');
    }
  });

  subjectForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!ensureLoggedIn()) return;
    const formData = new FormData(subjectForm);
    const name = String(formData.get('subject-name') || '').trim();
    const description = String(formData.get('subject-description') || '').trim();
    if (!name) return setNotice('请输入学科名称。', 'warning');

    subjectSubmit && (subjectSubmit.disabled = true);
    subjectSubmit && (subjectSubmit.textContent = '创建中...');
    try {
      const created = await api('/api/v1/subjects', { method: 'POST', body: JSON.stringify({ name, description }) });
      subjectForm.reset();
      saveActiveSubject(created.id);
      syncSubjectControls(created.id);
      await refreshSubjects();
      setNotice('学科创建成功。已设为活动学科。', 'success');
    } catch (error) {
      setNotice(error.message || '学科创建失败。', 'warning');
    } finally {
      subjectSubmit && (subjectSubmit.disabled = false);
      subjectSubmit && (subjectSubmit.textContent = '新建学科');
    }
  });
}


async function bindAssistant() {
  $('#generate-flashcards')?.addEventListener('click', async () => {
    if (!ensureLoggedIn()) return;
    const materialId = Number($('#material-select')?.value || 0);
    const scope = selectedStudyScope();
    const subjectId = selectedStudySubjectId();
    if (scope === 'subject' && !subjectId) return setNotice('请先选择学科。', 'warning');
    if (scope !== 'subject' && !materialId) return setNotice('请先选择一份资料。', 'warning');
    const count = Number($('#flashcard-count')?.value || 5);
    const payload = { count, user_level: currentUserLevel() };
    if (scope === 'subject') {
      payload.subject_id = subjectId;
    } else {
      payload.material_id = materialId;
    }
    const data = await api('/api/v1/assistant/knowledge-cards/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderFlashcards(data);
    setNotice('知识卡片已生成。', 'success');
  });

  $('#generate-question')?.addEventListener('click', async () => {
    if (!ensureLoggedIn()) return;
    const materialId = Number($('#material-select')?.value || 0);
    const scope = selectedStudyScope();
    const subjectId = selectedStudySubjectId();
    if (scope === 'subject' && !subjectId) return setNotice('请先选择学科。', 'warning');
    if (scope !== 'subject' && !materialId) return setNotice('请先选择一份资料。', 'warning');
    const concept = String($('#practice-concept')?.value || '').trim();
    const level = String($('#practice-level')?.value || currentUserLevel());
    const payload = { concept, user_level: level };
    if (scope === 'subject') {
      payload.subject_id = subjectId;
    } else {
      payload.material_id = materialId;
    }
    const data = await api('/api/v1/assistant/practice/question', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderQuestion(data.question, data.references, data.basis_points || []);
    $('#answer-text') && ($('#answer-text').value = '');
    setNotice('练习问题已生成。', 'success');
  });

  $('#answer-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!ensureLoggedIn()) return;
    const materialId = Number($('#material-select')?.value || 0);
    const scope = selectedStudyScope();
    const subjectId = selectedStudySubjectId();
    const questionText = currentPracticeQuestion || String($('#practice-concept')?.value || '').trim();
    if (scope === 'subject' && !subjectId) return setNotice('请先选择学科。', 'warning');
    if (scope !== 'subject' && !materialId) return setNotice('请先选择一份资料。', 'warning');
    const answer = String($('#answer-text')?.value || '').trim();
    if (!answer) return setNotice('请输入你的答案。', 'warning');
    const concept = String($('#practice-concept')?.value || '').trim();
    const level = String($('#practice-level')?.value || currentUserLevel());
    const payload = {
      concept,
      question: questionText,
      answer,
      user_level: level,
    };
    if (scope === 'subject') {
      payload.subject_id = subjectId;
    } else {
      payload.material_id = materialId;
    }
    const data = await api('/api/v1/assistant/practice/answer', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderAnswer(data);
    await refreshMistakes();
    await refreshHistory();
    setNotice('答案已评分，结果已同步到错题本和历史记录。', 'success');
  });

  $('#check-consistency')?.addEventListener('click', async () => {
    const answer = String($('#answer-text')?.value || '').trim();
    if (!answer) return setNotice('请先输入答案后再做一致性评估。', 'warning');
    if (!currentReferences.length) return setNotice('请先生成问题，确保有参考证据。', 'warning');
    const data = await api('/api/v1/assistant/consistency', {
      method: 'POST',
      body: JSON.stringify({ answer, references: currentReferences }),
    });
    const box = $('#consistency-result');
    if (!box) return;
    box.innerHTML = `
      <div class="item-card">
        <div class="item-title">一致性得分：${data.consistency_score}</div>
        <div class="item-text">${escapeHtml(data.explanation || '')}</div>
      </div>`;
  });
}

function bindUtilityButtons() {
  $('#refresh-mistakes')?.addEventListener('click', async () => {
    if (!ensureLoggedIn()) return;
    await refreshMistakes();
    setNotice('错题本已刷新。', 'info');
  });

  $('#refresh-history')?.addEventListener('click', async () => {
    if (!ensureLoggedIn()) return;
    await refreshHistory();
    setNotice('历史记录已刷新。', 'info');
  });
}

async function refreshAll() {
  const user = loadUser();
  renderUser(user);
  if (!user) return;
  await Promise.allSettled([refreshSubjects(), refreshMaterials(), refreshMistakes(), refreshHistory()]);
}

document.addEventListener('DOMContentLoaded', async () => {
  if (!loadToken() && !['/login', '/register'].includes(location.pathname)) {
    location.href = '/login';
    return;
  }

  activateAuthTab('login');
  await bindAuth();
  await bindMaterials();
  await bindAssistant();
  bindUtilityButtons();

  const user = loadUser();
  if (user) {
    renderUser(user);
    await refreshAll();
  }

  if (!user) {
    $('#dashboard')?.classList.add('hidden');
  }
});

