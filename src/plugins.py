"""
Plugin and extension architecture supporting dynamic lifecycle hooks.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BasePlugin(ABC):
    """Abstract interface for application plugins."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.enabled = True

    @abstractmethod
    def on_load(self) -> None:
        """Called when plugin is loaded into the manager."""
        pass

    def before_request(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Optional hook executed before request handling."""
        return None

    def after_response(self, context: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """Optional hook executed after response generation."""
        return response


class AuditLogPlugin(BasePlugin):
    """Sample plugin recording request metadata."""

    def __init__(self):
        super().__init__(name="AuditLogPlugin", version="1.0.0")
        self.log: List[Dict[str, Any]] = []

    def on_load(self) -> None:
        pass

    def after_response(self, context: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        self.log.append({
            "endpoint": context.get("endpoint"),
            "status_code": response.get("status_code"),
        })
        return response


class PluginManager:
    """Manages lifecycle and execution of registered plugins."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        """Register and initialize a plugin."""
        self._plugins[plugin.name] = plugin
        plugin.on_load()

    def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin by name."""
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            return True
        return False

    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Retrieve a registered plugin by name."""
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins with their status."""
        return [
            {"name": p.name, "version": p.version, "enabled": p.enabled}
            for p in self._plugins.values()
        ]

    def trigger_before_request(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute before_request hooks across all enabled plugins."""
        for plugin in self._plugins.values():
            if plugin.enabled:
                err = plugin.before_request(context)
                if err is not None:
                    return err
        return None

    def trigger_after_response(self, context: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """Execute after_response hooks across all enabled plugins."""
        for plugin in self._plugins.values():
            if plugin.enabled:
                response = plugin.after_response(context, response)
        return response


# Global plugin manager instance
plugins = PluginManager()
