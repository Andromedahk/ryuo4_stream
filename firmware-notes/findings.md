# ASUS ROG RYUO IV SLC 360 ARGB — firmware static analysis

Analyst: firmware-re (teammate). Scope: static analysis of the official firmware ZIP only.
No device writes, no flashing. All artifacts under `D:\ROG longwang4\firmware\`.

## 1. Input artifact

| item | value |
|---|---|
| file | `D:\ROG longwang4\firmware\ROG_RYUO_IV_Series_Firmware_File.zip` |
| size | 512,187,047 B |
| SHA-256 | `6F2A2BD9C1C029D6FD03FD7989DF587B95E7960E58B9C279DCCC39A8AA370D1E` |
| format | Android **block-based OTA** (Rockchip/`otapackage`), 34 entries, total uncompressed 537,007,731 B |
| build | `rockchip/cm16/cm16:13/TQ3C.230805.001.B2/eng.server.20251229.092713:user/release-keys` |
| device | `cm16`, sdk 33 (Android 13), build date 2025-12-29, `post-timestamp=1766971588` |

Members (see `extracted\`, inventory `firmware\zip-inventory.json`):

- Boot chain: `RKLoader.bin` (455,104 B, magic `LDR ` = Rockchip USB loader), `uboot.img` (4 MiB, FIT image), `boot.img` (35,581,952 B), `dtbo.img` (443 B, one 379-B overlay).
- Dynamic partitions (Android super), as brotli + transfer.list: `system` (876,687,360 B), `vendor` (266,530,816), `product` (19,742,720), `system_ext` (48,095,232), `vendor_dlkm` (28,098,560), `odm` (679,936), `system_dlkm`/`odm_dlkm` (262,144 each). Sizes match `dynamic_partitions_op_list` exactly.
- `META-INF\com\google\android\{update-binary,updater-script,otacert}`, `META-INF\com\android\metadata`.
- `updater-script`: assert device `cm16`, then `block_image_update()` for 8 logical partitions, then **raw `package_extract_file` writes of `boot.img`→`/dev/block/by-name/boot`, `uboot.img`→`uboot`, `dtbo.img`→`dtbo`**. No vbmeta image is shipped.

Note: the `.new.dat.br` payloads decompress to **plain raw ext4 images** (not Android sparse; `magic` check failed, ext4 superblock `53 ef` at 0x438). Decompressed to `unpacked\*.new.dat`, mounted read-only by my own ext4 reader.

## 2. SoC / OS / boot

- SoC: **Rockchip RK3562** (`ro.soc.model=RK3562`, `ro.board.platform=rk3562`, `ro.vendor.sdkversion=rk3562_ANDROID13.0_MID_V1.0`), 4× Cortex-A53 (`arm,cortex-a53` cpu@0..3), Mali GPU, low-RAM device config (`ro.config.low_ram=true`, zram 75% swap).
- Serial console addresses: DT `/chosen bootargs = "earlycon=uart8250,mmio32,0xff210000 console=ttyFIQ0"` ⇒ UART at **0xff210000** (RK3562 UART2), console `ttyFIQ0`.
- Kernel: `Linux version 5.10.157+ (server@server-MS-7E24) #57 SMP PREEMPT Mon Dec 29 09:25:50 CST 2025`, aarch64 (arm64 Image, uncompressed, 33,189,896 B), clang 14.0.6 / LLD.
- U-Boot: `U-Boot 2017.09 (Dec 29 2025 - 09:24:24 +0800)`, FIT `"FIT Image with ATF/OP-TEE/U-Boot/MCU"`, `board=evb_rk3562`, `bootcmd=boot_android ... boot_fit`.
- DTB (in `boot.img` second stage = Rockchip **RSCE resource image**): `compatible = "rockchip,rk3562-evb2-ddr4-v10", "rockchip,rk3562"`, `model = "Rockchip RK3562 EVB2 DDR4 V10 Board"` — the product DT is the EVB reference DT; ASUS customization is in kernel drivers + userspace.
- boot.img cmdline: `console=ttyFIQ0 firmware_class.path=/vendor/etc/firmware init=/init rootwait ro loop.max_part=7 androidboot.console=ttyFIQ0 androidboot.wificountrycode=CN androidboot.hardware=rk30board androidboot.boot_devices=ff870000.mmc androidboot.selinux=permissive buildvariant=user`
- Partitions (`vendor/etc/fstab.rk30board`): logical `system/vendor/odm/product/system_ext/*_dlkm`; physical `boot`, `cache`, `metadata`, `misc`; `/dev/block/by-name/userdata` = **f2fs, fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized, metadata encryption** (data at rest encrypted, `reservedsize=128M`).

