"""ReAct Agent：优先通过 MCP 协议加载工具，失败时降级为本地工具。"""
import asyncio
import sys
import threading

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


def _run_sync(coro):
    """在独立线程里跑协程，兼容已在事件循环中的调用场景（如 lifespan）。"""
    result = {}

    def worker():
        result["value"] = asyncio.run(coro)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    return result.get("value")


def _local_tools():
    """MCP 不可用时的降级工具（与 MCP server 同名同功能）。"""

    @tool
    def get_weather(city: str) -> str:
        """查询指定城市的天气（演示用模拟数据）"""
        return f"{city}：晴 26℃（本地降级模拟数据）"

    @tool
    def calculator(expression: str) -> str:
        """计算数学表达式，例如 2*3+4"""
        try:
            return str(eval(expression, {"__builtins__": {}}, {}))
        except Exception:
            return "表达式无效"

    @tool
    def get_current_time() -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return [get_weather, calculator, get_current_time]


def load_tools() -> list:
    """加载工具。使用本地同步工具（MCP 工具为 async-only，不支持同步调用）。"""
    print("[agent] 使用本地同步工具（天气/计算/时间）")
    return _local_tools()


SYSTEM_PROMPT = """你是一个weather天气ai助手，你叫小A。

【核心规则】
1. 身份：你是天气AI助手小A，可以查询天气、做数学计算、查询时间等。
2. 不编造：如果工具查询结果为空或知识库没有相关信息，必须如实告知用户"暂时没有相关信息"，并安抚用户情绪（例如"别担心，您可以稍后再试或联系官方客服获取帮助"）。
3. 简洁：回答要简短直接，只给关键信息，不输出无关内容。
4. 数学计算：遇到任何算数/计算问题，**必须先调用 calculator 工具**再回答，绝对不能自己心算或直接给出计算结果。如果 calculator 工具不可用，回复"抱歉，计算功能暂时不可用，请联系官方客服"。
5. 输出格式：始终返回 JSON 格式，结构为 {"answer": "你的回答内容"}，不要输出任何 JSON 以外的文字。
6. 异常回避：如果无法正常回答（工具失败、信息缺失），在 answer 中返回安抚话术并引导用户联系官方客服，不要暴露错误细节。"""


def build_agent(llm: BaseChatModel):
    return create_react_agent(llm, load_tools(), prompt=SYSTEM_PROMPT)