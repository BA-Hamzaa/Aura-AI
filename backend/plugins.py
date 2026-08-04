"""
plugins.py — J.A.R.V.I.S. Plugin SDK & Plugin Manager.

Plugin Contract:
  A plugin is a Python class with:
    - metadata()    → dict with name, description, version, author, permissions
    - tools()       → dict mapping tool_name → callable
    - on_load()     → called when plugin is activated
    - on_unload()   → called when plugin is deactivated

Plugins are auto-discovered from the /plugins directory.
"""

import os
import json
import importlib.util
import threading
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field, asdict

log = logging.getLogger("jarvis.plugins")

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins")


@dataclass
class PluginMetadata:
    name:        str
    description: str
    version:     str = "1.0.0"
    author:      str = "Unknown"
    permissions: List[str] = field(default_factory=list)
    enabled:     bool = True
    config:      Dict = field(default_factory=dict)


class BasePlugin:
    """Every J.A.R.V.I.S. plugin must inherit from this class."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError

    def tools(self) -> Dict[str, Callable]:
        """Return a dict of tool_name -> callable."""
        return {}

    def on_load(self):
        """Called when the plugin is loaded. Set up resources here."""
        pass

    def on_unload(self):
        """Called when the plugin is unloaded. Release resources here."""
        pass


class PluginManager:
    """Discovers, loads, and manages J.A.R.V.I.S. plugins."""

    def __init__(self, plugins_dir: str = PLUGINS_DIR):
        self.plugins_dir = plugins_dir
        self._plugins: Dict[str, BasePlugin] = {}
        self._tools: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        os.makedirs(plugins_dir, exist_ok=True)

    def discover(self) -> List[str]:
        """Scan plugins directory and return list of plugin module names."""
        found = []
        if not os.path.isdir(self.plugins_dir):
            return found
        for f in os.listdir(self.plugins_dir):
            if f.endswith(".py") and not f.startswith("_"):
                found.append(f[:-3])
            elif os.path.isdir(os.path.join(self.plugins_dir, f)):
                init = os.path.join(self.plugins_dir, f, "__init__.py")
                if os.path.exists(init):
                    found.append(f)
        return found

    def load_plugin(self, module_name: str) -> Optional[str]:
        """Load a single plugin by module name. Returns error string or None."""
        try:
            # Determine module path
            mod_path = os.path.join(self.plugins_dir, module_name + ".py")
            if not os.path.exists(mod_path):
                mod_path = os.path.join(self.plugins_dir, module_name, "__init__.py")
            if not os.path.exists(mod_path):
                return f"Module not found: {module_name}"

            spec = importlib.util.spec_from_file_location(f"plugins.{module_name}", mod_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the plugin class (subclass of BasePlugin)
            plugin_class = None
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BasePlugin)
                    and obj is not BasePlugin
                ):
                    plugin_class = obj
                    break

            if not plugin_class:
                return f"No BasePlugin subclass found in {module_name}"

            instance = plugin_class()
            meta = instance.metadata()
            instance.on_load()

            with self._lock:
                # Unload existing if already loaded
                if meta.name in self._plugins:
                    self.unload_plugin(meta.name)

                self._plugins[meta.name] = instance
                # Register tools — namespaced as plugin_name.tool_name
                for tool_name, func in instance.tools().items():
                    full_name = f"{meta.name}.{tool_name}"
                    self._tools[full_name] = func
                    # Also register without namespace for convenience
                    self._tools[tool_name] = func

            log.info(f"Loaded plugin: {meta.name} v{meta.version}")
            return None

        except Exception as e:
            return f"Failed to load '{module_name}': {e}"

    def load_all(self) -> Dict[str, Optional[str]]:
        """Load all discovered plugins. Returns dict of module_name -> error."""
        results = {}
        for module_name in self.discover():
            results[module_name] = self.load_plugin(module_name)
        return results

    def unload_plugin(self, plugin_name: str) -> bool:
        with self._lock:
            plugin = self._plugins.get(plugin_name)
            if not plugin:
                return False
            try:
                plugin.on_unload()
            except Exception:
                pass
            meta = plugin.metadata()
            # Remove tools
            for tool_name in list(self._tools.keys()):
                if tool_name.startswith(f"{meta.name}."):
                    del self._tools[tool_name]
            del self._plugins[plugin_name]
        return True

    def get_tool(self, tool_name: str) -> Optional[Callable]:
        return self._tools.get(tool_name)

    def call_tool(self, tool_name: str, **kwargs) -> Any:
        func = self.get_tool(tool_name)
        if not func:
            raise ValueError(f"Tool not found: {tool_name}")
        return func(**kwargs)

    def list_plugins(self) -> List[Dict]:
        with self._lock:
            result = []
            for name, plugin in self._plugins.items():
                try:
                    meta = plugin.metadata()
                    result.append({
                        "name":        meta.name,
                        "description": meta.description,
                        "version":     meta.version,
                        "author":      meta.author,
                        "permissions": meta.permissions,
                        "tools":       list(plugin.tools().keys()),
                    })
                except Exception:
                    pass
        return result

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    @property
    def all_tools(self) -> Dict[str, Callable]:
        return dict(self._tools)


# ── Built-in plugins (inlined for reliability) ────────────────────────────────

class WeatherPlugin(BasePlugin):
    """Simple weather lookup via wttr.in (no API key needed)."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="weather",
            description="Get current weather for any city using wttr.in",
            version="1.0.0",
            author="J.A.R.V.I.S.",
            permissions=["internet"],
        )

    def tools(self) -> Dict[str, Callable]:
        return {"get_weather": self.get_weather}

    def get_weather(self, city: str = "London") -> str:
        try:
            import requests
            r = requests.get(
                f"https://wttr.in/{city}?format=3",
                timeout=8,
                headers={"User-Agent": "curl/7.64.1"}
            )
            if r.status_code == 200:
                return f"🌤 {r.text.strip()}"
            return f"Could not get weather for {city}."
        except Exception as e:
            return f"Weather error: {e}"


