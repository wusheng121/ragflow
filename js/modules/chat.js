import { api } from '../api.js';
import { escapeHtml, showToast } from '../utils.js';

let chatHistory = [];
let sending = false;

export async function renderChat(container) {
  const subjects = await api.getSubjects();

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">\u667a\u80fd\u95ee\u7b54</h2>
    </div>
    <div class="chat-layout">
      <div class="chat-sidebar card">
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">\u5173\u8054\u79d1\u76ee\uff08\u53ef\u9009\uff09</label>
          <select class="form-select" id="chatSubject">
            <option value="">\u901a\u7528\u5bf9\u8bdd</option>
            ${subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('')}
          </select>
          <p style="margin-top:10px;font-size:0.8rem;color:var(--text-muted);">\u9009\u62e9\u79d1\u76ee\u540e\uff0c\u6a21\u578b\u4f1a\u7ed3\u5408\u8be5\u79d1\u76ee\u7684\u77e5\u8bc6\u5361\u7247\u56de\u7b54</p>
        </div>
        <button class="btn btn-sm btn-secondary" id="btnClearChat" style="margin-top:16px;width:100%;">\u6e05\u7a7a\u5bf9\u8bdd</button>
      </div>
      <div class="chat-main card">
        <div class="chat-messages" id="chatMessages">
          <div class="chat-welcome">
            <div class="empty-icon">&#129302;</div>
            <p>\u5411 AI \u52a9\u624b\u63d0\u95ee\uff0c\u89e3\u91ca\u6982\u5ff5\u3001\u516c\u5f0f\u6216\u590d\u4e60\u96be\u70b9</p>
          </div>
        </div>
        <div class="chat-input-bar">
          <textarea class="form-textarea" id="chatInput" rows="2" placeholder="\u8f93\u5165\u4f60\u7684\u95ee\u9898\uff0c\u4f8b\u5982\uff1a\u8bf7\u89e3\u91ca\u8fd9\u4e2a\u516c\u5f0f\u7684\u542b\u4e49\u2026"></textarea>
          <button class="btn btn-primary" id="btnSendChat">\u53d1\u9001</button>
        </div>
      </div>
    </div>
  `;

  document.getElementById('btnSendChat').addEventListener('click', sendMessage);
  document.getElementById('btnClearChat').addEventListener('click', clearChat);
  document.getElementById('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

function clearChat() {
  chatHistory = [];
  document.getElementById('chatMessages').innerHTML = `
    <div class="chat-welcome">
      <div class="empty-icon">&#129302;</div>
      <p>\u5bf9\u8bdd\u5df2\u6e05\u7a7a\uff0c\u7ee7\u7eed\u63d0\u95ee\u5427</p>
    </div>`;
}

function appendMessage(role, content) {
  const box = document.getElementById('chatMessages');
  box.querySelector('.chat-welcome')?.remove();

  const el = document.createElement('div');
  el.className = `chat-bubble chat-bubble-${role}`;
  el.innerHTML = `
    <div class="chat-bubble-role">${role === 'user' ? '\u4f60' : 'AI'}</div>
    <div class="chat-bubble-content">${formatChatContent(content)}</div>
  `;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function formatChatContent(text) {
  return escapeHtml(text).replace(/\n/g, '<br>');
}

function showTyping() {
  const box = document.getElementById('chatMessages');
  const el = document.createElement('div');
  el.id = 'chatTyping';
  el.className = 'chat-bubble chat-bubble-assistant chat-typing';
  el.innerHTML = '<div class="chat-bubble-content">\u6b63\u5728\u601d\u8003\u2026</div>';
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function hideTyping() {
  document.getElementById('chatTyping')?.remove();
}

async function sendMessage() {
  if (sending) return;
  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;

  const subjectId = document.getElementById('chatSubject').value || undefined;
  sending = true;
  document.getElementById('btnSendChat').disabled = true;

  appendMessage('user', message);
  chatHistory.push({ role: 'user', content: message });
  input.value = '';
  showTyping();

  try {
    const { reply } = await api.sendChat({ message, subjectId, history: chatHistory.slice(0, -1) });
    hideTyping();
    appendMessage('assistant', reply);
    chatHistory.push({ role: 'assistant', content: reply });
  } catch (err) {
    hideTyping();
    showToast(err.message || '\u53d1\u9001\u5931\u8d25', 'error');
  } finally {
    sending = false;
    document.getElementById('btnSendChat').disabled = false;
    input.focus();
  }
}
