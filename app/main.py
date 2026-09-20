"""FastAPI 入口：统一问答入口 = 知识库优先，答不了交给 ReAct Agent。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agent import build_agent
from app.config import settings
from app.rag import answer_from_kb
from app.utils import get_cached, set_cached


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    source: str  # kb = 知识库 / agent = 工具调用 / cache = 缓存


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    # 3. 交给 ReAct Agent 调用工具
    result = app.state.agent.invoke(
        {"messages": [("user", req.question)]})
    final = result["messages"][-1].content
    set_cached(req.question, final, "agent")
    return ChatResponse(answer=final, source="agent")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
