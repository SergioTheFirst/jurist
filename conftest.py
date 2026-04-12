"""Root conftest — patches for Python 3.11+ compatibility."""

from __future__ import annotations

import inspect
from collections import namedtuple

# pymorphy2 uses inspect.getargspec which was removed in Python 3.11.
# The old getargspec returned a 4-tuple (args, varargs, varkw, defaults).
# getfullargspec returns a 6-element FullArgSpec — we must truncate.
if not hasattr(inspect, "getargspec"):
    _ArgSpec = namedtuple("ArgSpec", ["args", "varargs", "varkw", "defaults"])

    def _getargspec(func):  # type: ignore[no-untyped-def]
        spec = inspect.getfullargspec(func)
        return _ArgSpec(spec.args, spec.varargs, spec.varkw, spec.defaults)

    inspect.getargspec = _getargspec  # type: ignore[attr-defined]
