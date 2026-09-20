# Agentic RAG Demo（实习面试项目）

带 MCP 工具的 Agentic RAG 问答系统：**知识库优先，答不上则调用工具**。

## 架构
用户提问 → Redis 缓存 → Corrective RAG（检索+相关性校验）→ ReAct Agent（MCP 工具）→ 返回答案

## 技术点（面试可讲）
- Corrective RAG：检索后由 LLM 校验相关性，不相关拒答，防幻觉
- ReAct Agent（LangGraph）：工具调用推理链
- MCP 协议：工具以 stdio 方式通过标准协议暴露，Agent 自动发现工具；失败自动降级
- FastAPI + lifespan 管理模型生命周期
- Redis 缓存问答结果，TTL 过期
- Docker / docker-compose 一键部署

## 本地运行
pip install -r requirements.txt
cp .env.example .env   # 填入 API Key
uvicorn app.main:app --reload

## Docker 运行
docker-compose up --build

## 测试
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "年假有几天？"}'
# -> 知识库回答 {"answer": "...", "source": "kb"}

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "北京今天天气怎么样，顺便算一下 12*8"}'
# -> 走 Agent 工具调用 {"answer": "...", "source": "agent"}

## Git 版本管理

首次提交：
git init
git add .
git commit -m "init: agentic rag demo"

常用流程：
git checkout -b feature/xxx   # 开新分支开发
git add app/ && git commit -m "feat: xxx"
git merge feature/xxx         # 合回主分支

注意：.env 已被 .gitignore 排除；若误提交过密钥，
先改密钥，再执行 git rm --cached .env 并重新提交。
