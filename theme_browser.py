"""
Stable Theme Browser - Updates theme without destroying window
"""

import tkinter as tk
from tkinter import ttk as tkttk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# All available themes
THEMES = [
    "cosmo", "flatly", "litera", "minty", "lumen", "sandstone",
    "yeti", "journal", "quartz", "darkly", "superhero", "solar",
    "cyborg", "vapor", "pulse", "united", "morph"
]

class StableThemeBrowser:
    def __init__(self):
        self.current_index = 0
        self.root = ttk.Window(themename=THEMES[0])
        self.root.title("Theme Browser")
        self.root.geometry("850x650")

        self.create_ui()

    def create_ui(self):
        """Build the UI once - we'll just update the theme"""
        # Header
        header = ttk.Frame(self.root, padding=20)
        header.pack(fill=X)

        self.title_label = ttk.Label(
            header,
            text=f"Theme: {THEMES[0].upper()}",
            font=("Segoe UI", 16, "bold")
        )
        self.title_label.pack()

        self.subtitle = ttk.Label(
            header,
            text="Preview how Claude Memory will look with each theme",
            font=("Segoe UI", 10)
        )
        self.subtitle.pack()

        ttk.Separator(self.root, orient=HORIZONTAL).pack(fill=X, pady=10)

        # Main content
        content = ttk.Frame(self.root, padding=20)
        content.pack(fill=BOTH, expand=YES)

        # Left sidebar
        left = ttk.Frame(content)
        left.pack(side=LEFT, fill=Y, padx=(0, 10))

        ttk.Label(left, text="Controls:", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))
        ttk.Entry(left, width=25).pack(pady=5)
        ttk.Button(left, text="Search", bootstyle="primary", width=23).pack(pady=5)
        ttk.Button(left, text="+ Add Entry", bootstyle="success", width=23).pack(pady=5)
        ttk.Button(left, text="Delete", bootstyle="danger", width=23).pack(pady=5)
        ttk.Button(left, text="Remove Duplicates", bootstyle="warning", width=23).pack(pady=5)
        ttk.Button(left, text="AI Summarize", bootstyle="info", width=23).pack(pady=5)
        ttk.Button(left, text="Refresh", bootstyle="secondary", width=23).pack(pady=5)

        # Right content
        right = ttk.Frame(content)
        right.pack(side=LEFT, fill=BOTH, expand=YES)

        ttk.Label(right, text="Sample Entries:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 10))

        for i in range(5):
            frame = ttk.Frame(right, bootstyle="light")
            frame.pack(fill=X, pady=2)
            ttk.Checkbutton(frame, text=f"Memory Entry {i+1}").pack(side=LEFT, padx=5, pady=5)
            ttk.Label(frame, text="email | sample", foreground="gray").pack(side=LEFT, padx=10)

        ttk.Separator(self.root, orient=HORIZONTAL).pack(fill=X, pady=10)

        # Footer with navigation
        footer = ttk.Frame(self.root, padding=20)
        footer.pack(fill=X)

        btn_frame = ttk.Frame(footer)
        btn_frame.pack()

        ttk.Button(btn_frame, text="← Previous", command=self.prev_theme, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Apply Theme ✓", command=self.print_instructions, bootstyle="success").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Next →", command=self.next_theme, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.info_label = ttk.Label(
            footer,
            text=f"Theme 1 of {len(THEMES)}",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.info_label.pack(pady=(10, 0))

    def next_theme(self):
        """Switch to next theme WITHOUT destroying window"""
        self.current_index = (self.current_index + 1) % len(THEMES)
        self.update_theme()

    def prev_theme(self):
        """Switch to previous theme WITHOUT destroying window"""
        self.current_index = (self.current_index - 1) % len(THEMES)
        self.update_theme()

    def update_theme(self):
        """Update to new theme"""
        theme_name = THEMES[self.current_index]

        # Update the style to new theme
        self.root.style.theme_use(theme_name)

        # Update labels
        self.title_label.config(text=f"Theme: {theme_name.upper()}")
        self.info_label.config(text=f"Theme {self.current_index + 1} of {len(THEMES)}")
        self.root.title(f"Theme Browser - {theme_name.upper()}")

    def print_instructions(self):
        """Print how to apply current theme"""
        theme_name = THEMES[self.current_index]
        print(f"\n{'='*60}")
        print(f"TO APPLY '{theme_name.upper()}' THEME:")
        print(f"{'='*60}")
        print(f"\nTell Claude: 'Apply the {theme_name} theme'")
        print(f"\n{'='*60}\n")

    def run(self):
        """Start the browser"""
        self.root.mainloop()

if __name__ == "__main__":
    print("="*60)
    print("STABLE THEME BROWSER")
    print("="*60)
    print("\nUse Next/Previous buttons to browse themes.")
    print("This version won't crash when switching!\n")

    browser = StableThemeBrowser()
    browser.run()
