import { api } from '../api.js';
import { escapeHtml, showToast } from '../utils.js';

let quizState = null;
let practiceForm = { subjectId: '', count: 5 };
let practiceView = 'setup';
let quizGenerating = false;
let quizGenProgress = { percent: 0, message: '' };
let quizError = null;
let quizResult = null;
let practiceMounted = false;

export async function renderPractice(container) {
  if (practiceMounted && container.querySelector('#quizArea')) {
    return;
  }

  const subjects = await api.getSubjects();

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">\u7ec3\u4e60\u62bd\u67e5</h2>
    </div>
    ${!subjects.length
        ? `<div class="empty-state">
            <div class="empty-icon">&#9998;</div>
            <h3 class="empty-title">\u65e0\u6cd5\u5f00\u59cb\u7ec3\u4e60</h3>
            <p class="empty-desc">\u8bf7\u5148\u521b\u5efa\u79d1\u76ee\u5e76\u4ece\u8d44\u6599\u4e2d\u62bd\u53d6\u91cd\u8981\u6982\u5ff5</p>
          </div>`
        : `<div class="card" style="max-width:480px;margin:0 auto;">
            <div class="form-group">
              <label class="form-label">\u9009\u62e9\u79d1\u76ee</label>
              <select class="form-select" id="practiceSubject">
                ${subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)} (${s.cardCount} \u5361\u7247)</option>`).join('')}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">\u9898\u76ee\u6570\u91cf</label>
              <select class="form-select" id="questionCount">
                <option value="5">5 \u9898</option>
                <option value="10">10 \u9898</option>
                <option value="15">15 \u9898</option>
              </select>
            </div>
            <button class="btn btn-primary" id="startQuiz" style="width:100%;">\u5f00\u59cb\u7ec3\u4e60</button>
          </div>
          <div id="quizArea"></div>`}
  `;

  if (!subjects.length) return;

  practiceMounted = true;

  const subjectSelect = document.getElementById('practiceSubject');
  const countSelect = document.getElementById('questionCount');

  if (practiceForm.subjectId && [...subjectSelect.options].some((o) => o.value === practiceForm.subjectId)) {
    subjectSelect.value = practiceForm.subjectId;
  } else if (subjects.length) {
    practiceForm.subjectId = subjectSelect.value;
  }

  countSelect.value = String(practiceForm.count || 5);

  subjectSelect.addEventListener('change', () => {
    practiceForm.subjectId = subjectSelect.value;
  });
  countSelect.addEventListener('change', () => {
    practiceForm.count = Number(countSelect.value);
  });

  document.getElementById('startQuiz').addEventListener('click', startQuiz);

  restorePracticeView();
}

function restorePracticeView() {
  const startBtn = document.getElementById('startQuiz');
  if (!startBtn) return;

  if (practiceView === 'generating') {
    startBtn.disabled = quizGenerating;
    renderQuizGeneratingPanel();
    return;
  }

  if (practiceView === 'quiz' && quizState) {
    startBtn.disabled = false;
    renderQuestion();
    return;
  }

  if (practiceView === 'result' && quizResult) {
    startBtn.disabled = false;
    renderQuizResultPanel();
    return;
  }

  if (practiceView === 'error' && quizError) {
    startBtn.disabled = false;
    const quizArea = document.getElementById('quizArea');
    if (quizArea) {
      quizArea.innerHTML = `<div class="empty-state" style="padding:32px;">
        <p class="empty-desc">${escapeHtml(quizError)}</p>
      </div>`;
    }
    return;
  }

  startBtn.disabled = false;
}

function setQuizProgress(percent, message) {
  const p = Math.max(0, Math.min(100, percent));
  quizGenProgress = { percent: p, message: message || quizGenProgress.message };

  const fill = document.getElementById('quizGenProgressFill');
  const pctEl = document.getElementById('quizGenProgressPercent');
  const msgEl = document.getElementById('quizGenProgressMessage');
  if (fill) fill.style.width = `${p}%`;
  if (pctEl) pctEl.textContent = `${p}%`;
  if (msgEl && message) msgEl.textContent = message;
}

