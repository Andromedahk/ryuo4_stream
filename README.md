# ROG RYUO IV SLC 360 ARGB 逆向与 USB 低延迟串流

> 对 ASUS ROG 龙王 IV SLC 360 ARGB 水冷冷头屏的完整逆向工程：从官方 Info Hub 软件、设备端 Android 系统到官方固件，
> 打通了主机侧控制链路，并基于官方固件离线构建了预置串流播放器的定制固件（**未刷入设备**）。

- 目标设备：`USB\VID_0B05&PID_1C76` → **ROG RYUO IV Standard**（序列号 `TC26011200324725`）
- 面板：2240×1080 @60Hz（原生 1080×2240，MIPI-DSI，RK3562 + Android 13）
- 交付形态：可执行测试工具 `RyuoStreamTest.exe` + 逆向报告 + 自研播放器 APK + 定制 OTA 固件
- 当前状态：设备保持官方 V1.0.10 原样，**未刷写**；所有固件产物仅完成离线构建与校验

---

## 1. 项目结论（TL;DR）

1. **目标不是一块 USB 显示器，而是一台完整 Android 13 设备**（Rockchip RK3562，4×Cortex-A53，Kernel 5.10.157），
   通过复合 USB 设备暴露 **HID（MI_00，1024 字节自定义帧协议）** 与 **ADB（MI_01，标准 ff/42/01）** 两个接口。
2. **ADB 出厂即 root**：`adb shell id → uid=0(root)`，`ro.secure=0 / ro.debuggable=1 / ro.adb.secure=0`，SELinux permissive，
   无需任何漏洞利用即可获得 root shell。
3. 屏幕由系统应用 **`com.baiyi.homeui.hshomeui`（HomeUI）** 渲染：
   `HomeUI → MediaPlayer → rockit(rk_mpp 硬解) → SurfaceFlinger → HWC → MIPI-DSI`。
   官方架构**只播放本地文件**：主机通过 ADB push 媒体到 `/sdcard/pcMedia`，再通过 HID 下发 `config` JSON 选择播放内容。
4. 已完整逆向并复现 **HID 帧协议**（帧头/长度/校验和/命令/JSON），主机侧可用 `hid.dll` 直接控制屏幕（切媒体、调亮度），
   无需安装 ASUS Info Hub 也能工作。
5. **串流可行性**：
   - 官方播放器不支持 URL/网络流；FIFO 方案会触发内核 BUG（已放弃）。
   - 已实现「编码 → ADB push → HID 立即切换」的近实时链路，实测 **约 5.8 次内容更新/秒**（真实屏幕验证）。
   - 真正连续 30fps 串流需要设备端自研播放器；本机 ROM 的 PackageManager 安装流程存在缺陷（`install-commit` 永久挂起），
     无法在线安装 APK，因此改为**定制固件预置播放器**（见第 5 节）。
6. 官方固件为 **Rockchip Android 13 block-OTA**，使用 **AOSP 公开 testkey 签名、无 AVB 校验、有 MaskROM/Loader 通道**，
   可在不依赖厂商私钥的情况下重打包（本项目的定制固件即基于此）。

---

## 2. 目录结构

