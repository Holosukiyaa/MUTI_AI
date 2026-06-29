import sys
import shutil
import subprocess

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

errors = []

def check(label, passed, fix=""):
    mark = OK if passed else FAIL
    print(f"  {mark}  {label}")
    if not passed:
        errors.append((label, fix))


print("\n── Python ──────────────────────────────")
major, minor = sys.version_info[:2]
check(f"Python 版本 {major}.{minor} (需要 3.12+)", major == 3 and minor >= 12,
      "请安装 Python 3.12 或更高版本：https://python.org/downloads/")

for pkg in ["fastapi", "uvicorn", "openai", "anthropic", "rich"]:
    try:
        __import__(pkg)
        check(f"pip: {pkg}", True)
    except ImportError:
        check(f"pip: {pkg}", False, f"pip install {pkg}")

try:
    import uvicorn.config
    import websockets
    check("uvicorn[standard] / websockets", True)
except ImportError:
    check("uvicorn[standard] / websockets", False, "pip install \"uvicorn[standard]\"")

print("\n── Node.js / npm ───────────────────────")
try:
    out = subprocess.run("node --version", shell=True, capture_output=True, text=True).stdout.strip()
    ver = int(out.lstrip("v").split(".")[0]) if out else 0
    check(f"Node.js {out} (需要 18+)", ver >= 18, "请安装 Node.js 18+：https://nodejs.org/")
except Exception:
    check("Node.js", False, "请安装 Node.js 18+：https://nodejs.org/")

try:
    out = subprocess.run("npm --version", shell=True, capture_output=True, text=True).stdout.strip()
    check(f"npm {out}", bool(out), "npm 未找到，请重新安装 Node.js")
except Exception:
    check("npm", False, "npm 未找到，请重新安装 Node.js")

print("\n── 前端依赖 ─────────────────────────────")
import os
node_modules = os.path.join(os.path.dirname(__file__), "web", "node_modules")
check("web/node_modules 已安装", os.path.isdir(node_modules),
      "cd web && npm install")

print("\n── 配置文件 ─────────────────────────────")
root = os.path.dirname(__file__)
env_path = os.path.join(root, ".env")
has_env = os.path.isfile(env_path)
check(".env 文件存在", has_env, "cp .env.example .env  并填写 DEEPSEEK_API_KEY")

if has_env:
    with open(env_path, encoding="utf-8") as f:
        content = f.read()
    has_key = "DEEPSEEK_API_KEY=" in content and "sk-" in content
    check("DEEPSEEK_API_KEY 已配置", has_key, "编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx")

print("\n────────────────────────────────────────")
if errors:
    print(f"\n  {FAIL}  发现 {len(errors)} 个问题，请修复后重试：\n")
    for label, fix in errors:
        print(f"    • {label}")
        if fix:
            print(f"      → {fix}")
else:
    print(f"\n  {OK}  环境检测通过，运行 run.bat 启动项目\n")
