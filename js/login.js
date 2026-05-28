import { api, getAuthUser, isLoggedIn } from './api.js';
import { showToast } from './utils.js';

function redirectIfLoggedIn() {
  if (isLoggedIn()) {
    window.location.href = 'app.html';
  }
}

function switchTab(tab) {
  document.querySelectorAll('.auth-tab').forEach((el) => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });
  document.getElementById('loginForm').hidden = tab !== 'login';
  document.getElementById('registerForm').hidden = tab !== 'register';
  document.getElementById('loginError').hidden = true;
  document.getElementById('registerError').hidden = true;
}

function showFormError(formId, message) {
  const el = document.getElementById(formId === 'login' ? 'loginError' : 'registerError');
  el.textContent = message;
  el.hidden = !message;
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('loginSubmit');
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  showFormError('login', '');
  btn.disabled = true;
  btn.textContent = '登录中…';
  try {
    await api.login(email, password);
    window.location.href = 'app.html';
  } catch (err) {
    showFormError('login', err.message || '登录失败');
  } finally {
    btn.disabled = false;
    btn.textContent = '登录';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('registerSubmit');
  const email = document.getElementById('registerEmail').value.trim();
  const password = document.getElementById('registerPassword').value;
  const confirm = document.getElementById('registerConfirm').value;
  showFormError('register', '');

  if (password !== confirm) {
    showFormError('register', '两次输入的密码不一致');
    return;
  }
  if (password.length < 6) {
    showFormError('register', '密码至少 6 位');
    return;
  }

  btn.disabled = true;
  btn.textContent = '注册中…';
  try {
    await api.register(email, password);
    window.location.href = 'app.html';
  } catch (err) {
    showFormError('register', err.message || '注册失败');
  } finally {
    btn.disabled = false;
    btn.textContent = '注册并登录';
  }
}

document.querySelectorAll('.auth-tab').forEach((tab) => {
  tab.addEventListener('click', () => switchTab(tab.dataset.tab));
});

document.getElementById('loginForm').addEventListener('submit', handleLogin);
document.getElementById('registerForm').addEventListener('submit', handleRegister);

redirectIfLoggedIn();

// Restore email if switching back from app
const user = getAuthUser();
if (user?.email) {
  document.getElementById('loginEmail').value = user.email;
}
