# RAGFlow 复习助手（FastAPI + MySQL + RAGFlow）

一个面向学生的「以教代学」RAG 复习助手，侧重于知识沉淀、抽查练习与错题管理：

- **知识卡片（LLM）**：从上传资料中抽取专业术语，由 RAGFlow 大模型输出结构化 JSON 卡片并入库。
- **抽查式练习**：基于知识卡片生成选择题，答错自动进入错题本。
- **智能问答**：可选关联科目，结合知识卡片背景由 AI 解答复习疑问。
- **错题本**：练习中答错的题目自动收录，按科目筛选复习。
- **练习历史**：记录每次练习得分、题量与用时，便于进度回溯。
- **用户与数据隔离**：邮箱注册/登录，JWT 鉴权，科目与资料按用户隔离。

**重要实现亮点：**

- 资料同步至 RAGFlow Dataset，解析完成后基于文档 chunks 做概念抽取。
- 概念抽取 Prompt 强调**专业术语**，过滤日常泛化词与纯公式算式。
- 抽取过程支持 **SSE 流式进度**（上传解析、AI 分析、保存卡片等阶段）。
- 单端口部署：`SERVE_FRONTEND=true` 时由后端同时托管前端静态资源。
- 未配置 RAGFlow 时，抽取/问答/部分能力可降级为本地规则模式（能力有限，仅供演示）。

（本仓库为持续迭代版本，Prompt 与生成策略会不断改进。）

## 项目结构

- `index.html`：登录 / 注册页
- `app.html`：主应用（仪表盘、科目、卡片、问答、练习等）
- `js/api.js`：API 封装（含 Mock 回退）
- `js/app.js`：路由与页面切换
- `js/modules/subjects.js`：科目与资料上传、概念抽取（进度条）
- `js/modules/knowledge-cards.js`：知识卡片浏览与管理
- `js/modules/chat.js`：智能问答
- `js/modules/practice.js`：练习抽查
- `js/modules/wrong-book.js`：错题本
- `js/modules/history.js`：练习历史
- `backend/app/main.py`：FastAPI 入口、CORS、静态资源挂载
- `backend/app/database.py`：SQLAlchemy 模型（User、Subject、Material、KnowledgeCard 等）
- `backend/app/schemas.py`：Pydantic 模型（API 输出 camelCase）
- `backend/app/routers/auth.py`：注册 / 登录 / 当前用户
- `backend/app/routers/subjects.py`：科目、资料上传、概念抽取
- `backend/app/routers/knowledge_cards.py`：知识卡片 CRUD
- `backend/app/routers/chat.py`：智能问答
- `backend/app/routers/practice.py`：练习题生成与提交
- `backend/app/routers/wrong_book.py`：错题本
- `backend/app/routers/history.py`：练习历史
- `backend/app/services/ragflow.py`：RAGFlow HTTP 客户端（Dataset、解析、对话）
- `backend/app/services/extract.py`：资料读取与概念抽取流程
- `backend/app/services/chat.py`：问答上下文构建
- `backend/app/services/quiz.py`：练习题生成
- `backend/sql/init.sql`：MySQL 建库脚本
- `backend/docker-compose.yml`：MySQL 8 容器
- `backend/.env.example`：环境变量示例

## 快速启动

### 1. 启动 MySQL（可选 Docker）

```powershell
cd backend
docker compose up -d
```

或在本机 MySQL 中执行 `sql/init.sql` 创建数据库 `ragflow_review`。

### 2. 创建虚拟环境并安装依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. 配置环境变量

```powershell
Copy-Item .env.example .env
# 编辑 .env：DATABASE_URL、RAGFLOW_API_URL、RAGFLOW_API_KEY、JWT_SECRET 等
```

### 4. 启动服务

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开 **http://127.0.0.1:8000/** 进入登录页；登录后访问 **http://127.0.0.1:8000/app.html**。

API 交互文档：**http://127.0.0.1:8000/docs**

### 前端页面说明

| 路径 | 说明 |
|------|------|
| `/` | 登录 / 注册 |
| `/app.html` | 主界面：仪表盘、科目管理、知识卡片、智能问答、练习抽查、错题本、历史 |

前端默认请求同源 `/api`；若后端未启动，会自动进入 **Mock 模式**（`localStorage` 模拟数据）。

## RAGFlow 接入