## 3. Display / panel (exact)

From `unpacked\dtb\dtb_00001600.dtb`, node `/dsi@ffb10000/panel@0` (`simple-panel-dsi`, `oled-backlight`):

- **Resolution: hactive = 1080 (0x438) × vactive = 2240 (0x8c0)** — 1080×2240 AMOLED.
- `clock-frequency = 0x90F5600` = 152,000,000 Hz; porches hfp 13 / hsync 6 / hbp 8, vfp 28 / vsync 8 / vbp 8 → htotal 1107, vtotal 2284 ⇒ **≈60.1 Hz**.
- `dsi,lanes = 4`, `dsi,format = 0` (RGB888), `dsi,flags = 0xa03`, `oled-scale = 13`, `oled-convert = 1`.
- Panel init sequence present (`panel-init-sequence = 15 00 02 fe 26 15 00 02 a4 1f …` DCS writes), `panel-bl-sequence = 39 00 03 51 0d bb`, PWM backlight (`pwms`, 100 brightness levels, default 200).
- `enable-gpios`/`reset-gpios` on a Rockchip pinctrl; no touch controller node in DT (screen likely non-touch input).
- Userspace: `ro.surface_flinger.primary_display_orientation=ORIENTATION_90`, `ro.sf.lcd_density=160`, `sf.power.control=2073600`; `vendor/etc/display_settings.xml` declares display `local:1` with `forcedDensity="240"`, `shouldShowSystemDecors=false`.

## 4. Video / graphics pipeline

`App/image/video → SurfaceFlinger (HWC2) → VOP2 (rockchip,rk3562-vop @0xff400000) → MIPI DSI (rockchip,rk3562-mipi-dsi @0xffb10000) → 4-lane DSI PHY → panel`. DRM service `rockchip.drmservice`; kernel has RGA3 (`rockchip,rga3_core0/1`), VPU v2 decoder/encoder nodes, GPU devfreq `ff320000.gpu`.

Media: `vendor/etc/media_codecs.xml` only includes Google audio/video + C2 (`libcodec2_rk_component.so`) — hardware decode via Rockchip MPP/Codec2; services `android.hardware.media.c2@1.1-service`, `...media.omx@1.0-service`, `libsfplugin_ccodec_utils.so`. Preloaded content: `/system/media/video/Screensaver.mp4` (18.4 MB), `Screensaver_left.mp4` (16.3 MB), `Screensaver_right.mp4` (8.6 MB).

No custom ASUS "virtual display"/UVC content path in the current USB config: the gadget *can* expose UVC (`functions/uvc.gs6`, 720p/960p MJPEG+uncompressed) but it is **not** in the active composition.

## 5. How the PC talks to the device (content/control path)

