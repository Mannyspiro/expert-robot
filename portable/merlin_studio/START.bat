@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0runtime\python\python.exe" goto bundled
where py >nul 2>nul
if errorlevel 1 goto installed_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto installed_python
py -3 "%~dp0server.py" --port 8771 --open %*
set "merlin_exit=%errorlevel%"
goto finished

:installed_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto missing_python
python "%~dp0server.py" --port 8771 --open %*
set "merlin_exit=%errorlevel%"
goto finished

:bundled
"%~dp0runtime\python\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto missing_python
"%~dp0runtime\python\python.exe" "%~dp0server.py" --port 8771 --open %*
set "merlin_exit=%errorlevel%"
goto finished

:missing_python
echo Merlin Studio requires Python 3.10 or newer. Install Python and run START.bat again.
set "merlin_exit=1"

:finished
if not "%merlin_exit%"=="0" pause
exit /b %merlin_exit%
