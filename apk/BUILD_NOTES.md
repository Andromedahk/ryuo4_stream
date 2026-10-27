# RYUO Stream APK — build & validation notes

Status date: 2026-10-27 (Asia/Shanghai)
Author: `apk-builder` teammate (delegated task)
Target device: ASUS ROG RYUO IV cooler screen, serial `TC26011200324725`, Rockchip RK3562,
Android 13 / API 33, 2240x1080 physical, density 160, model `cm16`,
build fingerprint `rockchip/cm16/cm16:13/TQ3C.230805.001.B2/eng.server.20251229.092713:user/release-keys`.
HomeUI is the HOME app (`com.baiyi.homeui.hshomeui/.MainActivity`).

> **Current state (handoff):** the APK is built and signed, and the build is reproducible from
> `build.bat` (host-side verified). On-device install is **blocked by a device-side platform bug**
> (see §8), and Test 1 / Test 2 were **not executed**. Per Lead instruction I stopped all
> adb/USB work on 2026-10-27 ~12:57 and the Lead took over install debugging. Validation command
> recipes are in §9 so whoever has the device can run them verbatim.

---

## 1. Deliverables

| Item | Path |
|---|---|
| APK | `D:\ROG longwang4\apk\ryuo-stream.apk` |
| Build script | `D:\ROG longwang4\apk\build.bat` |
| Manifest | `D:\ROG longwang4\apk\AndroidManifest.xml` |
| Source | `D:\ROG longwang4\apk\src\com\ryuo\stream\StreamActivity.java` |
| Debug signing key | `D:\ROG longwang4\apk\debug.keystore` (alias `ryuo`, storepass/keypass `android`) |
| These notes | `D:\ROG longwang4\apk\BUILD_NOTES.md` |
| Build intermediates | `D:\ROG longwang4\apk\build\` (safe to delete; build.bat recreates) |

APK facts (current artifact):

| Fact | Value |
|---|---|
| File size | **16,779 bytes** |
| SHA-256 | `6651e65883f7203734a7bf3f8aa4dc64d0287422287feee7793421244d11340a` |
| Last built | 2026-10-27 12:48:35 +08:00 |
| Package / version | `com.ryuo.stream`, versionCode 1, versionName 1.0 |
| minSdk / targetSdk / compileSdk | 30 / 33 / 33 |
| Launcher activity | `com.ryuo.stream.StreamActivity` (exported, landscape) |
| APK entries | `AndroidManifest.xml`, `resources.arsc`, `classes.dex`, `META-INF/RYUO.SF`, `META-INF/RYUO.RSA`, `META-INF/MANIFEST.MF` |
| `classes.dex` size | 11,660 bytes |
| Signature | APK Signature Scheme **v3 only** (v1/v2 auto-disabled because minSdk 30; Android 13 accepts v3) |
| Signer cert | `CN=RYUO, OU=Dev, O=RYUO, L=NA, ST=NA, C=CN`, SHA-256 `27b20cd0fce8ec5dbc4b477db99c569cc720ee1bc0f15c326ccda8c8d738f70c` |
| `zipalign -c -v 4` | passes (`resources.arsc` stored/aligned, other entries compressed) |

Re-running `build.bat` produces a functionally identical APK, but the SHA-256 changes (v3
signature uses randomized RSA-PSS and zip entry timestamps differ), so the hash above is for the
artifact currently in the folder, not a reproducible constant.

---

## 2. Toolchain provisioning (already done on this PC)

### JDK
- `D:\ROG longwang4\tools\jdk-21.0.12.1+1` (Temurin 21.0.12.1+1)
- Used via explicit paths: `bin\java.exe`, `bin\javac.exe`, `bin\keytool.exe`, `bin\jar.exe`.
- `build.bat` sets `JAVA_HOME` to it and prepends `%JAVA_HOME%\bin` to `PATH`.

### Android SDK
- SDK root: `D:\ROG longwang4\tools\android-sdk`
- Command-line tools zip (downloaded 12:41–12:45, 153,583,359 bytes, exact Content-Length match):
  `D:\ROG longwang4\tools\android-sdk\cmdline-tools.zip`
- Extracted and installed to the standard layout: `D:\ROG longwang4\tools\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat`
  (sdkmanager 12.0).
- Installed packages (via sdkmanager, licenses accepted):

```powershell
$sdk = "D:\ROG longwang4\tools\android-sdk"
$env:JAVA_HOME = "D:\ROG longwang4\tools\jdk-21.0.12.1+1"