- USB gadget (`vendor/etc/init/hw/init.rk30board.usb.rc`): default `idVendor 0x2207` (Rockchip); for `acm`/`acm,adb`/`hid`/`hid,adb` it writes **`idVendor 0x0b05, idProduct 0x1c76`**, manufacturer `"ASUS"`, product `"ROG RYUO IV Standard"` — matches your enumerated `VID_0B05&PID_1C76`.
- Active config: `persist.sys.usb.config=hid,adb` → function `hid.gs0` (vendor HID, `report_length 1024`, `subclass 0`, `protocol 0`) + `ffs.adb`. `init.rk3562.rc` does `chmod 0666 /dev/hidg0` and `chmod 0666 /dev/ttyGS0`.
- **`/system/lib/libhid_port.so` + `lib64/libhid_port.so`**: JNI shim `Java_android_1hidport_1api_HidPort_{open,read,write,close}` around `/dev/hidg0` (select/read/write, 1024-B reports). This is the PC↔device data channel used by the vendor app.
- **`/system/priv-app/SerialService/SerialService.apk`** = `com.baiyi.service.serialservice.serialdataservice`, v1.4.2, `sharedUserId=android.uid.system` (runs as system UID; holds SET_TIME / SYSTEM_ALERT_WINDOW / WRITE_SETTINGS). Manifest intents: `android.intent.action.BY_PC_ON`, `android.intent.action.BY_PC_OFF`, `com.baiyi.action.systemupdate.check.result`; components `SerialService`, `PCProgramStateReceiver`, `MainActivity`. Its DEX contains the `libhid_port` references **and** the AIO-cooler sysfs paths and the product-variant table `ROG_RYUO_IV_Standard`, `Ryuo IV Standard`, `Ryuo IV MIKU ACC`, `Ryuo IV MIKU WW`. ⇒ SerialService is the on-device bridge: PC state (on/off) from HID → cooler/UI, plus a system-update check path.
- **Home UI**: `/system/app/HomeUI/HomeUI.apk`, package `com.baiyi.homeui.hshomeui` v1.7.6, CATEGORY_HOME launcher (Baiyi = Chinese ODM). No ASUS-branded APK exists in the OTA; any further "Ryuo" app lives in `/data` (not shipped in this package).
- **Cooler MCU interface (ASUS kernel drivers, sysfs)**: `/sys/bus/i2c/drivers/aio_cooler/{firmware_version,hardware_revision,pump_configuration,harness_version,status,hw_address,pwm,rpm,inlet_outlet_temperature,inlet_temperature_only,outlet_temperature_only,control_source}` and `/sys/bus/platform/drivers/lcd_fan/speed`; also `/sys/system_monitor/system_status`. Vendor SELinux policy explicitly allows **untrusted_app_25/27/33** read/write on `sysfs_aio_cooler` and `sysfs_lcd_fan` (types defined in `vendor/etc/selinux`), and `/dev/hidg.*` is labeled `hid_device`. ⇒ Any app on the device can read pump RPM/temps and drive pump/fan PWM without root.

## 6. Debug / root surface

| item | evidence |
|---|---|
| ADB on by default, already key-authorized on your host | `persist.sys.usb.config=hid,adb`; `ffs.adb` function; adbd = `/system/apex/com.android.adbd/bin/adbd` (AOSP, adb-key auth) |
| SELinux **permissive** | `androidboot.selinux=permissive` in boot cmdline |
| Serial console configured | `console=ttyFIQ0`, `androidboot.console=ttyFIQ0` (RK FIQ debugger; physical UART pads needed, typical 1,500,000 8N1) |
| `adb root` / `su` | **not available**: `ro.build.type=user`, `ro.debuggable` unset, no `su` binary anywhere in the images, no `adb_keys` file shipped |
| `/data` encryption | f2fs + FBE (aes-256-xts) + metadata encryption ⇒ offline data readout not possible without keys |
| dd-based flash helper | `/vendor/bin/flash_img.sh`: `dd if=$(getprop vendor.flash_if_path) of=$(getprop vendor.flash_of_path)`, sets `flash.success 1` — attacker/root primitive if props are writable |
| OTA updater app | `/system/app/RKUpdateService` (ROCKCHIP update), `ro.rk.flash_enable=true` |
| Ramoops / pstore | `reserved-memory/ramoops@110000` in DT (crash logs to memory) |

## 7. Signature / verified-boot status — **weak**

