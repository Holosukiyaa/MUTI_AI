import os
import sys
import subprocess

PYTHON = r"C:\Users\Holoo\AppData\Local\Programs\Python\Python311\python.exe"
ROOT = os.path.dirname(os.path.abspath(__file__))

os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not os.environ.get("DEEPSEEK_API_KEY"):
    print("[错误] 请先设置环境变量 DEEPSEEK_API_KEY")
    print("示例: set DEEPSEEK_API_KEY=sk-xxxx")
    input("按回车退出...")
    sys.exit(1)

print()
print("  选择要运行的示例：")
print("  1. Todo 纠正实验  （Butler 发现 Worker 的错误并纠正）")
print("  2. 地下城 RPG 开发（Worker 从零向 Butler 问询设计蓝图）")
print()
choice = input("  请输入编号 (1/2): ").strip()

modules = {"1": "examples.todo_correction.run", "2": "examples.dungeon_rpg.run"}
if choice not in modules:
    print("无效选择")
    input("按回车退出...")
    sys.exit(1)

subprocess.run([PYTHON, "-m", modules[choice]], cwd=ROOT)
