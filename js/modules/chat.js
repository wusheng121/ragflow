import { api } from '../api.js';
import { escapeHtml, showToast } from '../utils.js';

const CHAT_STORAGE_KEY = 'ragflow_chat_ui';
const MAX_CONVERSATIONS_LIST = 10;
const MAX_TURNS_PER_CONVERSATION = 50;

let chatSubjectId = '';
let chatHistory = [];
let currentConversationId = null;
/** @type {Array<{id: string, title: string, turnCount: number, updatedAt: string}>} */
let conversationList = [];
let sending = false;
let streamingDraft = '';
let chatMounted = false;
/** @type {Promise<void> | null} */
let chatMountPromise = null;
/** @type {Record<string, string | null>} */
let activeConversationIds = {};

function sessionKey(subjectId) {
  return subjectId || '__general__';
}

function trimHistory(history) {
  const cleaned = (history || [])
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && (m.content || '').trim())
    .map((m) => ({ role: m.role, content: m.content.trim() }));
  const maxMessages = MAX_TURNS_PER_CONVERSATION * 2;
  return cleaned.length <= maxMessages ? cleaned : cleaned.slice(-maxMessages);
}

function formatConversationTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function saveUiState() {
  activeConversationIds[sessionKey(chatSubjectId)] = currentConversationId;
  try {
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({ activeSubjectId: chatSubjectId, activeConversationIds }),
    );
  } catch {
    /* ignore */
  }
}

function loadUiState() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data.activeConversationIds) activeConversationIds = data.activeConversationIds;
    if (typeof data.activeSubjectId === 'string') chatSubjectId = data.activeSubjectId;
  } catch {
    /* ignore */
  }
}

function readHistoryFromDom(root = document) {
  const box = root.querySelector('#chatMessages');
  if (!box) return null;
  const bubbles = box.querySelectorAll('.chat-bubble:not(.chat-streaming)');
  if (!bubbles.length) return null;
  return Array.from(bubbles).map((el) => ({
    role: el.classList.contains('chat-bubble-user') ? 'user' : 'assistant',
    content: el.querySelector('.chat-bubble-content')?.textContent || '',
  }));
}

function chatDomHasMessages(root) {
  return Boolean(root.querySelector('#chatMessages')?.querySelector('.chat-bubble'));
}

/** Call before leaving chat page. */
export function persistChatState() {
  saveUiState();
}

async function loadConversationList(subjectId) {
  try {
    const data = await api.listChatConversations(subjectId || '');
    conversationList = (data.conversations || []).slice(0, MAX_CONVERSATIONS_LIST);
  } catch {
    conversationList = [];
  }
  renderConversationList();
}

function renderConversationList() {
  const list = document.getElementById('chatHistoryList');
  if (!list) return;

  if (!conversationList.length) {
    list.innerHTML = '<li class="chat-history-empty">暂无历史对话</li>';
    return;
  }

  list.innerHTML = conversationList
    .map(
      (c) => `
    <li class="chat-history-item${c.id === currentConversationId ? ' active' : ''}" data-id="${escapeHtml(c.id)}" role="button" tabindex="0">
      <div class="chat-history-item-title">${escapeHtml(c.title || '新对话')}</div>
      <div class="chat-history-item-meta">${c.turnCount || 0} 轮 · ${escapeHtml(formatConversationTime(c.updatedAt))}</div>
    </li>`,
    )
    .join('');

  list.querySelectorAll('.chat-history-item').forEach((el) => {
    const open = () => openConversation(el.dataset.id);
    el.addEventListener('click', open);
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        open();
      }
    });
  });
}

async function openConversation(conversationId) {
  if (!conversationId || sending) return;
  if (conversationId === currentConversationId && chatHistory.length) return;

  try {
    const data = await api.getChatConversation(conversationId);
    currentConversationId = data.id;
    chatHistory = trimHistory(data.history || []);
    saveUiState();
    restoreChatMessages();
    renderConversationList();
  } catch (err) {
    showToast(err.message || '加载对话失败', 'error');
  }
}

function startNewChat() {
  currentConversationId = null;
  chatHistory = [];
  activeConversationIds[sessionKey(chatSubjectId)] = null;
  sending = false;
  streamingDraft = '';
  saveUiState();
  removeStreamingBubble();
  restoreChatMessages();
  renderConversationList();
}

function syncSubjectSelect() {
  const subjectSelect = document.getElementById('chatSubject');
  if (!subjectSelect) return;
  if (chatSubjectId && [...subjectSelect.options].some((o) => o.value === chatSubjectId)) {
    subjectSelect.value = chatSubjectId;
  } else {
    chatSubjectId = subjectSelect.value;
  }
}

