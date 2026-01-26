"""
Theme Preview Tool for Claude Memory
Run this to preview all available ttkbootstrap themes and pick your favorite.
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk

# All available themes
THEMES = [
    # Light themes
    "cosmo",      # Light blue (current)
    "flatly",     # Light green
    "litera",     # Light gray
    "minty",      # Light mint green
    "lumen",      # Light orange/red
    "sandstone",  # Light brown/tan
    "yeti",       # Light blue-gray
    "journal",    # Light serif
    "quartz",     # Light pink/purple

    # Dark themes
    "darkly",     # Dark gray
    "superhero",  # Dark blue
    "solar",      # Dark yellow/orange
    "cyborg",     # Dark gray-blue
    "vapor",      # Dark purple/pink
    "pulse",      # Dark purple
    "united",     # Dark orange
    "morph",      # Dark teal
]

class ThemePreview:
    def __init__(self):
        self.current_theme_index = 0
        self.root = None
        self.create_window()

    def create_window(self):
        """Create the preview window with current theme."""
        theme_name = THEMES[self.current_theme_index]

        if self.root:
            self.root.destroy()

        self.root = ttk.Window(themename=theme_name)
        self.root.title(f"Claude Memory Theme Preview - {theme_name.upper()}")
        self.root.geometry("800x600")

        # Prevent closing with X button during theme changes
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Header
        header = ttk.Frame(self.root, padding=20)
        header.pack(fill=X)

        title_label = ttk.Label(
            header,
            text=f"Current Theme: {theme_name.upper()}",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack()

        subtitle = ttk.Label(
            header,
            text="This is how your Claude Memory app will look with this theme",
            font=("Segoe UI", 10)
        )
        subtitle.pack()

        # Separator
        ttk.Separator(self.root, orient=HORIZONTAL).pack(fill=X, pady=10)

        # Main content - simulate search window
        content = ttk.Frame(self.root, padding=20)
        content.pack(fill=BOTH, expand=YES)

        # Left sidebar simulation
        left_frame = ttk.Frame(content)
        left_frame.pack(side=LEFT, fill=Y, padx=(0, 10))

        ttk.Label(left_frame, text="Search Controls:", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))

        ttk.Entry(left_frame, width=25).pack(pady=5)
        ttk.Button(left_frame, text="Search", bootstyle="primary", width=23).pack(pady=5)
        ttk.Button(left_frame, text="+ Add Entry", bootstyle="success", width=23).pack(pady=5)
        ttk.Button(left_frame, text="Delete Selected", bootstyle="danger", width=23).pack(pady=5)
        ttk.Button(left_frame, text="Remove Duplicates", bootstyle="warning", width=23).pack(pady=5)
        ttk.Button(left_frame, text="AI Summarize", bootstyle="info", width=23).pack(pady=5)
        ttk.Button(left_frame, text="Refresh", bootstyle="secondary", width=23).pack(pady=5)

        # Right content area
        right_frame = ttk.Frame(content)
        right_frame.pack(side=LEFT, fill=BOTH, expand=YES)

        ttk.Label(right_frame, text="Memory Entries:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 10))

        # Simulate entry list
        for i in range(5):
            entry_frame = ttk.Frame(right_frame, bootstyle="light")
            entry_frame.pack(fill=X, pady=2)

            ttk.Checkbutton(entry_frame, text=f"Sample Memory Entry {i+1}").pack(side=LEFT, padx=5, pady=5)
            ttk.Label(entry_frame, text=f"Category: email | Tags: sample", foreground="gray").pack(side=LEFT, padx=10)

        # Separator
        ttk.Separator(self.root, orient=HORIZONTAL).pack(fill=X, pady=10)

        # Navigation footer
        footer = ttk.Frame(self.root, padding=20)
        footer.pack(fill=X)

        btn_frame = ttk.Frame(footer)
        btn_frame.pack()

        ttk.Button(btn_frame, text="← Previous Theme", command=self.prev_theme, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Apply This Theme ✓", command=self.apply_theme, bootstyle="success").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Next Theme →", command=self.next_theme, bootstyle="secondary").pack(side=LEFT, padx=5)

        info_label = ttk.Label(
            footer,
            text=f"Theme {self.current_theme_index + 1} of {len(THEMES)} | Use arrow buttons to browse",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        info_label.pack(pady=(10, 0))

    def next_theme(self):
        """Switch to next theme."""
        self.current_theme_index = (self.current_theme_index + 1) % len(THEMES)
        self.create_window()

    def prev_theme(self):
        """Switch to previous theme."""
        self.current_theme_index = (self.current_theme_index - 1) % len(THEMES)
        self.create_window()

    def apply_theme(self):
        """Print instructions for applying the theme."""
        theme_name = THEMES[self.current_theme_index]
        print(f"\n{'='*60}")
        print(f"TO APPLY '{theme_name.upper()}' THEME:")
        print(f"{'='*60}")
        print(f"\nJust tell me: 'Apply the {theme_name} theme'")
        print(f"\nOr you can manually update main.py line 319 to:")
        print(f'    self._root = ttk.Window(themename="{theme_name}")')
        print(f"\n{'='*60}\n")

    def on_close(self):
        """Handle window close."""
        self.root.quit()
        self.root.destroy()

    def run(self):
        """Start the preview."""
        self.root.mainloop()

if __name__ == "__main__":
    print("=" * 60)
    print("CLAUDE MEMORY - THEME PREVIEW TOOL")
    print("=" * 60)
    print("\nBrowse through all available themes using the buttons.")
    print("When you find one you like, click 'Apply This Theme'")
    print("and I'll show you how to set it.\n")

    preview = ThemePreview()
    preview.run()
