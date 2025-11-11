import sys
from pathlib import Path

# Ensure local 'src' is importable for tests without requiring install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import sys
from pathlib import Path


# Ensure the package source is importable without installation
PKG_SRC = str((Path(__file__).resolve().parents[1] / "src").resolve())
if PKG_SRC not in sys.path:
    sys.path.insert(0, PKG_SRC)


