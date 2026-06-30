import sys
import subprocess
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

steps = [
    ("Python 依赖", [sys.executable, "-m", "pip", "install",
                    "fastapi", "uvicorn[standard]", "openai", "anthropic", "rich"]),
    ("前端依赖", ["npm", "install"] if os.name != "nt" else ["npm.cmd", "install"]),
]

for label, cmd in steps:
    print(f"\n[安装] {label}...")
    cwd = os.path.join(ROOT, "web") if "npm" in cmd[0] else ROOT
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"  ✗ {label} 安装失败")
        sys.exit(1)
    print(f"  ✓ {label} 安装完成")

env_example = os.path.join(ROOT, ".env.example")
env = os.path.join(ROOT, ".env")
if not os.path.exists(env) and os.path.exists(env_example):
    import shutil
    shutil.copy(env_example, env)
    print(f"\n  ✓ 已创建 .env（请填写 DEEPSEEK_API_KEY）")

print("\n  全部完成，运行 python devtools/check_env.py 验证环境\n")