class CalculatorPlugin(BasePlugin):
    """Safe math expression evaluator."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="calculator",
            description="Safely evaluate math expressions",
            version="1.0.0",
            author="J.A.R.V.I.S.",
            permissions=[],
        )

    def tools(self) -> Dict[str, Callable]:
        return {"calculate": self.calculate}

    def calculate(self, expression: str) -> str:
        import ast
        import operator as op

        _ops = {
            ast.Add: op.add,
            ast.Sub: op.sub,
            ast.Mult: op.mul,
            ast.Div: op.truediv,
            ast.Pow: op.pow,
            ast.Mod: op.mod,
            ast.USub: op.neg,
        }

        def _eval(node):
            if isinstance(node, ast.Constant):
                return node.n
            elif isinstance(node, ast.BinOp):
                return _ops[type(node.op)](_eval(node.left), _eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                return _ops[type(node.op)](_eval(node.operand))
            else:
                raise ValueError("Unsafe expression")

        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _eval(tree.body)
            return f"= {result}"
        except Exception as e:
            return f"Could not calculate: {e}"


class ClipboardPlugin(BasePlugin):
    """Read/write system clipboard."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="clipboard",
            description="Read and write to system clipboard",
            version="1.0.0",
            author="J.A.R.V.I.S.",
            permissions=["clipboard"],
        )

    def tools(self) -> Dict[str, Callable]:
        return {
            "read_clipboard":  self.read_clipboard,
            "write_clipboard": self.write_clipboard,
        }

    def read_clipboard(self) -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or "(clipboard empty)"
        except Exception as e:
            return f"Clipboard read error: {e}"

    def write_clipboard(self, text: str) -> str:
        try:
            import subprocess
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
                capture_output=True, timeout=5
            )
            return f"✅ Copied to clipboard: {text[:50]}"
        except Exception as e:
            return f"Clipboard write error: {e}"


class SystemInfoPlugin(BasePlugin):
    """System monitoring: CPU, RAM, disk, processes."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="system_info",
            description="Monitor CPU, RAM, disk usage and running processes",
            version="1.0.0",
            author="J.A.R.V.I.S.",
            permissions=["system"],
        )

    def tools(self) -> Dict[str, Callable]:
        return {
            "get_cpu": self.get_cpu,
            "get_ram": self.get_ram,
            "get_disk": self.get_disk,
            "get_system_status": self.get_system_status,
        }

    def get_cpu(self) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            return f"CPU: {cpu:.1f}%"
        except Exception as e:
            return f"CPU error: {e}"

    def get_ram(self) -> str:
        try:
            import psutil
            vm = psutil.virtual_memory()
            used_gb = vm.used / (1024**3)
            total_gb = vm.total / (1024**3)
            return f"RAM: {used_gb:.1f}GB / {total_gb:.1f}GB ({vm.percent:.0f}%)"
        except Exception as e:
            return f"RAM error: {e}"

    def get_disk(self, path: str = "C:\\") -> str:
        try:
            import psutil
            d = psutil.disk_usage(path)
            free_gb = d.free / (1024**3)
            total_gb = d.total / (1024**3)
            return f"Disk ({path}): {free_gb:.1f}GB free / {total_gb:.1f}GB ({d.percent:.0f}% used)"
        except Exception as e:
            return f"Disk error: {e}"

    def get_system_status(self) -> str:
        return "\n".join([
            self.get_cpu(),
            self.get_ram(),
            self.get_disk(),
        ])


# ── Plugin Manager Singleton ──────────────────────────────────────────────────

plugin_manager = PluginManager()

# Register built-in plugins
def _register_builtins():
    for cls in [WeatherPlugin, CalculatorPlugin, ClipboardPlugin, SystemInfoPlugin]:
        try:
            instance = cls()
            meta = instance.metadata()
            instance.on_load()
            plugin_manager._plugins[meta.name] = instance
            for tool_name, func in instance.tools().items():
                plugin_manager._tools[f"{meta.name}.{tool_name}"] = func
                plugin_manager._tools[tool_name] = func
        except Exception as e:
            log.warning(f"Built-in plugin init error: {e}")

_register_builtins()
