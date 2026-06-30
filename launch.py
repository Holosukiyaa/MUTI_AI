import os
import sys
import subprocess
import webbrowser
import time
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
WEB_DIR = os.path.join(ROOT, "web")
npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def load_env():
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except PermissionError:
            print("  [警告] .env 文件被占用，跳过加载。将使用环境变量或手动输入。")


def free_port(port: int):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess | Sort -Unique | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}"],
            capture_output=True,
        )
        print(f"  [清理] 已释放端口 {port}")
        time.sleep(0.5)
    except Exception as e:
        print(f"  [警告] 释放端口 {port} 失败: {e}")


load_env()

free_port(8765)
free_port(5173)

print("[1/2] 启动后端 (port 8765)...")
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server.main:app",
     "--host", "0.0.0.0", "--port", "8765", "--log-level", "warning"],
    cwd=ROOT,
)

print("[2/2] 启动前端开发服务器 (port 5173)...")
frontend = subprocess.Popen([npm, "run", "dev"], cwd=WEB_DIR)

# 等待后端就绪再打开浏览器，避免 Vite 代理 ECONNREFUSED
import socket
for _ in range(20):
    time.sleep(0.5)
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            break
    except OSError:
        continue

webbrowser.open("http://localhost:5173")
print("已打开 http://localhost:5173  (Ctrl+C 停止)")

try:
    backend.wait()
except KeyboardInterrupt:
    pass
finally:
    backend.terminate()
    frontend.terminate()
