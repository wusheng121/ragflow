# RAG 复习助手（FastAPI + RAGFlow + 本地模型）

一个面向学生的“以教代学”RAG 复习助手 MVP，侧重于可解释的练习与自动错题管理：

- 知识卡片（LLM-first）：优先让大模型输出结构化 JSON 卡片并校验，失败则回退本地规则提取。
- 抽查式练习（LLM-first）：问题默认采用 LLM 原句（通过质量检验）；仅在不合格时使用简洁模板回退（如“XXX 是什么？”）。
- 错题/疑难本：低分回答自动入库，支持人工编辑与复习优先级调整。
- 练习历史：记录每次答题与评分，便于进度回溯。
- 一致性评估：用知识源证据给出分数、短反馈与纠正建议。

重要实现亮点：
- 默认输出中文（术语可保留英文原名），并有语言检测与翻译辅助。
- 严格的概念归一化：屏蔽问词/占位词（如 why/what/该点）以避免生成无意义问题。
- LLM 质检与重试：问题与卡片均有输出质量判定，合格即直出，不合格才回退。

（本仓库为开发中版本，持续改进 prompt 与生成策略）

## 项目结构

- `app/main.py`: FastAPI 入口
- `app/api/v1/materials.py`: 资料上传与管理
- `app/api/v1/assistant.py`: 知识卡片、提问、评分
- `app/api/v1/attempts.py`: 练习历史查询
- `app/api/v1/users.py`: 用户注册/登录/查询
- `app/api/v1/mistakes.py`: 错题本查看与编辑
- `app/templates/frontend_index.html`: 一体化前端仪表盘
- `app/clients/ragflow_client.py`: RAGFlow 接口封装（失败自动回退本地检索）
- `app/clients/local_llm_client.py`: 本地模型接口封装（失败自动回退 mock）
- `tests/test_app.py`: 最小回归测试
- `scripts/demo_runner.py`: 一键演示流程

## 快速启动

1. 创建虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. 配置环境变量：

```powershell
Copy-Item .env.example .env
# 编辑 .env，根据你使用的后端调整（RAGFlow / 本地模型）
```

3. 启动服务：

```powershell
uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000` 查看一体化前端仪表盘。

前端页面说明：
- `/`：主页/仪表盘（登录、注册、上传资料、练习、错题本、历史）
- `/static/pages/page-login.html`：独立登录页
- `/static/pages/page-register.html`：独立注册页
- `/static/pages/page-history.html`：独立历史页

## 本地模型接入

本项目支持两类模型接入方式：

1) 本地兼容网关（推荐用于离线/快速迭代，例如 Ollama/vLLM）：

- 设置 `RAGFLOW_LOCAL_LLM_ENABLED=true`
- 设置 `RAGFLOW_LOCAL_LLM_BASE_URL`（例如 `http://127.0.0.1:11434`）和 `RAGFLOW_LOCAL_LLM_CHAT_PATH`（例如 `/v1/chat/completions`）
- 设置 `RAGFLOW_LOCAL_LLM_MODEL` 为本地模型名（或云端模型名，当使用云兼容网关时）

2) 云端兼容接口（例如 Qwen / DashScope 兼容模式）：

- 将 `RAGFLOW_LOCAL_LLM_BASE_URL` 指向云端兼容域名（例如 `https://dashscope.aliyuncs.com`）并设置 `RAGFLOW_LOCAL_LLM_CHAT_PATH=/compatible-mode/v1/chat/completions`，同时填 `RAGFLOW_LOCAL_LLM_API_KEY`。

注意：如果 LLM 无法连通，客户端会回退到 mock 响应或项目内置的提取规则，因此请优先确认 `BASE_URL`、`CHAT_PATH` 与 `MODEL` 匹配你的服务。

## RAGFlow 接入

`RagflowClient` 负责把检索/上传请求发到你部署的 RAGFlow 服务，用于生成基于证据的引用片段。
在 `.env` 中打开并设置：

- `RAGFLOW_RAGFLOW_ENABLED=true`
- `RAGFLOW_RAGFLOW_BASE_URL`（例如 `http://127.0.0.1:9380`）
- `RAGFLOW_RAGFLOW_UPLOAD_PATH`（上传文档端点模板）
- `RAGFLOW_RAGFLOW_RETRIEVE_PATH`（检索端点模板）

如果你的 RAGFlow API 字段命名不完全一致，可以在 `app/clients/ragflow_client.py` 做最小化适配。

## 本地部署 RAGFlow（推荐）

如果云端后台没有 API 页面，或者你拿不到 `API_KEY` / `dataset_id`，建议直接本地部署 RAGFlow。

详细步骤见：`docs/local-ragflow-deploy.md`

最短流程是：
1. 安装 Docker
2. 启动官方 RAGFlow 服务
3. 在 RAGFlow 后台创建 dataset
4. 找到 API Key
5. 回填当前项目的 `.env`
6. 先上传资料，再做检索和问答验证

## 运行测试与演示

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
python scripts/demo_runner.py
```

也可以直接用浏览器操作主页完成：登录/注册 → 上传资料 → 生成知识卡片 → 生成练习题 → 提交答案 → 查看错题本和历史。

## Prompt 工程要点

- 问题生成：强调“引导提问+举例+分层难度”，避免直接给答案。
- 评分纠错：强调“知识源一致性+关键遗漏点+短反馈”。
- 错题本策略：低于阈值自动入本；重复错误自动提升优先级（`reviewing`）。

## 后续可扩展

- 解析 PDF/PPT 课件并保留页码证据。
- 加入学习曲线、间隔重复（SRS）调度。
- 引入评测集离线对比不同 prompt/模型表现。
- 把当前的 username-only 登录升级成真正的密码/JWT 认证。
 
## 最近改动摘要

- 问题与卡片生成改为 LLM-first，新增输出质量检验与重试策略。
- 默认输出中文（材料语言检测 + 翻译辅助），并屏蔽问词/泛化占位符作为概念。
- 问题现在优先保留 LLM 原句（如果通过质检），否则回退为简洁模板。 

如需把当前仓库推到远程（例如 `git@github.com:wusheng121/ragflow.git`），请确保有对应的权限与 SSH key 配置。

