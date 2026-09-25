"""Entry point Claude Desktop runs for the TerraVision extension.

Claude Desktop installs the dependencies in ../pyproject.toml with uv and runs
this file, passing ``--output-dir`` from the extension's settings. It starts
the same server as ``terravision mcp``.
"""

import sys

from terravision.terravision import main

if __name__ == "__main__":
    sys.argv = ["terravision", "mcp", *sys.argv[1:]]
    main()
