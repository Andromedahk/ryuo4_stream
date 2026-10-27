# REA MCP 安装与暂停报告

日期：2026-10-27（Asia/Shanghai）

## 1. 已完成

| 项目 | 结果 |
|---|---|
| Node.js | 24.22.1，解压至 `D:\ROG longwang4\tools\node-v24.22.1-win-x64` |
| REA CLI | `rea-agents` 6.8.0，安装于 `D:\ROG longwang4\tools\npm-global` |
| DeepSeek Harness MCP | 已写入 `C:\Users\ZZZX\.dsh\cordis.patch.yml`，serverName=`rea` |
| REA Skill | 已安装 `reverse-engineer-anything`（version 49，229 tools）至 `C:\Users\ZZZX\.agents\skills` |
| Ghidra | 12.1.4，位于 `D:\ROG longwang4\tools\ghidra_12.1.4_PUBLIC` |
| JDK | Temurin 21.0.12.1，位于 `D:\ROG longwang4\tools\jdk-21.0.12.1+1` |
| 深度分析 Provider | `REA_ANALYSIS_PROVIDER=ghidra`，doctor 全部健康 |

`rea doctor --client dsh` 结果：`healthy: true`。Ghidra 的安装、版本、headless、Windows x64 原生反编译器、JDK 21、原生权限控制均通过检查。

## 2. MCP 注册内容

`C:\Users\ZZZX\.dsh\cordis.patch.yml`：

```yaml
- insert:
    - id: rea-mcp
      name: "@deepseek-ai/dsh-mcp-client"
      config:
        serverName: rea
        transport: stdio
        command: D:\ROG longwang4\tools\node-v24.22.1-win-x64\node.exe
        args:
          - D:\ROG longwang4\tools\npm-global\node_modules\rea-agents\scripts\rea.mjs
          - mcp
        env:
          GHIDRA_INSTALL_DIR: D:\ROG longwang4\tools\ghidra_12.1.4_PUBLIC
          JAVA_HOME: D:\ROG longwang4\tools\jdk-21.0.12.1+1
          REA_ANALYSIS_PROVIDER: ghidra
```

## 3. 暂停前必须知道的一件事

当前已经运行的 REA MCP 子进程（启动时尚未带 Ghidra 环境变量）仍是旧配置；因此**需要重启一次 DeepSeek Harness**，新的 MCP 子进程才会带上：

- `GHIDRA_INSTALL_DIR`
- `JAVA_HOME`
- `REA_ANALYSIS_PROVIDER=ghidra`

重启后在会话中可先用 `mcp__rea__binary_session` 检查 `analysis_provider_candidates` 中 ghidra 是否 `available: true`。

## 4. 已确认但尚未展开分析的目标设备

本机有多个小屏，已按 USB 描述符区分：

- **ROG RYUO IV / 龙王4 屏幕**：`USB\VID_345F&PID_9132`，BusReportedDeviceDesc=`usb extscreen`；其 MI_03 为厂商自定义接口，驱动为 `libusb0`（`msusb video` / `MS USB Display`），MI_00 为 HID 触摸。
- **ROG RYUO IV 控制器**：`USB\VID_0B05&PID_1C76`，BusReportedDeviceDesc=`ROG RYUO IV Standard`。
- 其他 ArtInChip 小屏：`USB\VID_33C3&PID_0E02`（HL-VMAX / ArtInChip），不是本次目标。

## 5. 暂停点

REA MCP + 深度 Ghidra 已完成安装与配置；按用户要求在此暂停，尚未开始对 ASUS Info Hub / USB 视频协议做实际逆向、提权、固件分析或 EXE 编写。

恢复时建议第一步：重启 Harness，然后从 `ASUS Info Hub - ROG RYUO IV\resources\app.asar` 的 Electron/JS 静态分析开始（可用 `mcp__rea__analyze_javascript_application`），同时用 `inspect_pe_imports` / Ghidra 查看 `MediaStation.dll` 和 `libusb0` 相关调用。
