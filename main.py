import os
import sys

# Ensure root workspace directory is in python path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from gui.app import main

if __name__ == "__main__":
    main()
