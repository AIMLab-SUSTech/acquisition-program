@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "OUTDIR=%~dp0out"

REM --- 1. cl.exe already in PATH ---
where cl.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 goto build_msvc

REM --- 2. vswhere.exe ---
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" set "VSWHERE="
if defined VSWHERE (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do (
        if exist "%%i\VC\Auxiliary\Build\vcvarsall.bat" (
            set "VCVARS=%%i\VC\Auxiliary\Build\vcvarsall.bat"
        ) else if exist "%%i\VC\vcvarsall.bat" (
            set "VCVARS=%%i\VC\vcvarsall.bat"
        )
    )
    if defined VCVARS goto found_vcvars
)

REM --- 3. Search common paths ---
set "VCVARS="
for %%d in (
    "C:\Program Files (x86)\Microsoft Visual Studio"
    "C:\Program Files\Microsoft Visual Studio"
) do (
    if not defined VCVARS (
        for /f "delims=" %%f in ('dir /s /b "%%~d\*vcvarsall.bat" 2^>nul') do set "VCVARS=%%f"
    )
)
if not defined VCVARS (
    for %%d in (D E) do (
        for /f "delims=" %%f in ('dir /s /b "%%d:\vs*\*vcvarsall.bat" 2^>nul') do set "VCVARS=%%f"
        if not defined VCVARS (
            for /f "delims=" %%f in ('dir /s /b "%%d:\Visual*\*vcvarsall.bat" 2^>nul') do set "VCVARS=%%f"
        )
    )
)

if defined VCVARS goto found_vcvars

echo [ERROR] Visual Studio not found.
exit /b 1

:found_vcvars
call "%VCVARS%" x64 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to activate MSVC environment
    exit /b 1
)

:build_msvc
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
echo [INFO] Copying DLLs to out\ ...
xcopy /y /q "%~dp0extern\lib\*.dll" "%OUTDIR%\" >nul
if exist "%~dp0extern\lib\ffmpeg.exe" copy /y "%~dp0extern\lib\ffmpeg.exe" "%OUTDIR%\" >nul

cl /nologo /TP /utf-8 /O2 /W3 /I extern\include main.c /link /LIBPATH:extern\lib SLStreamLink.lib /OUT:"%OUTDIR%\PhotonEyeSDK.exe"
if %ERRORLEVEL% EQU 0 (
    echo [ OK ] out\PhotonEyeSDK.exe
) else (
    echo [ERROR] Build failed (error %ERRORLEVEL%)
)
exit /b %ERRORLEVEL%
