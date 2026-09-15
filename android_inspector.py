#!/usr/bin/env python3
"""Android Package Inspector — entry point.

This is a thin launcher. The implementation lives in the ``apinspector``
package (see its docstring for the module map). Run either:

    python3 android_inspector.py [options]
    python -m apinspector [options]
"""

from __future__ import annotations

import sys

from apinspector.cli import main

if __name__ == "__main__":
    sys.exit(main())
