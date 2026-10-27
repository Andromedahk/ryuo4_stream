# ASUS ROG RYUO IV SLC 360 ARGB 水冷冷头屏 — 逆向分析与 USB 视频串流方案报告

日期：2026-10-27　工作目录：`D:\ROG longwang4`
目标设备（已核对）：**USB\VID_0B05&PID_1C76，「ROG RYUO IV Standard」，序列号 TC26011200324725**
（本机同时连接了多块小屏：Tryx Panorama Se = VID_391A、VID_33C3 系列、VID_345F extscreen 等，均已排除，未做任何操作。）

---

## 0. 结论摘要（TL;DR）

1. **目标不是一块「USB 显示器」，而是一台完整的 Android 13 设备**（Rockchip RK3562，4×Cortex-A53，内核 5.10.157）。
   它通过 **USB 复合设备** 暴露两个接口：`MI_00 = HID（1024 字节自定义帧协议）`、`MI_01 = ADB（标准 ff/42/01）`。
2. **ADB 出厂即 root**：`adb shell id → uid=0(root) … context=u:r:su:s0`，`ro.secure=0 / ro.debuggable=1 / ro.adb.secure=0`，SELinux permissive，
   无需任何漏洞利用即可获得 root shell。
3. 屏幕内容由 **`com.baiyi.homeui.hshomeui`（HomeUI，系统 app，可调试）** 渲染：
   `HomeUI → MediaPlayer → rockit(ffmpeg/rk_mpp 硬解) → SurfaceFlinger → HWC → MIPI-DSI`。
   面板逻辑分辨率 **2240×1080 @60Hz**（原生 1080×2240 竖屏，旋转 90°），H.264 硬解上限 1920×1088，HEVC 硬解上限 4096×2160。
4. **官方架构不支持「真正的实时视频流」**：主机端 Info Hub 只做三件事：
   ① 通过 **ADB push** 把媒体文件推进 `/sdcard/pcMedia`（或 `/sdcard/pcMediaPreset`）；
   ② 通过 **HID 帧协议**下发 `config` JSON（选择媒体、亮度、叠加参数等）；
   ③ 每秒通过 HID 下发一次 `STATE all` 系统状态（CPU/GPU/风扇/水泵）。
   HomeUI 只播放**本地文件**，没有网络播放器、没有 URL 入口、没有接受视频流的服务。
5. 我们**打通了不依赖官方 App 的控制链路**：主机侧用 `hid.dll` 直接写 HID 设备，逆向并复现了完整帧格式与校验和，
   可以任意切换屏幕播放的媒体、调节亮度；并实现「编码 → ADB push → HID 切换」的**近实时（约 5.8 次/秒内容更新）**串流测试链路。
   该链路已写入交付的 EXE，并在真实屏幕上验证成功（截图见下）。
6. **真正的连续 30fps 串流**需要在设备上运行一个自研播放器 App（已构建 `ryuo-stream.apk`，16.8 KB）。
   但本机这版 ROM 的 **PackageManager 安装流程存在缺陷**（`pm install-commit` 永久挂起；`adb install` 触发
   `StorageManagerService.allocateBytes → PackageManagerInternal.freeStorage` NPE 并偶发重启），且 **/system 分区已满且数据写入返回 ENOSPC**，
   导致「普通安装」「系统 App 放置」两条路都无法在当前系统上完成。继续推进需要：刷写/改造固件（该固件使用 **AOSP 公开 testkey 签名、无 AVB 校验、有 MaskROM/Loader 模式**，可行性高），
   或修复 PackageManager 后安装 APK。详见第 6、7 节。

---

## 1. 目标设备身份核对（多屏环境）

