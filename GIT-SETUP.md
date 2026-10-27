# Git / GitHub 连接说明（本机设置）

本文件记录本仓库的本地 git 环境、GitHub 连接方式与代理配置，便于迁移或重建。

## 1. 本地 Git

| 项目 | 值 |
|---|---|
| Git 版本 | `git version 2.56.0.windows.4` |
| 安装路径 | `C:\Program Files\Git\cmd\git.exe` |
| 安装方式 | 官方 Git for Windows 安装包，静默安装 |
| 全局用户名 | `Andromedahk` |
| 全局邮箱 | `105533798+Andromedahk@users.noreply.github.com` |
| 默认分支 | `main` |

新开终端若找不到 `git`，说明 PATH 未刷新，重新登录或临时执行：

```powershell
$env:Path = "C:\Program Files\Git\cmd;" + $env:Path
```

## 2. GitHub 连接（access token）

远端：

```
https://github.com/Andromedahk/ryuo4_stream.git
```

鉴权使用 **fine-grained personal access token**，直接内嵌在本仓库的 `.git/config` 远端 URL 中：

```
[remote "origin"]
	url = https://Andromedahk:<TOKEN>@github.com/Andromedahk/ryuo4_stream.git
```

- token 只保存在 `.git/config`（不会被提交、不会进入任何 commit）。
- token 需要 `Contents: Read and write` 权限（fine-grained）或 `repo` 权限（classic）。
- 更换/吊销 token 后，更新方式：

```powershell
git remote set-url origin "https://Andromedahk:<NEW_TOKEN>@github.com/Andromedahk/ryuo4_stream.git"
```

- 不想在 URL 里放 token 时，可改用凭据管理器：

```powershell
git config --local --unset remote.origin.url
git remote set-url origin https://github.com/Andromedahk/ryuo4_stream.git
git config --local credential.helper store   # 首次输入后存 %USERPROFILE%\.git-credentials
```

## 3. 代理（本地 7897）

本仓库已配置走本地 HTTP 代理：

```ini
[http]
	proxy = http://127.0.0.1:7897
	sslVerify = true
[https]
	proxy = http://127.0.0.1:7897
```

对应命令：

```powershell
git config --local http.proxy  "http://127.0.0.1:7897"
git config --local https.proxy "http://127.0.0.1:7897"
```

若代理端口变更或需要全局生效：

```powershell
git config --global http.proxy  "http://127.0.0.1:7897"
git config --global https.proxy "http://127.0.0.1:7897"
```

## 4. 日常操作

```powershell
cd "D:\ROG longwang4"

git status                # 查看改动
git add -A                # 暂存（自动遵守 .gitignore）
git commit -m "说明"      # 提交
git push                  # 推送到 origin/main
git pull                  # 拉取
```

首次推送已建立分支跟踪：`git push -u origin main`。

## 5. 仓库内容边界

- **纳入版本控制**：脚本（.py/.js/.sh/.bat）、文档与报告（.md）、笔记、小体积配置与测试数据。
- **排除（见 `.gitignore`）**：`firmware/`、`firmware-build/`、`tools/`、`host-re/asar/`、`stream_test/`、`device-notes/apk/`、`__pycache__/`、`*.mp4`、`_backup/`。
- 被排除的大文件清单：`BACKUP-MANIFEST.md`（汇总）与 `_backup/big-files-manifest.csv`（全量 38523 条）。
- 大文件离线备份：`_backup/big-files-backup.zip`（约 7 GB，仅本地，手工备份到移动硬盘/网盘）。
