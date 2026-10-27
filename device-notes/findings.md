# ASUS ROG RYUO IV SLC 360 ARGB ("龙王4") — On-device / ADB investigation

Author: teammate `device-adb`  ·  Date: 2026-10-27  ·  Host: Windows, working dir `D:\ROG longwang4`

Target device (ONLY this one; other small screens on the PC are NOT the target):
- USB `USB\VID_0B05&PID_1C76`, serial **TC26011200324725**, BusReportedDeviceDesc "ROG RYUO IV Standard"
- adb serial `TC26011200324725` (product:cm16 model:cm16 device:cm16)
- MI_00 = HID, MI_01 = ADB (WinUSB, GUID {F72FE0D4-CBCB-407d-8814-9ED673D0DD6B})

### How to invoke adb (the EXE must do exactly this)
```powershell
$root='C:\Program Files\ASUS Info Hub - ROG RYUO IV'
$env:PATH="$root;$root\bin;$env:PATH"          # AdbWinApi.dll / AdbWinUsbApi.dll live in $root
& "$root\bin\adb.exe" -s TC26011200324725 <args>
```
adb version 1.0.41 / 34.0.3-10161052. Without the PATH trick adb.exe fails to find its DLLs.

---

## 0. TL;DR — most important results

| Question | Answer |
|---|---|
| Root? | **YES, already root** — `adb shell id` = `uid=0(root) ... context=u:r:su:s0`. adbd runs as root (`ro.secure=0`, `ro.debuggable=1`, `ro.adb.secure=0`). No `su` binary, no Magisk, no exploit needed. |
| What is the screen? | A complete **Android 13 (SDK 33) device**, Rockchip **RK3562**, 4×Cortex-A53, kernel 5.10.157, 2240×1080 logical panel (1080×2240 native portrait rotated 90°). |
| What renders it? | `com.baiyi.homeui.hshomeui` (HomeUI.apk, /system/app, uid 1000, DEBUGGABLE) → `HSMainActivity` → `FullScreenVideoView main_video1` → MediaPlayer → rockit `rk_mpp` HW decoder → SurfaceFlinger → HWC2 → DSI-1. |
| How does the host send content? | **File push to `/sdcard/pcMedia`** + a **STATE JSON over HID** (`/dev/hidg0`, 1024-byte reports, ASCII framed). No TCP at all on the device. |
| Can we display arbitrary video? | **YES — VERIFIED on the physical panel.** Overwrite the bytes of the file currently in the active playlist; HomeUI re-opens it every loop. Screenshot proof: `screen_after.png`. |
| Best path for live streaming? | ~~FIFO~~ (causes **kernel panic**) → use **`adb reverse tcp:PORT` (measured 24.9 MB/s) + a sideloaded player APK** (installs are permitted). |
| Risks | FIFO/pipe through MediaPlayer ⇒ kernel panic. Never touch /system. HomeUI loses host config on reboot (recover by USB re-enumeration, see §11). |

---

## 1. Identity / OS (`getprop`)

```
ro.product.brand        = rockchip          ro.product.version   = ROG_RYUO_IV_Standard
ro.product.model        = cm16              ro.build.display.id  = V1.0.10
ro.product.device       = cm16              ro.build.type        = user
ro.product.name         = cm16              ro.build.date        = Mon Dec 29 09:26:28 CST 2025
ro.product.manufacturer = rockchip          ro.build.id          = TQ3C.230805.001.B2
ro.build.version.release= 13 (Android 13)   ro.build.version.sdk = 33
ro.build.version.security_patch = 2023-08-05
ro.build.fingerprint = rockchip/cm16/cm16:13/TQ3C.230805.001.B2/eng.server.20251229.092713:user/release-keys
ro.build.host = server-MS-7E24       ro.build.user = server
ro.soc.manufacturer = Rockchip       ro.soc.model = RK3562
ro.board.platform = rk3562           ro.product.board = rk30sdk
ro.hardware = rk30board              ro.kernel.version = 5.10
ro.serialno = TC26011200324725       ro.boot.serialno = TC26011200324725
ro.hwversion = V1.1                  ro.vendor.sdkversion = rk3562_ANDROID13.0_MID_V1.0
ro.rksdk.version = ANDROID13_RKR6    ro.treble.enabled = true
ro.crypto.state = encrypted, type=file   ro.config.low_ram = true
```
```
$ adb shell uname -a
Linux localhost 5.10.157+ #57 SMP PREEMPT Mon Dec 29 09:25:50 CST 2025 aarch64 Toybox
$ adb shell cat /proc/version
Linux version 5.10.157+ (server@server-MS-7E24) (Android (8490178, based on r450784d)
 clang version 14.0.6 ...) #57 SMP PREEMPT Mon Dec 29 09:25:50 CST 2025
$ adb shell cat /proc/cpuinfo   → 4 × "processor : 0..3", CPU part 0xd03 = Cortex-A53,
  Features: fp asimd evtstrm aes pmull sha1 sha2 crc32 cpuid, Serial 4f7b8b3c0f977cbd
$ adb shell cat /proc/cmdline
storagemedia=emmc androidboot.storagemedia=emmc androidboot.mode=normal androidboot.dtb_idx=0
androidboot.dtbo_idx=0 androidboot.verifiedbootstate=orange androidboot.serialno=TC26011200324725
androidboot.hwversion=V1.1 console=ttyFIQ0 firmware_class.path=/vendor/etc/firmware init=/init
rootwait ro loop.max_part=7 androidboot.console=ttyFIQ0 androidboot.wificountrycode=CN
androidboot.hardware=rk30board androidboot.boot_devices=ff870000.mmc androidboot.selinux=permissive
buildvariant=user earlycon=uart8250,mmio32,0xff210000
```