`backend/app/services/ragflow.py` 负责与 RAGFlow 通信：创建 Dataset、上传文档、等待解析、读取 chunks、调用 Chat Assistant 完成抽取与对话。

在 `backend/.env` 中配置：

- `RAGFLOW_API_URL`：RAGFlow 服务根地址（如 `http://127.0.0.1:9380` 或 ngrok 隧道地址）
- `RAGFLOW_API_KEY`：API Key
- `RAGFLOW_CHAT_ID`：（可选）Chat Assistant ID；留空则自动选用第一个助手
- `RAGFLOW_PARSE_TIMEOUT`：文档解析等待超时（秒）

**推荐流程：**

1. 在 RAGFlow 控制台创建 **Chat Assistant**（用于抽取、问答）。
2. 在本项目中创建科目并上传 PDF / PPTX / TXT / MD 等资料。
3. 等待 RAGFlow 解析完成后，执行「抽取概念」生成知识卡片。
4. 使用智能问答或练习抽查进行复习。

若云端无 API 页面或无法获取 Key，可参考 [RAGFlow 官方文档](https://github.com/infiniflow/ragflow) 进行本地 Docker 部署，再在后台创建 Dataset 与 API Key 并回填 `.env`。

## MySQL 配置

```env
DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/ragflow_review?charset=utf8mb4
```

表结构在应用启动时由 SQLAlchemy 自动创建；`sql/init.sql` 仅用于预先创建数据库。

## 环境变量一览

与 `backend/.env.example` 保持一致：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | MySQL 连接串 |
| `UPLOAD_DIR` | 上传目录（相对 `backend/`） |
| `RAGFLOW_API_URL` / `RAGFLOW_API_KEY` | RAGFlow 服务与密钥 |
| `RAGFLOW_CHAT_ID` | 可选，对话助手 ID |
| `RAGFLOW_PARSE_TIMEOUT` | 文档解析超时（秒） |
| `SERVE_FRONTEND` | 是否托管前端（`true` 推荐） |
| `FRONTEND_DIR` | 前端根目录（默认 `..`） |
| `CORS_ORIGINS` | 跨域来源（多端口或隧道时配置） |
| `JWT_SECRET` | JWT 密钥（生产环境务必修改） |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟） |

## API 端点（前缀 `/api`）

除注册、登录、健康检查外，需请求头：`Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录 |
| GET | `/auth/me` | 当前用户 |
| GET | `/stats` | 仪表盘统计 |
| GET/POST/DELETE | `/subjects` | 科目 |
| GET/POST/DELETE | `/subjects/{id}/materials` | 资料 |
| POST | `/subjects/{id}/extract` | 抽取知识卡片 |
| POST | `/subjects/{id}/extract/stream` | 流式抽取（SSE） |
| GET/DELETE | `/knowledge-cards` | 知识卡片 |
| POST | `/chat` | 智能问答 |
| POST | `/practice/generate` | 生成练习题 |
| POST | `/practice/submit` | 提交练习 |
| GET/DELETE | `/wrong-book` | 错题本 |
| GET | `/history` | 练习历史 |

## 浏览器使用流程

登录 / 注册 → 创建科目 → 上传资料 → **抽取概念**（观察进度条）→ 浏览知识卡片 → 智能问答 / 练习抽查 → 查看错题本与历史。

## Prompt 工程要点

- **概念抽取**：只抽资料中的专业术语；`summary` 限一句话，`detail` 基于原文展开；输出纯 JSON 数组。
- **智能问答**：注入科目知识卡片作为 system 背景，要求准确、结构化，公式保留原格式。
- **练习出题**：围绕卡片概念考查理解（当前实现以卡片内容为题库基础，后续可扩展为 LLM 原创题干与选项）。

## 后续可扩展

- 练习与问答全面改为 LLM 出题 / 流式回复，并增加输出质检与重试。
- 解析 PDF/PPT 时保留页码级证据引用。
- 间隔重复（SRS）与掌握度曲线。
- 离线评测集对比不同 Prompt / 模型效果。

## 最近改动摘要

- 前后端分离目录：`backend/` + 根目录静态前端；支持单端口一体化访问。
- 用户认证（JWT）与科目级数据隔离。
- RAGFlow 资料同步、解析等待与 LLM 概念抽取。
- 资料上传、概念抽取支持进度展示（SSE）。

## 许可证

本项目仅供学习与个人复习使用。使用 RAGFlow 时请遵守其官方许可与使用条款。
