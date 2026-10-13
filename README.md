# 知行 ZhiXing · 智能旅行规划助手

这是一个基于 LangChain、LangGraph、FastAPI、PostgreSQL、RAG 和 MCP 的旅行规划 Agent 项目。项目目标是把用户需求、目的地查询、交通规划、长期记忆和外部工具调用串成一条完整的应用链路。

## 项目亮点

- FastAPI 提供注册、登录、会话管理和 SSE 流式对话接口。
- LangGraph Travel Agent 负责需求收集、目的地推荐、交通、住宿、餐饮、行程、预算和订单等流程。
- Destination Router 会把目的地相关问题分发给探索 Agent 和天气 Agent。
- Transport Coordinator 会协调高铁、自驾等交通 Subagent。
- RAG 使用父子文档切分、混合检索和重排序，从本地旅游知识库中获取资料。
- MCP 统一接入天气、搜索、地图、车票、航班、酒店等工具服务。
- PostgreSQL 同时承载业务表、LangGraph Checkpointer 和用户长期记忆 Store。
- 前端使用 `frontend/zhixing.html`，支持登录、会话列表和流式回复。
- 接口层带滑动窗口限流与请求体上限，避免被脚本刷爆导致 LLM 额度损失。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 语言与包管理 | Python 3.11+、uv |
| Web 框架 | FastAPI、Uvicorn |
| Agent 框架 | LangChain、LangGraph |
| 数据库 | PostgreSQL、SQLAlchemy |
| 状态持久化 | LangGraph Checkpointer |
| 长期记忆 | LangGraph Store |
| 知识检索 | Chroma、BM25、Embedding |
| 外部工具 | MCP、FastMCP |
| 前端 | HTML、CSS、JavaScript |

## 目录结构

```text
.
├── app/
│   ├── agents/            # 主 Agent、Router、Subagents
│   ├── api/               # FastAPI 路由和认证依赖
│   ├── core/              # State、Checkpointer、Store、Middleware
│   ├── mcp_core/          # MCP Client 和本地 MCP Server
│   ├── models/            # SQLAlchemy 数据库模型
│   ├── rag/               # RAG 加载、切分、检索、重排序、管道
│   ├── schemas/           # Pydantic 请求/响应模型
│   ├── tools/             # Agent 可调用的工具
│   ├── utils/             # 日志、密码与令牌、限流
│   ├── main.py            # FastAPI 应用入口
│   └── run.py             # Windows 兼容启动脚本
├── data/
│   ├── documents/         # RAG 原始资料
│   └── vectorstore/       # Chroma 向量数据
├── frontend/
│   └── zhixing.html       # 前端页面
├── scripts/
│   ├── init_db.py         # 初始化 PostgreSQL
│   ├── init_rag.py        # 初始化 RAG 向量库
│   └── test_llm.py        # 检查 LLM 连通性
├── tests/                 # 测试脚本
├── .env                   # 本地环境变量，不提交真实密钥
└── pyproject.toml
```

## 环境变量

项目通过 `app/config.py` 读取项目根目录下的 `.env` 文件。不要把真实密钥提交到公开仓库。

核心变量示例：

```env
# LLM
LLM_API_KEY=your-llm-api-key
LLM_MODEL_NAME=qwen3.6-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# LangSmith
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=zhixing-travel-planner-dev
LANGSMITH_TRACING=false

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=travel_planner_db
POSTGRES_USER=travel_user
POSTGRES_PASSWORD=change-me

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# MCP / 外部服务
AMAP_API_KEY=your-amap-api-key
TAVILY_API_KEY=your-tavily-api-key
VARIFLIGHT_API_KEY=your-variflight-api-key
AIGOHOTEL_MCP_API=your-aigohotel-api-key

# 安全
JWT_SECRET_KEY=change-me-to-a-random-string
CORS_ALLOW_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
LLM_MAX_TOKENS=4000
```

说明：

- 当前 `Settings` 中 `LLM_API_KEY` 和 `LANGSMITH_API_KEY` 是必填项。
- 如果暂时不使用 LangSmith，也请给 `LANGSMITH_API_KEY` 一个非空占位值，并把 `LANGSMITH_TRACING=false`。
- 数据库连接串由 `POSTGRES_*` 变量在代码中拼出，不需要单独配置 `DATABASE_URL`。
- `JWT_SECRET_KEY` 必须单独配置，不要用 LLM 密钥代替。

## 本地启动

### 1. 安装依赖

在项目根目录执行：

```bash
uv sync
```

