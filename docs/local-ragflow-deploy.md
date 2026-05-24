# 本地部署 RAGFlow：从零开始

> 目标：先把 RAGFlow 在本地跑起来，再拿到 `API_KEY` 和 `dataset_id`，最后回填到本项目的 `.env`。

## 你需要准备什么

### 必要条件
- 一台能安装 Docker 的电脑
- Docker Desktop / Docker Engine + Docker Compose
- 至少 16GB 内存更稳，磁盘预留 30GB 以上更好
- 能访问 Docker 镜像仓库（如果网络受限，需要配置镜像加速或代理）

### 你要先理解的两件事
- **RAGFlow 本体**：单独部署的服务，不在当前这个 FastAPI 项目里
- **当前项目**：只是调用 RAGFlow 的客户端，真正的数据源和检索服务在 RAGFlow 里

---

## 第 1 步：安装 Docker

### Windows
1. 安装 Docker Desktop
2. 开启 WSL2（如果 Docker Desktop 要求）
3. 安装完成后，在终端里确认：

```powershell
docker --version
docker compose version
```

如果这两条都能正常输出，说明 Docker 环境可用。

### Linux
安装 Docker Engine 和 Compose 插件，然后确认：

```bash
docker --version
docker compose version
```

---

## 第 2 步：获取 RAGFlow 的官方部署包

去 RAGFlow 的官方仓库或官方发布页，获取它的本地部署方式。
通常会包含以下内容之一：
- `docker-compose.yml`
- `.env` 或 `.env.example`
- 启动说明文档

> 建议直接用官方提供的 compose / release，不要自己手写整套依赖，除非你已经非常熟悉它的组件。

---

## 第 3 步：按官方说明启动 RAGFlow

一般顺序是：

1. 下载/克隆 RAGFlow 部署包
2. 复制环境变量文件
3. 修改端口、数据库、模型配置
4. 启动服务

常见启动方式类似：

```bash
docker compose up -d
```

启动后先等所有容器变成 `healthy` 或 `running`。

---

## 第 4 步：打开 RAGFlow 后台

启动成功后，用浏览器打开 RAGFlow 的地址。
常见是：

- `http://127.0.0.1:9380`
- 或者你自己在 compose 里映射的端口

如果打不开：
- 先看容器是否都起来了
- 再看端口映射是否正确
- 再看日志里是否有数据库/依赖服务启动失败

---

## 第 5 步：在 RAGFlow 后台里创建数据集

进入后台后：

1. 点顶部的 `Dataset`
2. 新建一个 dataset / knowledge base
3. 打开这个数据集详情页
4. 记录它的 `dataset_id`

常见查法：
- 详情页直接显示 `ID`
- 页面 URL 里带着 id
- 复制按钮里可以直接复制

你最终要把它写进当前项目的 `.env`：

```dotenv
RAGFLOW_RAGFLOW_DATASET_ID=你的dataset_id
```

---

## 第 6 步：在 RAGFlow 后台里找到 API Key

通常在以下位置之一：
- 右上角头像菜单
- `Profile`
- `Settings`
- `API Keys`
- `Token` / `Access Token`

如果能新建 key，就复制出来。

写进当前项目的 `.env`：

```dotenv
RAGFLOW_RAGFLOW_API_KEY=你的API_KEY
```

如果后台里根本没有 API Key 相关页面，通常有三种可能：
- 你当前账号权限不够
- 这个云端/版本没有开放给普通用户
- 需要管理员后台单独开通

这种情况下，**本地部署反而更适合你**。

---

## 第 7 步：把当前项目改成指向本地 RAGFlow

你这个项目里，只需要改 `.env`，核心是这几项：

```dotenv
RAGFLOW_RAGFLOW_ENABLED=true
RAGFLOW_RAGFLOW_BASE_URL=http://127.0.0.1:9380
RAGFLOW_RAGFLOW_API_KEY=你的API_KEY
RAGFLOW_RAGFLOW_DATASET_ID=你的DATASET_ID
RAGFLOW_RAGFLOW_UPLOAD_PATH=/api/v1/datasets/{dataset_id}/documents
RAGFLOW_RAGFLOW_RETRIEVE_PATH=/api/v1/retrieval
```

建议先把本地模型关掉，先把 RAGFlow 跑通：

```dotenv
RAGFLOW_LOCAL_LLM_ENABLED=false
```

---

## 第 8 步：验证是否真正接通

### 第一次验证：上传资料
在当前项目里调用：
- `POST /api/v1/users/register`
- `POST /api/v1/materials/upload`

如果上传成功，说明：
- 你的项目能收到文件
- 文本抽取没问题
- RAGFlow 上传接口至少没有立刻报错

如果这里报 `502`，通常就是：
- `BASE_URL` 不对
- `API_KEY` 不对
- `dataset_id` 不对
- 上传接口路径不对

### 第二次验证：出题
调用：
- `POST /api/v1/assistant/practice/question`

如果返回了 `question` 和 `references`，说明：
- RAGFlow 检索能用了
- 当前项目能拿到证据片段

### 第三次验证：答题评分
调用：
- `POST /api/v1/assistant/practice/answer`

如果有分数和反馈，说明整条链路可用。

---

## 常见问题排查

### 1. `docker` 命令不存在
说明 Docker 没装好，或者没有加到 PATH。

### 2. 容器起来了，但网页打不开
检查：
- 端口映射
- 防火墙
- 代理
- 容器日志

### 3. 上传时提示 RAGFlow 失败
检查：
- `RAGFLOW_RAGFLOW_BASE_URL`
- `RAGFLOW_RAGFLOW_API_KEY`
- `RAGFLOW_RAGFLOW_DATASET_ID`
- 上传路径

### 4. 能上传，但检索不到结果
检查：
- dataset 里有没有真正导入资料
- dataset_id 是否是当前资料对应的那个
- 检索路径是否和官方版本一致

### 5. 先别急着开本地模型
建议先把 RAGFlow 跑通，再考虑：
- `RAGFLOW_LOCAL_LLM_ENABLED=true`
- 本地模型地址
- 模型名称

---

## 最后总结
如果你要“从零本地部署 RAGFlow”，最稳的顺序就是：

1. 安装 Docker
2. 获取官方 RAGFlow 部署包
3. `docker compose up -d`
4. 打开后台
5. 创建 dataset
6. 找 API Key
7. 把 `API_KEY` 和 `dataset_id` 填进当前项目 `.env`
8. 先上传资料，再做问答验证

如果你愿意，我可以下一步直接把这份流程压缩成一份“Windows 版 10 分钟上手清单”。

