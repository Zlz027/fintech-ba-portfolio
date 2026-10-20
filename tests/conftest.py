"""共享测试工具：把各项目的 src 目录挂到 sys.path 并按需导入 finance 模块。

四个项目都有名为 finance.py 的模块，直接 import 会互相覆盖，故用 importlib
按文件路径加载并缓存，互不干扰。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_MODULE_CACHE: dict[str, object] = {}


def load_finance(project: str, name: str | None = None):
    """按项目名加载其 src/finance.py，返回模块对象。

    参数
    ----
    project : 项目目录名，如 "01-python-credit-scoring"
    name    : 缓存的模块别名，默认取项目名的数字前缀，避免 sys.modules 冲突
    """
    alias = name or f"fin_{project.split('-')[0]}"
    if alias in _MODULE_CACHE:
        return _MODULE_CACHE[alias]

    path = ROOT / project / "src" / "finance.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module          # 让模块内的相对/绝对导入可解析
    spec.loader.exec_module(module)
    _MODULE_CACHE[alias] = module
    return module