# one-time licenses
(1..200 | ForEach-Object { "y" }) |
  & "$sdk\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root="$sdk" --licenses

# packages (downloads ~120 MB total)
& "$sdk\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root="$sdk" `
    "platforms;android-33" "build-tools;33.0.2"
```

Resulting paths used by the build:
`platforms\android-33\android.jar`, `build-tools\33.0.2\{aapt2.exe, zipalign.exe, apksigner.bat, lib\d8.jar}`.

---

## 3. Build — exact commands

`build.bat` performs exactly the sequence below from `D:\ROG longwang4\apk`:

```bat
set "JAVA_HOME=D:\ROG longwang4\tools\jdk-21.0.12.1+1"
set "SDK=D:\ROG longwang4\tools\android-sdk"
set "BT=%SDK%\build-tools\33.0.2"
set "PLATFORM=%SDK%\platforms\android-33"
set "PATH=%JAVA_HOME%\bin;%PATH%"

REM [1] clean: remove build\, base.apk, aligned.apk, ryuo-stream.apk; mkdir build\classes, build\dex

REM [2] resources + manifest -> base APK (no res/ needed; binary manifest only)
"%BT%\aapt2.exe" link -o build\base.apk -I "%PLATFORM%\android.jar" ^
  --manifest AndroidManifest.xml --min-sdk-version 30 --target-sdk-version 33 --auto-add-overlay

REM [3] compile Java against android.jar
"%JAVA_HOME%\bin\javac.exe" -source 8 -target 8 -Xlint:-options -encoding UTF-8 ^
  -classpath "%PLATFORM%\android.jar" -d build\classes ^
  src\com\ryuo\stream\StreamActivity.java

REM [4] classes.jar -> classes.dex with d8 (direct Java entry point, see §4)
"%JAVA_HOME%\bin\jar.exe" cf build\classes.jar -C build\classes .
"%JAVA_HOME%\bin\java.exe" -Xmx1024m -cp "%BT%\lib\d8.jar" com.android.tools.r8.D8 ^
  --release --min-api 30 --lib "%PLATFORM%\android.jar" ^
  --output build\dex build\classes.jar

