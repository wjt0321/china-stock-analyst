@echo off
setlocal EnableDelayedExpansion

rem Interim sidecar launcher for Windows.
rem Resolves paths relative to this batch file and invokes the system Python
rem with desktop/service.py. A full embedded Python runtime is not bundled yet.

set "SIDECAR_BAT_DIR=%~dp0"
set "PROJECT_ROOT=%SIDECAR_BAT_DIR%"

rem Walk up until we find desktop/service.py. This handles both
rem src-tauri/sidecars/ (direct dev run) and src-tauri/target/debug/sidecars/
rem (Tauri dev resource copy).
:find_root
if exist "%PROJECT_ROOT%desktop\service.py" goto :found_root
set "PARENT=%PROJECT_ROOT%..\"
for %%F in ("%PARENT%") do set "PARENT=%%~fF"
if /I "%PARENT%"=="%PROJECT_ROOT%" (
    echo ERROR: Could not locate desktop/service.py >&2
    exit /b 1
)
set "PROJECT_ROOT=%PARENT%"
goto :find_root

:found_root
set "PYTHONPATH=%PROJECT_ROOT%;%SIDECAR_BAT_DIR%python\Lib\site-packages;%PYTHONPATH%"

python "%PROJECT_ROOT%\desktop\service.py" 2>>"%PROJECT_ROOT%\sidecar_stderr.log"
