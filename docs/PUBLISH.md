# 发布到 AstrBot 插件市场

本文记录本插件提交到 AstrBot 官方插件市场的流程、当前状态与校验清单，方便后续更新版本时复用。

## 当前状态

- 插件仓库：<https://github.com/AcceleratorYue/astrbot_plugin_command_help>（公开，MIT）
- 已发布 GitHub Release：`v1.0.1`（含可上传安装的 zip）
- 市场提交：通过 <https://cloud.astrbot.app/publish> 提交（需要 AstrBot Cloud 账号 + GitHub App 授权）

## 官方流程（2026-10 时点）

1. 插件代码推送到 GitHub 公开仓库（本仓库已完成）。
2. 注册并登录 [AstrBot Cloud](https://cloud.astrbot.app/)（支持邮箱 / GitHub / Google）。
3. 在 Cloud 中连接并安装 **AstrBot Cloud GitHub App**，授予本仓库访问权限。
4. 打开 <https://cloud.astrbot.app/publish>：
   - 选择来源：**GitHub 仓库**（当前市场不开放 zip 上传，`zip_upload_enabled=false`）
   - 选择发布空间（namespace）与仓库 `AcceleratorYue/astrbot_plugin_command_help`
   - 平台会自动解析 `metadata.yaml`，确认名称、版本、简介、标签、分类（建议选「工具」）
   - 提交审核（每个账号最多同时 3 个待审、24 小时最多 3 次提交）
5. 审核通过后，插件即可在 AstrBot WebUI 的插件市场搜索到，也可通过 plugin_id `AcceleratorYue/astrbot_plugin_command_help` 安装。

## 市场规范校验清单（提交前自查）

依据官方规范 [插件市场 JSON 规范](https://docs.astrbot.app/dev/plugin-market/2026-06-27.html) 与 [发布插件文档](https://docs.astrbot.app/dev/star/plugin-publish.html)：

- [x] `metadata.yaml` 含 `name` / `author` / `version` / `desc` / `repo` 必填字段
- [x] `name` 为英文唯一标识：`astrbot_plugin_command_help`
- [x] `author` 与 GitHub 发布空间一致：`AcceleratorYue`（不含 `/`、控制字符）
- [x] `version` 遵循语义化版本：`1.0.1`
- [x] `repo` 为 HTTPS GitHub 仓库根地址（非子目录 / release / PR 链接）
- [x] `desc` / `short_desc` / `display_name` 完整，且与仓库 README 一致
- [x] `tags` 为字符串数组；`social_link` 为 HTTPS URL
- [x] 仓库根目录有 `logo.png`（AstrBot 插件图标约定）
- [x] 插件压缩包 < 16MB（本插件约 30KB）
- [x] 仓库不含 `.git` / `__pycache__` / 测试产物（已由 `.gitignore` 排除）
- [x] `metadata.yaml` 为 UTF-8（无 BOM）
- [x] 插件可在 AstrBot 4.16+ 加载；官方指令管理接口路径需要 4.29+，低版本会自动走兜底
- [x] Release 附件与仓库内容一致

## 发布新版本时

1. 修改 `metadata.yaml` 的 `version` 与 `CHANGELOG.md`。
2. 提交并推送到 `main`，打同名 tag（如 `v1.1.0`）。
3. 构建 zip：

   ```bash
   python - <<'PY'
   import zipfile
   from pathlib import Path
   repo = Path(".")
   out = repo / "dist" / "astrbot_plugin_command_help-1.1.0.zip"
   out.parent.mkdir(exist_ok=True)
   files = ["main.py", "metadata.yaml", "_conf_schema.json", "requirements.txt",
            "README.md", "LICENSE", "CHANGELOG.md", "logo.png"]
   with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
       for name in files:
           z.write(repo / name, f"astrbot_plugin_command_help/{name}")
   print(out)
   PY
   ```

4. 在 GitHub 创建 Release 并上传 zip。
5. 回到 <https://cloud.astrbot.app/publish>，选择「更新」重新提交（或等待市场自动检测新版本，具体以 Cloud 页面提示为准）。