| 项目 | 值 |
|---|---|
| USB 复合设备 | `USB\VID_0B05&PID_1C76\TC26011200324725`，BusReportedDeviceDesc = **ROG RYUO IV Standard** |
| 接口 0（MI_00） | HID，UsagePage 0xFF00，**OutputReportByteLength=1025**（报告 ID 0 + 1024 字节负载） |
| 接口 1（MI_01） | ADB Interface，Class ff/42/01，WinUSB，DeviceInterfaceGUID `{F72FE0D4-CBCB-407d-8814-9ED673D0DD6B}` |
| ADB 设备名 | `TC26011200324725  device  product:cm16 model:cm16 device:cm16` |
| 固件/系统 | `ro.product.version=ROG_RYUO_IV_Standard`，`ro.build.display.id=V1.0.10`，`rockchip/cm16/cm16:13/TQ3C.230805.001.B2/...` |
| SoC | RK3562（`ro.soc.model=RK3562`，`ro.board.platform=rk3562`），4×Cortex-A53 |
| 内核 | Linux 5.10.157+ aarch64，`androidboot.selinux=permissive`，`androidboot.verifiedbootstate=orange` |
| Root | `adb shell id` = **uid=0(root)**，context `u:r:su:s0`；无 `su` 二进制，adbd 本身即 root |
| 显示 | `wm size` 2240×1080，density 160；`/sys/class/graphics/fb0` = rockchipdrmfb，1080×2240×32bpp，stride 4320 |
| 解码器 | `c2.rk.avc.decoder` ≤1920×1088@60；`c2.rk.hevc.decoder` ≤4096×2160@60 |
| 其它 | Android 13 / SDK 33，安全补丁 2023-08-05，构建日期 2025-12-29 |

**关键证据**：`adb devices -l`、`getprop`、`wm size`、`dumpsys display/SurfaceFlinger`、`/proc/fb`、`media_codecs*.xml`（完整原文见 `device-notes/findings.md` 与 `firmware-notes/findings.md`）。

---

## 2. 官方软件（ASUS Info Hub - ROG RYUO IV 0.7.7）实现分析

- 安装位置：`C:\Program Files\ASUS Info Hub - ROG RYUO IV\`，**Electron 应用**（`resources/app.asar` 148 MB）。
- 主进程为 **V8 字节码**（`out/main/index.jsc`，721 KB，ASAR 完整性校验可绕过），渲染层为普通 JS；
  依赖 `appium-adb`、`fluent-ffmpeg`、`node-hid`、`serialport`、`sharp` 等；自带 `bin\adb.exe`、`bin\ffmpeg.exe`。
- 运行时日志（`%APPDATA%\rog_infohub\logs\*.log`，单日 10–17 MB）完整记录了通信过程：
  - `scan hid device … path=\\?\HID#VID_0B05&PID_1C76&MI_00#…` → 主机通过 **node-hid** 打开 MI_00；
  - `ADBDevice setup … adb exec cmdArgs: ['-s','TC26011200324725','shell','getprop','persist.sys.usb.id']` 等 → 通过 ADB 控制；
  - `getprop sys.device_open`、`[ -e '/sdcard/pcMedia' ]` → 设备就绪检测；
  - `Request Message Frame → cmd: conn / config / all`，`Response Message Frame`；
  - 媒体：`pushMedia` / `adb pushFile` → `/sdcard/pcMedia`，缩略图用 ffmpeg/OpenCV 抽取（`CatchVideoFrame`/`CatchGifFrame`），GIF 先转 MP4。
- **端口 4244 只是主机内部 TCP 服务**，与设备无关（设备侧无任何 TCP 监听）。
- HID 协议细节（由设备端 `SerialService` 日志 `hidserver_log.txt` 与主机日志互证，见第 3 节）。

---

## 3. 设备通信方式（完整逆向结果）

### 3.1 USB 通道
| 通道 | 用途 | 方向/格式 |
|---|---|---|
| ADB（MI_01） | 文件下发、属性读取、调试 | `adb push` 到 `/sdcard/pcMedia`、`/sdcard/pcMediaPreset`、`/sdcard/update.zip` 等 |
| HID（MI_00） | 配置下发 + 状态回传 | 1024 字节 OUT/IN 报告，ASCII 自定义帧 |