### 2. 准备 PostgreSQL

如果本地还没有 PostgreSQL，可以使用带 pgvector 的镜像：

```bash
docker run -d \
  --name langgraph-travel-postgres \
  -e POSTGRES_DB=travel_planner_db \
  -e POSTGRES_USER=travel_user \
  -e POSTGRES_PASSWORD=change-me \
  -p 5432:5432 \
  -v langgraph-travel-postgres-data:/var/lib/postgresql/data \
  pgvector/pgvector:pg17
```

然后确保 `.env` 中的 PostgreSQL 配置与实际数据库一致。

### 3. 初始化数据库

```bash
uv run python scripts/init_db.py
```

这一步会创建：

- `user`、`conversation`、`message` 等业务表。
- LangGraph Checkpointer 需要的表。
- LangGraph Store 需要的表。
- `vector` 扩展。

### 4. 初始化 RAG 知识库

```bash
uv run python scripts/init_rag.py
```

它会读取 `data/documents/destinations/` 下的资料，切分文档并写入 Chroma 向量库。更新旅游资料后建议重新执行。

### 5. 启动服务

```bash
uv run python app/run.py
```

启动成功后访问：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/>

## 使用前端

用浏览器打开：

```text
frontend/zhixing.html
```

基本流程：

1. 注册或登录，浏览器会拿到 JWT。
2. 创建或选择会话。
3. 输入旅行需求。
4. Agent 通过 SSE 逐步返回回答。

后端 CORS 使用白名单：精确来源走 `CORS_ALLOW_ORIGINS`（逗号分隔），
本机调试用的任意端口以及 `file://` 直接双击打开页面（此时浏览器 Origin 为 `null`）由 `CORS_ALLOW_ORIGIN_REGEX` 兜住。
上线时把正则改成 `^https://你的域名$` 或留空，只保留精确白名单。

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/users/register` | 用户注册 |
| POST | `/api/v1/users/login` | 用户登录 |
| GET | `/api/v1/users/me` | 获取当前用户 |
| POST | `/api/v1/conversations` | 创建会话 |
| GET | `/api/v1/conversations` | 查询会话列表 |
| PATCH | `/api/v1/conversations/{id}` | 更新会话 |
| DELETE | `/api/v1/conversations/{id}` | 删除会话（真删除，级联删消息） |
| POST | `/api/v1/chat/stream/{conversation_id}` | 流式对话 |
| GET | `/api/v1/chat/history/{conversation_id}` | 查询历史消息 |

受保护接口需要在请求头中携带：

```http
Authorization: Bearer <access_token>
```

## 防刷与限流

对话接口会真实调用大模型和第三方 MCP 服务，属于"花钱接口"，因此加了三道闸门：

| 闸门 | 位置 | 规则 | 触发返回 |
| --- | --- | --- | --- |
| 滑动窗口限流 | `app/utils/rate_limit.py` | 注册 5 次/小时/IP；登录 10 次/分钟/IP；对话 8 次/分钟 + 120 次/小时/用户，另有 300 次/小时/IP 兜底 | `429` + `Retry-After` |
| 请求体大小上限 | `app/main.py` 的 `limit_body_size` | 超过 1 MB 直接拒绝，不进业务代码 | `413` |
| 字段长度校验 | `app/schemas/` | 对话内容 1-2000 字；密码 6-128 字 | `422` |

阈值集中在 `RATE_RULES` 一张表里，改数字不用碰业务代码。
当前计数放在进程内存，单进程部署够用；多进程或多机部署时把 `SlidingWindowRateLimiter` 换成 Redis 实现即可。

流式对话请求体示例：

```json
{
  "content": "我想去西安玩三天，推荐一些景点和美食。"
}
```

SSE 响应的核心事件：

```text
data: {"type": "token", "content": "西"}
data: {"type": "token", "content": "安"}
data: {"type": "tool_call", "tool": "query_destination_info"}
data: {"type": "done"}
```

## Agent 执行链路

```text
前端请求
  ↓
FastAPI 认证与会话校验
  ↓
保存用户消息
  ↓
创建 Travel Agent
  ↓
StepConfigMiddleware 读取 current_step
  ↓
读取用户长期记忆
  ↓
注入当前步骤 Prompt 和工具
  ↓
Agent 调用 Router / RAG / MCP / 交通 Subagent
  ↓
SSE 逐步返回 token
  ↓
