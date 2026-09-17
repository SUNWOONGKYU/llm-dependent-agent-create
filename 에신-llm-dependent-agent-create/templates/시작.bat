@echo off
pushd "%~dp0"
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where python > nul 2>&1
if errorlevel 1 goto nopython
if exist "app\.deps_ok" goto run
echo Installing dependencies - first run only ...
python -m pip install -q -r app\requirements.txt
if errorlevel 1 goto depwarn
echo ok > "app\.deps_ok"
goto run
:depwarn
echo [WARN] Some packages failed. The screen will show what is missing.
goto run
:run
python app\ui.py
if errorlevel 1 goto failed
goto end
:nopython
echo [ERROR] Python not found. Install from https://www.python.org/downloads/ and check Add Python to PATH.
ping -n 6 127.0.0.1 > nul
goto end
:failed
echo [INFO] Screen server did not start. See the message above.
ping -n 8 127.0.0.1 > nul
:end
popd
