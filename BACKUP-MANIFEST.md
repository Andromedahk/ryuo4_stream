# 大文件备份清单 (BACKUP-MANIFEST)

本仓库只提交脚本 / 文档 / 笔记等小文件。以下大文件被 `.gitignore` 排除，未纳入 git。

| 项目 | 值 |
|---|---|
| 排除文件数 | 38523 |
| 排除总大小 | 6.8 GB |
| 清单 CSV | `_backup/big-files-manifest.csv` (本地，未入库) |
| 备份 zip | `_backup/big-files-backup.zip` (本地，未入库) |

## 按目录统计

| 顶层目录 | 文件数 | 大小 (MB) |
|---|---:|---:|
| `tools/` | 27262 | 2739.5 |
| `firmware/` | 2118 | 2276.6 |
| `firmware-build/` | 7 | 1664.9 |
| `host-re/` | 9072 | 158.3 |
| `device-notes/` | 10 | 63.6 |
| `stream_test/` | 43 | 53.4 |
| `hls_test/` | 7 | 9.3 |
| `__pycache__/` | 3 | 0 |
| `exe/` | 1 | 0 |

## 大于 50 MB 的文件

| 大小 (MB) | 路径 |
|---:|---|
| 836.07 | `firmware-build/system.img` |
| 836.07 | `firmware/unpacked/system.new.dat` |
| 543.26 | `tools/ghidra_12.1.4_PUBLIC_20260921.zip` |
| 488.46 | `firmware/ROG_RYUO_IV_Series_Firmware_File.zip` |
| 479.86 | `firmware-build/ROG_RYUO_IV_Streaming_Firmware_MOD.zip` |
| 356.28 | `firmware/extracted/system.new.dat.br` |
| 347.68 | `firmware-build/system.new.dat.br` |
| 254.18 | `firmware/unpacked/vendor.new.dat` |
| 195.57 | `tools/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip` |
| 146.47 | `tools/android-sdk/cmdline-tools.zip` |
| 134.36 | `tools/jdk-21.0.12.1+1/lib/modules` |
| 89.56 | `tools/node-v24.22.1-win-x64/node.exe` |
| 79.94 | `firmware/extracted/vendor.new.dat.br` |
| 53.72 | `tools/ghidra_12.1.4_PUBLIC/Extensions/Ghidra/ghidra_12.1.4_PUBLIC_20260921_Jython.zip` |
| 51.29 | `tools/ghidra_12.1.4_PUBLIC/docs/GhidraAPI_javadoc.zip` |
| 50.55 | `tools/jdk-21.0.12.1+1/lib/src.zip` |

## 说明

- `tools/`：JDK、Ghidra、Android SDK、Node 等第三方工具链，可从官方重新下载，无需备份。
- `firmware/`、`firmware-build/`：官方固件包与解包/重打包产物，体积最大。
- 备份 zip 与全量清单均在 `_backup/` 目录，已加入 `.gitignore`。

