@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

if "%DEEPSEEK_API_KEY%"=="" (
    echo [错误] 请先设置 DEEPSEEK_API_KEY 环境变量
    echo 示例: set DEEPSEEK_API_KEY=sk-xxxx
    pause
    exit /b 1
)

echo.
echo  选择要运行的示例：
echo  1. Todo纠正实验  （Butler发现Worker的错误并纠正）
echo  2. 地下城RPG开发 （Worker从零向Butler问询设计蓝图）
echo.
set /p choice=请输入编号 (1/2): 

if "%choice%"=="1" (
    C:\Users\Holoo\AppData\Local\Programs\Python\Python311\python.exe -m examples.todo_correction.run
) else if "%choice%"=="2" (
    C:\Users\Holoo\AppData\Local\Programs\Python\Python311\python.exe -m examples.dungeon_rpg.run
) else (
    echo 无效选择
    pause
)
