"""
2025-2026 Modern UI Components for PC Applications
Implements: Glassmorphism, Claymorphism, Micro-interactions, FABs, Ghost Buttons
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL import ImageTk
import math


class ModernButton2025(tk.Canvas):
    """
    Modern button with 2025-2026 design trends:
    - Glassmorphism
    - Claymorphism
    - Soft 3D effects
    - Micro-interactions
    - Rounded corners
    - Subtle shadows & elevation
    """

    STYLES = {
        'filled_primary': {
            'bg_color': '#0078D4',
            'text_color': '#FFFFFF',
            'corner_radius': 8,
            'shadow_blur': 12,
            'shadow_offset': (0, 4),
            'shadow_opacity': 60,
            'hover_lift': 2,
            'press_offset': 2,
            'border_width': 0
        },
        'glass': {
            'bg_color': 'rgba(255,255,255,0.15)',
            'text_color': '#000000',
            'corner_radius': 12,
            'shadow_blur': 20,
            'shadow_offset': (0, 8),
            'shadow_opacity': 40,
            'hover_lift': 3,
            'press_offset': 1,
            'border_width': 1,
            'border_color': 'rgba(255,255,255,0.3)',
            'blur_background': True
        },
        'clay': {
            'bg_color': '#E8ECF0',
            'text_color': '#2C3E50',
            'corner_radius': 16,
            'shadow_blur': 15,
            'shadow_offset': (6, 6),
            'shadow_opacity': 80,
            'shadow_color': '#A3B9CC',
            'highlight_shadow': True,
            'highlight_color': '#FFFFFF',
            'highlight_offset': (-6, -6),
            'hover_lift': 1,
            'press_offset': 3,
            'puffy': True
        },
        'ghost': {
            'bg_color': 'transparent',
            'text_color': '#0078D4',
            'corner_radius': 8,
            'border_width': 2,
            'border_color': '#0078D4',
            'shadow_blur': 0,
            'hover_lift': 0,
            'press_offset': 0,
            'hover_bg': 'rgba(0,120,212,0.1)'
        },
        'fluent': {
            'bg_color': '#005A9E',
            'text_color': '#FFFFFF',
            'corner_radius': 4,
            'shadow_blur': 8,
            'shadow_offset': (0, 2),
            'shadow_opacity': 50,
            'hover_lift': 1,
            'press_offset': 1,
            'reveal_effect': True  # Fluent Design reveal on hover
        },
        'mac_style': {
            'bg_color': '#007AFF',
            'text_color': '#FFFFFF',
            'corner_radius': 10,
            'shadow_blur': 10,
            'shadow_offset': (0, 3),
            'shadow_opacity': 50,
            'hover_lift': 2,
            'press_offset': 1,
            'gradient': True,
            'gradient_end': '#0051D5'
        }
    }

    def __init__(self, parent, text="Button", command=None,
                 style='filled_primary', width=140, height=40, **kwargs):

        # Add padding for shadows
        padding = 25
        super().__init__(parent,
                        width=width + padding*2,
                        height=height + padding*2,
                        highlightthickness=0,
                        **kwargs)

        self.text = text
        self.command = command
        self.btn_width = width
        self.btn_height = height
        self.style_name = style
        self.padding = padding

        self.is_hovered = False
        self.is_pressed = False
        self.hover_progress = 0.0  # For smooth animations

        # Load style configuration
        self.style_config = self.STYLES.get(style, self.STYLES['filled_primary'])

        # Render initial state
        self.render()

        # Bind events
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def parse_color(self, color_str):
        """Parse color string (supports rgba and hex)"""
        if color_str == 'transparent':
            return None
        elif color_str.startswith('rgba'):
            # Parse rgba(r,g,b,a)
            parts = color_str[5:-1].split(',')
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            a = int(float(parts[3]) * 255)
            return (r, g, b, a)
        else:
            # Hex color
            hex_color = color_str.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return rgb + (255,)

    def render(self):
        """Render the button"""
        self.delete("all")

        # Calculate button position with hover lift
        lift = 0
        if self.is_hovered and not self.is_pressed:
            lift = self.style_config.get('hover_lift', 0)

        press = 0
        if self.is_pressed:
            press = self.style_config.get('press_offset', 0)

        x = self.padding
        y = self.padding - lift + press
        w = self.btn_width
        h = self.btn_height

        # Create image
        img_w = self.btn_width + self.padding * 2
        img_h = self.btn_height + self.padding * 2
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw shadow
        if self.style_config.get('shadow_blur', 0) > 0:
            shadow_x = x + self.style_config['shadow_offset'][0]
            shadow_y = y + self.style_config['shadow_offset'][1]

            shadow_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_img)

            shadow_color = self.style_config.get('shadow_color', '#000000')
            if isinstance(shadow_color, str):
                shadow_rgb = self.parse_color(shadow_color)[:3]
            else:
                shadow_rgb = shadow_color

            shadow_opacity = self.style_config.get('shadow_opacity', 60)
            shadow_rgba = shadow_rgb + (shadow_opacity,)

            shadow_draw.rounded_rectangle(
                [shadow_x, shadow_y, shadow_x + w, shadow_y + h],
                radius=self.style_config['corner_radius'],
                fill=shadow_rgba
            )

            shadow_img = shadow_img.filter(
                ImageFilter.GaussianBlur(self.style_config['shadow_blur'])
            )
            img = Image.alpha_composite(img, shadow_img)
            draw = ImageDraw.Draw(img)

        # Draw highlight shadow for clay/neumorphism
        if self.style_config.get('highlight_shadow'):
            hl_x = x + self.style_config['highlight_offset'][0]
            hl_y = y + self.style_config['highlight_offset'][1]

            hl_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
            hl_draw = ImageDraw.Draw(hl_img)

            hl_color = self.parse_color(self.style_config['highlight_color'])
            hl_draw.rounded_rectangle(
                [hl_x, hl_y, hl_x + w, hl_y + h],
                radius=self.style_config['corner_radius'],
                fill=hl_color
            )

            hl_img = hl_img.filter(ImageFilter.GaussianBlur(10))
            img = Image.alpha_composite(img, hl_img)
            draw = ImageDraw.Draw(img)

        # Draw button background
        bg_color = self.style_config['bg_color']

        if bg_color and bg_color != 'transparent':
            bg_rgba = self.parse_color(bg_color)

            # Handle gradient
            if self.style_config.get('gradient'):
                gradient_end = self.parse_color(self.style_config['gradient_end'])
                for i in range(h):
                    ratio = i / h
                    r = int(bg_rgba[0] * (1-ratio) + gradient_end[0] * ratio)
                    g = int(bg_rgba[1] * (1-ratio) + gradient_end[1] * ratio)
                    b = int(bg_rgba[2] * (1-ratio) + gradient_end[2] * ratio)
                    a = int(bg_rgba[3] * (1-ratio) + gradient_end[3] * ratio)

                    draw.line([(x, y+i), (x+w, y+i)], fill=(r,g,b,a), width=1)
            else:
                # Solid or glassmorphism background
                if self.is_hovered and self.style_config.get('hover_bg'):
                    bg_rgba = self.parse_color(self.style_config['hover_bg'])

                draw.rounded_rectangle(
                    [x, y, x + w, y + h],
                    radius=self.style_config['corner_radius'],
                    fill=bg_rgba
                )

        # Draw border
        if self.style_config.get('border_width', 0) > 0:
            border_color = self.style_config.get('border_color', '#000000')
            border_rgba = self.parse_color(border_color)

            draw.rounded_rectangle(
                [x, y, x + w, y + h],
                radius=self.style_config['corner_radius'],
                outline=border_rgba,
                width=self.style_config['border_width']
            )

        # Add "puffy" effect for claymorphism
        if self.style_config.get('puffy'):
            # Top highlight
            highlight = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
            hl_draw = ImageDraw.Draw(highlight)

            hl_draw.rounded_rectangle(
                [x, y, x + w, y + h//2],
                radius=self.style_config['corner_radius'],
                fill=(255, 255, 255, 30)
            )

            img = Image.alpha_composite(img, highlight)
            draw = ImageDraw.Draw(img)

        # Draw text
        try:
            font = ImageFont.truetype("segoeui.ttf", 12)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), self.text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        text_x = x + (w - text_w) // 2
        text_y = y + (h - text_h) // 2

        text_rgba = self.parse_color(self.style_config['text_color'])
        draw.text((text_x, text_y), self.text, fill=text_rgba, font=font)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(img)
        self.create_image(0, 0, anchor='nw', image=self.photo)

    def on_click(self, event):
        """Handle click"""
        self.is_pressed = True
        self.render()

    def on_release(self, event):
        """Handle release"""
        self.is_pressed = False
        self.render()
        if self.command:
            self.command()

    def on_hover(self, event):
        """Handle hover"""
        self.is_hovered = True
        self.render()
        self.config(cursor="hand2")

    def on_leave(self, event):
        """Handle leave"""
        self.is_hovered = False
        self.render()
        self.config(cursor="")


class FloatingActionButton(tk.Canvas):
    """
    Floating Action Button (FAB)
    Circular button with icon, elevated with shadow
    """

    def __init__(self, parent, icon="➕", command=None, size=56, **kwargs):
        padding = 20
        super().__init__(parent,
                        width=size + padding*2,
                        height=size + padding*2,
                        highlightthickness=0,
                        **kwargs)

        self.icon = icon
        self.command = command
        self.size = size
        self.padding = padding
        self.is_hovered = False
        self.is_pressed = False

        self.render()

        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def render(self):
        """Render FAB"""
        self.delete("all")

        lift = 4 if self.is_hovered else 0
        press = 2 if self.is_pressed else 0

        img_size = self.size + self.padding * 2
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        x = self.padding
        y = self.padding - lift + press
        r = self.size // 2

        # Shadow
        shadow_img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)

        shadow_y = y + 6
        shadow_draw.ellipse(
            [x, shadow_y, x + self.size, shadow_y + self.size],
            fill=(0, 0, 0, 80)
        )

        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(15))
        img = Image.alpha_composite(img, shadow_img)
        draw = ImageDraw.Draw(img)

        # Button circle
        bg_color = (0, 122, 255, 255)
        if self.is_hovered:
            bg_color = (0, 100, 230, 255)

        draw.ellipse(
            [x, y, x + self.size, y + self.size],
            fill=bg_color
        )

        # Icon
        try:
            font = ImageFont.truetype("seguisym.ttf", 24)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), self.icon, font=font)
        icon_w = bbox[2] - bbox[0]
        icon_h = bbox[3] - bbox[1]

        icon_x = x + (self.size - icon_w) // 2
        icon_y = y + (self.size - icon_h) // 2

        draw.text((icon_x, icon_y), self.icon, fill=(255, 255, 255, 255), font=font)

        self.photo = ImageTk.PhotoImage(img)
        self.create_image(0, 0, anchor='nw', image=self.photo)

    def on_click(self, event):
        self.is_pressed = True
        self.render()

    def on_release(self, event):
        self.is_pressed = False
        self.render()
        if self.command:
            self.command()

    def on_hover(self, event):
        self.is_hovered = True
        self.render()
        self.config(cursor="hand2")

    def on_leave(self, event):
        self.is_hovered = False
        self.render()
        self.config(cursor="")


# Demo
if __name__ == "__main__":
    root = tk.Tk()
    root.title("2025-2026 Modern UI Gallery")
    root.geometry("900x700")
    root.configure(bg="#F0F2F5")

    # Title
    title = tk.Label(root, text="Modern PC Button Styles (2025-2026)",
                    font=("Segoe UI", 20, "bold"), bg="#F0F2F5", fg="#1C1E21")
    title.pack(pady=20)

    # Button styles showcase
    styles = [
        ('filled_primary', 'Filled Primary', 'Main action button'),
        ('glass', 'Glassmorphism', 'Transparent with blur effect'),
        ('clay', 'Claymorphism', 'Soft 3D puffy look'),
        ('ghost', 'Ghost Button', 'Transparent with border'),
        ('fluent', 'Fluent Design', 'Microsoft Fluent style'),
        ('mac_style', 'macOS Style', 'Apple design language')
    ]

    for style_id, name, desc in styles:
        frame = tk.Frame(root, bg="#F0F2F5")
        frame.pack(pady=8)

        # Label column
        label_frame = tk.Frame(frame, bg="#F0F2F5", width=250)
        label_frame.pack(side=tk.LEFT, padx=15)
        label_frame.pack_propagate(False)

        tk.Label(label_frame, text=name,
                font=("Segoe UI", 11, "bold"),
                bg="#F0F2F5", fg="#1C1E21", anchor='w').pack(anchor='w')

        tk.Label(label_frame, text=desc,
                font=("Segoe UI", 9),
                bg="#F0F2F5", fg="#65676B", anchor='w').pack(anchor='w')

        # Button
        btn = ModernButton2025(frame, text="Click Me",
                              command=lambda n=name: print(f"{n} clicked!"),
                              style=style_id, width=160, height=40, bg="#F0F2F5")
        btn.pack(side=tk.LEFT, padx=10)

    # Separator
    sep_frame = tk.Frame(root, bg="#DADDE1", height=1)
    sep_frame.pack(fill=tk.X, pady=20, padx=50)

    # FAB showcase
    fab_frame = tk.Frame(root, bg="#F0F2F5")
    fab_frame.pack(pady=15)

    tk.Label(fab_frame, text="Floating Action Button (FAB)",
            font=("Segoe UI", 11, "bold"),
            bg="#F0F2F5", fg="#1C1E21").pack(side=tk.LEFT, padx=15)

    fab = FloatingActionButton(fab_frame, icon="➕",
                               command=lambda: print("FAB clicked!"),
                               size=56, bg="#F0F2F5")
    fab.pack(side=tk.LEFT, padx=10)

    # Instructions
    info = tk.Label(root,
                   text="Hover and click to see micro-interactions\nNotice: shadows, elevation, rounded corners, smooth feedback",
                   font=("Segoe UI", 9),
                   bg="#F0F2F5", fg="#65676B",
                   justify=tk.CENTER)
    info.pack(pady=20)

    root.mainloop()