function renderQuizGeneratingPanel() {
  const quizArea = document.getElementById('quizArea');
  if (!quizArea) return;
  quizArea.innerHTML = `
    <div class="extract-progress-panel" style="margin-top:24px;">
      <div class="extract-progress-header">
        <span id="quizGenProgressMessage">${escapeHtml(quizGenProgress.message || '\u751f\u6210\u9898\u76ee\u4e2d\u2026')}</span>
        <span id="quizGenProgressPercent" class="progress-text">${quizGenProgress.percent}%</span>
      </div>
      <div class="progress-bar extract-progress-bar">
        <div class="progress-fill" id="quizGenProgressFill" style="width:${quizGenProgress.percent}%;"></div>
      </div>
    </div>`;
}

async function startQuiz() {
  const subjectId = document.getElementById('practiceSubject').value;
  const count = Number(document.getElementById('questionCount').value);
  practiceForm = { subjectId, count };
  practiceView = 'generating';
  quizError = null;
  quizResult = null;
  quizGenerating = true;
  quizGenProgress = { percent: 0, message: '\u51c6\u5907\u751f\u6210\u9898\u76ee\u2026' };

  const startBtn = document.getElementById('startQuiz');
  if (startBtn) startBtn.disabled = true;
  renderQuizGeneratingPanel();

  try {
    const questions = await api.generateQuizStream(subjectId, count, setQuizProgress);
    quizGenerating = false;

    if (!questions.length) {
      practiceView = 'error';
      quizError = '\u8be5\u79d1\u76ee\u6682\u65e0\u77e5\u8bc6\u5361\u7247\uff0c\u8bf7\u5148\u4ece\u4e0a\u4f20\u8d44\u6599\u4e2d\u62bd\u53d6\u91cd\u8981\u6982\u5ff5';
      restorePracticeView();
      return;
    }

    quizState = { subjectId, questions, current: 0, answers: [], startTime: Date.now() };
    practiceView = 'quiz';

    if (document.getElementById('quizArea')) {
      renderQuestion();
    }
  } catch (err) {
    quizGenerating = false;
    practiceView = 'error';
    quizError = err.message || '\u751f\u6210\u9898\u76ee\u5931\u8d25';
    showToast(quizError, 'error');
    restorePracticeView();
  } finally {
    const btn = document.getElementById('startQuiz');
    if (btn) btn.disabled = quizGenerating;
  }
}

function renderQuestion() {
  const quizArea = document.getElementById('quizArea');
  if (!quizArea || !quizState) return;

  const { questions, current } = quizState;
  const q = questions[current];
  const progress = (current / questions.length) * 100;

  quizArea.innerHTML = `
    <div class="quiz-container" style="margin-top:32px;">
      <div class="quiz-progress">
        <div class="progress-bar"><div class="progress-fill" style="width:${progress}%"></div></div>
        <span class="progress-text">${current + 1} / ${questions.length}</span>
      </div>
      <div class="quiz-question">
        <p class="question-text">${escapeHtml(q.question)}</p>
        <div class="option-list" id="optionList">
          ${q.options.map((opt, i) => `<div class="option-item" data-index="${i}">
              <span class="option-key">${String.fromCharCode(65 + i)}</span>
              <span>${escapeHtml(opt)}</span>
            </div>`).join('')}
        </div>
      </div>
      <div class="quiz-actions">
        <button class="btn btn-secondary" id="btnSkip">\u8df3\u8fc7</button>
        <button class="btn btn-primary" id="btnConfirm" disabled>\u786e\u8ba4\u7b54\u6848</button>
      </div>
    </div>`;

  let selected = -1;
  document.querySelectorAll('.option-item').forEach((el) => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.option-item').forEach((o) => o.classList.remove('selected'));
      el.classList.add('selected');
      selected = Number(el.dataset.index);
      document.getElementById('btnConfirm').disabled = false;
    });
  });

  document.getElementById('btnConfirm').onclick = () => submitAnswer(selected);
  document.getElementById('btnSkip').onclick = () => submitAnswer(-1);
}

