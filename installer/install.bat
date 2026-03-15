@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ── 관리자 권한 확인 및 자동 상승 (setx PATH에 필요) ──
net session >nul 2>&1
if errorlevel 1 (
    echo [안내] 관리자 권한이 필요합니다. 권한을 요청합니다...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================
echo   myAiCoder 설치 프로그램
echo ========================================
echo.

:: ── 1. config.json 읽기 ──
set "SCRIPT_DIR=%~dp0"
set "CONFIG=%SCRIPT_DIR%config.json"

if not exist "%CONFIG%" (
    echo [오류] config.json 파일을 찾을 수 없습니다.
    pause
    exit /b 1
)

for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).server_url"') do set "SERVER_URL=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).install_dir_name"') do set "INSTALL_DIR_NAME=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).model_name"') do set "MODEL_NAME=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).extension_file"') do set "VSIX_FILE=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).api_key"') do set "API_KEY=%%i"

set "INSTALL_DIR=%USERPROFILE%\%INSTALL_DIR_NAME%"

:: ── 2. 바이너리 복사 ──
echo [1/4] myAiCoder CLI 설치 중...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /Y "%SCRIPT_DIR%myaicoder.exe" "%INSTALL_DIR%\myaicoder.exe" >nul
echo       -^> %INSTALL_DIR%\myaicoder.exe

:: ── 3. PATH 추가 (현재 사용자) ──
echo [2/4] PATH 설정 중...
set "CURRENT_PATH="
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "CURRENT_PATH=%%b"
echo !CURRENT_PATH! | findstr /i /c:"%INSTALL_DIR%" >nul 2>&1
if errorlevel 1 (
    setx PATH "%INSTALL_DIR%;!CURRENT_PATH!" >nul 2>&1
    echo       -^> PATH에 추가됨
) else (
    echo       -^> 이미 PATH에 있음
)

:: ── 4. VS Code Extension 설치 ──
echo [3/4] VS Code Extension 설치 중...
where code >nul 2>&1
if errorlevel 1 (
    echo       [경고] VS Code가 설치되어 있지 않거나 PATH에 없습니다.
    echo       VS Code 설치 후 수동으로 .vsix를 설치해주세요.
) else (
    code --install-extension "%SCRIPT_DIR%%VSIX_FILE%" --force 2>nul
    echo       -^> Extension 설치 완료
)

:: ── 5. VS Code settings.json 주입 ──
echo [4/4] VS Code 설정 중...
set "SETTINGS_DIR=%APPDATA%\Code\User"
set "SETTINGS_FILE=%SETTINGS_DIR%\settings.json"

if not exist "%SETTINGS_DIR%" mkdir "%SETTINGS_DIR%"

if exist "%SETTINGS_FILE%" (
    powershell -Command ^
        "$s = Get-Content '%SETTINGS_FILE%' -Raw | ConvertFrom-Json; ^
         $s | Add-Member -NotePropertyName 'myaicoder.llmUrl' -NotePropertyValue '%SERVER_URL%' -Force; ^
         $s | Add-Member -NotePropertyName 'myaicoder.modelName' -NotePropertyValue '%MODEL_NAME%' -Force; ^
         $s | Add-Member -NotePropertyName 'myaicoder.apiKey' -NotePropertyValue '%API_KEY%' -Force; ^
         $s | Add-Member -NotePropertyName 'myaicoder.executablePath' -NotePropertyValue '%INSTALL_DIR%\myaicoder.exe' -Force; ^
         $s | ConvertTo-Json -Depth 10 | Set-Content '%SETTINGS_FILE%' -Encoding UTF8"
) else (
    powershell -Command ^
        "@{ 'myaicoder.llmUrl'='%SERVER_URL%'; 'myaicoder.modelName'='%MODEL_NAME%'; 'myaicoder.apiKey'='%API_KEY%'; 'myaicoder.executablePath'='%INSTALL_DIR%\myaicoder.exe' } | ConvertTo-Json | Set-Content '%SETTINGS_FILE%' -Encoding UTF8"
)
echo       -^> 서버 URL: %SERVER_URL%

echo.
echo ========================================
echo   설치가 완료되었습니다!
echo   VS Code를 켜고 왼쪽 바의 myAiCoder를
echo   클릭하면 바로 사용할 수 있습니다.
echo ========================================
echo.
pause
