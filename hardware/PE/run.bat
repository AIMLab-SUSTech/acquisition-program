@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ============================================================
REM  PhotonEyeSDK_c - Auto-detect compiler + build + run
REM ============================================================

set "OUTDIR=%~dp0out"

REM --- 1. cl.exe already in PATH ---
where cl.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] cl.exe found in PATH
    goto build_msvc
)

REM --- 2. vswhere.exe (ships with VS 2017+ installer) ---
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" set "VSWHERE="
if defined VSWHERE (
    echo [INFO] Searching for Visual Studio via vswhere ...
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do (
        if exist "%%i\VC\Auxiliary\Build\vcvarsall.bat" (
            set "VCVARS=%%i\VC\Auxiliary\Build\vcvarsall.bat"
        ) else if exist "%%i\VC\vcvarsall.bat" (
            set "VCVARS=%%i\VC\vcvarsall.bat"
        )
    )
    if defined VCVARS goto found_vcvars
)

REM --- 3. Search common install locations ---
echo [INFO] Searching for Visual Studio installation ...
set "VCVARS="
for %%d in (
    "C:\Program Files (x86)\Microsoft Visual Studio"
    "C:\Program Files\Microsoft Visual Studio"
) do (
    if not defined VCVARS (
        for /f "delims=" %%f in ('dir /s /b "%%~d\*vcvarsall.bat" 2^>nul') do set "VCVARS=%%f"
    )
)

REM also check D: and E: (VS root-level dirs)
if not defined VCVARS (
    for %%d in (D E) do (
        for /f "delims=" %%f in ('dir /s /b "%%d:\vs*\*vcvarsall.bat" 2^>nul') do set "VCVARS=%%f"
        if not defined VCVARS (
            for /f "delims=" %%f in ('dir /s /b "%%d:\Visual*\*vcvarsall.bat" 2^>nul') do set "VCVARS=%%f"
        )
    )
)

if defined VCVARS goto found_vcvars

REM --- 4. g++ / gcc / MinGW fallback ---
where g++.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 goto build_gcc
where gcc.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 goto build_gcc_c

echo.
echo  ============================================================
echo   [ERROR] No C/C++ compiler found.
echo.
echo   Please install one of the following:
echo     - Visual Studio 2017 / 2019 / 2022
echo       (select "Desktop development with C++" workload)
echo     - MinGW-w64 (gcc)
echo.
echo   If Visual Studio is already installed, try running
echo   this script from "Developer Command Prompt for VS".
echo  ============================================================
goto end

REM --- Activate MSVC environment ---
:found_vcvars
echo [INFO] Found: !VCVARS!
call "!VCVARS!" x64 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to activate MSVC environment
    goto end
)

REM --- Build: MSVC (as C++ because SLApi.h uses default params) ---
:build_msvc
echo [INFO] Building with MSVC (as C++) ...

if not exist "%OUTDIR%" mkdir "%OUTDIR%"
echo [INFO] Copying DLLs to out\ ...
xcopy /y /q "%~dp0extern\lib\*.dll" "%OUTDIR%\" >nul
echo [INFO] Copying ffmpeg.exe to out\ ...
if exist "%~dp0extern\lib\ffmpeg.exe" copy /y "%~dp0extern\lib\ffmpeg.exe" "%OUTDIR%\" >nul

cl /nologo /TP /utf-8 /O2 /W3 /I extern\include main.c /link /LIBPATH:extern\lib SLStreamLink.lib /OUT:"%OUTDIR%\PhotonEyeSDK.exe"
if %ERRORLEVEL% EQU 0 (
    echo [ OK ] out\PhotonEyeSDK.exe
    goto run
)
echo [WARN] MSVC build failed (error %ERRORLEVEL%)
where g++.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Trying g++ fallback ...
    goto build_gcc
)
where gcc.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 goto build_gcc_c
goto end

REM --- Build: MinGW g++ ---
:build_gcc
echo [INFO] Building with MinGW g++ ...

if not exist "%OUTDIR%" mkdir "%OUTDIR%"
xcopy /y /q "%~dp0extern\lib\*.dll" "%OUTDIR%\" >nul
if exist "%~dp0extern\lib\ffmpeg.exe" copy /y "%~dp0extern\lib\ffmpeg.exe" "%OUTDIR%\" >nul

if not exist "%~dp0extern\lib\libSLStreamLink.a" (
    echo [INFO] Generating MinGW import library from DLL ...
    pushd "%~dp0extern\lib"
    gendef SLStreamLink.dll >nul 2>&1
    if exist SLStreamLink.def (
        dlltool -d SLStreamLink.def -l libSLStreamLink.a >nul 2>&1
        del SLStreamLink.def >nul 2>&1
    )
    popd
)

g++ -O2 -Wall -I extern/include -o "%OUTDIR%\PhotonEyeSDK.exe" main.c -L"%~dp0extern\lib" -lSLStreamLink
if %ERRORLEVEL% EQU 0 (
    echo [ OK ] out\PhotonEyeSDK.exe
    goto run
)

echo [ERROR] g++ build failed (error %ERRORLEVEL%)
echo [INFO] MSVC is recommended for this project.
goto end

REM --- Build: MinGW gcc (may fail on C++ default params in SLApi.h) ---
:build_gcc_c
echo [INFO] Building with MinGW gcc ...

if not exist "%OUTDIR%" mkdir "%OUTDIR%"
xcopy /y /q "%~dp0extern\lib\*.dll" "%OUTDIR%\" >nul
if exist "%~dp0extern\lib\ffmpeg.exe" copy /y "%~dp0extern\lib\ffmpeg.exe" "%OUTDIR%\" >nul

if not exist "%~dp0extern\lib\libSLStreamLink.a" (
    echo [INFO] Generating MinGW import library from DLL ...
    pushd "%~dp0extern\lib"
    gendef SLStreamLink.dll >nul 2>&1
    if exist SLStreamLink.def (
        dlltool -d SLStreamLink.def -l libSLStreamLink.a >nul 2>&1
        del SLStreamLink.def >nul 2>&1
    )
    popd
)

gcc -O2 -Wall -I extern/include -o "%OUTDIR%\PhotonEyeSDK.exe" main.c -L"%~dp0extern\lib" -lSLStreamLink
if %ERRORLEVEL% EQU 0 (
    echo [ OK ] out\PhotonEyeSDK.exe
    goto run
)

echo [ERROR] gcc build failed (error %ERRORLEVEL%)
echo [INFO] Tip: SLApi.h uses C++ default params. Edit extern\include\SLApi.h
echo [INFO] to remove default values (ValType = PARAM_VALUE_INT) for gcc.
goto end

REM --- Launch ---
:run
echo.
echo ============================================================
echo   Launching PhotonEyeSDK.exe ...
echo ============================================================
cd /d "%OUTDIR%"
PhotonEyeSDK.exe

:end
pause