function submitAnswer(selected) {
  const { questions, current } = quizState;
  const q = questions[current];
  const isCorrect = selected === q.correctIndex;

  quizState.answers.push({
    cardId: q.cardId,
    question: q.question,
    userAnswer: selected >= 0 ? q.options[selected] : '\uff08\u8df3\u8fc7\uff09',
    correctAnswer: q.options[q.correctIndex],
    isCorrect,
  });

  document.querySelectorAll('.option-item').forEach((el, i) => {
    el.style.pointerEvents = 'none';
    if (i === q.correctIndex) el.classList.add('correct');
    else if (i === selected && !isCorrect) el.classList.add('wrong');
  });

  const btn = document.getElementById('btnConfirm');
  btn.textContent = current + 1 >= questions.length ? '\u67e5\u770b\u7ed3\u679c' : '\u4e0b\u4e00\u9898';
  btn.disabled = false;
  btn.onclick = () => {
    quizState.current++;
    if (quizState.current >= questions.length) finishQuiz();
    else renderQuestion();
  };
  document.getElementById('btnSkip').style.display = 'none';
}

function renderQuizResultPanel() {
  const quizArea = document.getElementById('quizArea');
  if (!quizArea || !quizResult) return;

  const { session, wrongCount, duration, pct } = quizResult;

  quizArea.innerHTML = `
    <div class="quiz-container" style="margin-top:32px;">
      <div class="card quiz-result">
        <div class="result-score">${pct}%</div>
        <p class="result-label">\u7b54\u5bf9 ${session.score} / ${session.total} \u9898 \u00b7 \u7528\u65f6 ${duration}s</p>
        ${wrongCount
            ? `<p style="margin-top:12px;color:var(--warning);">\u6709 ${wrongCount} \u9053\u9519\u9898\u5df2\u52a0\u5165\u9519\u9898\u672c</p>`
            : `<p style="margin-top:12px;color:var(--success);">\u5168\u90e8\u6b63\u786e\uff0c\u592a\u68d2\u4e86\uff01</p>`}
        <div style="margin-top:32px;display:flex;gap:12px;justify-content:center;">
          <button class="btn btn-secondary" id="btnRetry">\u518d\u6765\u4e00\u6b21</button>
          <button class="btn btn-primary" id="btnReview">\u67e5\u770b\u9519\u9898</button>
        </div>
      </div>
    </div>`;

  document.getElementById('btnRetry').onclick = () => {
    practiceView = 'setup';
    quizResult = null;
    quizState = null;
    const quizAreaEl = document.getElementById('quizArea');
    if (quizAreaEl) quizAreaEl.innerHTML = '';
    startQuiz();
  };
  document.getElementById('btnReview').onclick = () => {
    window.dispatchEvent(new CustomEvent('navigate', { detail: wrongCount ? 'wrong-book' : 'history' }));
  };
}

async function finishQuiz() {
  const duration = Math.round((Date.now() - quizState.startTime) / 1000);
  const result = await api.submitPractice({
    subject_id: quizState.subjectId,
    answers: quizState.answers,
    duration,
  });

  const { session } = result;
  const pct = Math.round((session.score / session.total) * 100);

  quizResult = {
    session,
    wrongCount: result.wrongCount,
    duration,
    pct,
  };
  practiceView = 'result';
  quizState = null;

  showToast('\u7ec3\u4e60\u5b8c\u6210\uff01', 'success');

  if (document.getElementById('quizArea')) {
    renderQuizResultPanel();
  }
}