```
D:\ROG longwang4
├─ README.md                      ← 本文件（项目总览）
├─ 报告-ROG_RYUO_IV_逆向与串流方案.md   ← 完整逆向分析报告（通信协议、root、可行性、固件逆向）
├─ firmware-build\                ← ★ 定制固件产物（未刷入）
│  ├─ ROG_RYUO_IV_Streaming_Firmware_MOD.zip   定制 OTA（预置串流播放器）
│  ├─ system.img                               修改后的 system ext4 镜像
│  ├─ system.new.dat.br                        OTA 用 brotli 压缩镜像
│  ├─ SHA256SUMS.txt / build-facts.json        校验和与构建信息
│  ├─ README-固件说明.md                       固件改动/校验/刷写方式/使用说明
│  └─ device_unchanged_check.png               构建完成后设备未被刷写的截图
├─ exe\                           ← ★ 主机侧测试工具（可执行）
│  ├─ RyuoStreamTest.exe         串流/屏幕控制测试工具（内嵌播放器 APK）
│  ├─ RyuoStreamTest.cs          EXE 源码
│  ├─ Hid.cs                     HID 协议实现（Win32 P/Invoke）
│  └─ build.bat                  一键构建脚本（无需 .NET SDK）
├─ apk\                           ← ★ 自研播放器 APK
│  ├─ ryuo-stream.apk / ryuo-stream-v2.apk   播放器（v3 签名，16,779 B）
│  ├─ src\com\ryuo\stream\StreamActivity.java 源码
│  ├─ build.bat                  无 Gradle 构建脚本（aapt2/javac/d8/apksigner）
│  └─ BUILD_NOTES.md             构建说明与踩坑记录
├─ device-notes\                  ← 设备端证据（75 MB）
│  ├─ findings.md                设备调查报告
│  ├─ apk\                       从设备拉取的 HomeUI.apk / SerialService.apk 及字符串
│  ├─ pulled\                    设备属性、codec 配置等
│  ├─ screen_*.png               屏幕截图（原始画面/自定义画面/测试画面）
│  ├─ console-ramoops-0.txt      FIFO 实验导致的内核 panic 记录
│  └─ ...                        HID 日志片段、tombstone、trace
├─ firmware-notes\findings.md    官方固件逆向报告（OTA 结构、SoC/面板、签名、调试口）
├─ firmware\                     官方固件解包（2.2 GB）
│  ├─ ROG_RYUO_IV_Series_Firmware_File.zip   官方原包（512 MB）
│  ├─ extracted\                 OTA 原始解包（boot.img、uboot.img、*.new.dat.br、transfer.list…）
│  ├─ unpacked\                  system/vendor/product 等 ext4 镜像与索引、提取的文件
│  └─ scripts\                   ext4/dtb 解析脚本
├─ host-re\                      ASUS Info Hub 主机软件逆向（app.asar 解包、字节码字符串、日志解析）
├─ tools\                        JDK 21、Android SDK/build-tools、Ghidra 等（约 2.7 GB，非交付物）
├─ hls_test\ stream_test\        HLS/TS 流媒体原型实验数据
├─ rea-docs\                     REA 工具文档
└─ *.py / *.js                   ← 根目录为研究用一次性脚本（见第 8 节索引），非交付物
```

**核心交付物只有 4 项**：`exe\RyuoStreamTest.exe`、`报告-ROG_RYUO_IV_逆向与串流方案.md`、`firmware-build\ROG_RYUO_IV_Streaming_Firmware_MOD.zip`、`apk\ryuo-stream-v2.apk`。

---

## 3. 快速开始（主机侧测试工具）

### 环境要求
- Windows 10/11，**.NET Framework 4.x**（系统自带，EXE 为单文件、无需安装 .NET SDK）
- 已安装 **ASUS Info Hub - ROG RYUO IV**（用于其自带的 `adb.exe` / `ffmpeg.exe`；也可用 `--adb` / `--ffmpeg` 指定）
- 目标屏幕通过 USB 连接；多屏环境下工具会按 **VID_0B05&PID_1C76 / 序列号** 校验目标

### 命令一览
```powershell
cd D:\ROG longwang4\exe

# 0) 校验目标设备并打印设备/面板/解码器信息
.\RyuoStreamTest.exe probe

# 1) 编码一段测试视频 → ADB push → HID 配置切换（立即上屏）
.\RyuoStreamTest.exe play --source testsrc --codec h264 --width 1920 --height 960 `
    --fps 30 --bitrate 8000 --screenshots shots

# 2) 分段近实时测试（反复 编码→push→HID 切换，输出每次耗时与更新率）
.\RyuoStreamTest.exe stream --source testsrc --segment 1 --segments 20 --bitrate 6000

# 3) 直接控制屏幕：播放指定媒体 / 调亮度
.\RyuoStreamTest.exe hid --media-name 2026-10-07_11-59-09-827.mp4 --brightness 60

# 4) 真流模式：MPEG-TS over adb-reverse HTTP（需设备已安装/预置播放器 APK）
.\RyuoStreamTest.exe netstream --source screen --width 1920 --height 960 --fps 30 --bitrate 8000

