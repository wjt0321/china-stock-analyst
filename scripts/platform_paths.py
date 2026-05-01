import os
import sys
from pathlib import Path


def get_skill_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[1]


def get_platform_cache_dir() -> Path:
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
        return Path(base) / 'china-stock-analyst' / 'cache'
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Caches' / 'china-stock-analyst'
    else:
        xdg_cache = os.environ.get('XDG_CACHE_HOME')
        if xdg_cache:
            return Path(xdg_cache) / 'china-stock-analyst'
        return Path.home() / '.cache' / 'china-stock-analyst'


def get_platform_config_dir() -> Path:
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or str(Path.home())
        return Path(base) / 'china-stock-analyst' / 'config'
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'china-stock-analyst'
    else:
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config:
            return Path(xdg_config) / 'china-stock-analyst'
        return Path.home() / '.config' / 'china-stock-analyst'


def get_platform_data_dir() -> Path:
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
        return Path(base) / 'china-stock-analyst' / 'data'
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'china-stock-analyst'
    else:
        xdg_data = os.environ.get('XDG_DATA_HOME')
        if xdg_data:
            return Path(xdg_data) / 'china-stock-analyst'
        return Path.home() / '.local' / 'share' / 'china-stock-analyst'


def ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def get_cache_path(filename: str) -> Path:
    cache_dir = get_platform_cache_dir()
    ensure_dir(cache_dir)
    return cache_dir / filename


def get_config_path(filename: str) -> Path:
    config_dir = get_platform_config_dir()
    ensure_dir(config_dir)
    return config_dir / filename


def get_data_path(filename: str) -> Path:
    data_dir = get_platform_data_dir()
    ensure_dir(data_dir)
    return data_dir / filename


PLATFORM_INFO = {
    "platform": sys.platform,
    "cache_dir": str(get_platform_cache_dir()),
    "config_dir": str(get_platform_config_dir()),
    "data_dir": str(get_platform_data_dir()),
    "skill_root": str(get_skill_root()),
}


if __name__ == "__main__":
    print("=== 跨平台路径信息 ===")
    for key, value in PLATFORM_INFO.items():
        print(f"{key}: {value}")
    print()
    print("=== 测试缓存文件路径 ===")
    test_cache = get_cache_path(".test_cache.json")
    print(f"缓存文件: {test_cache}")
    print(f"目录存在: {test_cache.parent.exists()}")
