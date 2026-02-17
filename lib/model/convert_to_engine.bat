@echo off
setlocal

:: Make sure you are in the same directory as best.pt
:: And have ultralytics installed

echo [*] Exporting best.pt to ENGINE...
yolo export model='best.pt' format='engine'

if %ERRORLEVEL% neq 0 (
    echo [!] Export failed. Keeping best.pt
    exit /b %ERRORLEVEL%
)

:: Confirm best.engine was created
if exist "best.engine" (
    echo [+] Export successful. Deleting best.pt...
    del /f /q best.pt
    echo Done.
) else (
    echo [!] best.engine not found. Export may have failed.
)

endlocal
pause