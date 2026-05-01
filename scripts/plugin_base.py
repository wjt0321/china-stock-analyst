"""
插件化架构 - 核心模块
"""

import abc
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

LOGGER = logging.getLogger(__name__)


@dataclass
class PluginContext:
    """插件运行上下文"""
    stock_code: str = ""
    stock_name: str = ""
    request: str = ""
    request_date: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    intent_category: str = "query"
    config: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginResult:
    """插件执行结果"""
    success: bool = False
    content: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExpertPlugin(abc.ABC):
    """专家插件抽象基类"""

    # 插件元数据（必须由子类实现）
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "general"  # fundamental/technical/flow/industry/event/risk
    priority: int = 100
    enabled: bool = True
    requires_akshare: bool = False
    requires_config: List[str] = field(default_factory=list)

    @abc.abstractmethod
    def can_handle(self, context: PluginContext) -> bool:
        """判断插件是否能处理当前请求"""
        pass

    @abc.abstractmethod
    def execute(self, context: PluginContext) -> PluginResult:
        """执行插件逻辑"""
        pass

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件（可选）"""
        return True

    def cleanup(self) -> None:
        """清理资源（可选）"""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """获取插件元数据"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "priority": self.priority,
            "enabled": self.enabled,
            "requires_akshare": self.requires_akshare,
        }


class FilterPlugin(abc.ABC):
    """过滤器插件抽象基类"""

    name: str = ""
    version: str = "1.0.0"
    description: ""
    enabled: bool = True
    priority: int = 50

    @abc.abstractmethod
    def can_filter(self, text: str, source: Dict[str, Any]) -> bool:
        """判断是否需要过滤"""
        pass

    @abc.abstractmethod
    def filter(self, text: str, source: Dict[str, Any]) -> Optional[str]:
        """执行过滤，返回过滤后的文本或 None（拒绝）"""
        pass


class TransformPlugin(abc.ABC):
    """转换器插件抽象基类"""

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = True
    priority: int = 50

    @abc.abstractmethod
    def can_transform(self, text: str) -> bool:
        """判断是否需要转换"""
        pass

    @abc.abstractmethod
    def transform(self, text: str) -> str:
        """执行转换，返回转换后的文本"""
        pass


if __name__ == "__main__":
    print("=== 插件抽象基类测试 ===")
    print("✅ ExpertPlugin - 专家插件基类")
    print("✅ FilterPlugin - 过滤器插件基类")
    print("✅ TransformPlugin - 转换器插件基类")
    print("\n请继承这些基类创建自定义插件。")