### Partitions / storage (`df -h`, `cat /proc/mounts`)
```
/dev/block/dm-0   835M 833M 2.5M 100% /            (system, ro, ext4, dynamic partition)
/dev/block/dm-3   254M 253M  812K 100% /vendor     (ro)
/dev/block/dm-5   640K 636K   4.0K 100% /odm        (ro)
/dev/block/dm-1   232K  36K  196K  16% /system_dlkm (ro)
/dev/block/dm-2    46M  46M  144K 100% /system_ext  (ro)
/dev/block/dm-4    27M  27M   88K 100% /vendor_dlkm (ro)
/dev/block/dm-6   232K  36K  196K  16% /odm_dlkm    (ro)
/dev/block/dm-7    19M  19M   60K 100% /product     (ro)
/dev/block/mmcblk2p11 10M /metadata ; mmcblk2p10 320M /cache
/dev/block/dm-8   3.5G 405M 3.1G  12% /data         (f2fs, rw)
/dev/fuse         3.5G 405M 3.1G  12% /mnt/user/0/emulated  (scoped storage / "sdcard")
tmpfs 982M /dev, /apex, /linkerconfig ; configfs /config ; binderfs /dev/binderfs
adb /dev/usb-ffs/adb (functionfs) ; mtp, ptp also mounted but not exported over USB
```
Root `/` listing: acct, apex, bin→/system/bin, cache, config, d, data, data_mirror, debug_ramdisk,
dev, etc→/system/etc, init, linkerconfig, mnt, odm, odm_dlkm, oem, postinstall, proc, product,
sdcard→/storage/self/primary, storage, sys, system, system_dlkm, system_ext, vendor, vendor_dlkm.

---

## 2. Root status — ALREADY ROOT

```
$ adb shell id
uid=0(root) gid=0(root) groups=0(root),1004(input),1007(log),1011(adb),1015(sdcard_rw),
1028(sdcard_r),1078(ext_data_rw),1079(ext_obb_rw),3001(net_bt_admin),3002(net_bt),3003(inet),
3006(net_bw_stats),3009(readproc),3011(uhid),3012(readtracefs) context=u:r:su:s0

$ adb shell "which su"      → (none)         $ adb shell "su -c id" → /system/bin/sh: su: inaccessible or not found
```
Root-relevant props:
```
ro.secure = 0            ro.debuggable = 1        ro.adb.secure = 0
ro.build.type = user     ro.boot.selinux = permissive
ro.boot.verifiedbootstate = orange   ro.boot.flash.locked = 0
ro.oem_unlock_supported = 1          sys.oem_unlock_allowed = 0
sys.rkadb.root = 0                   (irrelevant: adbd already uid 0)
```
⇒ `adb root` is unnecessary; every `adb shell` is a root shell. `adb shell` also runs in
`u:r:su:s0` so SELinux (permissive anyway) does not block reads of /data, /proc, /sdcard logs.

Vendor apps are additionally `pkgFlags=[ SYSTEM DEBUGGABLE HAS_CODE ...]` and signed with the
same platform key (`signatures=[b1a1812f]`, sharedUser `android.uid.system` / uid 1000).

---

## 3. Display / panel

