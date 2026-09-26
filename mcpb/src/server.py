"""Entry point Claude Desktop runs for the TerraVision extension.

Claude Desktop installs the dependencies in ../pyproject.toml with uv and runs
this file, passing ``--output-dir`` from the extension's settings. It starts
the same server as ``terravision mcp``.
"""

import sys
from pathlib import Path

# Where diagrams go when the folder setting is left empty.
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "TerraVision"


def server_args(argv):
    """Return the ``terravision mcp`` command line for these arguments.

    An empty folder setting, or one the host passed through unexpanded (a
    literal ``${DOCUMENTS}`` or ``${user_config.output_dir}``, as Claude
    Desktop on Linux did), would otherwise become a folder with that name
    inside the extension, so it is replaced by the default.
    """
    args = list(argv)
    if "--output-dir" not in args:
        args += ["--output-dir", str(DEFAULT_OUTPUT_DIR)]
    else:
        i = args.index("--output-dir")
        value = args[i + 1] if i + 1 < len(args) else ""
        if not value.strip() or "${" in value:
            args[i + 1 : i + 2] = [str(DEFAULT_OUTPUT_DIR)]
    return ["terravision", "mcp", *args]


if __name__ == "__main__":
    from terravision.terravision import main

    sys.argv = server_args(sys.argv[1:])
    main()
