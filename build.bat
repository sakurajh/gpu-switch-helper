@echo off
rem ============================================================
rem  GPU 切换助手 一键重新打包脚本
rem  双击运行即可；所有路径都相对本文件所在目录，拷到任何机器都能用。
rem  产物：dist\GPU切换助手.exe  ->  自动复制为当前目录 GPU切换助手.exe
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
setlocal

echo [1/4] 检查 Python 与 PyInstaller...
python --version >nul 2>&1
if errorlevel 1 (
    echo     未找到 python，请先安装 Python 3.8+ 并加入 PATH。
    pause
    exit /b 1
)
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo     未安装 PyInstaller，正在安装...
    python -m pip install pyinstaller || (echo     PyInstaller 安装失败 & pause & exit /b 1)
)

echo [2/4] 运行自测...
python gpu_switch_app.py --selftest
if errorlevel 1 (
    echo     自测未通过，已停止打包（详见 gpu_switch_selftest.txt）。
    pause
    exit /b 1
)

echo [3/4] 打包 exe（相对路径 spec）...
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build "GPU切换助手.spec"
if errorlevel 1 (
    echo     打包失败。
    pause
    exit /b 1
)

echo [4/4] 复制成品...
python version_copy.py
if errorlevel 1 (
    echo     成品复制失败。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  完成：GPU切换助手.exe，单文件，可直接发给别人。
echo  打包中间产物在 build\ 与 dist\，可放心删除。
echo ============================================================
pause
endlocal
