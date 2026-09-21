"""Corrective RAG：检索 -> 相关性校验 -> 不相关则拒答，相关则带引用生成。

文档来源：MySQL（documents 表），数据库不可用时降级为内置示例文档。
"""
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import json

from app.config import settings
from app.circuit_breaker import circuit
from app.db import fetch_documents

_llm = ChatOpenAI(base_url=settings.llm_base_url,
                  api_key=settings.llm_api_key,
                  model=settings.llm_model)

_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2")

GRADE_PROMPT = ChatPromptTemplate.from_template(
    "判断下面的文档是否与问题相关，只回答 yes 或 no。\n\n问题：{question}\n文档：{doc}")

QA_PROMPT = ChatPromptTemplate.from_template(
    "你是一个weather天气ai助手，你叫小A。\n"
    "只能根据给定资料回答问题，不要编造资料外的内容。\n"
    "回答要简短直接，只给关键信息。\n"
    "如果资料中没有答案，如实告知用户暂时没有相关信息，并安抚用户情绪。\n"
    "始终返回 JSON 格式：{{\"answer\": \"你的回答\"}}\n\n"
    "资料：\n{context}\n\n问题：{question}")

FALLBACK_DOCS = [
    "员工年假规则：入职满一年可享5天带薪年假，此后每满一年增加1天，上限15天。",
    "报销流程：在OA系统提交报销单，附上发票照片，部门主管审批后3个工作日内到账。",
    "服务器部署规范：所有服务必须容器化部署，禁止在宿主机直接运行业务进程。",
    "请假制度：病假需提供医院证明，事假提前3天在OA申请。",
]


def load_documents() -> list[Document]:
    """优先从 MySQL 加载，失败降级为内置文档。"""
    contents = fetch_documents()
    if not contents:
        print("[rag] MySQL 无数据，使用内置示例文档")
        contents = FALLBACK_DOCS
    return [Document(page_content=c) for c in contents]


def build_vectorstore():
    return FAISS.from_documents(load_documents(), _embeddings)


vectorstore = build_vectorstore()
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})


@circuit("llm-grade",
         failure_threshold=settings.cb_failure_threshold,
         recovery_timeout=settings.cb_recovery_timeout,
         fallback=lambda question, doc: False)
def _is_relevant(question: str, doc: str) -> bool:
    resp = (_llm | (lambda x: x.content.strip().lower())).invoke(
        GRADE_PROMPT.format(question=question, doc=doc))
    return resp.startswith("yes")


def _parse_answer(content: str) -> str:
    """从 LLM 返回内容中提取 answer 字段，解析失败返回原文。"""
    try:
        # 尝试提取 JSON 部分
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            obj = json.loads(content[start:end + 1])
            if isinstance(obj, dict) and "answer" in obj:
                return str(obj["answer"])
    except (json.JSONDecodeError, ValueError):
        pass
    return content


@circuit("llm-qa",
         failure_threshold=settings.cb_failure_threshold,
         recovery_timeout=settings.cb_recovery_timeout,
         fallback=lambda question: None)
def answer_from_kb(question: str) -> str | None:
    """Corrective RAG：检索并校验相关性，返回 None 表示知识库无法回答。"""
    docs = retriever.invoke(question)
    relevant = [d for d in docs if _is_relevant(question, d.page_content)]
    if not relevant:
        return None
    context = "\n\n".join(d.page_content for d in relevant)
    raw = (_llm | (lambda x: x.content)).invoke(
        QA_PROMPT.format(context=context, question=question))
    return _parse_answer(raw)
