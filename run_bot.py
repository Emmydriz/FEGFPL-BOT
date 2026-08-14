import os
import sys

# Ensure project root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from bot.main import main

if __name__ == "__main__":
    main()
