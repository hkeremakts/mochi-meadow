"""Meadow: a living pixel-art habitat for a cat.

    python main.py                 # windowed, real local time
    python main.py --screensaver   # fullscreen; any input exits
    python main.py --help          # all options
"""

import os
import sys

# A settings file must be known before the meadow's modules load (they read
# their tuning as they import), so --settings is picked out first.
for i, arg in enumerate(sys.argv):
    if arg == "--settings" and i + 1 < len(sys.argv):
        os.environ["MEADOW_SETTINGS"] = sys.argv[i + 1]
    elif arg.startswith("--settings="):
        os.environ["MEADOW_SETTINGS"] = arg.split("=", 1)[1]

from habitat.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
