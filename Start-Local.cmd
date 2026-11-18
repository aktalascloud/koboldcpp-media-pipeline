@echo off
setlocal
set "KOBOLD=%~dp0..\KoboldCpp\KoboldCpp.exe"
if not exist "%KOBOLD%" set "KOBOLD=%~dp0KoboldCpp.exe"
if not exist "%KOBOLD%" (
    echo Install the runtime using docs\BUILD.md, or place this project next to KoboldCpp.
    exit /b 2
)
start "" /wait "%KOBOLD%" --background
if errorlevel 1 exit /b %ERRORLEVEL%
start "" "http://127.0.0.1:5003/docs"