```
$ adb shell wm size          → Physical size: 2240x1080
$ adb shell wm density       → Physical density: 160
$ adb shell dumpsys display | head
  mViewports=[DisplayViewport{type=INTERNAL, valid=true, isActive=true, displayId=0,
     uniqueId='local:0', physicalPort=0, orientation=0,
     logicalFrame=Rect(0, 0 - 2240, 1080), physicalFrame=Rect(0, 0 - 2240, 1080),
     deviceWidth=2240, deviceHeight=1080}]
  mStableDisplaySize=Point(2240, 1080)
  Display State=ON   Display Brightness=0.83137274   SdrBrightness=0.83137274
  DisplayColorSetting: Managed    ColorMode::NATIVE (0)  (dumpsys SurfaceFlinger)
$ adb shell dumpsys SurfaceFlinger --display-id
  Display 0 (HWC display 0): no identification data
  Build configuration: [... FORCE_HWC_FOR_RBG_TO_YUV=0 ...]   Refresh rate: 60.00 Hz
```
Framebuffer (native, un-rotated):
```
/sys/class/graphics/fb0/name         = rockchipdrmfb
/sys/class/graphics/fb0/virtual_size = 1080,2240        ← portrait!
/sys/class/graphics/fb0/bits_per_pixel= 32              (RGBX_8888, ro.minui.pixel_format=RGBX_8888)
/sys/class/graphics/fb0/stride       = 4320             (1080*4)
/sys/class/graphics/fb0/modes        = U:1080x2240p-0
/sys/class/graphics/fb0/rotate       = 0
/sys/class/drm/card0-DSI-1/modes     = 1080x2240
/proc/fb                             = 0 rockchipdrmfb
vendor.hwc.device.display-0          = DSI-1:71:connected
vendor.hwc.version                   = HWC2-1.5.143
ro.surface_flinger.primary_display_orientation = ORIENTATION_90
vendor.gralloc.fb_size               = 2419200          (=1080*2240*1? / see gralloc)
```
⇒ Panel is a **1080×2240 portrait AMOLED/DSI panel**, composed and rotated 90° to the Android
logical resolution **2240×1080 @ 60 Hz**, density 160 dpi.

Device nodes for graphics:
```
/dev/graphics/fb0         crw-rw---- root graphics  29,0
/dev/dri/card0            crw-rw-rw- root graphics 226,0
/dev/dri/card1            crw-rw-rw- root graphics 226,1
/dev/dri/renderD128/129   crw-rw-rw- root graphics 226,128 / 226,129
Only PID 230 (android.hardware.graphics.composer@2.1-service) holds fb0.
```

### Verified screen capture oracle (used for all visual proof below)
```powershell
adb shell screencap -p /data/local/tmp/s.png ; adb pull /data/local/tmp/s.png
# NOTE: do NOT use PowerShell ">" redirection for exec-out screencap (corrupts PNG).
# File is 2240x1080 RGB PNG.
```

---

## 4. Packages / processes / services

`pm list packages -3` → **EMPTY** (no user-installed apps). Total 57 packages, all AOSP + vendor.

```
/system/app/HomeUI/HomeUI.apk                       = com.baiyi.homeui.hshomeui   v1.7.6 uid 1000
/system/priv-app/SerialService/SerialService.apk    = com.baiyi.service.serialservice.serialdataservice v1.4.2 uid 1000
/system/priv-app/FactoryMode/FactoryMode.apk        = com.baiyi.app.factorymode
android.rockchip.update.service, com.android.providers.media(.module), systemui, … (AOSP)
```
No gallery / video player / media app exists on the device.

Running processes of interest (`ps -A`):
```
system  736  com.baiyi.homeui.hshomeui                       ← the UI/display app
system  1166 com.baiyi.service.serialservice.serialdataservice ← the HID daemon
system  185  surfaceflinger    system 230 android.hardware.graphics.composer@2.1-service
media   375  mediaserver       mediacodec 378 media.codec   381 media.swcodec
media   315  rockchip.hardware.rockit.hw@1.0-service        (Rockchip media framework)
system  458  system_server     root 350 adbd
```

### Who owns the data path (file descriptor proof)
```
for p in /proc/[0-9]*; do for f in $p/fd/*; do t=$(readlink $f); case "$t" in *hidg*) echo "$p $t";; esac; done; done
→ /proc/1166 /dev/hidg0 (deleted)
```
`SerialService` alone holds `/dev/hidg0` open (fd 65). HomeUI holds
`/system/app/HomeUI/HomeUI.apk`, `/dev/mali0`, `/dev/binderfs/*`, many dmabuf/gralloc fds.
HomeUI's class list contains `ISerialControl`, `IOnSerialDataCallback`,
`com.baiyi.homeui.hshomeui.FullScreenVideoView`, `HSMainActivity`, Glide, Gson, ExoPlayer-ish
`MediaPlayer` usage, `setDataSource`, `mediaName`, `basevideoPath`, `sdcard/pcMedia/`,
`sdcard/pcMediaPreset/`, `STATE_POST`, `waterBlockScreen`.

