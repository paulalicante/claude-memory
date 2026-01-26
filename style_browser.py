"""
Advanced Style Browser
Shows different button shapes, borders, fonts, and layouts
"""

import tkinter as tk
from tkinter import ttk as tkttk
import ttkbootstrap as ttb
from ttkbootstrap.constants import *
from custom_styles import CUSTOM_STYLES, apply_custom_style

# Combine theme + custom style
THEMES = ["cosmo", "flatly", "darkly", "superhero", "vapor"]

class StyleBrowser:
    def __init__(self):
        self.theme_index = 0
        self.style_index = 0
        self.theme_name = THEMES[0]
        self.style_name = list(CUSTOM_STYLES.keys())[0]

        self.root = ttb.Window(themename=self.theme_name)
        self.root.title("Advanced Style Browser")
        self.root.geometry("900x700")

        self.create_ui()
        self.apply_current_style()

    def create_ui(self):
        """Build the UI"""
        # Top bar with style info
        top_bar = ttb.Frame(self.root, padding=15, bootstyle="dark")
        top_bar.pack(fill=X)

        self.theme_label = ttb.Label(
            top_bar,
            text=f"Theme: {self.theme_name.upper()}",
            font=("Segoe UI", 12, "bold"),
            bootstyle="inverse-dark"
        )
        self.theme_label.pack(side=LEFT)

        self.style_label = ttb.Label(
            top_bar,
            text=f"Style: {CUSTOM_STYLES[self.style_name]['name']}",
            font=("Segoe UI", 12, "bold"),
            bootstyle="inverse-dark"
        )
        self.style_label.pack(side=RIGHT)

        # Description
        desc_frame = ttb.Frame(self.root, padding=10)
        desc_frame.pack(fill=X)

        self.desc_label = ttb.Label(
            desc_frame,
            text=CUSTOM_STYLES[self.style_name]['description'],
            font=("Segoe UI", 10),
            foreground="gray"
        )
        self.desc_label.pack()

        ttb.Separator(self.root, orient=HORIZONTAL).pack(fill=X, pady=5)

        # Main content area - split view
        content = ttb.Frame(self.root, padding=20)
        content.pack(fill=BOTH, expand=YES)

        # Left sidebar
        left = ttb.Frame(content)
        left.pack(side=LEFT, fill=Y, padx=(0, 15))

        ttb.Label(left, text="Button Styles:", font=("Segoe UI", 11, "bold")).pack(pady=(0, 10), anchor=W)

        ttb.Button(left, text="Primary Action", bootstyle="primary", width=25).pack(pady=4)
        ttb.Button(left, text="Success", bootstyle="success", width=25).pack(pady=4)
        ttb.Button(left, text="Warning", bootstyle="warning", width=25).pack(pady=4)
        ttb.Button(left, text="Danger", bootstyle="danger", width=25).pack(pady=4)
        ttb.Button(left, text="Info", bootstyle="info", width=25).pack(pady=4)
        ttb.Button(left, text="Secondary", bootstyle="secondary", width=25).pack(pady=4)

        # Right area - forms and entries
        right = ttb.Frame(content)
        right.pack(side=LEFT, fill=BOTH, expand=YES)

        ttb.Label(right, text="Form Elements:", font=("Segoe UI", 11, "bold")).pack(pady=(0, 10), anchor=W)

        # Search entry
        search_frame = ttb.Frame(right)
        search_frame.pack(fill=X, pady=5)
        ttb.Label(search_frame, text="Search:", width=12).pack(side=LEFT)
        ttb.Entry(search_frame).pack(side=LEFT, fill=X, expand=YES, padx=(5, 0))

        # Category dropdown
        cat_frame = ttb.Frame(right)
        cat_frame.pack(fill=X, pady=5)
        ttb.Label(cat_frame, text="Category:", width=12).pack(side=LEFT)
        combo = ttb.Combobox(cat_frame, values=["All", "Email", "Notes", "Tasks"])
        combo.pack(side=LEFT, fill=X, expand=YES, padx=(5, 0))
        combo.set("All")

        # Checkboxes
        ttb.Label(right, text="Options:", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5), anchor=W)
        ttb.Checkbutton(right, text="Show archived items").pack(anchor=W, pady=2)
        ttb.Checkbutton(right, text="Include tags in search").pack(anchor=W, pady=2)
        ttb.Checkbutton(right, text="Case sensitive").pack(anchor=W, pady=2)

        # Sample text area
        ttb.Label(right, text="Preview:", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5), anchor=W)
        text_frame = ttb.Frame(right)
        text_frame.pack(fill=BOTH, expand=YES, pady=5)

        text = tk.Text(text_frame, height=8, width=50, font=("Consolas", 9))
        text.pack(side=LEFT, fill=BOTH, expand=YES)
        text.insert("1.0", "Sample memory entry content...\n\nThis shows how text will look with the current font and styling choices.\n\nNotice the difference in:\n- Font family\n- Font size\n- Line spacing\n- Border styles")

        scroll = ttb.Scrollbar(text_frame, command=text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        text.config(yscrollcommand=scroll.set)

        ttb.Separator(self.root, orient=HORIZONTAL).pack(fill=X, pady=5)

        # Navigation footer
        footer = ttb.Frame(self.root, padding=15, bootstyle="secondary")
        footer.pack(fill=X)

        btn_row1 = ttb.Frame(footer)
        btn_row1.pack(pady=(0, 5))

        ttb.Label(btn_row1, text="Color Theme:", font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 10))
        ttb.Button(btn_row1, text="← Prev Theme", command=self.prev_theme, bootstyle="light", width=15).pack(side=LEFT, padx=2)
        ttb.Button(btn_row1, text="Next Theme →", command=self.next_theme, bootstyle="light", width=15).pack(side=LEFT, padx=2)

        btn_row2 = ttb.Frame(footer)
        btn_row2.pack()

        ttb.Label(btn_row2, text="Visual Style:", font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 10))
        ttb.Button(btn_row2, text="← Prev Style", command=self.prev_style, bootstyle="light", width=15).pack(side=LEFT, padx=2)
        ttb.Button(btn_row2, text="Next Style →", command=self.next_style, bootstyle="light", width=15).pack(side=LEFT, padx=2)
        ttb.Button(btn_row2, text="✓ Apply This", command=self.print_config, bootstyle="success", width=15).pack(side=LEFT, padx=10)

    def next_theme(self):
        """Switch to next color theme"""
        self.theme_index = (self.theme_index + 1) % len(THEMES)
        self.theme_name = THEMES[self.theme_index]
        self.root.style.theme_use(self.theme_name)
        self.theme_label.config(text=f"Theme: {self.theme_name.upper()}")
        self.apply_current_style()

    def prev_theme(self):
        """Switch to previous color theme"""
        self.theme_index = (self.theme_index - 1) % len(THEMES)
        self.theme_name = THEMES[self.theme_index]
        self.root.style.theme_use(self.theme_name)
        self.theme_label.config(text=f"Theme: {self.theme_name.upper()}")
        self.apply_current_style()

    def next_style(self):
        """Switch to next visual style"""
        style_keys = list(CUSTOM_STYLES.keys())
        self.style_index = (self.style_index + 1) % len(style_keys)
        self.style_name = style_keys[self.style_index]
        self.apply_current_style()

    def prev_style(self):
        """Switch to previous visual style"""
        style_keys = list(CUSTOM_STYLES.keys())
        self.style_index = (self.style_index - 1) % len(style_keys)
        self.style_name = style_keys[self.style_index]
        self.apply_current_style()

    def apply_current_style(self):
        """Apply the current style configuration"""
        result = apply_custom_style(self.root, self.style_name)
        self.style_label.config(text=f"Style: {CUSTOM_STYLES[self.style_name]['name']}")
        self.desc_label.config(text=CUSTOM_STYLES[self.style_name]['description'])
        print(f"Applied: {self.theme_name} + {self.style_name}")

    def print_config(self):
        """Print how to apply this configuration"""
        print("\n" + "="*60)
        print(f"TO APPLY THIS CONFIGURATION:")
        print("="*60)
        print(f"\nColor Theme: {self.theme_name}")
        print(f"Visual Style: {CUSTOM_STYLES[self.style_name]['name']}")
        print(f"\nTell Claude: 'Apply {self.theme_name} theme with {self.style_name} style'")
        print("="*60 + "\n")

    def run(self):
        """Start the browser"""
        self.root.mainloop()

if __name__ == "__main__":
    print("="*60)
    print("ADVANCED STYLE BROWSER")
    print("="*60)
    print("\nThis shows REAL visual variety:")
    print("- Different button shapes and borders")
    print("- Various font families and sizes")
    print("- Different padding and spacing")
    print("- Unique relief styles (flat, raised, sunken, etc.)")
    print("\nUse the navigation buttons to explore!\n")

    browser = StyleBrowser()
    browser.run()
