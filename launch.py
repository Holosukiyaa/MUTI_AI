import os
import sys
import subprocess
import shutil

PYTHON = shutil.which("python") or shutil.which("python3") or sys.executable
ROOT = os.path.dirname(os.path.abspath(__file__))

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
            pass

load_env()
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not os.environ.get("DEEPSEEK_API_KEY"):
    print()
    print("  未检测到 DEEPSEEK_API_KEY，请输入你的 API Key：")
    key = input("  sk-").strip()
    if not key:
        print("已取消")
        sys.exit(1)
    full_key = f"sk-{key}"
    os.environ["DEEPSEEK_API_KEY"] = full_key
    save = input("  是否保存到 .env 文件？(y/n): ").strip().lower()
    if save == "y":
        with open(os.path.join(ROOT, ".env"), "w", encoding="utf-8") as f:
            f.write(f"DEEPSEEK_API_KEY={full_key}\n")
            f.write(f"DEEPSEEK_BASE_URL={os.environ['DEEPSEEK_BASE_URL']}\n")
        print("  已保存，下次启动无需重新输入")
    print()

print()
print("  选择要运行的示例：")
print("  1. Todo 纠正实验  （Butler 发现 Worker 的错误并纠正）")
print("  2. 地下城 RPG 开发（Worker 从零向 Butler 问询设计蓝图）")
print("  3. Planner 大管家  （Planner 拆解需求 → 分配任务 → Butler+Worker 执行）")
print()
choice = input("  请输入编号 (1/2/3): ").strip()

modules = {"1": "examples.todo_correction.run", "2": "examples.dungeon_rpg.run", "3": "examples.planner_workflow.run"}
if choice not in modules:
    print("无效选择")
    input("按回车退出...")
    sys.exit(1)

subprocess.run([PYTHON, "-m", modules[choice]], cwd=ROOT)
