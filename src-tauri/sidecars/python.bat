@echo off
setlocal

rem Interim sidecar launcher for Windows.
rem Resolves paths relative to this batch file and invokes the system Python
rem with desktop/service.py. A full embedded Python runtime is not bundled yet.

set "SIDECAR_DIR=%~dp0"
set "PROJECT_ROOT=%SIDECAR_DIR%..\.."
set "PYTHONPATH=%SIDECAR_DIR%python\Lib\site-packages;%PYTHONPATH%"

python "%PROJECT_ROOT%\desktop\service.py"
