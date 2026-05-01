"""
插件加载器 - 动态发现和加载插件
"""

import importlib
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from plugin_base import ExpertPlugin, FilterPlugin, TransformPlugin

LOGGER = logging.getLogger(__name__)


class PluginLoader:
    """插件加载器"""

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        self.plugin_dirs: List[Path] = plugin_dirs or []
        self.expert_plugins: Dict[str, ExpertPlugin] = {}
        self.filter_plugins: Dict[str, FilterPlugin] = {}
        self.transform_plugins: Dict[str, TransformPlugin] = {}
        self.plugin_errors: Dict[str, List[str]] = {}

    def add_plugin_dir(self, dir_path: Path) -> None:
        """添加插件目录"""
        if dir_path.exists() and dir_path.is_dir():
            if dir_path not in self.plugin_dirs:
                self.plugin_dirs.append(dir_path)
                LOGGER.info(f"✅ 添加插件目录: {dir_path}")
        else:
            LOGGER.warning(f"⚠️ 目录不存在: {dir_path}")

    def discover_plugins(self) -> None:
        """发现并加载所有插件"""
        self.expert_plugins.clear()
        self.filter_plugins.clear()
        self.transform_plugins.clear()
        self.plugin_errors.clear()

        LOGGER.info("🔍 开始发现插件...")

        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue

            LOGGER.info(f"📁 扫描目录: {plugin_dir}")

            # 添加到 sys.path
            if str(plugin_dir.parent) not in sys.path:
                sys.path.insert(0, str(plugin_dir.parent))

            # 扫描 Python 文件
            for py_file in plugin_dir.glob("**/*.py"):
                if py_file.name.startswith("_"):
                    continue

                try:
                    self._load_plugin_from_file(py_file, plugin_dir)
                except Exception as e:
                    error_msg = f"加载 {py_file.name} 失败: {str(e)}"
                    LOGGER.error(f"❌ {error_msg}")
                    if str(py_file) not in self.plugin_errors:
                        self.plugin_errors[str(py_file)] = []
                    self.plugin_errors[str(py_file)].append(error_msg)

        self._log_plugin_summary()

    def _load_plugin_from_file(self, py_file: Path, plugin_dir: Path) -> None:
        """从单个文件加载插件"""
        rel_path = py_file.relative_to(plugin_dir.parent)
        module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")

        LOGGER.debug(f"📄 加载模块: {module_name}")

        # 导入模块
        spec = importlib.util.spec_from_file_location(module_name, str(py_file))
        if not spec or not spec.loader:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 查找插件类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            if isinstance(attr, type):
                if issubclass(attr, ExpertPlugin) and attr != ExpertPlugin:
                    self._register_expert_plugin(attr)
                elif issubclass(attr, FilterPlugin) and attr != FilterPlugin:
                    self._register_filter_plugin(attr)
                elif issubclass(attr, TransformPlugin) and attr != TransformPlugin:
                    self._register_transform_plugin(attr)

    def _register_expert_plugin(self, plugin_class: Type[ExpertPlugin]) -> None:
        """注册专家插件"""
        try:
            plugin = plugin_class()
            if plugin.name and plugin.enabled:
                self.expert_plugins[plugin.name] = plugin
                LOGGER.info(f"✅ 注册专家插件: {plugin.name} (v{plugin.version})")
        except Exception as e:
            LOGGER.error(f"❌ 注册专家插件失败: {e}")

    def _register_filter_plugin(self, plugin_class: Type[FilterPlugin]) -> None:
        """注册过滤器插件"""
        try:
            plugin = plugin_class()
            if plugin.name and plugin.enabled:
                self.filter_plugins[plugin.name] = plugin
                LOGGER.info(f"✅ 注册过滤器插件: {plugin.name} (v{plugin.version})")
        except Exception as e:
            LOGGER.error(f"❌ 注册过滤器插件失败: {e}")

    def _register_transform_plugin(self, plugin_class: Type[TransformPlugin]) -> None:
        """注册转换器插件"""
        try:
            plugin = plugin_class()
            if plugin.name and plugin.enabled:
                self.transform_plugins[plugin.name] = plugin
                LOGGER.info(f"✅ 注册转换器插件: {plugin.name} (v{plugin.version})")
        except Exception as e:
            LOGGER.error(f"❌ 注册转换器插件失败: {e}")

    def _log_plugin_summary(self) -> None:
        """输出插件发现总结"""
        total = len(self.expert_plugins) + len(self.filter_plugins) + len(self.transform_plugins)
        LOGGER.info(f"\n{'=' * 60}")
        LOGGER.info(f"📊 插件发现完成: {total} 个")
        LOGGER.info(f"  • 专家插件: {len(self.expert_plugins)}")
        LOGGER.info(f"  • 过滤器插件: {len(self.filter_plugins)}")
        LOGGER.info(f"  • 转换器插件: {len(self.transform_plugins)}")
        if self.plugin_errors:
            LOGGER.info(f"  • 错误: {len(self.plugin_errors)}")
        LOGGER.info(f"{'=' * 60}")

    def get_expert_plugins(self) -> List[ExpertPlugin]:
        """获取所有专家插件（按优先级排序）"""
        plugins = list(self.expert_plugins.values())
        plugins.sort(key=lambda x: x.priority, reverse=True)
        return plugins

    def get_filter_plugins(self) -> List[FilterPlugin]:
        """获取所有过滤器插件（按优先级排序）"""
        plugins = list(self.filter_plugins.values())
        plugins.sort(key=lambda x: x.priority, reverse=True)
        return plugins

    def get_transform_plugins(self) -> List[TransformPlugin]:
        """获取所有转换器插件（按优先级排序）"""
        plugins = list(self.transform_plugins.values())
        plugins.sort(key=lambda x: x.priority, reverse=True)
        return plugins

    def get_expert_plugin(self, name: str) -> Optional[ExpertPlugin]:
        """获取指定名称的专家插件"""
        return self.expert_plugins.get(name)

    def get_filter_plugin(self, name: str) -> Optional[FilterPlugin]:
        """获取指定名称的过滤器插件"""
        return self.filter_plugins.get(name)

    def get_transform_plugin(self, name: str) -> Optional[TransformPlugin]:
        """获取指定名称的转换器插件"""
        return self.transform_plugins.get(name)

    def initialize_plugins(self, config: Dict[str, Any]) -> None:
        """初始化所有插件"""
        for name, plugin in self.expert_plugins.items():
            try:
                plugin.initialize(config)
                LOGGER.info(f"🔧 初始化插件: {name}")
            except Exception as e:
                LOGGER.error(f"❌ 初始化插件失败 {name}: {e}")

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """获取所有插件元数据"""
        metadata = []
        for plugin in self.get_expert_plugins():
            metadata.append(plugin.get_metadata())
        return metadata


def create_default_plugin_loader() -> PluginLoader:
    """创建默认插件加载器"""
    plugin_dirs = [
        Path(__file__).parent.parent / "plugins",
        Path.home() / ".china_stock_analyst" / "plugins",
    ]
    loader = PluginLoader()
    for plugin_dir in plugin_dirs:
        if plugin_dir.exists():
            loader.add_plugin_dir(plugin_dir)
    return loader


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== 插件加载器测试 ===\n")

    loader = create_default_plugin_loader()
    loader.discover_plugins()

    print("\n=== 已加载插件 ===")
    for plugin in loader.get_expert_plugins():
        print(f"  • {plugin.name} (v{plugin.version}) - {plugin.category}")
