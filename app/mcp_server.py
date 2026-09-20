"""MCP Server：以标准 MCP 协议暴露工具。
运行方式：python -m app.mcp_server （agent 会通过 stdio 自动拉起）
"""
from datetime import datetime

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag-demo-tools")


@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的天气（演示用模拟数据）"""
    data = {"北京": "晴 26℃", "上海": "多云 28℃", "成都": "阴 22℃",
            "广州": "雷阵雨 30℃"}
    return f"{city}：{data.get(city, '暂无数据')}（模拟数据）"


@mcp.tool()
def calculator(expression: str) -> str:
    """计算数学表达式，例如 2*3+4"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception:
        return "表达式无效，请检查后重试"


@mcp.tool()
def get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    mcp.run()
