@echo off
:: 设置UTF-8编码，防止中文路径或提示乱码
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:menu
cls
echo =======================================================
echo               Python 脚本快捷运行工具
echo =======================================================
echo.

set count=0

:: 查找当前目录及所有子目录下的 .py 文件
for /f "delims=" %%i in ('dir /s /b *.py 2^>nul') do (
    set /a count+=1
    :: 将文件完整路径存入伪数组变量
    set "file[!count!]=%%i"
    :: 单行展示：[序号] 完整路径
    echo [!count!] %%i
)

echo.

:: 如果没有找到任何文件
if %count%==0 (
    echo 未在当前目录或子文件夹中找到任何 .py 文件！
    echo.
    pause
    exit /b
)

echo =======================================================
set /p choice="请输入要运行的脚本序号 (输入 0 退出): "

:: 处理退出指令
if "%choice%"=="0" exit /b

:: 检查输入的序号是否有效
if not defined file[%choice%] (
    echo.
    echo 输入的序号无效，请重新输入！
    pause
    goto menu
)

:: 运行指定的脚本
cls
echo 正在运行: !file[%choice%]!
echo =======================================================
echo.

:: 调用 python 运行脚本，路径加引号防止含有空格
python "!file[%choice%]!"

echo.
echo =======================================================
echo 脚本执行完毕。
pause
goto menu