#!/usr/bin/env python3
"""
插件系统测试
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

print("=" * 70)
print("插件系统测试")
print("=" * 70)

# 测试 1: 导入插件模块
print("\n[测试 1] 导入插件模块...")
try:
    from scripts.plugin_loader import create_default_plugin_loader
    from scripts.plugin_base import PluginContext, PluginResult
    from scripts.team_router import (
        get_available_plugins,
        get_matching_plugins,
        execute_plugin,
    )
    print("✅ 插件模块导入成功")
except Exception as e:
    print(f"❌ 插件模块导入失败: {e}")
    sys.exit(1)

# 测试 2: 初始化插件加载器
print("\n[测试 2] 初始化插件加载器...")
try:
    loader = create_default_plugin_loader()
    loader.add_plugin_dir(root_dir / "plugins")
    loader.discover_plugins()
    print(f"✅ 发现插件: {len(loader.get_expert_plugins())} 个专家插件")
except Exception as e:
    print(f"❌ 插件加载器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 获取插件元数据
print("\n[测试 3] 获取插件元数据...")
try:
    meta = loader.get_all_metadata()
    for plugin_meta in meta:
        print(f"  • {plugin_meta['name']} (v{plugin_meta['version']}) - {plugin_meta['category']}")
    print(f"✅ 成功获取 {len(meta)} 个插件元数据")
except Exception as e:
    print(f"❌ 获取元数据失败: {e}")

# 测试 4: team_router 插件 API
print("\n[测试 4] team_router 插件 API...")
try:
    plugins = get_available_plugins()
    print(f"✅ get_available_plugins: {len(plugins)} 个插件")

    matching = get_matching_plugins(
        stock_code="600519",
        stock_name="贵州茅台",
        request="分析贵州茅台的技术指标和资金流向"
    )
    print(f"✅ get_matching_plugins: {len(matching)} 个匹配插件")
    for p in matching:
        print(f"  • {p['name']} - {p['description']}")
except Exception as e:
    print(f"❌ team_router 插件 API 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 运行单元测试
print("\n[测试 5] 运行单元测试...")
try:
    import unittest
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 运行原有的测试
    if (root_dir / "tests").exists():
        from tests.test_stock_skill import TestStockSkill
        suite.addTests(loader.loadTestsFromTestCase(TestStockSkill))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n✅ 所有测试通过")
    else:
        print(f"\n⚠️ 测试失败: {len(result.failures) + len(result.errors)} 个")
        for failure in result.failures:
            print(f"  - 失败: {failure[0]}")
        for error in result.errors:
            print(f"  - 错误: {error[0]}")
except Exception as e:
    print(f"❌ 单元测试运行失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("插件系统测试完成")
print("=" * 70)