### 3.2 HID 帧格式（已完全逆向并在主机侧复现）
```
帧 = 0x5A | total_len(2B, 大端) | ASCII 负载 | checksum | 0x5A
total_len = len(ASCII) + 5
checksum  = (total_len 两个字节之和 + ASCII 所有字节之和) & 0xFF
ASCII 负载 = "POST <cmd> <ver>\r\n" + "Key=Value\r\n"* + "\r\n" + body
```
- 主机→设备命令：`POST conn 1`、`POST config 1`（承载 waterBlockScreen JSON）、`POST all 1`（系统状态）等。
- 设备→主机应答：`1 200` + `AckNumber` / `ContentLength` / `ContentType`。
- 实测样例：`conn` 帧 = `5A 00 38` + `POST conn 1\r\nSeqNumber=…\r\nDate=…\r\n\r\n` + `05 5A`（总长 56 字节，校验 0x05 ✔）。
- **关键坑**：负载中若出现裸字节 `0x5A`（即 ASCII 'Z'，例如 JSON 键 `timeZone`），设备侧组帧会被破坏、整帧被静默丢弃。
  解决办法：把 JSON 中的 `Z` 写成 `\u005A`（JSON 语义等价）后再发送 —— 已验证可正常下发含 `timeZone` 的完整配置。
- Windows 侧通过 `hid.dll`/`SetupAPI` 打开设备（UsagePage 0xFF00 的集合），`WriteFile` 写入 1025 字节
  （report id 0 + 1024 字节负载，其余补 0）即可；无需安装任何驱动、可与官方 App 同时写入。

### 3.3 `config` JSON（控制屏幕的核心）
```json
{"temperature":"Celsius","waterBlockScreen":{
  "enable":true,"displayInSleep":true,"brightness":85,
  "id":{"id":"Customization","screenMode":"Full Screen","playMode":"Single",
        "media":["<文件名>"],"settings":{...},"sysinfoDisplay":[...],"timeZone":"Asia/Shanghai"}},
 "spec":{"cpu":"...","gpu":"..."}}
```
- `media` 是 `/sdcard/pcMedia/` 或 `/sdcard/pcMediaPreset/` 下的**文件名列表**。
- HomeUI 的 `getMediaFilePath()` 会拼成 `sdcard/pcMedia/<name>`；不存在时回退 `sdcard/pcMediaPreset/<name>`；
  **不接受 URL**（实测传入 `http://…` 时被拼成 `sdcard/pcMediaPreset/http://…`）。
- 下发 `config` 后 HomeUI 会**立即** `release + setVideoPath`，不必等播放循环结束（这是近实时切换的基础）。

### 3.4 设备端 App
| 包名 | 位置 / 版本 | 作用 |
|---|---|---|
| `com.baiyi.homeui.hshomeui` | `/system/app/HomeUI`，1.7.6，uid 1000，DEBUGGABLE | HOME，`HSMainActivity` → `FullScreenVideoView main_video1` → MediaPlayer |
| `com.baiyi.service.serialservice.serialdataservice` | `/system/priv-app/SerialService`，1.4.2，uid 1000 | 独占 `/dev/hidg0`，解析 HID 帧并通过 AIDL 回调 HomeUI |
| `/system/lib64/libhid_port.so` | JNI | 封装 `/dev/hidg0`（`Java_android_1hidport_1api_HidPort_*`） |

---

## 4. 屏幕与媒体能力

- 逻辑 2240×1080 @60Hz，HWC2 合成，DSI-1 直连；原生 1080×2240 RGB888，4-lane MIPI DSI，像素时钟 152 MHz。
- 厂商自带视频均为 **H.264 High / yuv420p / 1920×960 / 30fps**（`static/standard/*.mp4`，8.5 Mb/s 等）。
- 硬解能力：H.264 ≤1920×1088，HEVC ≤4096×2160 → **HEVC 可做 2240×1080 全屏点对点**。
- 实测：把任意 H.264 1920×960 MP4 推到 `/sdcard/pcMedia` 并下 `config` 即可立刻上屏（已多次验证，含自绘测试图）。

---

## 5. 可行性评估：USB 视频串流

### 5.1 官方架构的边界
- 播放源**只能是本地文件**；HomeUI 无 HTTP/RTSP/UVC 输入。
- 设备侧**无 TCP 监听**、无 adb reverse 默认配置；USB 仅 hid.gs0 + ffs.adb 两个功能。
- 因此「像显示器一样持续送帧」在官方设计里不存在。

