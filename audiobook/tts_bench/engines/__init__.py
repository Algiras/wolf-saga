"""Plugin discovery: every module in this package that defines ENGINES is picked up."""

from __future__ import annotations

import importlib
import pkgutil
import traceback
from typing import Dict, List, Tuple

from .base import Engine


def discover() -> Tuple[Dict[str, Engine], Dict[str, str]]:
    """-> ({engine id: instance}, {module name: import error})"""
    engines: Dict[str, Engine] = {}
    errors: Dict[str, str] = {}
    for mod in pkgutil.iter_modules(__path__):
        if mod.name == "base":
            continue
        try:
            m = importlib.import_module(__name__ + "." + mod.name)
        except Exception as e:   # a broken plugin must never break the bench
            errors[mod.name] = "%s: %s" % (type(e).__name__, e)
            continue
        for cls in getattr(m, "ENGINES", []):
            inst = cls()
            engines[inst.id] = inst
    return dict(sorted(engines.items())), errors
