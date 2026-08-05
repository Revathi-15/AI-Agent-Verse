# backend/tools/__init__.py — Auto-discover and register all tool plugins

import importlib, pkgutil, pathlib
from backend.tools.base import BaseTool

_registry: dict[str, BaseTool] = {}

def _discover():
    pkg_dir = pathlib.Path(__file__).parent
    for _, name, _ in pkgutil.iter_modules([str(pkg_dir)]):
        if name == "base":
            continue
        mod = importlib.import_module(f"backend.tools.{name}")
        for attr in vars(mod).values():
            if isinstance(attr, type) and issubclass(attr, BaseTool) and attr is not BaseTool:
                inst = attr()
                _registry[inst.name] = inst

_discover()

def get_tool(name: str) -> BaseTool | None:
    return _registry.get(name)

def all_tools() -> dict[str, BaseTool]:
    return dict(_registry)
