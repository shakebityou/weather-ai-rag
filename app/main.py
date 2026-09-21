"""FastAPI 入口：统一问答入口 = 知识库优先，答不了交给 ReAct Agent。"""
import json
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agent import build_agent
from app.circuit_breaker import circuit
from app.config import settings
from app.db import init_db
from app.rag import answer_from_kb
from app.utils import get_cached, set_cached
from fastapi.staticfiles import StaticFiles

# 异常输出兜底话术
FALLBACK_MSG = "抱歉，这个问题我暂时无法回答。建议您联系官方客服获取准确帮助，感谢您的理解。"


def _safe_extract_answer(content: str) -> str:
    """从 Agent 返回内容中提取 JSON 的 answer 字段，异常时返回兜底话术。"""
    if not content or not content.strip():
        return FALLBACK_MSG
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            obj = json.loads(content[start:end + 1])
            if isinstance(obj, dict) and "answer" in obj:
                ans = str(obj["answer"]).strip()
                return ans if ans else FALLBACK_MSG
    except (json.JSONDecodeError, ValueError):
        pass
    # 不是 JSON，检查内容是否明显异常（空、纯标点、报错信息）
    text = content.strip()
    if not text or re.match(r'^[\s\W]+$', text):
        return FALLBACK_MSG
    return text



class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    source: str  # kb = 知识库 / agent = 工具调用 / cache = 缓存 / degraded = 降级


@circuit("agent",
         failure_threshold=settings.cb_failure_threshold,
         recovery_timeout=settings.cb_recovery_timeout,
         fallback=lambda agent, question: {
             "messages": [{"content": "抱歉，工具服务暂时不可用，请稍后再试。"}]
         })
def run_agent(agent, question: str) -> dict:
    """带熔断器的 Agent 调用，失败时返回降级提示。"""
    return agent.invoke({"messages": [("user", question)]})


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # MySQL 建库建表 + 空库灌示例数据
    app.state.llm = ChatOpenAI(base_url=settings.llm_base_url,
                               api_key=settings.llm_api_key,
                               model=settings.llm_model)
    app.state.agent = build_agent(app.state.llm)
    yield


app = FastAPI(title="Agentic RAG Demo", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 1. 查缓存
    cached = get_cached(req.question)
    if cached:
        return ChatResponse(answer=cached["answer"], source="cache")

    # 2. Corrective RAG：知识库优先
    kb_answer = answer_from_kb(req.question)
    if kb_answer:
        set_cached(req.question, kb_answer, "kb")
        return ChatResponse(answer=kb_answer, source="kb")

    # 3. 交给 ReAct Agent 调用工具（带熔断）
    result = run_agent(app.state.agent, req.question)
    raw = result["messages"][-1].content
    if raw == "抱歉，工具服务暂时不可用，请稍后再试。":
        return ChatResponse(answer=raw, source="degraded")
    final = _safe_extract_answer(raw)
    set_cached(req.question, final, "agent")
    return ChatResponse(answer=final, source="agent")

app.mount("/", StaticFiles(directory="static", html=True), name="static")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
