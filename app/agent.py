"""ReAct Agent：优先通过 MCP 协议加载工具，失败时降级为本地工具。"""
import asyncio

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


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
    try:
        client = MultiServerMCPClient({
            "demo": {
                "command": "python",
                "args": ["-m", "app.mcp_server"],
                "transport": "stdio",
            }
        })
        tools = asyncio.get_event_loop().run_until_complete(client.get_tools())
        print(f"[agent] 已通过 MCP 协议加载 {len(tools)} 个工具")
        return tools
    except Exception as e:
        print(f"[agent] MCP 加载失败，降级为本地工具：{e}")
        return _local_tools()


def build_agent(llm: BaseChatModel):
    return create_react_agent(llm, load_tools())