# 5) 恢复原始画面、删除测试媒体
.\RyuoStreamTest.exe restore
```

### 常用参数
`--codec h264|hevc`、`--width/--height`、`--fps`、`--bitrate`（kbps）、`--gop`、`--preset`、
`--source testsrc|smpte|screen|file:PATH`、`--file PATH`、`--segment/--segments`、`--brightness`、
`--media-name`、`--screenshots DIR`、`--transport ts|hls`（netstream）、`--port`、`--serial`、`--adb`、`--ffmpeg`、`--verbose`。

### 实测数据（真机）
| 项目 | 结果 |
|---|---|
| 目标识别 | VID_0B05 PID_1C76 / TC26011200324725 / RK3562 / Android 13 / V1.0.10 / root |
| 面板 | 2240×1080 @60Hz，H.264 硬解 ≤1920×1088，HEVC ≤4096×2160 |
| `play` | encode≈75 ms + push≈75 ms + HID 切换≈2 ms，<1 s 上屏 |
| `stream`（1 s 分段） | 160–195 ms/次 → **约 5.8–6.2 次内容更新/秒** |
| USB 链路带宽（adb reverse） | 实测 **约 25 MB/s（200 Mbps）**，1080p30 编码仅需 ~8 Mbps |

---

## 4. 技术要点

### 4.1 目标设备识别
| 项目 | 值 |
|---|---|
| USB 复合设备 | `USB\VID_0B05&PID_1C76\TC26011200324725`，BusReportedDeviceDesc = `ROG RYUO IV Standard` |
| MI_00 | HID，UsagePage 0xFF00，OutputReportByteLength=1025（report id 0 + 1024 字节） |
| MI_01 | ADB Interface（Class ff/42/01，WinUSB，GUID `{F72FE0D4-CBCB-407d-8814-9ED673D0DD6B}`） |
| 系统 | Rockchip RK3562，Android 13 / SDK 33，`ro.product.version=ROG_RYUO_IV_Standard`，`ro.build.display.id=V1.0.10` |
| 权限 | adbd 以 **root** 运行（`uid=0`，SELinux permissive），无 `su` 二进制 |
| 显示 | `wm size` 2240×1080，density 160；fb0 = rockchipdrmfb 1080×2240×32bpp |

> ⚠️ 本机同时连接多块小屏（Tryx Panorama Se = VID_391A、VID_33C3 系列、VID_345F 等）。
> 所有工具都以 VID/PID + 序列号锁定目标，不会误操作其它屏幕。

### 4.2 HID 帧协议（已复现）
```
帧 = 0x5A | total_len(2B 大端) | ASCII 负载 | checksum | 0x5A
total_len = len(ASCII) + 5
checksum  = (total_len 两字节之和 + ASCII 所有字节之和) & 0xFF
ASCII 负载 = "POST <cmd> <ver>\r\n" + "Key=Value\r\n"* + "\r\n" + body
```
- 主机→设备：`POST conn 1`、`POST config 1`（waterBlockScreen JSON）、`POST all 1` 等；设备回 `1 200` + `AckNumber`。
- Windows 侧通过 `hid.dll` + SetupAPI 打开 UsagePage 0xFF00 集合，`WriteFile` 写入 1025 字节（report id 0 + 1024 负载）。
- **关键坑**：负载中出现裸字节 `0x5A`（ASCII `Z`，如 JSON 键 `timeZone`）会破坏设备组帧导致整帧被丢弃；
  解决：把 JSON 中的 `Z` 转义为 `\u005A`（语义等价）。
- `config` JSON 中 `media` 为 `/sdcard/pcMedia`（或 `pcMediaPreset`）下的**文件名列表**；HomeUI 会立即 `release + setVideoPath`，
  这是近实时切换的基础。

### 4.3 媒体与播放链路
- 主机 Info Hub（Electron 0.7.7，主进程为 V8 字节码）通过 **ADB push** 下发媒体、**HID** 下发配置与状态。
- 设备端：HomeUI（`/system/app/HomeUI`，可调试）→ `FullScreenVideoView` → MediaPlayer → **rockit/ffmpeg + rk_mpp 硬解**。
- 厂商自带媒体均为 H.264 High / yuv420p / 1920×960 / 30fps；HEVC 硬解可支持 2240×1080 全屏。
- 官方架构不支持 HTTP/RTSP/UVC 输入；`getMediaFilePath()` 对 URL 会拼接成本地路径（实测无效）。

### 4.4 安装限制（为何需要定制固件）
- `adb install` → `StorageManagerService.allocateBytes → PackageManagerInternal.freeStorage` NPE，偶发重启；
- `pm install-commit` → 永久挂起（`LocalIntentReceiver.getResult` 无返回），无法完成普通安装；
- `/system` 分区 100% 满，数据写入返回 ENOSPC，无法放置系统 App；
- 结论：在线安装/系统 App 放置均不可行 → 采用**官方固件离线重打包**方案（第 5 节）。

---

## 5. 定制固件（低延迟串流，未刷入）

### 5.1 改动内容
- 仅修改 **system** 分区；其余分区（boot/uboot/dtbo/vendor/product/system_ext/odm 等）与官方 OTA **逐字节一致**。
- system 分区无空闲块，无法新增文件 → **原位替换**未使用的系统应用：
  `/system/priv-app/SharedStorageBackup/SharedStorageBackup.apk`（16,798 B）
  → 自研播放器 **`com.ryuo.stream`（16,779 B）**，写入其原有 ext4 extent 并同步修改 inode 大小。
- 镜像未启用 `metadata_csum`，无需重算 inode/位图校验和；inode 号、块分配、位图、组描述符未变。
- 播放器为全屏 `VideoView/MediaPlayer`，支持 **HTTP/RTSP/本地文件 URL**，断线自动重连；包名 `com.ryuo.stream`，minSdk 30 / targetSdk 33，v3 签名。

### 5.2 产物
| 文件 | 大小 | SHA-256 |
|---|---|---|
| `firmware-build\ROG_RYUO_IV_Streaming_Firmware_MOD.zip` | 503,172,018 | `72c2ea90b04edbc23819062acb419f4b6f6f9ee708976f125259ec7d7802292b` |
| `firmware-build\system.img` | 876,687,360 | `ab92b13f4300f7fc80dfcd249b647de0ab2eee4ae89ee40ef370d7ee736dfb14` |
| `firmware-build\system.new.dat.br` | 364,573,188 | `8da9ffe51b648fc778be83d574ead15b8d2951582bd660755faf556c0d824910` |
| `apk\ryuo-stream-v2.apk` | 16,779 | `ed26ea1690793cede0b403029f4a6ab9c2fb21b66b50effbeafc5be636bd30ce` |

### 5.3 已完成的离线校验
1. 从修改后的镜像按 inode 回读 APK，SHA-256 与 `ryuo-stream-v2.apk` 一致；
2. APK：`apksigner verify` 通过、`aapt2 dump badging` 正常、`resources.arsc` 未压缩且 4 字节对齐；
3. OTA zip：34 个条目顺序与官方一致，`ota-property-files` 偏移（69/489）有效，除 system 外条目逐字节相同，CRC 通过；
4. brotli 往返：zip 内镜像解压后与 `system.img` SHA-256 完全一致；
5. `system.transfer.list` 块数 214,035 与镜像大小一致。

### 5.4 刷写方式（**未执行**）
详见 [`firmware-build\README-固件说明.md`](firmware-build/README-固件说明.md)，摘要：
- **A. 官方 OTA 升级通道**：zip 重命名为 `update.zip`，走厂商升级入口（推荐先试）；
- **B. Rockchip 工具（MaskROM/Loader，VID 0x2207）**：用 `system.img` 写 system 逻辑分区（先备份 boot/uboot/misc/super）；
- **C. recovery sideload**：`adb reboot recovery` → `adb sideload <zip>`（原厂包无 JAR 签名）。
- 回滚：重刷官方 `ROG_RYUO_IV_Series_Firmware_File.zip`。
- ⚠️ 刷机有风险；建议先备份并在可恢复条件下首次验证。

### 5.5 刷入后的串流方式
```powershell
cd D:\ROG longwang4\exe
.\RyuoStreamTest.exe netstream --source screen --width 1920 --height 960 --fps 30 --bitrate 8000 --port 18080
# 等价手动命令：
#   adb reverse tcp:18080 tcp:18080
#   adb shell am start -n com.ryuo.stream/.StreamActivity --es url http://127.0.0.1:18080/live.ts
```
USB 链路约 25 MB/s，延迟主要来自 MediaPlayer/NuPlayer 缓冲（约 1–3 秒）；可切换 `--transport hls`。
若需更低延迟，可后续将播放器改为 `MediaCodec + MediaDataSource(TCP)` 直读裸 H.264（固件已预留系统应用位置，可原位替换升级）。

---

## 6. 固件逆向摘要（官方 V1.0.10）
- 格式：Rockchip Android 13 **block-based OTA**（`RKLoader.bin`、`uboot.img`、`boot.img`、`dtbo.img` + 8 个动态分区 brotli 镜像）。
- 构建：`rockchip/cm16/cm16:13/TQ3C.230805.001.B2/eng.server.20251229.092713:user/release-keys`，SDK 33。
- 面板：`/dsi@ffb10000/panel@0`，1080×2240 AMOLED，MIPI DSI 4-lane，RGB888，152 MHz 像素时钟。
- 安全：**OTA 证书 = AOSP 公开 testkey**（与 `/system/etc/security/otacerts.zip` 一致）；`boot.img` 无 AVB footer；`ro.boot.verifiedbootstate=orange`。
- 调试：内核 cmdline `console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000` → **UART2 @ 0xFF210000**；Rockchip MaskROM（USB VID 0x2207）可强制下载。
- 详见 [`firmware-notes\findings.md`](firmware-notes/findings.md)。

---

## 7. 设备状态与回滚
- **本次固件构建未对设备执行任何刷写**：设备仍为官方 V1.0.10，未安装 `com.ryuo.stream`，`/sdcard/update.zip` 不存在
  （证据：`firmware-build\device_unchanged_check.png`）。
- 前序实验已恢复：原始媒体文件、原始 HomeUI 画面、删除测试媒体、清空 adb reverse。
- **需披露的系统侧改动**（前序为尝试在线安装而删除，当前系统内无法恢复，不影响使用）：
  `/system/app/CameraExtensionsProxy`（相机扩展，本机无摄像头）与 `/system/priv-app/FactoryMode`（工厂测试 App）。
  恢复方法：重刷官方 OTA；备份 APK 存于设备 `/data/local/tmp/`。
- 设备 ADB root 为出厂设计，未做任何持久修改。

---

## 8. 根目录实验脚本索引（研究用，非交付物）

| 前缀 | 用途 |
|---|---|
| `extract_asar.py`、`jsc_strings*.py`、`parse_log*.py`、`hidlog.py`、`decode_hid.py` | ASUS Info Hub 逆向（ASAR 解包、字节码字符串、日志/HID 帧解析） |
| `hid_*.py`、`checksum_*.py`、`frame_recon.py`、`decode_msgstr.py` | HID 帧协议逆向、校验和求解、HID 注入实验 |
| `jdwp_*.py`、`jdb_inject.py`、`jdb_cmds.txt` | HomeUI JDWP 注入实验（安卓调试协议客户端） |
| `build_firmware_step1*.py`、`ext4csum.py`、`build_ota_zip.py`、`brotli_stream.js`、`brotli_decompress.js`、`validate_firmware.py`、`generate_firmware_readme.py` | 定制固件构建与校验 |
| `make_base*.py`、`hls_test\`、`stream_test\` | 文件/TS/HLS 串流原型实验 |
| `apk_*.py`、`align*.py`、`peek_apk.py` | APK 尺寸/对齐/签名调试 |
| `parse_transfer.py`、`zip_probe.py`、`fw_candidates.py`、`ext4_probe.py`、`neigh_check.py` | OTA/transfer.list/ext4 分析 |

---

## 9. 已知限制
1. 官方固件下**无法实现连续 30fps 真流**：设备端没有可运行的自定义播放器，且当前 ROM 安装机制损坏。
2. 定制固件中的播放器**尚未在实际设备上运行验证**（因为无法在线安装、且按要求未刷机）；固件本身（镜像/OTA/签名/文件系统）已完成离线校验。
3. 若厂商升级器强制校验签名/哈希，OTA 方式可能被拒收；需使用 Rockchip 工具或 recovery 方式。
4. 播放器基于 Android `MediaPlayer`，延迟约 1–3 秒；更低延迟需改用 `MediaCodec + TCP`（后续可原位替换 APK 升级）。
5. 根目录脚本为研究过程产物，未做工程化整理。

---

## 10. 证据与文档索引
| 内容 | 路径 |
|---|---|
| 完整逆向报告 | [`报告-ROG_RYUO_IV_逆向与串流方案.md`](报告-ROG_RYUO_IV_逆向与串流方案.md) |
| 设备端调查报告 | [`device-notes\findings.md`](device-notes/findings.md) |
| 固件逆向报告 | [`firmware-notes\findings.md`](firmware-notes/findings.md) |
| 固件改动/刷写/使用说明 | [`firmware-build\README-固件说明.md`](firmware-build/README-固件说明.md) |
| 播放器构建说明 | [`apk\BUILD_NOTES.md`](apk/BUILD_NOTES.md) |
| 屏幕效果截图 | `device-notes\screen_after.png`、`device-notes\exe_shots\play_*.png`、`device-notes\screen_final_check.png` |
| FIFO 内核 panic 证据 | `device-notes\console-ramoops-0.txt` |
| 固件校验和 | `firmware-build\SHA256SUMS.txt`、`firmware-build\build-facts.json` |

---

## 11. 免责声明
本项目仅用于本机自有硬件的兼容性研究与学习。刷写固件、修改系统分区存在变砖风险，请在完整备份后自行评估。
所有固件产物均未被执行刷写；设备当前运行官方系统。

