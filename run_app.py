#!/usr/bin/env python
"""
Run Script for CENACE Demand Downloader
========================================
Simple script to launch the Streamlit application
"""

import subprocess
import sys
import os
from pathlib import Path

def check_requirements():
    """Check if all required packages are installed"""
    required = ['streamlit', 'pandas', 'numpy', 'requests', 'plotly']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"⚠️  Missing packages: {', '.join(missing)}")
        print("Please run: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Main function to run the app"""
    print("=" * 50)
    print("⚡ CENACE Demand Downloader")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Please install missing dependencies first!")
        sys.exit(1)
    
    print("✅ All dependencies installed")
    print("\n🚀 Starting Streamlit app...")
    print("📊 The app will open in your browser automatically")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Run Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "app_streamlit.py",
            "--server.headless=true",
            "--browser.gatherUsageStats=false"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error running app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