- **OTA package and recovery trust the AOSP public test key.** `META-INF/com/android/otacert` and `/system/etc/security/otacerts.zip → testkey.x509.pem` are byte-identical (both 1,440 B, SHA-256 `10A7B524D14750A12B44472524340DF6B300F1B648FB63C3B17A161BDE1E08D7`; issuer `CN=Android, O=Android, E=android@android.com`, serial `92a528c773d7a141`, RSA-2048, SHA256-RSA). The matching private key is public (AOSP `build/target/product/security/testkey`), so **a self-built OTA ZIP can be signed so that this recovery accepts it**.
- **No Android Verified Boot**: `boot.img` has no `AVBf` footer (last 139,264 B are zero), no `vbmeta` partition/image is shipped, and U-Boot contains the "`Not AVB images, AVB skip`" path plus `androidboot.verifiedbootstate=orange` (unlocked).
- `uboot.img` does carry Rockchip `libavb` and both branches: "`Vboot=1, SecureBoot enabled, AVB verify`" / "`Vboot=0, AVB images, AVB verify`". `Vboot` is a device-side flag (OTP/secure storage); typical consumer units are `Vboot=0`. Must be confirmed on the live device before attempting a flash.
- Recovery/loader chain available: `RKLoader.bin` + Rockchip **MaskROM/Loader USB mode (VID 0x2207)** — the standard `rkdeveloptool`/`RKDevTool` path for `read`/`write` of `parameter`, `uboot`, `boot`, `super`, `userdata`, independent of the OTA signature.

## 8. Feasibility of custom firmware

- **High**, via either (a) testkey-signed OTA applied through `RKUpdateService`/recovery, or (b) Rockchip Loader/MaskROM + `rkdeveloptool` writing `boot`/`uboot`/`super` directly, or (c) booting a modified boot image to get a root shell (permissive SELinux makes `init`/`adbd` patching easy).
- Blockers/risks: secure-boot (`Vboot`) fuse state unknown; `/data` FBE means a custom build keeps user data but a factory reset/format is needed if keys change; panel/DSI and cooler drivers are **out-of-tree ASUS/RK additions** in this exact kernel, so a from-scratch kernel would need those drivers (better: patch the shipped `boot.img`/`vendor_dlkm`, not rebuild).
- Safest first move: **read-only** `rkdeveloptool read` (or adb `dd` after root) of `boot`, `uboot`, `misc`, `parameter` to snapshot the unit, and `getprop ro.boot.verifiedbootstate`/`Vboot` state — before any write.

## 9. Known gaps / next steps

1. Live-device recon (`adb shell`, no writes): `getprop | grep -Ei 'verifiedboot|secure|serialno|product.version'`; `cat /proc/cmdline`; `pm list packages -3`; `dumpsys activity activities | head`; `pm list packages | grep -Ei 'baiyi|ryuo|asus|rog'`; `cmd package resolve-activity -c android.intent.category.HOME`; `dumpsys SurfaceFlinger --display-id`; `ls -l /dev/hidg* /dev/ttyGS*`; `cat /sys/bus/i2c/drivers/aio_cooler/{status,firmware_version,rpm,inlet_temperature_only,outlet_temperature_only,control_source}`; `ls /sys/bus/i2c/devices`.
2. Identify/recover the PC-facing screen app: it may live in `/data/app` (not in the OTA). `pm path`, then `adb pull` the APK from the live device (read-only) and decompile locally.
3. HID protocol recovery: capture USB (`USBPcap`/Wireshark) while the official ASUS software drives the cooler, then decode the 1024-B report layout; correlate with `libhid_port.so` usage.
4. DEX decompilation blocked statically: no JADX/JDK-in-REA on this host (REA `inspect_android_package` needs a caller-supplied JADX MCP JAR). JDK 21 is already unpacked at `D:\ROG longwang4\tools\jdk-21.0.12.1+1`; a local JADX download would unlock full source recovery of `HomeUI.apk` / `SerialService.apk` / `RKUpdateService.apk`.
5. Custom content path (recommended, non-destructive): since adb is already authorized, install a replacement HOME app (`pm install` + `pm set-home-activity`) or use `am start`/intents to display custom images/videos; no firmware modification required for the "show my own content on the panel" goal.

## 10. Reproduction artifacts

Tooling written (Node, no external deps): `firmware\scripts\{zipls.js,brdec.js,sparse2raw.js,bootimg.js,findfdt.js,fdt.js,ext4.js,strings.js,binpeek.js}`.
Outputs: `firmware\extracted\` (zip members), `firmware\unpacked\` (raw ext4 `*.new.dat`, `raw\*.img`, `boot\kernel.bin|ramdisk.bin|second.bin`, `dtb\dtb_00001600.dtb`, `files\` pulled files & APKs, `idx-*.json` full file indexes).
