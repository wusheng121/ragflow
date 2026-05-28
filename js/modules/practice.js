import { api } from '../api.js';
import { escapeHtml, showToast } from '../utils.js';

let quizState = null;

export async function renderPractice(container) {
  const subjects = await api.getSubjects();

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">练习抽查</h2>
    </div>
    ${!subjects.length
        ? `<div class="empty-state">
            <div class="empty-icon">&#9998;</div>
            <h3 class="empty-title">无法开始练习</h3>
            <p class="empty-desc">\u8bf7\u5148\u521b\u5efa\u79d1\u76ee\u5e76\u4ece\u8d44\u6599\u4e2d\u62bd\u53d6\u91cd\u8981\u6982\u5ff5</p>
          </div>`
        : `<div class="card" style="max-width:480px;margin:0 auto;">
            <div class="form-group">
              <label class="form-label">选择科目</label>
              <select class="form-select" id="practiceSubject">
                ${subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)} (${s.cardCount} 卡片)</option>`).join('')}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">题目数量</label>
              <select class="form-select" id="questionCount">
                <option value="5">5 题</option>
                <option value="10">10 题</option>
                <option value="15">15 题</option>
              </select>
            </div>
            <button class="btn btn-primary" id="startQuiz" style="width:100%;">开始练习</button>
          </div>
          <div id="quizArea"></div>`}
  `;

  document.getElementById('startQuiz')?.addEventListener('click', startQuiz);
}

async function startQuiz() {
  const subjectId = document.getElementById('practiceSubject').value;
  const count = Number(document.getElementById('questionCount').value);
  const quizArea = document.getElementById('quizArea');

  quizArea.innerHTML = '<div class="page-loading"><div class="loading-spinner"></div><div class="page-loading-text">生成题目中...</div></div>';

  const questions = await api.generateQuiz(subjectId, count);
  if (!questions.length) {
    quizArea.innerHTML = `<div class="empty-state" style="padding:32px;">
      <p class="empty-desc">\u8be5\u79d1\u76ee\u6682\u65e0\u77e5\u8bc6\u5361\u7247\uff0c\u8bf7\u5148\u4ece\u4e0a\u4f20\u8d44\u6599\u4e2d\u62bd\u53d6\u91cd\u8981\u6982\u5ff5</p>
    </div>`;
    return;
  }

  quizState = { subjectId, questions, current: 0, answers: [], startTime: Date.now() };
  renderQuestion();
}

function renderQuestion() {
  const quizArea = document.getElementById('quizArea');
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
        <button class="btn btn-secondary" id="btnSkip">跳过</button>
        <button class="btn btn-primary" id="btnConfirm" disabled>确认答案</button>
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
    userAnswer: selected >= 0 ? q.options[selected] : '（跳过）',
    correctAnswer: q.options[q.correctIndex],
    isCorrect,
  });

  document.querySelectorAll('.option-item').forEach((el, i) => {
    el.style.pointerEvents = 'none';
    if (i === q.correctIndex) el.classList.add('correct');
    else if (i === selected && !isCorrect) el.classList.add('wrong');
  });

  const btn = document.getElementById('btnConfirm');
  btn.textContent = current + 1 >= questions.length ? '查看结果' : '下一题';
  btn.disabled = false;
  btn.onclick = () => {
    quizState.current++;
    if (quizState.current >= questions.length) finishQuiz();
    else renderQuestion();
  };
  document.getElementById('btnSkip').style.display = 'none';
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
  const quizArea = document.getElementById('quizArea');

  quizArea.innerHTML = `
    <div class="quiz-container" style="margin-top:32px;">
      <div class="card quiz-result">
        <div class="result-score">${pct}%</div>
        <p class="result-label">答对 ${session.score} / ${session.total} 题 · 用时 ${duration}s</p>
        ${result.wrongCount
            ? `<p style="margin-top:12px;color:var(--warning);">有 ${result.wrongCount} 道错题已加入错题本</p>`
            : `<p style="margin-top:12px;color:var(--success);">全部正确，太棒了！</p>`}
        <div style="margin-top:32px;display:flex;gap:12px;justify-content:center;">
          <button class="btn btn-secondary" id="btnRetry">再来一次</button>
          <button class="btn btn-primary" id="btnReview">查看错题</button>
        </div>
      </div>
    </div>`;

  showToast('练习完成！', 'success');
  document.getElementById('btnRetry').onclick = () => startQuiz();
  document.getElementById('btnReview').onclick = () => {
    window.dispatchEvent(new CustomEvent('navigate', { detail: result.wrongCount ? 'wrong-book' : 'history' }));
  };
}