async function switchChatSession(nextSubjectId) {
  if (sessionKey(chatSubjectId) === sessionKey(nextSubjectId)) return;
  activeConversationIds[sessionKey(chatSubjectId)] = currentConversationId;
  chatSubjectId = nextSubjectId;
  currentConversationId = activeConversationIds[sessionKey(nextSubjectId)] ?? null;
  chatHistory = [];
  await loadConversationList(nextSubjectId);
  if (currentConversationId) {
    await openConversation(currentConversationId);
  } else {
    restoreChatMessages();
  }
  saveUiState();
}

function reattachChatPage(container) {
  chatMounted = true;
  syncSubjectSelect();
  syncChatSendingUi();
  scrollChatToBottom();
  updateSubjectHint();
  renderConversationList();
  if (chatDomHasMessages(container)) return;
  if (chatHistory.length) restoreChatMessages();
}

export async function renderChat(container) {
  if (container.querySelector('#chatMessages')) {
    reattachChatPage(container);
    return;
  }
  if (chatMountPromise) {
    await chatMountPromise;
    if (container.querySelector('#chatMessages')) {
      reattachChatPage(container);
      return;
    }
  }
  chatMountPromise = mountChatPage(container);
  try {
    await chatMountPromise;
  } finally {
    chatMountPromise = null;
  }
}

