const USER_KEY = 'rag_review_current_user';
const TOKEN_KEY = 'rag_review_token';

function setNotice(message, kind = 'info') {
  const box = document.getElementById('auth-message');
  if (!box) return;
  box.className = `notice ${kind}`;
  box.textContent = message;
  box.classList.remove('hidden');
}

function saveSession(auth) {
  localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
  localStorage.setItem(TOKEN_KEY, auth.access_token);
}

function hasSession() {
  return Boolean(localStorage.getItem(TOKEN_KEY));
}

function readQueryNotice() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('registered') === '1') {
	setNotice('注册成功，请登录。', 'success');
  }
}

function extractErrorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
	return data.detail
	  .map((item) => item.msg || item.message || JSON.stringify(item))
	  .join('；');
  }
  return data.message || fallback;
}

document.addEventListener('DOMContentLoaded', function () {
  readQueryNotice();
  if (hasSession()) {
	setNotice('检测到已有登录状态，可直接登录或前往学习空间。', 'info');
  }

  const form = document.getElementById('login-form');
  const btn = document.getElementById('login-submit');
  if (!form || !btn) return;

  form.addEventListener('submit', async function (event) {
	event.preventDefault();
	const formData = new FormData(form);
	const name = String(formData.get('username') || '').trim();
	const password = String(formData.get('password') || '').trim();
	if (!name) return setNotice('请输入用户名。', 'warning');
	if (!password) return setNotice('请输入密码。', 'warning');

	btn.disabled = true;
	btn.textContent = '登录中...';
	setNotice('正在验证登录信息...', 'info');
	try {
	  const res = await fetch('/api/v1/users/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ name, password }),
	  });
	  const data = await res.json();
	  if (!res.ok) {
		throw new Error(extractErrorMessage(data, '登录失败，请检查账号和密码。'));
	  }

	  saveSession(data);
	  setNotice('登录成功，正在进入学习空间...', 'success');
	  setTimeout(() => {
		location.href = '/dashboard';
	  }, 350);
	} catch (error) {
	  setNotice(error.message || '登录失败，请稍后重试。', 'warning');
	} finally {
	  btn.disabled = false;
	  btn.textContent = '登录';
	}
  });
});

