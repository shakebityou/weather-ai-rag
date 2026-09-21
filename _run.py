import os
import re
import subprocess
import sys
import threading
import time

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# cloudflared 可执行文件路径：优先在当前目录和脚本所在目录查找
CLOUDFLARED_PATHS = [
    os.path.join(os.getcwd(), "cloudflared.exe"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflared.exe"),
]


def find_cloudflared() -> str | None:
    for p in CLOUDFLARED_PATHS:
        if os.path.isabs(p) and os.path.exists(p):
            return p
        if not os.path.isabs(p):
            # 尝试用 where 查找
            try:
                result = subprocess.run(["where", p], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip().splitlines()[0]
            except Exception:
                pass
    return None


def start_tunnel(port: int) -> subprocess.Popen | None:
    """启动 cloudflared 内网穿透，返回子进程对象。公网 URL 会打印到控制台。"""
    cf = find_cloudflared()
    if cf is None:
        print("[tunnel] 未找到 cloudflared，跳过内网穿透。"
              "安装：winget install Cloudflare.cloudflared")
        return None

    print(f"[tunnel] 启动 cloudflared 内网穿透...")
    try:
        proc = subprocess.Popen(
            [cf, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        print(f"[tunnel] 启动失败：{e}")
        return None

    # 后台线程读取输出，提取公网 URL
    def read_output():
        url_pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
        printed = False
        for line in proc.stdout:
            if not printed:
                m = url_pattern.search(line)
                if m:
                    print(f"\n{'='*60}")
                    print(f"  🌐 公网访问地址：{m.group()}")
                    print(f"  📱 手机直接打开即可访问（无验证页）")
                    print(f"{'='*60}\n")
                    printed = True
            # 其余日志不打印，保持控制台干净

    threading.Thread(target=read_output, daemon=True).start()
    return proc


if __name__ == "__main__":
    PORT = 8000

    # 1. 先启动内网穿透
    tunnel_proc = start_tunnel(PORT)

    # 2. 给 cloudflared 几秒建连
    if tunnel_proc:
        time.sleep(5)

    # 3. 启动 Web 服务
    try:
        from app.main import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    finally:
        # 4. 退出时清理穿透进程
        if tunnel_proc:
            tunnel_proc.terminate()
            try:
                tunnel_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel_proc.kill()
            print("[tunnel] 内网穿透已停止")