REM [5] insert classes.dex at APK root (PowerShell System.IO.Compression ZipArchive update mode)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.IO.Compression; Add-Type -AssemblyName System.IO.Compression.FileSystem; $apk=(Resolve-Path 'build\base.apk').Path; $dex=(Resolve-Path 'build\dex\classes.dex').Path; $z=[System.IO.Compression.ZipFile]::Open($apk,'Update'); if ($z.GetEntry('classes.dex')) { $z.GetEntry('classes.dex').Delete() }; [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($z,$dex,'classes.dex',[System.IO.Compression.CompressionLevel]::Optimal); $z.Dispose()"

REM [6] 4-byte align
"%BT%\zipalign.exe" -f 4 build\base.apk build\aligned.apk

REM [7] keystore (created if missing) + sign + verify
"%JAVA_HOME%\bin\keytool.exe" -genkeypair -v -keystore debug.keystore -alias ryuo ^
  -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 ^
  -dname "CN=RYUO, OU=Dev, O=RYUO, L=NA, ST=NA, C=CN"

call "%BT%\apksigner.bat" sign --ks debug.keystore --ks-key-alias ryuo ^
  --ks-pass pass:android --key-pass pass:android --out ryuo-stream.apk build\aligned.apk

call "%BT%\apksigner.bat" verify --verbose ryuo-stream.apk
```

Run:

```
D:\ROG longwang4\apk\build.bat
```

Exit code 0 and `=== BUILD OK ===` mean success; the final APK path, size, SHA-256 and an
`apksigner verify` report are printed. The optional install step (`build.bat install`) currently
hits the device issue in §8 and should be treated as informational.

Observed clean-build output (2026-10-27 12:48):

```
=== [1/7] clean ===
=== [2/7] aapt2 link (manifest only, no res/) ===
=== [3/7] javac ===
=== [4/7] d8 -> classes.dex ===
=== [5/7] add classes.dex to APK ===
classes.dex added: 11660 bytes
=== [6/7] zipalign ===
=== [7/7] keystore + apksigner ===
--- apksigner verify ---
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
=== BUILD OK ===
APK: D:\ROG longwang4\apk\ryuo-stream.apk  size=16779 bytes
SHA256: 6651e65883f7203734a7bf3f8aa4dc64d0287422287feee7793421244d11340a
```

`javac` also prints a non-fatal note that the source uses deprecated API (from android.jar);
`-Xlint:-options` only silences the source/target-8 warning.

---

## 4. Build-time pitfalls found (important for anyone editing this build)

### 4.1 `d8.bat` / `apksigner.bat` from build-tools 33.0.2 are JDK-21-hostile
`build-tools\33.0.2\d8.bat` launches Java with `-Djava.ext.dirs=...\lib`, which JDK 21 rejects:

```
Error: Could not create the Java Virtual Machine.
-Djava.ext.dirs=...\build-tools\33.0.2\lib is not supported.  Use -classpath instead.
```

Fix already in `build.bat`: bypass the `.bat` wrapper entirely and call the D8 entry point:

```bat
"%JAVA_HOME%\bin\java.exe" -Xmx1024m -cp "%BT%\lib\d8.jar" com.android.tools.r8.D8 ...
```

`apksigner.bat` uses `-jar`, so it works with JDK 21 unchanged.

### 4.2 D8 (R8 3.3.20) crashes on javac-21 non-static/anonymous inner classes
`d8` dies with an internal NPE on classes that a JDK 21 `javac` compiles as *anonymous* or
*non-static inner* classes (outer-instance synthetic constructor parameter + `MethodParameters`
attribute). Minimal reproduction: any `new Runnable() {...}` inside a method, or a
`private final class Foo` — both fail; a `static` nested class succeeds.

```
java.lang.NullPointerException: Cannot invoke "String.length()" because "<parameter1>" is null
	at com.android.tools.r8.graph.d1.<init>(...)
	...
Compilation failed with an internal error.
```

Workaround used in `StreamActivity.java`: **every listener/task type is a `static` nested class
holding an explicit `StreamActivity host` field** (see file header comment). Do not reintroduce
anonymous or non-static inner classes unless a newer `d8` is used.

### 4.3 No `res/` directory
The APK intentionally has zero resources; the theme is the platform theme
`@android:style/Theme.NoTitleBar.Fullscreen`, the UI is built programmatically, and the launcher
icon is omitted. `aapt2 link` therefore only needs `--manifest` and `-I android.jar` and still
emits a valid `resources.arsc`.

---

## 5. Manifest / app behavior (as built)

- `<uses-sdk minSdkVersion="30" targetSdkVersion="33"/>`
- `INTERNET` (+ harmless `ACCESS_NETWORK_STATE`) permissions; **no root, no storage permission**.
- `android:usesCleartextTraffic="true"` — required for the default plain-HTTP URL on targetSdk 33.
- One exported activity `com.ryuo.stream.StreamActivity`:
  - `screenOrientation="landscape"`, `launchMode="singleTask"`,
    `configChanges` covering orientation/screen size so rotation cannot recreate it.
  - Intent filters: `MAIN`/`LAUNCHER`; and `VIEW` with schemes `http`, `https`, `rtsp` plus
    `mimeType="video/*"`.
- Fullscreen immersive: `Window.setDecorFitsSystemWindows(false)` +
  `WindowInsetsController.hide(statusBars|navigationBars)` with swipe-to-reveal behavior,
  reapplied in `onWindowFocusChanged`, `FLAG_FULLSCREEN` + `FLAG_KEEP_SCREEN_ON`.
- UI: `FrameLayout` (black) with a `VideoView` at `match_parent`/`match_parent`, plus a small
  top-left debug `TextView` HUD (11 sp, white on `#8C000000`, two lines: state + shortened URL).
- Extras on the launched activity:
  - `url` (String): `http://`, `https://`, `rtsp://` or `file://` URI;
    default `http://127.0.0.1:18080/live.ts`. `Intent.getData()` is also honored.
  - `restart` (boolean, default `true`): on completion / MediaPlayer error / 15 s prepare
    timeout, wait **800 ms** and reopen the same URL.
  - `hud` (boolean, default `true`): show/hide the debug HUD.
- Logging: everything goes to logcat tag **`RYUO_STREAM`** (`Log.i`/`Log.e`):
  `onCreate sdk=… url=… extent=…`, `onStart`, `open attempt=N url=…`,
  `prepared <w>x<h> durationMs=… restartCount=…`, `info what=… extra=…`,
  `error what=… extra=… url=…`, `completion`, `auto-restart #N`, lifecycle events.
- State machine: `OPENING` → `prepared` → `PLAYING`/`RENDERING`/`BUFFERING`; failure paths:
  `ERROR what/extra`, `TIMEOUT 15000ms`, `COMPLETED`, followed by `… | restart in 800ms`.
  `MediaPlayer.OnErrorListener` returns `true` (no system error dialog) and retries internally.
- Playback stops on `onStop` (`stopPlayback`) so the HomeUI stays/returns behind the app; screen
  wake is held while playing.

---

## 6. Device/environment facts used

```
adb version 1.0.41 (34.0.3-10161052), from
  C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\adb.exe
  (PATH must prepend "C:\Program Files\ASUS Info Hub - ROG RYUO IV" and its \bin for AdbWinApi.dll)
Serial: TC26011200324725  (adbd runs as root, uid=0, SELinux permissive)
Android 13, SDK 33; wm size 2240x1080; wm density 160; model cm16
Foreground/HOME: com.baiyi.homeui.hshomeui/.MainActivity
/data free space at the time: 3.1 GB available of 3.5 GB (not a plausible-space problem)
```

Host media helpers (for the validation recipes):
- `C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\ffmpeg.exe` — ffmpeg 6.0-essentials;
  `ffmpeg -h protocol=http` confirms `-listen <int>` is supported (values 0..2, default 0).
- Known-good test clip `C:\Program Files\ASUS Info Hub - ROG RYUO IV\static\standard\RYUO_IV_HW_Info_01.mp4`:
  1920x960, **H.264 High**, yuv420p, 30 fps, **10.00 s**, ~8.5 Mbps, 10,677,244 bytes.

---

## 7. Install command (intended)

```powershell
$adb = "C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\adb.exe"
& $adb -s TC26011200324725 install -r -g "D:\ROG longwang4\apk\ryuo-stream.apk"
```

or `D:\ROG longwang4\apk\build.bat install` (same command, after the build).

---

## 8. Install attempts and exact failure evidence (2026-10-27)

All attempts happened after a clean `apksigner verify` on the host. **None succeeded.**

### 8.1 ~12:48 — `adb install -r -g` (default incremental/streamed)
Client aborted because the device disappeared mid-install:

```
Serving...
Performing Incremental Install
Performing Streamed Install
adb: failed to run abb_exec. Error: device 'TC26011200324725' not found
adb: connect error for write: device 'TC26011200324725' not found
```

Device logcat shows the whole platform restarting at ~12:49:09–12:49:24, i.e. the device
rebooted around **12:49:40** (confirmed by `uptime` = 3 min at 12:52:40).

### 8.2 ~12:50 — `adb install --no-incremental -r -g` (after adb reconnect)
Install reached the device and failed there with a platform NPE:

```
Performing Streamed Install
adb: failed to install D:\ROG longwang4\apk\ryuo-stream.apk:
Exception occurred while executing 'install':
java.lang.NullPointerException: Attempt to invoke virtual method 'void android.content.pm.PackageManagerInternal.freeStorage(java.lang.String, long, int)' on a null object reference
	at com.android.server.StorageManagerService.allocateBytes(StorageManagerService.java:4177)
	at android.os.storage.StorageManager.allocateBytes(StorageManager.java:2353)
	at android.os.storage.StorageManager.allocateBytes(StorageManager.java:2432)
	at com.android.server.pm.PackageI...
```

(the customer ROM's `StorageManagerService` dereferences a null `PackageManagerInternal` while
allocating install space; adb truncated the stack inside `com.android.server.pm.PackageI…`.)

Related device logcat lines captured around the same attempts:

```
12:49:12.992  468  582 E PackageManager: ERROR: could not load root hash from incremental install
12:49:12.993  468  582 E PackageManager: Required verifier is null
12:49:13.031  468  582 I PackageManager: Integrity check passed for file:///data/app/vmdl1606814104.tmp
```

### 8.3 ~12:50–12:54 — `adb push` + `pm install -r -g /data/local/tmp/ryuo-stream.apk`
APK pushed fine (`16779 bytes, 94.3 MB/s`), then `pm install` **hung indefinitely** on the device
(no output; killed after >180 s on the host). Stale session dirs were created in `/data/app/`:
`vmdl1606814104.tmp` (12:49) and `vmdl1397077035.tmp` (12:52).

### 8.4 ~12:53–12:56 — `adb install --no-streaming -r -g`
Push succeeded (`106.3 MB/s`, i.e. APK transfer is fine); the install step **hung** >120 s and was
killed. Device rebooted again at **12:56:54** (`uptime` = 0 min), creating session
`vmdl1397077035.tmp`.

### 8.5 12:57:30 — post-reboot control test
After the reboot settled, a session-create control test succeeded:

```
adb -s TC26011200324725 shell 'pm install-create -r -g -S 16779'
Success: created install session [524127100]
```

This matches the Lead's observation that `pm install-create` works (their earlier test:
`pm install-create -S 1048576`). So the APK is not rejected up front; the failure appears to be in
the `StorageManagerService.allocateBytes` path / stale `vmdl*.tmp` session state of this ROM.
No further device operations were performed (Lead requested a stop at ~12:57).

