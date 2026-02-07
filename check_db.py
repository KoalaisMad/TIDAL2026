#!/usr/bin/env python3
"""
Wrapper script to run check_db from its new location in apps/scripts/
"""
import sys
from pathlib import Path

# Add the asthma-forecaster directory to Python path
sys.path.append(str(Path(__file__).parent / "asthma-forecaster"))

# Import and run the check_db script
from apps.scripts.check_db import main

if __name__ == "__main__":
    main()