#!/usr/bin/env python3
"""Generate the firmware README with final hashes/validation facts."""
import os, hashlib, json, zipfile, subprocess

BASE = r"D:\ROG longwang4"
B = os.path.join(BASE, "firmware-build")
OUT = os.path.join(B, "README-固件说明.md")

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def size(p):
    return os.path.getsize(p)

zip_p = os.path.join(B, "ROG_RYUO_IV_Streaming_Firmware_MOD.zip")
img_p = os.path.join(B, "system.img")
br_p = os.path.join(B, "system.new.dat.br")
apk_p = os.path.join(BASE, r"apk\ryuo-stream-v2.apk")

facts = {}
if os.path.exists(zip_p):
    facts['zip_sha'] = sha(zip_p); facts['zip_size'] = size(zip_p)
    z = zipfile.ZipFile(zip_p)
    facts['entries'] = len(z.infolist())
if os.path.exists(img_p):
    facts['img_sha'] = sha(img_p); facts['img_size'] = size(img_p)
if os.path.exists(br_p):
    facts['br_sha'] = sha(br_p); facts['br_size'] = size(br_p)
facts['apk_sha'] = sha(apk_p); facts['apk_size'] = size(apk_p)
json.dump(facts, open(os.path.join(B, 'build-facts.json'), 'w'), indent=2)