保存完整 AI 回复
```

核心模块职责：

| 模块 | 职责 |
| --- | --- |
| `app/core/state.py` | 定义旅行规划主状态 |
| `app/core/checkpointer.py` | 保存会话级 LangGraph 状态 |
| `app/core/store.py` | 保存用户长期记忆 |
| `app/core/middleware.py` | 按步骤注入 Prompt、工具和记忆 |
| `app/agents/handoffs/step_config.py` | 配置每个业务步骤 |
| `app/agents/handoffs/travel_agent.py` | 组装主 Agent |
| `app/agents/routers/destination_router.py` | 分发目的地相关任务 |
| `app/agents/subagents/` | 交通相关 Subagent |
| `app/rag/` | RAG 检索管道 |
| `app/mcp_core/` | MCP 服务和客户端 |
| `app/api/v1/` | 用户、会话、聊天接口 |

## MCP 服务

项目包含两类 MCP 服务。

本地服务：

```text
app/mcp_core/servers/weather_server.py
app/mcp_core/servers/search_server.py
```

外部服务：

```text
amap
12306-mcp
VariFlight-Aviation
aigohotel-mcp
```

`MCPClientManager` 在应用启动时初始化客户端，并把 MCP 工具转换成 LangChain 可用的 `BaseTool`。外部 MCP 不可用时，工具加载可能为空，但不一定会阻断整个 FastAPI 启动。

## 测试

运行全部测试：

```bash
uv run pytest -q
```

注意：项目里的部分测试属于集成测试，可能需要真实的 PostgreSQL、LLM、外部 MCP 或 API Key。只测试静态逻辑时，可以先跳过这些依赖较重的用例。

## 常见问题

### 数据库初始化失败

检查：

1. PostgreSQL 是否已经启动。
2. 数据库、用户名、密码是否和 `.env` 一致。
3. 数据库镜像是否支持 `CREATE EXTENSION IF NOT EXISTS vector;`。

### MCP 工具数量为 0

检查：

1. `.env` 中对应 API Key 是否有效。
2. 外部 MCP 服务是否能访问。
3. 本地 MCP Server 是否能通过 `python -m app.mcp_core.servers.weather_server` 启动。

### Windows 事件循环问题

优先使用：

```bash
uv run python app/run.py
```

`app/run.py` 已经针对 Windows 设置了 `SelectorEventLoop`。

### 日志在哪里

日志输出到控制台，同时写入项目根目录下的：

```text
logs/app.log
logs/error.log
```

## 当前定位

知行目前适合作为本地学习和演示的多 Agent 旅行规划项目。它已经覆盖了 Agent 工具调用、RAG、MCP、状态持久化和长期记忆，但在真实生产使用前，还需要根据实际需求完善鉴权配置、外部服务可用性、测试隔离和部署流程。

## 关于本项目

作者：桃（GitHub: 527665）。

这是一个独立设计与实现的工程化项目，代码结构、状态机设计、提示词体系、记忆分层、安全边界和测试用例均由本人完成，并做过完整的端到端流程验证与安全测试。仓库不包含任何密钥、真实用户数据与本地环境配置，克隆后按上文「本地启动」五步即可运行。

## 许可证与使用边界

**本项目公开源代码，但不属于开源项目。** 根目录 `LICENSE` 文件写明的是 All Rights Reserved（保留所有权利），不是开源许可证；下面这份清单与该文件内容一致，以 `LICENSE` 为准。

明确允许：

- 阅读、克隆、在本地编译运行、改造后仅用于个人学习与研究。
- 在技术文章、课程作业、面试演示中引用本项目思路，注明出处与仓库地址即可。
- 提交 Issue 反馈问题，提交 Pull Request 建议改动。

未经作者书面许可，不允许：

- 把本仓库的代码、提示词、文档复制进你自己的项目（无论开源、闭源、是否盈利）。
- 去除作者署名后重新发布，或把本仓库内容作为独立作品对外分发。
- 把本仓库内容作为模型训练语料再分发。

需要商用或二次授权，请通过 GitHub Issue 或账号主页联系方式与作者协商。

一个必须说清的前提：本节约束的是**别人对这份代码能做什么**，管不到 GitHub 平台自身的运作。按 GitHub 服务条款，公开仓库的内容会向所有人可见并可被检索；平台为渲染和提供服务所必需的使用（含 Fork 功能）已在条款里获得授权；条款同时声明不额外限制第三方对公开仓库内容的"合法访问与使用"。也就是说，转公开之后，"看"和"被平台索引"这两件事拦不住，能拦住的是"把你的代码搬进他自己的项目"。

如果你需要严格保密，唯一可靠做法是保持仓库私有。
