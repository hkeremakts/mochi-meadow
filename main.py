"""Meadow: a living pixel-art habitat for a cat.

    python main.py                 # windowed, real local time
    python main.py --screensaver   # fullscreen; any input exits
    python main.py --help          # all options
"""

import sys

from habitat.app import main

if __name__ == "__main__":
    sys.exit(main())
