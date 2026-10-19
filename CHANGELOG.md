# Changelog

## 1.0.0 (2026-10-19)

首个版本。

- 只注册一个指令 `/指令大全`（别名 `/帮助`、`/指令帮助`、`/指令列表`），汇总当前所有已加载插件的指令。
- 支持指令组 / 子指令、别名、必填/可选参数提示、管理员 / 群管权限角标。
- 采集优先走 AstrBot 官方 `command_management.list_commands()`，失败时回退遍历 `star_handlers_registry`。
- 使用 Pillow 在本机把结果渲染成自适应高度的卡片图（1~3 栏），不依赖远端 T2I 服务。
- 支持包含 AstrBot 内置指令（可开关），内置指令带中文说明。
- 图片写入 AstrBot 临时目录，自动清理 1 小时前的旧图；带可配置的短时缓存。
- 提供离线自测脚本 `tests/test_offline_render.py`，覆盖注册、metadata、配置 schema、权限过滤、端到端出图与缓存。