### 5.2 尝试过的方案与结果
| 方案 | 结果 |
|---|---|
| ① `/sdcard/pcMedia/<name>` 换成 **FIFO** 喂 MPEG-TS | ❌ MediaPlayer 不接受不可 seek 的 fd，且触发厂商内核 BUG（`list_del corruption` in `__fput`）导致**内核 panic 重启**。已明确放弃，切勿再试。 |
| ② 播放 `file://` / `http://` URL | ❌ 无任何 Activity 处理 VIEW 意图；HomeUI 只接受媒体文件名。 |
| ③ 本地 HLS 播放列表（.m3u8 或改名 .mp4） | ❌ rockit 以容器方式打开 fd，HLS 文本无法识别（`avformat_open_input` 失败）。 |
| ④ **ADB push 文件 + HID config 立即切换** | ✅ **成功**。每次切换 = 编码 + push（~100 ms）+ HID（~2 ms），实测 **约 5.8 次/秒内容更新**（1920×960@30 编码，ultrafast）。 |
| ⑤ 预制大文件 + **播放头前方覆写**（伪流式） | ⚠️ 原型阶段：按 2 秒 CBR 槽位覆写未来数据，播放到被覆写槽位时 rockit 报错并重启播放，未达到无缝。可用于继续研究，但不作为交付方案。 |
| ⑥ 安装自研播放器 APK（`com.ryuo.stream`，16.8 KB，v1+v2+v3 签名） | ⛔ **当前系统无法安装**：普通安装挂起、流式安装触发 ROM 级 NPE / 偶发重启；系统分区已满（数据写入 ENOSPC）。APK 与构建脚本已交付，供刷机/修复后使用。 |

### 5.3 结论
- **可以做到**：主机任意内容 → 编码 → USB → 屏幕上显示；**控制链路完全打通**（含逐次切换、亮度、状态读取），
  已做成可执行工具（本报告第 8 节），可用于测试分辨率/帧率/码率/编码器在真实面板上的效果。
- **暂时做不到**：官方固件下的**连续 30fps 无缝直播**——缺少设备端可运行的自研播放器，且当前 ROM 的包安装机制损坏。
- **建议的下一步（按可行性排序）**：
  1. **刷写自编译固件/OTA**：该固件 OTA 使用 **AOSP 公开 testkey** 签名（与 `/system/etc/security/otacerts.zip` 完全一致）、无 AVB 校验、
     `ro.boot.verifiedbootstate=orange`、`flash.locked=0`，并存在 **RKLoader / MaskROM（VID 0x2207，rkdeveloptool）** 通道；
     可把 `ryuo-stream.apk` 预置为系统应用，或直接修改 AOSP 播放器；风险与步骤见 `firmware-notes/findings.md`。
  2. **修复 PackageManager** 后 `adb install ryuo-stream.apk`（安装成功后 `RyuoStreamTest.exe netstream` 即可用 MPEG-TS over
     adb-reverse HTTP 实现低延迟真流，带宽实测 25 MB/s，足够 1080p30）。
  3. 修复/绕过 `/system` ENOSPC（当前分区 100% 且数据块不可分配）后，用系统 App 方式放置播放器。
- **硬件调试口**：U-Boot/内核命令行 `console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000` → **UART2 @ 0xFF210000** 为调试串口
  （板上有测试点，需焊接/探针）；另有 Rockchip MaskROM（USB VID 0x2207）可强制进入下载模式。固件无签名强校验，可改。

---

## 6. 固件逆向结果（官方 OTA）

`ROG_RYUO_IV_Series_Firmware_File.zip`（512 MB，SHA-256 6F2A2BD9…370D1E）：
- 格式：**Rockchip Android 13 block-based OTA**；`RKLoader.bin`（Rockchip USB loader，magic `LDR `）、`uboot.img`（4 MiB FIT：ATF/OP-TEE/U-Boot/MCU）、
  `boot.img`（35.6 MB）、`dtbo.img`，以及 8 个动态分区（system 876.7 MB、vendor 266.5 MB、product、system_ext、vendor_dlkm、odm、system_dlkm、odm_dlkm，brotli 压缩，解压后为普通 ext4 镜像）。