**Handoff suggestion for install debugging** (owner: Lead): abandon stale sessions
(`pm install-abandon <id>`), retry a streamed install while watching logcat
(`adb logcat -s PackageManager PackageInstaller StorageManagerService`), and/or avoid the
`allocateBytes` path with `pm install-create` + `pm install-write` + `pm install-commit` sessions
(no `-S` size hint, push `base.apk`). If the ROM always NPEs in `allocateBytes`, a root-side
manual install into a writable data/app layout or a fixed StorageManager is needed; do not reboot
the panel unless ready to recover HomeUI.

---

## 9. Validation recipes (prepared, NOT yet executed)

All commands assume `$adb = "C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\adb.exe"` and
`-s TC26011200324725`, with the tool folder prepended to PATH so `AdbWinApi.dll` loads.
Every run should be observed with `adb logcat -s RYUO_STREAM` and a `screencap` PNG.

### Test 1 — local MP4 via `file://` (target: real frame visible, PNG clearly > 50 KB)

The app is a normal unprivileged app, so `/data/local/tmp` is **not** reliably readable by it.
Use the app's own external files dir (no storage permission needed), or as root its data dir:

```powershell
# A) preferred: app-private external dir (app can read it without any permission)
& $adb shell mkdir -p /sdcard/Android/data/com.ryuo.stream/files
& $adb push "C:\Program Files\ASUS Info Hub - ROG RYUO IV\static\standard\RYUO_IV_HW_Info_01.mp4" /sdcard/Android/data/com.ryuo.stream/files/test.mp4
& $adb shell am start -n com.ryuo.stream/.StreamActivity --es url file:///sdcard/Android/data/com.ryuo.stream/files/test.mp4

# B) alternative (adbd is root): app data dir
#   adb shell mkdir -p /data/data/com.ryuo.stream/files
#   adb push <clip> /data/data/com.ryuo.stream/files/test.mp4
#   adb shell chown -R $(stat -c %u:%g /data/data/com.ryuo.stream) /data/data/com.ryuo.stream/files

Start-Sleep -Seconds 3
& $adb shell screencap -p /data/local/tmp/test1.png
& $adb pull /data/local/tmp/test1.png "D:\ROG longwang4\apk\screens\test1.png"
```

