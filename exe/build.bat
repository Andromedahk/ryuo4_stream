@echo off
setlocal
rem Build RyuoStreamTest.exe with the in-box .NET Framework compiler (no SDK required).
rem Optional: place ryuo-stream.apk next to this script and it is embedded as a resource.
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
  echo ERROR: csc.exe not found
  exit /b 1
)
set OUT=RyuoStreamTest.exe
set SRC=RyuoStreamTest.cs
if exist ryuo-stream.apk (
  "%CSC%" /nologo /target:exe /platform:x64 /optimize+ /out:%OUT% /resource:ryuo-stream.apk,RyuoStream.apk /r:System.dll /r:System.Drawing.dll /r:System.Core.dll %SRC% Hid.cs
) else (
  echo NOTE: ryuo-stream.apk not present - building without embedded APK.
  "%CSC%" /nologo /target:exe /platform:x64 /optimize+ /out:%OUT% /r:System.dll /r:System.Drawing.dll /r:System.Core.dll %SRC% Hid.cs
)
if errorlevel 1 exit /b 1
echo.
echo Built %OUT%
dir /b %OUT%


