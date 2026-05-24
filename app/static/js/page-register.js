const USER_KEY = 'rag_review_current_user';
const TOKEN_KEY = 'rag_review_token';
const AUTO_LOGIN_AFTER_REGISTER = true;

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

function validateRegisterInput({ name, email, password }) {
  if (!name) return '请输入用户名。';
  if (!/^[A-Za-z0-9_]{3,20}$/.test(name)) {
	return '用户名需为 3-20 位，仅可包含字母、数字和下划线。';
  }
  if (!password) return '请输入密码。';
  if (!/^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]{8,32}$/.test(password)) {
	return '密码需为 8-32 位，且至少包含字母和数字。';
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
	return '邮箱格式不正确。';
  }
  return '';
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
  if (hasSession()) {
	setNotice('检测到已有登录状态，可直接前往学习空间。', 'info');
  }

  const form = document.getElementById('register-form');
  const btn = document.getElementById('register-submit');
  if (!form || !btn) return;

  form.addEventListener('submit', async function (event) {
	event.preventDefault();
	const formData = new FormData(form);
	const name = String(formData.get('username') || '').trim();
	const password = String(formData.get('password') || '').trim();
	const email = String(formData.get('email') || '').trim();

	const invalidReason = validateRegisterInput({ name, email, password });
	if (invalidReason) {
	  setNotice(invalidReason, 'warning');
	  return;
	}

	btn.disabled = true;
	btn.textContent = '注册中...';
	setNotice('正在创建账号...', 'info');
	try {
	  const res = await fetch('/api/v1/users/register', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ name, password, email: email || null, level: 'beginner' }),
	  });
	  const data = await res.json();
	  if (!res.ok) {
		setNotice(extractErrorMessage(data, '注册失败，请检查输入后重试。'), 'warning');
		return;
	  }

	  form.reset();
	  if (AUTO_LOGIN_AFTER_REGISTER) {
		saveSession(data);
		setNotice('注册成功，已自动登录，正在进入学习空间...', 'success');
		setTimeout(() => {
		  location.href = '/dashboard';
		}, 650);
	  } else {
		setNotice('注册成功，正在返回登录页...', 'success');
		setTimeout(() => {
		  location.href = '/login?registered=1';
		}, 700);
	  }
	} catch (error) {
	  setNotice(error.message || '注册失败，请稍后重试。', 'warning');
	} finally {
	  btn.disabled = false;
	  btn.textContent = '注册';
	}
  });
});