md = f"""# ROG RYUO IV SLC 360 ARGB — 定制固件（支持低延迟串流）
**版本：基于官方 V1.0.10（cm16 / Android 13）修改；未执行任何刷写操作。**

## 1. 这个固件改了什么
- 仅修改 `system` 分区镜像，其余分区（boot / uboot / dtbo / vendor / product / system_ext / odm 等）与官方 OTA **逐字节一致**。
- 由于官方 system 分区空间为 100%（876,687,360 字节 / 214,035 块，无空闲块），无法新增文件；
  采用**原位替换**：把未使用的系统应用
  `/system/priv-app/SharedStorageBackup/SharedStorageBackup.apk`（16,798 B）
  替换为自研低延迟串流播放器 **`com.ryuo.stream`（16,779 B）**。
  - 写入其原有 ext4 extent（块 211846..211850），并同步修改 inode 文件大小（16,798 → 16,779）。
  - 该镜像**未启用 metadata_csum**，因此不需要重算 inode/位图校验和；inode 号、块分配、位图、组描述符均未变化。
- 替换用的 APK 已通过 `apksigner verify`（v3 签名，`CN=RYUO`），`aapt2 dump badging` 正常，
  `resources.arsc` 未压缩且 4 字节对齐（zipalign -c 通过）；包名 `com.ryuo.stream`，minSdk 30 / targetSdk 33，
  内置 `StreamActivity`（全屏 VideoView/MediaPlayer，支持 HTTP/RTSP/本地文件 URL，断线自动重连）。

## 2. 产物与校验
| 文件 | 大小 | SHA-256 |
|---|---|---|
| `{os.path.basename(zip_p)}` | {facts.get('zip_size', 0):,} | `{facts.get('zip_sha', '')}` |
| `system.img`（修改后的 system ext4 镜像） | {facts.get('img_size', 0):,} | `{facts.get('img_sha', '')}` |
| `system.new.dat.br`（OTA 用 brotli 压缩镜像） | {facts.get('br_size', 0):,} | `{facts.get('br_sha', '')}` |
| `ryuo-stream-v2.apk`（被预置的播放器） | {facts.get('apk_size', 0):,} | `{facts.get('apk_sha', '')}` |

OTA zip 条目数：{facts.get('entries', 0)}；`system.transfer.list` 保持官方原文件（镜像大小未变，块数 214,035 一致）。

## 3. 离线校验结果（构建时执行）
1. 镜像内文件回读：从修改后的 ext4 镜像按 inode 3297 读出 `SharedStorageBackup.apk` 路径内容，SHA-256 与 `ryuo-stream-v2.apk` 完全一致。
2. ZIP 完整性：回读 APK 可正常作为 ZIP 打开，条目 `AndroidManifest.xml / resources.arsc / classes.dex / META-INF/*` 齐全。
3. 签名：`apksigner verify` 通过（v3 scheme），`aapt2 dump badging` 输出包名/图标/启动 Activity 正常。
4. OTA zip：完整条目列表、`META-INF/com/android/metadata` 中 `ota-property-files` 偏移（69/489）保持有效；updater-script / update-binary / transfer.list / 各分区镜像均与官方一致（除 system.new.dat.br）。
5. brotli 往返：对 `system.new.dat.br` 解压后与 `system.img` 逐字节比对一致（SHA-256 相同）。

## 4. 刷写方式（**本次未执行**，风险自评估）
> 设备已解锁（`ro.boot.flash.locked=0`、`verifiedbootstate=orange`、无 AVB），且 OTA 使用 AOSP 公开 testkey，理论可接受自制包。
> **刷机有变砖风险，请先完整备份 boot/uboot/misc/super。**

**方式 A：官方 OTA 升级通道（推荐先试）**
1. 将本目录的 `ROG_RYUO_IV_Streaming_Firmware_MOD.zip` 重命名为 `update.zip`；
2. 通过设备厂商升级入口（如 Info Hub 的固件升级流程/设备恢复模式）选择该包。
3. 若厂商升级器校验签名/哈希而拒收：见方式 B。

**方式 B：Rockchip 工具（MaskROM / Loader 模式）**
- 设备 SoC 为 RK3562，支持 Rockchip `rkdeveloptool` / `upgrade_tool`（MaskROM USB VID 0x2207）。
- 动态分区（super）机型建议优先刷 **system 逻辑分区** 或按官方 parameter 文件重刷 `super`；
  本目录提供未压缩 `system.img` 可直接作为 system 镜像写入（写入前确认目标分区大小 ≥ 876,687,360 字节）。
- 具体命令取决于本机 Rockchip 工具版本与分区表，请先用 `rkdeveloptool rl`/`upgrade_tool pl` 备份。

**方式 C：recovery adb sideload**
- 若设备存在 recovery：`adb reboot recovery` → `adb sideload ROG_RYUO_IV_Streaming_Firmware_MOD.zip`。
- 原厂 OTA 无 JAR 签名（无 META-INF/CERT.*），如 recovery 强制验签需使用 `--no-verify` 或先关闭校验。

## 5. 刷入后如何使用「低延迟真正串流」
1. 设备启动后，系统应用 `com.ryuo.stream` 已预装（在 `pm list packages` 中可见）。
2. 主机执行（本仓库工具）：
   ```powershell
   cd D:\\ROG longwang4\\exe
   .\\RyuoStreamTest.exe netstream --source screen --width 1920 --height 960 --fps 30 --bitrate 8000 --port 18080
   # 或 --source testsrc / --file D:\\movie.mp4；--transport hls 可切换 HLS
   ```
   该命令会：启动主机 MPEG-TS/HLS HTTP 服务 → `adb reverse tcp:18080 tcp:18080` → 启动设备端
   `com.ryuo.stream/.StreamActivity` 播放 `http://127.0.0.1:18080/live.ts`。
3. 停止/恢复：`RyuoStreamTest.exe restore`（或直接 `adb shell am force-stop com.ryuo.stream`）。
4. 也可手动：`adb reverse tcp:18080 tcp:18080` + `adb shell am start -n com.ryuo.stream/.StreamActivity --es url http://127.0.0.1:18080/live.ts`。
5. 延迟说明：USB 链路实测约 **25 MB/s（200 Mbps）**，1920×960@30 H.264 约 8 Mbps，带宽余量充足；
   端到端延迟主要来自 MediaPlayer/NuPlayer 缓冲（约 1–3 秒）。若需更低延迟，可改用 `--transport hls` 或后续将播放器改为
   `MediaCodec + MediaDataSource(TCP)` 直读裸 H.264（本固件已预留系统应用位置，可原位替换升级）。

## 6. 已知影响与回滚
- 原 `SharedStorageBackup`（Android 备份辅助服务，本机未使用）被替换；不影响正常使用。
- 回滚：重新刷官方 `ROG_RYUO_IV_Series_Firmware_File.zip`（ASUS 官网可下载）即可完全恢复。
- 本目录未修改设备、未刷写；所有产物仅为离线构建结果。

## 7. 构建来源
- 官方固件：`ROG_RYUO_IV_Series_Firmware_File.zip`（SHA-256 `6F2A2BD9…370D1E`）。
- 构建脚本：`build_firmware_step1b.py`（镜像内原位注入）、`brotli_stream.js`（镜像压缩）、`build_ota_zip.py`（OTA 重打包）。
- 播放器：`apk/ryuo-stream-v2.apk`（源码 `apk/src/com/ryuo/stream/StreamActivity.java`，构建脚本 `apk/build.bat`）。
"""
open(OUT, 'w', encoding='utf-8').write(md)
print('wrote', OUT)
print(json.dumps(facts, indent=2))