Pass criteria: screenshot shows a real video frame (not black). Reference: a real frame PNG on this
panel was ~1.15 MB in earlier device experiments; a black screen is ~12 KB. Also check
`adb logcat -s RYUO_STREAM` for `prepared 1920x960 durationMs=10000` + `info … 3` (rendering start),
and after the 10 s clip ends `completion` → `auto-restart #1` (restart default true).
Add `--ez hud false` to hide the HUD if it obscures the picture.

### Test 2 — host ffmpeg HTTP MPEG-TS + `adb reverse` (streaming smoke test)

Host (leave running in a background console; `-listen 1` is verified supported):

```powershell
$ff = "C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\ffmpeg.exe"
& $ff -hide_banner -re -stream_loop -1 -i "C:\Program Files\ASUS Info Hub - ROG RYUO IV\static\standard\RYUO_IV_HW_Info_01.mp4" `
  -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -g 30 `
  -muxdelay 0 -f mpegts -listen 1 http://127.0.0.1:18080/live.ts
# lightweight alternative if ffmpeg listen misbehaves:
#   python -m http.server 18080 --directory <dir-with-live.ts>   (no live transcode, but probative)
# or a tiny PowerShell/Python TCP HTTP server serving a looping .ts file.
```

Device:

```powershell
& $adb reverse tcp:18080 tcp:18080
& $adb shell am start -n com.ryuo.stream/.StreamActivity --es url http://127.0.0.1:18080/live.ts
# (or simply: am start -n com.ryuo.stream/.StreamActivity   -> default URL is the same)
Start-Sleep -Seconds 4
& $adb shell screencap -p /data/local/tmp/test2.png
& $adb pull /data/local/tmp/test2.png "D:\ROG longwang4\apk\screens\test2.png"
```