---

## 5. How the host talks to the device (transport)

**There is NO TCP on the device.** Proof:
```
$ adb reverse --list      → (empty)
$ adb forward --list      → (empty)
$ adb shell cat /proc/net/tcp /proc/net/tcp6   → header only, zero sockets
$ adb shell netstat -tlnp                      → no listening sockets
```
So the host's "TCP socket server on port 4244" mentioned in host logs is **host-internal only** —
it never reaches the device. The only USB functions bound are HID + adb:
```
/config/usb_gadget/g1/configs/b.1/
   f1 -> functions/hid.gs0        f2 -> functions/ffs.adb
   strings/0x409/configuration = "hid_adb"
   MaxPower=500  bmAttributes=...
/config/usb_gadget/g1/ idVendor=0x0b05 idProduct=0x1c76 bcdDevice=0x0310
   UDC=fe500000.usb  max_speed=super-speed-plus
functions/hid.gs0/: report_length=1024, protocol=0, subclass=0, dev=509:0
/sys/class/udc/fe500000.usb/state=configured, current_speed=**high-speed**, function=g1
getprop sys.usb.config = hid,adb ;  sys.usb.state = hid,adb ; persist.sys.usb.config = hid,adb
getprop sys.usb.controller = fe500000.usb ; sys.usb.configfs = 1 ; sys.usb.ffs.ready = 1
```
Other gadget functions exist but are **not** bound: ncm, uvc, midi, rndis, acm, audio_source,
accessory, ffs.ptp, ffs.mtp. (So no UVC/RNDIS/CDC-ACM network path is active.)

### HID frame protocol (reverse-engineered from `/sdcard/catchlog/log/hidserver_log.txt`, 47 MB)
- Fixed **1024-byte HID reports** on `/dev/hidg0`.
- Payload is an ASCII frame:
```
5A <b0> <b1> <command line>\r\n<Header=Value\r\n ... >\r\n\r\n<body> <checksumByte> 5A
```
Real samples (hex, from log):
```
RX (host→device) state push:
5A 03 25 "STATE all 1\r\n" "SeqNumber=1939\r\n" "Date=1793075338842\r\n" "ContentType=json\r\n"
        "ContentLength=712\r\n\r\n" {json} ... 38 5A
TX (device→host) ack:
5A 00 41 "1 200\r\n" "AckNumber=1940\r\n" "ContentLength=0\r\n" "ContentType=json\r\n\r\n" 38 5A
```
The checksum byte is the ASCII char before the trailing `5A` (e.g. `0x38` = "8"). The device
parses: `requestState` (STATE), `cmdType` (all), `version`, `SeqNumber`, `AckNumber`,
`ContentType` (json), `ContentLength`, `FileName`, `FileSize`, `ContentRange`, `Counter`, `Date`,
`msgId`. Device acks with `A1 200` and an increasing AckNumber.
The JSON state payload that selects screen content:
```json
{"temperature":"Celsius","waterBlockScreen":{"enable":true,"displayInSleep":true,"brightness":85,
 "id":{"id":"Customization","screenMode":"Full Screen","playMode":"Single",
       "media":["<filename in /sdcard/pcMedia or pcMediaPreset>", ...],
       "settings":{"titleColor":"#E5252B","contentColor":"#FFFFFF",
                   "filter":{"value":null,"opacity":100},"badges":[]},
       "sysinfoDisplay":["","","","","",""],"timeZone":"Asia/Shanghai"}},
 "spec":{"cpu":"AMD Ryzen 7 9700X","gpu":"NVIDIA GeForce RTX 5090"}}
```
Host also polls with `STATE all 1`; device answers `STATE_STATE {...pcinfo...}`.

---

## 6. On-device media pipeline and file layout

`/sdcard/` (root of scoped storage):
```
pcMedia/        2026-10-07_11-59-09-827.mp4  45,894,584 B   ← currently played custom clip
                Color_White.png 12,551 B ; QRcode-e7f21a0b-…jpg 115,553 B
pcMediaPreset/  RYUO_IV_HW_Info_01.mp4 10,677,244 B
                RYUO_IV_HW_Info_02.mp4  3,280,373 B
                RYUO_IV_HW_Info_03.mp4  2,449,132 B
                RYUO_IV_HW_Info_04.mp4  3,695,986 B
                RYUO_IV_HW_Info_05.mp4  4,306,098 B
catchlog/log/   hidserver_log.txt 47,772,884 B ; home_log.txt 1,596,403 B
```
`/sdcard/pcMediaFilter` and `/sdcard/update.zip` **do not exist**.
`/data/local/tmp` was empty originally.

