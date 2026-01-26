"""
Test script for file discovery dialog.
Run this to test the file indexing system.
"""

import sys
from PyQt6.QtWidgets import QApplication
from claude_memory.discovery_dialog import DiscoveryDialog
from claude_memory.database import init_database

if __name__ == '__main__':
    # Initialize database (creates new tables if needed)
    print("Initializing database...")
    init_database()
    print("Database initialized with file indexing tables.")

    # Launch discovery dialog
    app = QApplication(sys.argv)
    dialog = DiscoveryDialog()
    result = dialog.exec()

    if result:
        print("Discovery completed and folders indexed!")
    else:
        print("Discovery cancelled.")

    sys.exit(0)