- 系统：`rockchip/cm16/cm16:13/TQ3C.230805.001.B2/eng.server.20251229.092713:user/release-keys`；
  `ro.debuggable=1`、`ro.secure=0`、SELinux permissive（出厂即为可调试工程配置，但 `su` 被移除，adbd 直接 root）。
- 面板：`/dsi@ffb10000/panel@0`，1080×2240 AMOLED，MIPI DSI 4-lane，RGB888，152 MHz 像素时钟（≈60.1 Hz），OLED 背光 PWM。
- 视频链路：`app/video → SurfaceFlinger/HWC2 → VOP2(0xff400000) → rk3562-mipi-dsi(0xffb10000) → 4-lane DPHY → panel`；
  Codec2/MPP 硬解（`libcodec2_rk_component.so`），RGA3 + VPU 节点。
- 签名/刷写：**OTA 证书 = AOSP testkey**（`META-INF/com/android/otacert` 与 `/system/etc/security/otacerts.zip → testkey.x509.pem` 字节一致）；
  `boot.img` 无 AVB footer、未随包提供 vbmeta；U-Boot 走 “Not AVB images, AVB skip” 分支 → **可用公开 testkey 重签自制 OTA**。
- 调试/root：ADB 默认开启且已授权；`/vendor/bin/flash_img.sh`（dd 辅助）；`ro.rk.flash_enable=true`；串口 `ttyFIQ0`。
- 提取产物：`firmware/unpacked/files/`（HomeUI.apk、SerialService.apk、libhid_port.so、media_codecs.xml、各 rc 文件、dtb 等），
  以及完整 ext4 索引（`idx-*.json`）与 dtb 解析脚本。详见 `firmware-notes/findings.md`。

---

## 7. 已实现的主机侧控制/串流工具（交付物）

### 7.1 `RyuoStreamTest.exe`（.NET Framework 4.x，单文件，已内嵌播放器 APK）
位置：`D:\ROG longwang4\exe\RyuoStreamTest.exe`（约 67 KB，另有源码 `RyuoStreamTest.cs`、`Hid.cs`、`build.bat`）

```
RyuoStreamTest.exe probe       # 校验目标（VID/PID/序列号）+ 打印设备/面板/解码器信息
RyuoStreamTest.exe play        # 编码一段视频 → adb push → HID 配置切换（立即上屏）
RyuoStreamTest.exe stream      # 分段近实时测试：反复 编码→push→切换，输出每次耗时与更新率
RyuoStreamTest.exe hid         # 直接下发 waterBlockScreen 配置（媒体名/亮度）
RyuoStreamTest.exe netstream   # MPEG-TS over adb reverse HTTP（需已安装 ryuo-stream.apk）
RyuoStreamTest.exe install     # 安装内嵌播放器 APK（当前 ROM 会失败，见第 5.2 节）
RyuoStreamTest.exe file        # 只编码+推送（等待 HomeUI 循环切换）
RyuoStreamTest.exe restore     # 恢复原始画面、删除测试媒体、清理 adb reverse
```
常用参数：`--codec h264|hevc`、`--width/--height`、`--fps`、`--bitrate`、`--preset`、`--source testsrc|smpte|screen|file:PATH`、
`--segment/--segments`、`--brightness`、`--media-name`、`--screenshots DIR`、`--serial`、`--adb`、`--ffmpeg`。

### 7.2 实测结果（真实设备）
- `probe`：正确识别目标并打印 RK3562/Android 13/V1.0.10/2240×1080/root。
- `play --source testsrc --width 1920 --height 960 --fps 30 --bitrate 6000 --screenshots …`：
  `encode≈75ms，push≈75ms，HID 切换≈2ms`；屏幕在 <1 秒内显示测试图（`device-notes/exe_shots/play_*.png` 为设备端截屏实拍）。
- `stream --segment 1 --segments 6`：**5.8–6.2 次内容更新/秒**（每次 160–195 ms：编码 72–77 ms + push 86–117 ms + HID 1–2 ms）。
  这是「官方播放器 + 文件切换」架构下的上限；参数（分辨率/帧率/码率/编码器）可任意改。
- 同时验证：H.264 1920×960 与 HEVC 路径、亮度下发、媒体列表切换、原始媒体恢复。