Playback logs (`home_log.txt`) show the loop behaviour:
```
HSMainActivity: ---VideoLog---main_video1.结束播放:非单个循环播放：
HSMainActivity: --handler--MSG_HANDEL_MEDIA
HSMainActivity: setLayout1Path--sdcard/pcMedia/2026-10-07_11-59-09-827.mp4
HSMainActivity: ---VideoLog---释放资源:2131230988
HSMainActivity: ---VideoLog---main_video1.setVideoPath:sdcard/pcMedia/2026-10-07_11-59-09-827.mp4
HSMainActivity: ---VideoLog---main_video1.视频准备完毕,可以进行播放:false
```
Logcat shows the decoding stack:
```
D/rockit RTMediaPlayer {setDataSource :143} setDataSource(fd=8, offset=0, length=45894584) called
D/rockit RTMediaPlayer {setVideoSink :408} setVideoSink(0x…)
D/rockit video chain: chain(demux/avcodec/videosink), codec(name=rk_mpp/bitrate=9815k/1920x960x@30.03)
D/rockit RTMediaSync V:… M:… (frame pacing)
```
Media formats the vendor uses (probed with the vendor's own ffmpeg):
```
pcMedia/2026-10-07_…mp4 : h264 High (avc1), yuv420p, 1920x960, 30.03 fps, 9815 kb/s, 37.40 s, encoder Lavf58.45.100
pcMediaPreset/…02.mp4   : h264 High (avc1), yuv420p, 1920x926 (DAR 960:463), 30 fps, 2201 kb/s, 11.90 s
```
Fallback when no config is present, HomeUI plays `/system/media/video/standby.mp4`
(observed as `standbyPath.setVideoPath:/system/media/video/standby.mp4` → grey standby layout).

**Encoder is shipped with the host app** (this is how ASUS makes custom media):
`C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\ffmpeg.exe` (ffmpeg 6.0-essentials_build).
The app dir also contains `gif5.dll`, `MediaStation.dll`, `opencv_world430.dll`,
`opencv_videoio_ffmpeg430_64.dll`, `avcodec-58.dll`, etc.

---

## 7. ✅ CONFIRMED: displaying arbitrary video on the panel (no host app needed)

Mechanism: HomeUI calls `setVideoPath()` again on every loop completion, so it re-opens the file
each cycle. Overwriting the bytes of the file that is currently in the active playlist swaps the
displayed content within one loop.

```powershell
$root='C:\Program Files\ASUS Info Hub - ROG RYUO IV'; $env:PATH="$root;$root\bin;$env:PATH"
$adb="$root\bin\adb.exe"; $S='TC26011200324725'
$TGT='/sdcard/pcMedia/2026-10-07_11-59-09-827.mp4'     # file currently in the state media[] list

# 1) backup original (verified md5 f1e02290ddd84670881ebd7afd58924b)
& $adb -s $S shell "cp '$TGT' /data/local/tmp/orig_playing_backup.mp4"

# 2) produce a compatible clip with the vendor's ffmpeg
& "$root\bin\ffmpeg.exe" -y -f lavfi -i "color=c=0x0a1020:s=1920x960:r=30:d=12" `
   -vf "drawtext=fontfile=C\:/Windows/Fonts/arialbd.ttf:text='CUSTOM CONTENT':fontsize=120:fontcolor=white:x=(w-text_w)/2:y=h/2-220" `
   -c:v libx264 -profile:v high -level 4.1 -pix_fmt yuv420p -g 30 -crf 18 -movflags +faststart custom.mp4

# 3) overwrite the playing file
& $adb -s $S push custom.mp4 $TGT

# 4) wait ≤ one loop (≤38 s for the 37.4 s clip) then screenshot to verify
& $adb -s $S shell 'screencap -p /data/local/tmp/s.png'
& $adb -s $S pull /data/local/tmp/s.png screen_after.png
```
Result — **verified on the physical screen** (device-side screencap, 2240×1080):
- `screen_now.png` before: ROG eye animation
- `screen_after.png` after: my clip, reading "CUSTOM CONTENT / frame 168 / ADB INJECT TEST"
- logcat during: `setDataSource(fd=8, offset=0, length=560972)` = exactly my file size.

Restore:
```powershell
& $adb -s $S shell "cp /data/local/tmp/orig_playing_backup.mp4 '$TGT'"
# or: & $adb -s $S push current_playing.mp4 $TGT     (identical copy kept on host)
```
### 7b. Measured refresh rate of the swap technique (no host app involved)
A short clip makes HomeUI re-open the file sooner, so swapping the file gives a rough
"frame sequence" player. Measured with a 1.2 s clip:
```
home_log setLayout1Path at 12:39:44, :45, :47, :48, :49, :51   → loop turnaround ≈ 1.2–2.0 s
⇒ ≈ 0.7–0.8 file swaps / second  (≈0.7 fps ceiling for arbitrary frames this way)
```
Each swap is a plain file overwrite (no panic) and renders correctly: `swap_A.png` (red FRAME A),
`swap_B.png` (green FRAME B). Use this only as a low-rate fallback — it is NOT video streaming.

Constraints found empirically:
- Container/codec: mp4 / H.264 High, `yuv420p`, ~1920x960, 30 fps decodes reliably.
- 2240×1080 H.264 is **not** decodable in HW (AVC decoder max 1920×1088); the app scales the
  1920×960/1080 frame to the panel. HEVC can go up to 4096×2160 if pixel-exact is needed.
- Only files named in the state `media[]` array get played; dropping a new file in pcMedia does
  not display it by itself (the list comes from the host over HID).

---

## 8. ❌ FIFO / pipe streaming — DO NOT USE (kernel panic)

Test (as requested by Lead):
```
adb shell "rm -f $TGT; mkfifo $TGT"                  # works: prw-rw---- u0_a40 media_rw
adb shell "nohup sh -c 'nc -l -p 18082 | cat > $TGT' >/dev/null 2>&1 &"
# host: ffmpeg -re -f lavfi -i testsrc2=size=1920x960:rate=30 -c:v libx264 -preset ultrafast
#       -tune zerolatency -pix_fmt yuv420p -f mpegts tcp://127.0.0.1:18081   (with adb forward)
```
Outcome: the device **hard-rebooted**. `getprop persist.sys.boot.reason.history` gained
`kernel_panic,bug,1793075731`. Console (pstore) evidence, saved as `console-ramoops-0.txt`:
```
[ 2397.596527] kernel BUG at lib/list_debug.c:61!
[ 2397.596535] Internal error: Oops - BUG: 0 [#1] PREEMPT SMP
[ 2397.596…] list_del corruption. prev->next should be ffffff800608a528, but was ffffff800bf6cc80
             Call trace:
               __list_del_entry_valid+0xb8/0xcc
               cd_forget+0x2c/0x70
               evict+0x15c/0x274
               iput+0x22c/0x270
               dentry_unlink_inode+0x148/0x168
               __dentry_kill+0x100/0x1c8
               dentry_kill+0xc0/0x104
               dput+0x94/0xf8
               __fput+0x160/0x224
               ____fput+0x10/0x1c
               task_work_run+0x8c/0x178
               do_exit+0x1b0/0x814
[ 2398.084359] Kernel panic - not syncing: Oops - BUG: Fatal exception
[ 2399.308906] Rebooting in 5 seconds..
```
⇒ MediaPlayer/rockit does not handle a non-seekable fd, and this vendor 5.10.157 VFS has a list
corruption bug on the FIFO fput path. **FIFO is not viable. Not retried.**

Recovery performed (all additive/reversible):
```
adb shell "rm -f /data/media/0/pcMedia/2026-10-07_11-59-09-827.mp4"    # remove FIFO
adb shell "cp /data/local/tmp/orig_playing_backup.mp4 /data/media/0/pcMedia/2026-10-07_11-59-09-827.mp4"
adb shell "chown u0_a40:media_rw …; chmod 660 …"                      # match original ownership
# verified md5 f1e02290ddd84670881ebd7afd58924b, size 45,894,584
```

---

## 9. ✅ adb reverse / forward and measured USB TCP throughput

```
$ adb reverse tcp:18080 tcp:18080        # device -> host
$ adb reverse --list
  UsbFfs tcp:18080 tcp:18080
$ adb forward tcp:18081 tcp:18082        # host -> device
$ adb forward --list
  TC26011200324725 tcp:18081 tcp:18082
```
Throughput test (host = .NET TcpListener counting bytes; device = toybox nc):
```
adb shell 'time dd if=/dev/zero bs=65536 count=1600 2>/dev/null | nc 127.0.0.1 18080'
host: received_bytes=104857600  seconds=4.014  MBps=24.92
device: real 3.88s  user 0.04s  sys 0.63s
```
⇒ **24.92 MB/s ≈ 200 Mbit/s** device→host over the same USB cable that carries ADB.
Latency is low (single USB 2.0 high-speed hop through adbd). This is plenty for 1080p60
(≈4–12 Mbit/s typical) — the recommended streaming transport.

`toybox nc` supports `-l -p PORT`, `-f FILE`, `-w SECS`, `-U` (unix). `curl`/`wget`/`ffmpeg`
are **not** present on the device; `nc` and `toybox` are at `/system/bin/`.

---

## 10. APK install capability — ✅ permitted

```
$ adb shell 'pm install-create -S 1048576'
  Success: created install session [526034645]
$ adb shell 'pm install-abandon 526034645'
  Success
$ adb shell 'settings get global verifier_verify_adb_installs'   → null
$ adb shell 'settings get global package_verifier_enable'        → null
```
⇒ We can sideload an APK as root (no verifier blocking, debuggable device). Host currently has
**no** Android build tooling (`java`, `aapt2`, `aapt`, `apksigner`, `gradle`, `ANDROID_HOME` all
missing), so a sideloaded player must be a **prebuilt APK** (mpv / VLC / ExoPlayer demo / custom).

No installed activity resolves video intents today:
```
am start -a android.intent.action.VIEW -d file:///sdcard/pcMedia/x.mp4 -t video/mp4
  → Error: Activity not started, unable to resolve Intent
cmd package query-activities -a android.intent.action.VIEW -t video/mp4 → No activities found
```

---

## 11. Recovering the host config after a device reboot (important operational note)

After the panic reboot, HomeUI started but showed the grey **standby** layout because the host's
`STATE_POST` (waterBlockScreen config) had been received while HomeUI was initialising and was
lost. The room-fixed recipe (no host interaction needed):
```
# force the host app to see the device disconnect/reconnect → it re-pushes STATE_POST
adb shell 'nohup sh -c "sleep 1; echo > /config/usb_gadget/g1/UDC; sleep 4; echo fe500000.usb > /config/usb_gadget/g1/UDC" >/dev/null 2>&1 &'
```
After ~10 s the device re-enumerated (adb transport_id changed 2→3), a new `STATE_POST` arrived at
12:37:50 and playback resumed:
```
HSMainActivity: ---VideoLog---main_video1.setVideoPath:sdcard/pcMedia/2026-10-07_11-59-09-827.mp4
rockit: setDataSource(fd=8, offset=0, length=45894584)
```
Screenshot `screen_restored.png` = the user's original clip playing again.
(Alternative: restart the ASUS Info Hub app on the host or change any screen setting.)

---

## 12. Codec capability matrix (RK3562)

`/vendor/etc/media_codecs_c2_base.xml` limits and `/vendor/etc/media_codecs_performance.xml`
measured rates:
```
c2.rk.avc.decoder   video/avc  size 2x2 .. 1920x1088  fps 1..60  blocks/s 489600
                    measured: 320x240 500-560, 720x480 480-520, 1280x720 310-315, 1920x1080 164 fps
c2.rk.hevc.decoder  video/hevc size 2x2 .. 4096x2160  fps 1..60  blocks/s 1966080
                    measured: 1280x720 200-203, 1920x1080 175-180, 3840x2160 30-40 fps
c2.rk.vp9.decoder   video/x-vnd.on2.vp9  measured 1920x1080 172-197, 3840x2160 30-40
c2.rk.avc.encoder   video/avc  max 1920x1088, bitrate 1..10000000
                    measured: 1920x1080 82-84 fps (fast!)
software fallbacks: c2.android.avc.decoder (max 1920x1080, 51 fps @1080p),
                    c2.android.hevc.decoder, c2.android.av1.decoder, vp8/vp9/mpeg2/mpeg4…
```
⇒ For streaming: **H.264 ≤1920×1088** (HW, very fast) or **H.265 ≤4096×2160** (HW; 2240×1080 OK).
Panel is 2240×1080, so 1920×1080/1920×960 is upscaled; HEVC 2240×1080 gives pixel-exact.

---

## 13. Risks, invariants, rollback

**Do not:**
1. Use a FIFO/pipe/socket as the media path ⇒ kernel panic (proven).
2. Modify `/system`, `/vendor`, `/product` (read-only ext4 on dm-*; changing requires
   `adb disable-verity`/remount — out of scope, never done).
3. Delete vendor files. `/sdcard/pcMediaPreset/*` are vendor presets — leave them.

**Safe / reversible:**
- `/data/local/tmp/*` (root), `/sdcard/pcMedia/<active file>` with backup + restore, `/sdcard` test files.
- `adb reverse/forward`, `pm install-create/abandon`, USB gadget re-bind (`UDC`), `am force-stop`
  /`am start` HomeUI, `am broadcast -a android.intent.action.BY_PC_ON`.

**Current device state after this investigation (all verified):**
- `/sdcard/pcMedia/2026-10-07_11-59-09-827.mp4` = original, md5 `f1e02290ddd84670881ebd7afd58924b`,
  45,894,584 B, owner u0_a40:media_rw, mode 660, playing normally.
- Original backup: on device `/data/local/tmp/orig_playing_backup.mp4`, on host `current_playing.mp4`.
- No FIFOs left (`/data/local/tmp/test.fifo` removed). Uptime/health normal, HomeUI resumed.
- Host adb mappings from the tests were removed at the end (`reverse --remove-all`,
  `forward --remove-all`); re-add with `adb reverse tcp:18080 tcp:18080` if needed.
- Test scripts/pngs remain in `/data/local/tmp` (t1.sh, t2.sh, s*.png) — harmless.
- Final visual state verified: `screen_final.png` = original animation playing, md5 matches.

**Hardware/side effects to be aware of:** a panic reboot resets the host-provided screen config
(§11 recipe recovers it); HomeUI is the HOME app, so `am force-stop` briefly blanks the screen
before it restarts.

---

## 14. Artifacts produced (all under `D:\ROG longwang4\device-notes\`)

| File | What |
|---|---|
| `findings.md` | this document |
| `screen_now.png` | panel BEFORE: ROG eye animation (2240×1080) |
| `screen_after.png` | panel AFTER custom video injection: "CUSTOM CONTENT / frame 168 / ADB INJECT TEST" |
| `screen_fifo.png` / `screen_recovered.png` / `screen_fix2.png` | black + standby states after the panic reboot |
| `screen_restored.png` | panel back to the original clip (final state) |
| `screen_final.png` | FINAL state: user's original clip playing again after all tests |
| `swap_A.png`, `swap_B.png` | proof of 0.7 fps file-swap frames (red FRAME A / green FRAME B) |
| `custom_test.mp4`, `custom_frame.png` | my generated 1920×960 H.264 test clip + frame |
| `frame_A/B/C.mp4` | 1.2 s colour clips for the swap-rate test |
| `current_playing.mp4` | host copy of the original pcMedia clip |
| `preset02.mp4` | host copy of RYUO_IV_HW_Info_02.mp4 |
| `console-ramoops-0.txt` | full pstore kernel log of the FIFO panic (240,962 B) |
| `apk\HomeUI.apk`, `apk\SerialService.apk` | pulled vendor APKs (+ `.strings.txt` dumps) |
| `apk\unz\` | extracted APK contents (if produced) |
| `pulled\_vendor_etc_media_codecs_c2_base.xml` | codec limits |
| `pulled\_vendor_etc_media_codecs_performance.xml` | measured codec frame rates |
| `pulled\_system_build.prop`, `pulled\_vendor_build.prop` | build props |
| `pulled\proc_cmdline.txt`, `pulled\dmesg_tail.txt` | kernel cmdline / dmesg tail |

On-device logs worth mining further (as root, read directly):
`/sdcard/catchlog/log/hidserver_log.txt` (47 MB, full HID protocol history incl. every frame
header) and `/sdcard/catchlog/log/home_log.txt` (1.6 MB, HomeUI behaviour).

---

## 15. Command quick reference

```powershell
$root='C:\Program Files\ASUS Info Hub - ROG RYUO IV'; $env:PATH="$root;$root\bin;$env:PATH"
$adb="$root\bin\adb.exe"; $S='TC26011200324725'

& $adb devices -l                       # must show TC26011200324725  device
& $adb -s $S shell id                   # uid=0(root) context=u:r:su:s0
& $adb -s $S shell 'wm size; wm density'        # 2240x1080 / 160
& $adb -s $S shell 'screencap -p /data/local/tmp/s.png'
& $adb -s $S pull /data/local/tmp/s.png out.png
& $adb -s $S logcat -d -v brief | Select-String 'setDataSource|setVideoPath|HSMainActivity'
& $adb -s $S shell 'tail -5 /sdcard/catchlog/log/home_log.txt'
# display custom video (proven):
& $adb -s $S push custom.mp4 /sdcard/pcMedia/2026-10-07_11-59-09-827.mp4
# recover host config after reboot:
& $adb -s $S shell 'nohup sh -c "sleep 1; echo > /config/usb_gadget/g1/UDC; sleep 4; echo fe500000.usb > /config/usb_gadget/g1/UDC" >/dev/null 2>&1 &'
```
