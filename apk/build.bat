@echo off
REM ============================================================================
REM  RYUO Stream - reproducible APK build (no Gradle, no network deps)
REM  Output: ryuo-stream.apk in this directory
REM  Usage:  build.bat            -> build only
REM          build.bat install    -> build, then adb install -r -g to the panel
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "JAVA_HOME=D:\ROG longwang4\tools\jdk-21.0.12.1+1"
set "SDK=D:\ROG longwang4\tools\android-sdk"
set "BT=%SDK%\build-tools\33.0.2"
set "PLATFORM=%SDK%\platforms\android-33"
set "SERIAL=TC26011200324725"
set "ADB_BIN=C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\adb.exe"

set "PATH=%JAVA_HOME%\bin;%PATH%"

if not exist "%JAVA_HOME%\bin\javac.exe" (
  echo [FAIL] JDK not found at %JAVA_HOME%
  exit /b 1
)
if not exist "%BT%\aapt2.exe" (
  echo [FAIL] build-tools 33.0.2 not found at %BT%
  echo        install with: sdkmanager --sdk_root="%SDK%" "build-tools;33.0.2" "platforms;android-33"
  exit /b 1
)
if not exist "%PLATFORM%\android.jar" (
  echo [FAIL] platforms;android-33 not found at %PLATFORM%
  exit /b 1
)

pushd "%ROOT%"

echo === [1/7] clean ===
if exist build rmdir /s /q build
if exist base.apk del /q base.apk
if exist aligned.apk del /q aligned.apk
if exist ryuo-stream.apk del /q ryuo-stream.apk
mkdir build\classes 2>nul
mkdir build\dex 2>nul

echo === [2/7] aapt2 link (manifest only, no res/) ===
"%BT%\aapt2.exe" link ^
  -o "%ROOT%\build\base.apk" ^
  -I "%PLATFORM%\android.jar" ^
  --manifest "%ROOT%\AndroidManifest.xml" ^
  --min-sdk-version 30 ^
  --target-sdk-version 33 ^
  --auto-add-overlay
if errorlevel 1 goto :fail

echo === [3/7] javac ===
"%JAVA_HOME%\bin\javac.exe" -source 8 -target 8 -Xlint:-options -encoding UTF-8 ^
  -classpath "%PLATFORM%\android.jar" ^
  -d "%ROOT%\build\classes" ^
  "%ROOT%\src\com\ryuo\stream\StreamActivity.java"
if errorlevel 1 goto :fail

echo === [4/7] d8 -> classes.dex ===
"%JAVA_HOME%\bin\jar.exe" cf "%ROOT%\build\classes.jar" -C "%ROOT%\build\classes" .
if errorlevel 1 goto :fail
REM NOTE: build-tools 33.0.2 d8.bat passes -Djava.ext.dirs, which JDK 21 refuses.
REM       Call the D8 entry point directly instead.
"%JAVA_HOME%\bin\java.exe" -Xmx1024m -cp "%BT%\lib\d8.jar" com.android.tools.r8.D8 ^
  --release --min-api 30 --lib "%PLATFORM%\android.jar" ^
  --output "%ROOT%\build\dex" "%ROOT%\build\classes.jar"
if errorlevel 1 goto :fail
if not exist "%ROOT%\build\dex\classes.dex" (
  echo [FAIL] d8 did not produce classes.dex
  goto :fail
)

echo === [5/7] add classes.dex to APK ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Add-Type -AssemblyName System.IO.Compression; Add-Type -AssemblyName System.IO.Compression.FileSystem; $apk=(Resolve-Path 'build\base.apk').Path; $dex=(Resolve-Path 'build\dex\classes.dex').Path; $z=[System.IO.Compression.ZipFile]::Open($apk,'Update'); if ($z.GetEntry('classes.dex')) { $z.GetEntry('classes.dex').Delete() }; [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($z,$dex,'classes.dex',[System.IO.Compression.CompressionLevel]::Optimal); $z.Dispose(); Write-Host ('classes.dex added: ' + (Get-Item $dex).Length + ' bytes')"
if errorlevel 1 goto :fail

echo === [6/7] zipalign ===
"%BT%\zipalign.exe" -f 4 "%ROOT%\build\base.apk" "%ROOT%\build\aligned.apk"
if errorlevel 1 goto :fail

echo === [7/7] keystore + apksigner ===
if not exist "%ROOT%\debug.keystore" (
  echo creating debug.keystore ...
  "%JAVA_HOME%\bin\keytool.exe" -genkeypair -v ^
    -keystore "%ROOT%\debug.keystore" -alias ryuo ^
    -storepass android -keypass android ^
    -keyalg RSA -keysize 2048 -validity 10000 ^
    -dname "CN=RYUO, OU=Dev, O=RYUO, L=NA, ST=NA, C=CN"
  if errorlevel 1 goto :fail
)

call "%BT%\apksigner.bat" sign ^
  --ks "%ROOT%\debug.keystore" ^
  --ks-key-alias ryuo ^
  --ks-pass pass:android ^
  --key-pass pass:android ^
  --out "%ROOT%\ryuo-stream.apk" ^
  "%ROOT%\build\aligned.apk"
if errorlevel 1 goto :fail

echo --- apksigner verify ---
call "%BT%\apksigner.bat" verify --verbose "%ROOT%\ryuo-stream.apk"
if errorlevel 1 goto :fail

echo.
echo === BUILD OK ===
for %%F in ("%ROOT%\ryuo-stream.apk") do @echo APK: %%~fF  size=%%~zF bytes
certutil -hashfile "%ROOT%\ryuo-stream.apk" SHA256 | findstr /r /v "^CertUtil"
echo.

if /i "%~1"=="install" (
  echo === adb install to %SERIAL% ===
  if not exist "%ADB_BIN%" (
    echo [FAIL] adb not found: %ADB_BIN%
    goto :fail
  )
  "%ADB_BIN%" -s %SERIAL% install -r -g "%ROOT%\ryuo-stream.apk"
  if errorlevel 1 goto :fail
  echo === INSTALL OK ===
)

popd
exit /b 0

:fail
echo.
echo *** BUILD FAILED ***
popd
exit /b 1