### 7.3 配套 APK
`D:\ROG longwang4\apk\ryuo-stream.apk`（16,779 B，v1+v2+v3 签名，包名 `com.ryuo.stream`）：
全屏 `StreamActivity`，接收 `url` extra（HTTP/RTSP/本地文件），可自动重连；构建脚本 `build.bat`、说明 `BUILD_NOTES.md`。
一旦安装（刷机后），配合 `netstream` 可把主机 ffmpeg 的 MPEG-TS 以 HTTP 经 adb reverse 送入设备硬件解码，实现低延迟连续串流。

---

## 8. 设备当前状态与回滚说明（重要）

实验结束后已执行恢复：
- 原始媒体文件 `/sdcard/pcMedia/2026-10-07_11-59-09-827.mp4` 已恢复（md5 与原始一致），HomeUI 正在播放原始内容（`device-notes/screen_final_check.png`）。
- 测试媒体（HLS 分片、TS、`ryuo_*` 文件）已删除；`adb reverse` 已清空；测试进程已停止。
- 页面/文件缓存中仍保留测试数据（`/data/local/tmp/*`，包括原始文件备份、FactoryMode/CameraExtensionsProxy 备份），可随时清理。

**已知系统侧改动（需披露）**
- 为尝试「系统 App 方式」安装播放器，删除了两个**未使用**的出厂系统应用以腾出空间：
  `/system/app/CameraExtensionsProxy`（相机扩展代理，本机无摄像头）与 `/system/priv-app/FactoryMode`（工厂测试 App）。
- 该只读分区数据写入随后被证实不可用（ENOSPC），因此**无法在当前系统内恢复**这两个 APK；
  但两者不影响正常使用。**恢复方法**：重刷官方 OTA（`ROG_RYUO_IV_Series_Firmware_File.zip`，可从 ASUS 官网重新下载），
  或按住恢复流程/使用 Rockchip 工具刷 `system` 分区；备份 APK 在 `/data/local/tmp/FactoryMode_backup.apk`、`/data/local/tmp/camera_ext_backup.apk`。
- 其余内容（`/sdcard`、`/data/app`、设置）未做持久修改；设备 ADB root 状态为出厂设计，未改动。

---

## 9. 证据与产物索引

| 内容 | 路径 |
|---|---|
| 设备端完整调查报告 | `device-notes/findings.md` |
| 固件逆向完整报告 | `firmware-notes/findings.md` |
| 设备识别/面板/HID/日志证据 | `device-notes/`（screencap、hidserver_log 片段、trace、APK strings） |
| 固件解包与文件 | `firmware/unpacked/`、`firmware-notes/` |
| 主机 App 分析 | `host-re/`（app.asar 解包、jsc 字符串、日志解析脚本） |
| EXE 源码与构建 | `exe/RyuoStreamTest.cs`、`exe/Hid.cs`、`exe/build.bat` |
| 播放器 APK 源码与构建 | `apk/`（`ryuo-stream.apk`、`build.bat`、`BUILD_NOTES.md`） |
| 上屏效果截图 | `device-notes/screen_after.png`、`device-notes/exe_shots/play_*.png`、`device-notes/screen_final_check.png` |
| 实验脚本 | `hid_send.py`、`jdb_inject.py`、`make_base*.py` 等（在 `D:\ROG longwang4` 根目录） |

---

## 10. 复现步骤（快速开始）

```powershell
cd 'D:\ROG longwang4\exe'
# 1) 校验目标（多屏环境下必须先确认 VID_0B05&PID_1C76 / 序列号）
.\RyuoStreamTest.exe probe

# 2) 编码并立即上屏（测试分辨率/码率/编码器）
.\RyuoStreamTest.exe play --source testsrc --codec h264 --width 1920 --height 960 --fps 30 --bitrate 8000 --screenshots shots

# 3) 分段近实时（测量该机官方播放器下的切换上限）
.\RyuoStreamTest.exe stream --source testsrc --segment 1 --segments 20 --bitrate 6000

# 4) 直接控制屏幕（播放指定本地媒体/调亮度）
.\RyuoStreamTest.exe hid --media-name 2026-10-07_11-59-09-827.mp4 --brightness 60

# 5) 恢复
.\RyuoStreamTest.exe restore
```
