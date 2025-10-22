#!/usr/bin/env python3
"""
Development runner for ClipperTV
Run this script to start the application during development
"""

import streamlit.web.cli as stcli
import sys
import os

if __name__ == "__main__":
    # Get the directory of the current file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Set up the command line arguments for Streamlit
    sys.argv = [
        "streamlit", "run", 
        os.path.join(current_dir, "src", "clippertv", "app.py"),
        "--server.port=8501", 
        "--server.address=localhost"
    ]
    
    # Run the Streamlit CLI
    sys.exit(stcli.main())