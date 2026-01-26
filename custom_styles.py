"""
Custom Style Configurations for Claude Memory
Goes beyond color themes to customize button shapes, borders, fonts, etc.
"""

import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *


def apply_modern_minimalist(root):
    """
    Ultra-minimal flat design
    - Very thin borders
    - Sans-serif fonts
    - Lots of whitespace
    - Subtle shadows
    """
    style = root.style

    # Fonts
    style.configure('.', font=('Segoe UI Light', 10))
    style.configure('TButton', font=('Segoe UI Semibold', 10))
    style.configure('Header.TLabel', font=('Segoe UI Light', 14))

    # Buttons - ultra flat with thin borders
    style.configure('TButton',
                   borderwidth=1,
                   relief='flat',
                   padding=(20, 10))

    # Entry fields - minimal
    style.configure('TEntry',
                   borderwidth=1,
                   relief='solid',
                   padding=8)

    # Frames - clean
    style.configure('TFrame', borderwidth=0)

    return "Modern Minimalist Applied"


def apply_classic_3d(root):
    """
    Traditional 3D Windows look
    - Raised/sunken buttons
    - Beveled edges
    - Classic relief styles
    - MS Sans Serif feel
    """
    style = root.style

    # Fonts - classic Windows
    style.configure('.', font=('MS Sans Serif', 9))
    style.configure('TButton', font=('MS Sans Serif', 9, 'bold'))

    # Buttons - 3D raised effect
    style.configure('TButton',
                   borderwidth=2,
                   relief='raised',
                   padding=(15, 8))

    # Entry fields - sunken
    style.configure('TEntry',
                   borderwidth=2,
                   relief='sunken',
                   padding=5)

    # Frames - groove borders
    style.configure('Card.TFrame',
                   borderwidth=2,
                   relief='groove',
                   padding=10)

    return "Classic 3D Applied"


def apply_rounded_bubble(root):
    """
    Soft, rounded, bubbly design
    - Heavy rounded corners
    - Thick borders
    - Playful fonts
    - Generous padding
    """
    style = root.style

    # Fonts - rounded feel
    style.configure('.', font=('Segoe UI', 10))
    style.configure('TButton', font=('Segoe UI', 10, 'bold'))
    style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'))

    # Buttons - extra padding for bubble effect
    style.configure('TButton',
                   borderwidth=2,
                   relief='raised',
                   padding=(25, 12))

    # Entry fields
    style.configure('TEntry',
                   borderwidth=2,
                   relief='solid',
                   padding=10)

    return "Rounded Bubble Applied"


def apply_compact_dense(root):
    """
    Information-dense layout
    - Smaller fonts
    - Tight spacing
    - Thin borders
    - Maximum info per screen
    """
    style = root.style

    # Fonts - compact
    style.configure('.', font=('Segoe UI', 8))
    style.configure('TButton', font=('Segoe UI', 8, 'bold'))
    style.configure('Header.TLabel', font=('Segoe UI', 11, 'bold'))

    # Buttons - compact
    style.configure('TButton',
                   borderwidth=1,
                   relief='flat',
                   padding=(10, 4))

    # Entry fields - minimal padding
    style.configure('TEntry',
                   borderwidth=1,
                   relief='solid',
                   padding=4)

    return "Compact Dense Applied"


def apply_large_touch(root):
    """
    Touch-friendly design
    - Large buttons
    - Big fonts
    - Generous spacing
    - High contrast
    """
    style = root.style

    # Fonts - large
    style.configure('.', font=('Segoe UI', 12))
    style.configure('TButton', font=('Segoe UI', 12, 'bold'))
    style.configure('Header.TLabel', font=('Segoe UI', 18, 'bold'))

    # Buttons - big touch targets
    style.configure('TButton',
                   borderwidth=2,
                   relief='raised',
                   padding=(30, 15))

    # Entry fields - large
    style.configure('TEntry',
                   borderwidth=2,
                   relief='solid',
                   padding=12)

    return "Large Touch Applied"


def apply_elegant_serif(root):
    """
    Elegant serif design
    - Serif fonts (Georgia, Times)
    - Subtle colors
    - Refined spacing
    - Professional look
    """
    style = root.style

    # Fonts - serif
    style.configure('.', font=('Georgia', 10))
    style.configure('TButton', font=('Georgia', 10, 'bold'))
    style.configure('Header.TLabel', font=('Georgia', 14, 'bold'))

    # Buttons - refined
    style.configure('TButton',
                   borderwidth=1,
                   relief='solid',
                   padding=(18, 10))

    # Entry fields
    style.configure('TEntry',
                   borderwidth=1,
                   relief='solid',
                   padding=8)

    return "Elegant Serif Applied"


# Style registry
CUSTOM_STYLES = {
    'modern_minimalist': {
        'name': 'Modern Minimalist',
        'description': 'Ultra-flat, thin borders, lots of whitespace',
        'apply': apply_modern_minimalist
    },
    'classic_3d': {
        'name': 'Classic 3D',
        'description': 'Traditional Windows with raised buttons and beveled edges',
        'apply': apply_classic_3d
    },
    'rounded_bubble': {
        'name': 'Rounded Bubble',
        'description': 'Soft rounded design with generous padding',
        'apply': apply_rounded_bubble
    },
    'compact_dense': {
        'name': 'Compact Dense',
        'description': 'Small fonts, tight spacing, maximum information',
        'apply': apply_compact_dense
    },
    'large_touch': {
        'name': 'Large Touch',
        'description': 'Big buttons and fonts for touch screens',
        'apply': apply_large_touch
    },
    'elegant_serif': {
        'name': 'Elegant Serif',
        'description': 'Refined serif fonts with professional styling',
        'apply': apply_elegant_serif
    }
}


def apply_custom_style(root, style_name):
    """Apply a custom style to the root window."""
    if style_name in CUSTOM_STYLES:
        return CUSTOM_STYLES[style_name]['apply'](root)
    else:
        return f"Unknown style: {style_name}"
