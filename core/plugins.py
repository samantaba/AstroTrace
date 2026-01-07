import importlib
import pkgutil
from pathlib import Path
from typing import Any


def load_plugins(ui: Any, tab_widget: Any) -> None:
    """
    Discover and load plugins from astrotrace/plugins.

    A plugin is any module with a `register(ui, tab_widget)` function.
    """
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
    if not plugins_dir.exists():
        return

    for _, modname, ispkg in pkgutil.iter_modules([str(plugins_dir)]):
        if ispkg:
            continue
        try:
            module = importlib.import_module(f"plugins.{modname}")
            if hasattr(module, "register"):
                module.register(ui=ui, tab_widget=tab_widget)
        except Exception as exc:
            # Fail soft: do not break UI if a plugin errors.
            try:
                ui.log_output.append(f"Plugin load failed: {modname}: {exc}")
            except Exception:
                pass