async function mountChatPage(container) {
  loadUiState();
  const subjects = await api.getSubjects();
  if (container.querySelector('#chatMessages')) {
    reattachChatPage(container);
    return;
  }

  container.innerHTML = `
    <div class="section-header">
      <h2 class="section-title">智能问答</h2>
    </div>
    <div class="chat-layout">
      <div class="chat-sidebar card">
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label">关联科目（可选）</label>
          <select class="form-select" id="chatSubject">
            <option value="">通用对话</option>
            ${subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('')}
          </select>
          <p id="chatSubjectHint" style="margin-top:10px;font-size:0.8rem;color:var(--text-muted);"></p>
        </div>
        <button class="btn btn-sm btn-secondary" id="btnClearChat" style="margin-top:16px;width:100%;">清空对话</button>
        <div class="chat-history-section">
          <div class="chat-history-header">
            <span>对话历史</span>
            <span class="chat-history-limit">最多 ${MAX_CONVERSATIONS_LIST} 条</span>
          </div>
          <ul class="chat-history-list" id="chatHistoryList"></ul>
        </div>
      </div>
      <div class="chat-main card">
        <div class="chat-messages" id="chatMessages">
          <div class="chat-welcome">
            <div class="empty-icon">&#129302;</div>
            <p>向 AI 助手提问，解释概念、公式或复习难点</p>
          </div>
        </div>
        <div class="chat-input-bar">
          <textarea class="form-textarea" id="chatInput" rows="2" placeholder="输入你的问题，例如：请解释这个公式的含义…"></textarea>
          <button class="btn btn-primary" id="btnSendChat">发送</button>
        </div>
      </div>
    </div>
  `;

  chatMounted = true;
  syncSubjectSelect();
  currentConversationId = activeConversationIds[sessionKey(chatSubjectId)] ?? null;

  document.getElementById('chatSubject').addEventListener('change', async (e) => {
    if (sending) {
      showToast('等待当前回复结束后再切换科目', 'error');
      e.target.value = chatSubjectId;
      return;
    }
    await switchChatSession(e.target.value);
    updateSubjectHint();
  });

  document.getElementById('btnSendChat').addEventListener('click', sendMessage);
  document.getElementById('btnClearChat').addEventListener('click', startNewChat);
  document.getElementById('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  await loadConversationList(chatSubjectId);
  if (currentConversationId) {
    await openConversation(currentConversationId);
  } else {
    restoreChatMessages();
  }
  syncChatSendingUi();
  updateSubjectHint();
}

function updateSubjectHint() {
  const hint = document.getElementById('chatSubjectHint');
  const select = document.getElementById('chatSubject');
  if (!hint || !select) return;
  const note = `每条对话最多 ${MAX_TURNS_PER_CONVERSATION} 轮，保留最近 ${MAX_CONVERSATIONS_LIST} 条历史`;
  if (!select.value) {
    hint.textContent = `通用对话不使用科目知识库。${note}`;
    return;
  }
  const name = select.options[select.selectedIndex]?.text || '';
  hint.textContent = `当前使用「${name}」知识库。${note}`;
}

function scrollChatToBottom() {
  const box = document.getElementById('chatMessages');
  if (box) box.scrollTop = box.scrollHeight;
}

function restoreChatMessages() {
  const box = document.getElementById('chatMessages');
  if (!box) return;
  box.innerHTML = '';
  if (!chatHistory.length && !sending) {
    box.innerHTML = `
      <div class="chat-welcome">
        <div class="empty-icon">&#129302;</div>
        <p>向 AI 助手提问，解释概念、公式或复习难点</p>
      </div>`;
    return;
  }
  for (const msg of chatHistory) {
    appendMessage(msg.role, msg.content, false);
  }
  if (sending) {
    ensureStreamingBubble();
    updateStreamingContent(streamingDraft);
  }
  scrollChatToBottom();
}

function syncChatSendingUi() {
  const btn = document.getElementById('btnSendChat');
  const input = document.getElementById('chatInput');
  const select = document.getElementById('chatSubject');
  const list = document.getElementById('chatHistoryList');
  if (btn) btn.disabled = sending;
  if (select) select.disabled = sending;
  if (list) list.classList.toggle('is-disabled', sending);
  if (input && !sending) input.focus();
}

function appendMessage(role, content, scroll = true) {
  const box = document.getElementById('chatMessages');
  if (!box) return;
  box.querySelector('.chat-welcome')?.remove();
  const el = document.createElement('div');
  el.className = `chat-bubble chat-bubble-${role}`;
  el.innerHTML = `
    <div class="chat-bubble-role">${role === 'user' ? '你' : 'AI'}</div>
    <div class="chat-bubble-content">${escapeHtml(content).replace(/\n/g, '<br>')}</div>
  `;
  box.appendChild(el);
  if (scroll) box.scrollTop = box.scrollHeight;
}

function ensureStreamingBubble() {
  if (document.getElementById('chatStreaming')) {
    return document.getElementById('chatStreamingContent');
  }
  const box = document.getElementById('chatMessages');
  if (!box) return null;
  box.querySelector('.chat-welcome')?.remove();
  const el = document.createElement('div');
  el.id = 'chatStreaming';
  el.className = 'chat-bubble chat-bubble-assistant chat-streaming';
  el.innerHTML = `
    <div class="chat-bubble-role">AI</div>
    <div class="chat-bubble-content" id="chatStreamingContent"><span class="chat-stream-cursor"></span></div>
  `;
  box.appendChild(el);
  scrollChatToBottom();
  return document.getElementById('chatStreamingContent');
}

function updateStreamingContent(text) {
  streamingDraft = text || '';
  const contentEl = document.getElementById('chatStreamingContent') || ensureStreamingBubble();
  if (!contentEl) return;
  const html = streamingDraft ? escapeHtml(streamingDraft).replace(/\n/g, '<br>') : '';
  contentEl.innerHTML = `${html}<span class="chat-stream-cursor"></span>`;
  scrollChatToBottom();
}

function finalizeStreamingBubble() {
  document.getElementById('chatStreaming')?.classList.remove('chat-streaming');
  document.getElementById('chatStreamingContent')?.querySelector('.chat-stream-cursor')?.remove();
  streamingDraft = '';
}

function removeStreamingBubble() {
  document.getElementById('chatStreaming')?.remove();
  streamingDraft = '';
}

async function sendMessage() {
  if (sending) return;
  const input = document.getElementById('chatInput');
  const message = input?.value.trim();
  if (!message) return;

  const subjectId = document.getElementById('chatSubject')?.value || undefined;
  chatSubjectId = subjectId || '';

  sending = true;
  streamingDraft = '';
  if (input) input.value = '';
  syncChatSendingUi();

  appendMessage('user', message);
  chatHistory = trimHistory([...chatHistory, { role: 'user', content: message }]);
  ensureStreamingBubble();
  updateStreamingContent('');

  try {
    const result = await api.sendChatStream(
      { message, subjectId, conversationId: currentConversationId },
      (text) => updateStreamingContent(text),
    );
    const reply = result?.reply ?? result;
    if (result?.conversationId) currentConversationId = result.conversationId;
    chatHistory = Array.isArray(result?.history)
      ? trimHistory(result.history)
      : trimHistory([...chatHistory, { role: 'assistant', content: reply }]);
    if (Array.isArray(result?.conversations)) {
      conversationList = result.conversations.slice(0, MAX_CONVERSATIONS_LIST);
    } else {
      await loadConversationList(chatSubjectId);
    }
    saveUiState();
    finalizeStreamingBubble();
    renderConversationList();
  } catch (err) {
    removeStreamingBubble();
    chatHistory = chatHistory.filter(
      (m, i) => !(i === chatHistory.length - 1 && m.role === 'user' && m.content === message),
    );
    restoreChatMessages();
    showToast(err.message || '发送失败', 'error');
  } finally {
    sending = false;
    syncChatSendingUi();
  }
}
