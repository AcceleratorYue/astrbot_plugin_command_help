"""离线自测脚本（开发用，不参与插件运行）。

把本机 AstrBot ``data/plugins`` 下已安装的插件模块导入到当前进程，复刻 AstrBot
加载插件后 ``star_handlers_registry`` 里的状态，然后：

1. 走兜底采集（遍历注册表）验证指令抓取；
2. 用假的 ``command_management.list_commands()`` 验证官方接口路径；
3. 渲染预览图，检查出图是否成功。

用法（需要装有 astrbot + Pillow 的 Python 环境，通常是 AstrBot 自己的 venv）：

    python tests/test_offline_render.py --astrbot-root "D:/QQbot/astrbot"

或者用环境变量指定 AstrBot 根目录（包含 data/plugins 的那一层）：

    ASTRBOT_ROOT=/path/to/astrbot python tests/test_offline_render.py
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
PLUGIN_DIR = HERE.parents[1]


def _resolve_astrbot_root() -> Path:
    """从命令行参数或环境变量取 AstrBot 根目录。"""

    root: str | None = None
    args = sys.argv[1:]
    for index, arg in enumerate(args):
        if arg == "--astrbot-root" and index + 1 < len(args):
            root = args[index + 1]
        elif arg.startswith("--astrbot-root="):
            root = arg.split("=", 1)[1]
    root = root or os.environ.get("ASTRBOT_ROOT") or os.environ.get("ASTRBOT_HOME")
    if not root:
        raise SystemExit(
            "请用 --astrbot-root 或环境变量 ASTRBOT_ROOT 指定 AstrBot 根目录"
            "（即包含 data/plugins 的那一层目录）。"
        )
    path = Path(root).expanduser().resolve()
    if not (path / "data" / "plugins").is_dir():
        raise SystemExit(f"{path} 下没有 data/plugins，请确认 AstrBot 根目录填对了。")
    return path


ASTROOT = _resolve_astrbot_root()
INSTALLED_PLUGINS_DIR = ASTROOT / "data" / "plugins"
PREVIEW_PATH = PLUGIN_DIR / "_preview_command_help.png"

# 出图会写 AstrBot 的 data/temp；测试时指到仓库内的临时目录，别碰真实实例。
TEST_RUNTIME = PLUGIN_DIR / "_test_runtime"
(TEST_RUNTIME / "data" / "temp").mkdir(parents=True, exist_ok=True)
os.environ["ASTRBOT_ROOT"] = str(TEST_RUNTIME)

# 复刻 AstrBot 的插件模块路径（data.plugins.<目录>.main），并让本插件可被导入。
sys.path.insert(0, str(ASTROOT))
sys.path.insert(0, str(PLUGIN_DIR.parent))

import astrbot_plugin_command_help.main as plugin  # noqa: E402


def load_installed_plugins() -> tuple[list[str], list[tuple[str, str]]]:
    """导入已安装插件，让它们的装饰器把 handler 注册进全局注册表。"""

    loaded: list[str] = []
    failed: list[tuple[str, str]] = []
    if not INSTALLED_PLUGINS_DIR.is_dir():
        print(f"[!] 没找到插件目录：{INSTALLED_PLUGINS_DIR}")
        return loaded, failed

    for plugin_dir in sorted(INSTALLED_PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith((".", "_")):
            continue
        if not (plugin_dir / "main.py").is_file():
            continue
        module_name = f"data.plugins.{plugin_dir.name}.main"
        try:
            importlib.import_module(module_name)
            loaded.append(plugin_dir.name)
        except Exception as exc:  # noqa: BLE001
            failed.append((plugin_dir.name, f"{type(exc).__name__}: {exc}"))

    # AstrBot 自带的保留插件（/reset、/new、/stats 等内置指令）也一并载入。
    for builtin in ("builtin_commands", "astrbot"):
        try:
            importlib.import_module(f"astrbot.builtin_stars.{builtin}.main")
            loaded.append(f"[内置] {builtin}")
        except Exception as exc:  # noqa: BLE001
            failed.append((builtin, f"{type(exc).__name__}: {exc}"))
    return loaded, failed


def emulate_loader_binding() -> None:
    """生产环境里 AstrBot 会把 handler 绑定到插件实例。

    像 meme_manager 这类用 Mixin 写指令的插件，还会在插件的 __init__ 里把
    Mixin 模块的 handler_module_path 改回插件主模块；这里调一下它们自己的
    归一化方法，尽量贴近真实运行状态。另外把保留插件标记成 reserved。
    """

    from astrbot.core.star.star import star_registry

    for meta in star_registry:
        module_path = getattr(meta, "module_path", "") or ""
        if module_path.startswith("astrbot.builtin_stars."):
            meta.reserved = True
        cls = getattr(meta, "star_cls_type", None)
        normalize = getattr(cls, "_normalize_mixin_handler_module_paths", None)
        if callable(normalize):
            try:
                normalize()
            except Exception as exc:  # noqa: BLE001
                print(f"  [归一化失败] {meta.name}: {exc}")


def describe(sections: list[plugin.PluginSection]) -> None:
    total = sum(section.command_count for section in sections)
    print(f"\n采集结果：{len(sections)} 个插件 / {total} 条指令")
    for section in sections:
        print(f"  - {section.display_name} ({section.key}) v{section.version}: {section.command_count} 条")
        for entry in section.entries[:3]:
            kind = "组" if entry.is_group else "指令"
            print(f"      {kind} /{entry.name} {entry.params}".rstrip())
        if len(section.entries) > 3:
            print(f"      ... 共 {len(section.entries)} 项")


async def exercise_official_api() -> None:
    """用一个假的 list_commands() 返回值验证官方接口路径的归一化逻辑。"""

    from astrbot.core.star import command_management

    fake_payload = [
        {
            "handler_full_name": "data.plugins.demo.main.demo_cmd",
            "handler_name": "demo_cmd",
            "plugin": "demo",
            "plugin_display_name": "演示插件",
            "module_path": "data.plugins.demo.main",
            "description": "示例指令。参数: [标签]",
            "type": "command",
            "parent_signature": "",
            "original_command": "示例",
            "current_fragment": "示例",
            "effective_command": "示例",
            "aliases": ["demo"],
            "permission": "everyone",
            "enabled": True,
            "plugin_activated": True,
            "is_group": False,
            "reserved": False,
            "sub_commands": [],
        },
        {
            "handler_full_name": "data.plugins.demo.main.demo_group",
            "handler_name": "demo_group",
            "plugin": "demo",
            "plugin_display_name": "演示插件",
            "module_path": "data.plugins.demo.main",
            "description": "示例指令组。",
            "type": "group",
            "parent_signature": "",
            "original_command": "示例组",
            "current_fragment": "示例组",
            "effective_command": "示例组",
            "aliases": [],
            "permission": "everyone",
            "enabled": True,
            "plugin_activated": True,
            "is_group": True,
            "reserved": False,
            "sub_commands": [
                {
                    "handler_full_name": "data.plugins.demo.main.demo_sub",
                    "handler_name": "demo_sub",
                    "plugin": "demo",
                    "plugin_display_name": "演示插件",
                    "module_path": "data.plugins.demo.main",
                    "description": "组内子指令。",
                    "type": "sub_command",
                    "parent_signature": "示例组",
                    "original_command": "示例组 查看",
                    "current_fragment": "查看",
                    "effective_command": "示例组 查看",
                    "aliases": ["查看"],
                    "permission": "admin",
                    "enabled": True,
                    "plugin_activated": True,
                    "is_group": False,
                    "reserved": False,
                    "sub_commands": [],
                },
            ],
        },
    ]

    async def fake_list_commands():
        return fake_payload

    original = command_management.list_commands
    command_management.list_commands = fake_list_commands  # type: ignore[assignment]
    try:
        sections = await plugin.collect_command_sections()
    finally:
        command_management.list_commands = original  # type: ignore[assignment]

    names = {section.key: [entry.name for entry in section.entries] for section in sections}
    print("\n官方接口归一化结果：", names)
    assert "demo" in names, names
    demo_entries = {entry.name: entry for section in sections for entry in section.entries}
    assert "示例" in demo_entries
    assert demo_entries["示例"].params == "[标签]", demo_entries["示例"].params
    assert demo_entries["示例"].aliases == ["demo"]
    assert "示例组" in demo_entries
    group = demo_entries["示例组"]
    assert group.is_group and group.children, group
    child = group.children[0]
    assert child.name == "示例组 查看"
    assert child.aliases == [], child.aliases  # 别名与指令名相同会被折叠
    assert child.permission == "admin"
    print("官方接口路径断言全部通过")


def render(sections: list[plugin.PluginSection]) -> None:
    options = plugin.RenderOptions(
        title="指令总览",
        columns=2,
        show_aliases=True,
        command_prefix="/",
        generated_at=time.strftime("%Y-%m-%d %H:%M"),
        plugin_count=len(sections),
        command_count=sum(section.command_count for section in sections),
        astrbot_version="4.29.1",
    )
    path = plugin.render_command_image(sections, options, PREVIEW_PATH)
    from PIL import Image

    with Image.open(path) as img:
        print(f"\n出图成功：{path}（{img.width}x{img.height}，{path.stat().st_size / 1024:.0f} KB）")


def check_registration_and_loader() -> None:
    """检查指令注册、类名探测、metadata 校验这些 AstrBot 加载环节。"""

    from astrbot.core.star.filter.command import CommandFilter
    from astrbot.core.star.star_handler import EventType, star_handlers_registry

    handlers = [
        handler
        for handler in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent
        )
        if "astrbot_plugin_command_help" in handler.handler_module_path
    ]
    assert handlers, "插件没有注册任何 handler"
    names: set[str] = set()
    for handler in handlers:
        for event_filter in handler.event_filters:
            if isinstance(event_filter, CommandFilter):
                names.update(event_filter.get_complete_command_names())
    expected = {"指令大全", "帮助", "指令帮助", "指令列表"}
    assert expected <= names, f"指令注册不完整：{names}"
    print(f"\n指令注册正常：{sorted(names)}")

    from astrbot.core.star.star_manager import PluginManager

    metadata = PluginManager._load_plugin_metadata(str(PLUGIN_DIR))
    assert metadata is not None, "metadata.yaml 读取失败"
    assert metadata.name == "astrbot_plugin_command_help", metadata.name
    assert metadata.display_name == "指令大全", metadata.display_name
    print(
        f"metadata 正常：{metadata.name} / {metadata.display_name} / v{metadata.version} / {metadata.author}"
    )

    classes = PluginManager._get_classes(sys.modules[plugin.__name__])
    assert classes == ["CommandHelpPlugin"], classes
    print(f"插件类探测正常：{classes}")

    schema = PluginManager._load_plugin_config_schema(str(PLUGIN_DIR / "_conf_schema.json"))
    assert isinstance(schema, dict) and schema, schema
    print(f"配置 schema 正常：{sorted(schema)}")


def check_config_filtering(sections: list[plugin.PluginSection]) -> None:
    """验证「隐藏管理员指令」开关只删掉权限指令。"""

    from copy import deepcopy

    pruned = plugin.filter_sections(
        deepcopy(sections), include_builtin=True, include_admin_only=False
    )
    before = sum(section.command_count for section in sections)
    after = sum(section.command_count for section in pruned)
    assert after < before, (before, after)
    for section in pruned:
        flat = list(section.entries)

        def walk(entries):
            for entry in entries:
                if entry.is_group:
                    yield from walk(entry.children)
                else:
                    yield entry

        for entry in walk(section.entries):
            assert entry.permission == "everyone", entry.name
    print(f"\n管理员指令过滤正常：{before} -> {after} 条")

    no_builtin = plugin.filter_sections(
        deepcopy(sections), include_builtin=False, include_admin_only=True
    )
    assert all(not section.reserved for section in no_builtin), [
        s.key for s in no_builtin if s.reserved
    ]
    assert any(section.reserved for section in sections), "测试数据里没有内置插件"
    print("内置指令开关正常：关闭后不出现 reserved 插件")


class _StubContext:
    """只实现插件用到的 Context 方法。"""

    def get_config(self, umo=None):
        return {"wake_prefix": ["/"]}


class _FakeEvent:
    """记录插件 yield 出来的结果。"""

    def __init__(self) -> None:
        self.unified_msg_origin = "aiocqhttp:GroupMessage:12345"
        self.results: list = []

    def image_result(self, path: str):
        self.results.append(("image", path))
        return self.results[-1]

    def plain_result(self, text: str):
        self.results.append(("text", text))
        return self.results[-1]


async def check_handler_end_to_end() -> None:
    """模拟真实调用：走一遍指令处理函数并出图。"""

    plugin_instance = object.__new__(plugin.CommandHelpPlugin)
    plugin_instance.context = _StubContext()
    plugin_instance._config = None
    plugin_instance._cache_path = None
    plugin_instance._cache_at = 0.0
    plugin_instance._cache_key = ""

    event = _FakeEvent()
    results = [item async for item in plugin_instance.cmd_command_help(event)]
    assert results, "处理函数没有输出"
    kind, payload = results[0]
    assert kind == "image", results[0]
    from pathlib import Path

    image_path = Path(payload)
    assert image_path.is_file(), image_path
    assert image_path.stat().st_size > 50_000, image_path.stat().st_size

    # 第二次调用应命中缓存（默认 cache_seconds=30）。
    event2 = _FakeEvent()
    results2 = [item async for item in plugin_instance.cmd_command_help(event2)]
    assert results2 and results2[0][0] == "image"
    assert results2[0][1] == payload, "缓存未生效"
    print(f"\n端到端调用正常：{image_path.name}，缓存命中")


def main() -> int:
    loaded, failed = load_installed_plugins()
    print(f"已导入插件 {len(loaded)} 个：{', '.join(loaded) or '无'}")
    for name, error in failed:
        print(f"  [导入失败] {name}: {error}")
    emulate_loader_binding()

    sections = plugin.filter_sections(plugin._collect_from_registry())
    describe(sections)
    assert sections, "兜底采集没有结果"
    render(sections)

    try:
        check_registration_and_loader()
        check_config_filtering(sections)
        asyncio.run(check_handler_end_to_end())
        asyncio.run(exercise_official_api())
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
