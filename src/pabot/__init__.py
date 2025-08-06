from __future__ import absolute_import

# Avoid import errors during setup/build
try:
    from .pabotlib import PabotLib
    __all__ = ["PabotLib"]
except ImportError:
    pass

__version__ = "5.0.0"
