const USER_KEY = 'rag_review_current_user';

function loadUser() {
  try {
	return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch {
	return null;
  }
}

async function loadHistory() {
  const user = loadUser();
  const query = user?.id ? `?user_id=${user.id}&limit=50` : '?limit=50';
  const res = await fetch(`/api/v1/attempts${query}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '读取历史失败');
  const list = document.getElementById('history-page-list');
  const userInfo = document.getElementById('history-page-user');
  if (userInfo) {
	userInfo.textContent = user ? `当前用户：${user.name}（${user.level || 'beginner'}）` : '当前未登录，显示全部历史（若后端允许）';
  }
  if (list) {
	list.innerHTML = data.length
	  ? data.map((item) => `
		<div class="item-card">
		  <div class="item-title">${item.material_title || `材料 #${item.material_id}`} · ${item.concept || '综合练习'}</div>
		  <div class="muted">分数：${item.score} · ${item.is_correct ? '正确' : '待复习'} · ${new Date(item.created_at).toLocaleString()}</div>
		  <div class="item-text">${item.feedback || ''}</div>
		</div>`).join('')
	  : '<div class="empty-state">暂无练习历史。</div>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('refresh-history-page')?.addEventListener('click', () => {
	loadHistory().catch((err) => alert(err.message));
  });
  loadHistory().catch((err) => alert(err.message));
});