Pass criteria: PNG shows a frame; logcat shows `prepared 1920x960`, `info … MEDIA_INFO_BUFFERING_*`,
`MEDIA_INFO_VIDEO_RENDERING_START`; stream keeps running (10 s clip loops forever server-side, so no
completion expected). Latency to report: time from starting ffmpeg to first rendered frame /
`VIDEO_RENDERING_START` in logcat, plus subjective glass-to-glass delay. Note MediaPlayer's MPEG-TS
support is unverified on this panel; if TS fails, try `-f mpegts` with higher `-g` (e.g. 60),
`-fflags nobuffer`, or an HLS/mp4-over-HTTP variant to distinguish container vs transport issues.

### Cleanup after tests

```powershell
& $adb shell am force-stop com.ryuo.stream
& $adb reverse --remove tcp:18080
& $adb shell rm -f /data/local/tmp/test1.png /data/local/tmp/test2.png
# leave the panel on HomeUI; if the screen is grey standby do NOT toggle USB gadget re-enumeration
# without the Lead — report it instead.
```

---

## 10. Media/format constraints (observed or expected — device playback unverified)

- Encoder-side clip used for validation: **H.264 High, 1920x960, yuv420p, 30 fps, 10 s**. Panel is
  2240x1080 (2.074:1) so 1920x960 (2.0:1) is a 3.6 % aspect difference; `VideoView` is
  `match_parent` in both axes, so Android's surface is stretched to the panel (expect a very small
  geometric stretch or thin bars depending on vendor MediaPlayer surface scaling — inspect the
  screenshot).
- MediaPlayer/VideoView is the only player path in the APK; there is no ExoPlayer/VLC. Container
  support therefore depends on the vendor's `libstagefright`/codec stack (H.264 + AAC-in-MPEG-TS
  and RTSP/H.264 are the expected mainstream paths on RK3562 Android 13).
- Plain HTTP is allowed (`usesCleartextTraffic=true`), RTSP is accepted by the app and by
  `MediaPlayer.setVideoURI` (no special flags needed).
- Auto-restart is stateful on the activity: `restart=false` stops retries; the HUD is purely
  cosmetic and never affects playback.
- No audio focus/volume handling was added (video-only panel use case); MediaPlayer may still play
  a stream's audio track — mute externally if undesired.

---

## 11. Remaining issues / TODO for the device owner

1. **Install** is blocked by the ROM-side `StorageManagerService.allocateBytes` NPE / hanging
   `pm install` path (§8). The Lead is handling this. The APK itself passes `apksigner verify`,
   `zipalign -c`, and `aapt2 dump badging` cleanly.
2. **Test 1 / Test 2** unexecuted; recipes above.
3. No follow-up APK changes requested; if a code change is needed, edit
   `src\com\ryuo\stream\StreamActivity.java` and re-run `build.bat` (remember §4.2).
4. If the platform's `allocateBytes` bug persists, root-side install alternatives (write to a
   writable `/data/app` staging layout + PMS rescan, or fixing `StorageManagerService`) are
   outside the APK and were not attempted here because the device is shared/rebooting.

---

## 12. Reproduce from scratch

1. Ensure JDK 21 at `D:\ROG longwang4\tools\jdk-21.0.12.1+1` and SDK packages
   `platforms;android-33` + `build-tools;33.0.2` under `D:\ROG longwang4\tools\android-sdk`
   (§2).
2. `D:\ROG longwang4\apk\build.bat` → expect `=== BUILD OK ===`, `ryuo-stream.apk` ≈ 16.7 KB.
3. `apksigner verify --print-certs ryuo-stream.apk` → `Verifies`, v3 scheme true.
4. Install (§7) and validate (§9).
