"""
Modern Custom Widgets with Real Visual Effects
Uses Canvas and PIL to create beautiful buttons with gradients, shadows, and depth
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL import ImageTk
import math


class ModernButton(tk.Canvas):
    """
    Custom button with real visual effects:
    - Gradient backgrounds
    - Drop shadows
    - Rounded corners
    - Hover animations
    - Click feedback
    """

    def __init__(self, parent, text="Button", command=None,
                 width=200, height=50, style="modern_blue", **kwargs):
        super().__init__(parent, width=width, height=height,
                        highlightthickness=0, **kwargs)

        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.style_name = style
        self.is_hovered = False
        self.is_pressed = False

        # Load style
        self.load_style(style)

        # Draw button
        self.render()

        # Bind events
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def load_style(self, style):
        """Load color scheme and settings for style"""
        styles = {
            'modern_blue': {
                'gradient_top': '#4A90E2',
                'gradient_bottom': '#357ABD',
                'shadow_color': '#000000',
                'shadow_opacity': 80,
                'text_color': '#FFFFFF',
                'hover_brightness': 1.1,
                'border_radius': 8,
                'shadow_blur': 10,
                'shadow_offset': (0, 4)
            },
            'green_success': {
                'gradient_top': '#5CB85C',
                'gradient_bottom': '#4CAE4C',
                'shadow_color': '#000000',
                'shadow_opacity': 80,
                'text_color': '#FFFFFF',
                'hover_brightness': 1.1,
                'border_radius': 8,
                'shadow_blur': 10,
                'shadow_offset': (0, 4)
            },
            'red_danger': {
                'gradient_top': '#D9534F',
                'gradient_bottom': '#C9302C',
                'shadow_color': '#000000',
                'shadow_opacity': 80,
                'text_color': '#FFFFFF',
                'hover_brightness': 1.1,
                'border_radius': 8,
                'shadow_blur': 10,
                'shadow_offset': (0, 4)
            },
            'glass_morphism': {
                'gradient_top': 'rgba(255,255,255,0.2)',
                'gradient_bottom': 'rgba(255,255,255,0.1)',
                'shadow_color': '#000000',
                'shadow_opacity': 40,
                'text_color': '#333333',
                'hover_brightness': 1.05,
                'border_radius': 12,
                'shadow_blur': 15,
                'shadow_offset': (0, 6),
                'border': '#FFFFFF',
                'border_width': 1
            },
            'neumorphism': {
                'gradient_top': '#E0E5EC',
                'gradient_bottom': '#E0E5EC',
                'shadow_color': '#A3B1C6',
                'shadow_opacity': 255,
                'text_color': '#2C3E50',
                'hover_brightness': 1.0,
                'border_radius': 15,
                'shadow_blur': 20,
                'shadow_offset': (5, 5),
                'highlight_shadow': '#FFFFFF',
                'highlight_offset': (-5, -5)
            },
            'material': {
                'gradient_top': '#6200EA',
                'gradient_bottom': '#6200EA',
                'shadow_color': '#6200EA',
                'shadow_opacity': 100,
                'text_color': '#FFFFFF',
                'hover_brightness': 1.15,
                'border_radius': 4,
                'shadow_blur': 8,
                'shadow_offset': (0, 2)
            },
            'neon': {
                'gradient_top': '#00F5FF',
                'gradient_bottom': '#00D4FF',
                'shadow_color': '#00F5FF',
                'shadow_opacity': 200,
                'text_color': '#000000',
                'hover_brightness': 1.2,
                'border_radius': 25,
                'shadow_blur': 25,
                'shadow_offset': (0, 0),
                'glow': True
            }
        }

        self.style = styles.get(style, styles['modern_blue'])

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def adjust_brightness(self, color, factor):
        """Adjust color brightness"""
        r, g, b = self.hex_to_rgb(color)
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return f'#{r:02x}{g:02x}{b:02x}'

    def render(self):
        """Draw the button with all effects"""
        # Clear canvas
        self.delete("all")

        # Create image with extra space for shadow
        padding = 15
        img_width = self.width + padding * 2
        img_height = self.height + padding * 2

        # Create transparent image
        img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Button position (accounting for shadow)
        x = padding
        y = padding
        w = self.width
        h = self.height

        # Draw shadow
        shadow_x = x + self.style['shadow_offset'][0]
        shadow_y = y + self.style['shadow_offset'][1]

        shadow_img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)

        # Shadow rounded rectangle
        shadow_color = self.hex_to_rgb(self.style['shadow_color'])
        shadow_rgba = shadow_color + (self.style['shadow_opacity'],)

        shadow_draw.rounded_rectangle(
            [shadow_x, shadow_y, shadow_x + w, shadow_y + h],
            radius=self.style['border_radius'],
            fill=shadow_rgba
        )

        # Blur shadow
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(self.style['shadow_blur']))

        # Composite shadow onto main image
        img = Image.alpha_composite(img, shadow_img)
        draw = ImageDraw.Draw(img)

        # Determine colors based on state
        top_color = self.style['gradient_top']
        bottom_color = self.style['gradient_bottom']

        if self.is_hovered and not self.is_pressed:
            brightness = self.style['hover_brightness']
            top_color = self.adjust_brightness(top_color, brightness)
            bottom_color = self.adjust_brightness(bottom_color, brightness)
        elif self.is_pressed:
            # Darken when pressed
            top_color = self.adjust_brightness(top_color, 0.9)
            bottom_color = self.adjust_brightness(bottom_color, 0.9)
            y += 2  # Push down effect

        # Draw gradient button
        top_rgb = self.hex_to_rgb(top_color)
        bottom_rgb = self.hex_to_rgb(bottom_color)

        for i in range(h):
            # Linear interpolation between top and bottom colors
            ratio = i / h
            r = int(top_rgb[0] * (1 - ratio) + bottom_rgb[0] * ratio)
            g = int(top_rgb[1] * (1 - ratio) + bottom_rgb[1] * ratio)
            b = int(top_rgb[2] * (1 - ratio) + bottom_rgb[2] * ratio)

            color = (r, g, b, 255)
            draw.line([(x, y + i), (x + w, y + i)], fill=color, width=1)

        # Overlay rounded rectangle mask for clean edges
        mask = Image.new('L', (img_width, img_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [x, y, x + w, y + h],
            radius=self.style['border_radius'],
            fill=255
        )

        # Apply mask
        output = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        output.paste(img, (0, 0))

        # Draw button text
        try:
            font = ImageFont.truetype("segoeui.ttf", 14)
        except:
            font = ImageFont.load_default()

        # Get text bounding box
        bbox = draw.textbbox((0, 0), self.text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = x + (w - text_width) // 2
        text_y = y + (h - text_height) // 2

        text_color = self.style['text_color']
        draw.text((text_x, text_y), self.text, fill=text_color, font=font)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(output)

        # Display on canvas
        self.create_image(0, 0, anchor='nw', image=self.photo)

    def on_click(self, event):
        """Handle mouse click"""
        self.is_pressed = True
        self.render()

    def on_release(self, event):
        """Handle mouse release"""
        self.is_pressed = False
        self.render()

        if self.command:
            self.command()

    def on_hover(self, event):
        """Handle mouse enter"""
        self.is_hovered = True
        self.render()
        self.config(cursor="hand2")

    def on_leave(self, event):
        """Handle mouse leave"""
        self.is_hovered = False
        self.render()
        self.config(cursor="")


# Demo window
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Modern Button Styles")
    root.geometry("800x600")
    root.configure(bg="#F5F5F5")

    title = tk.Label(root, text="Modern Button Gallery",
                    font=("Segoe UI", 18, "bold"), bg="#F5F5F5")
    title.pack(pady=20)

    styles = [
        ('modern_blue', 'Modern Blue'),
        ('green_success', 'Success Green'),
        ('red_danger', 'Danger Red'),
        ('material', 'Material Design'),
        ('neumorphism', 'Neumorphism'),
        ('neon', 'Neon Glow')
    ]

    for style_id, style_name in styles:
        frame = tk.Frame(root, bg="#F5F5F5")
        frame.pack(pady=10)

        label = tk.Label(frame, text=f"{style_name}:",
                        font=("Segoe UI", 11), bg="#F5F5F5", width=20, anchor='w')
        label.pack(side=tk.LEFT, padx=10)

        btn = ModernButton(frame, text="Click Me!",
                          command=lambda s=style_name: print(f"{s} clicked!"),
                          style=style_id, width=200, height=50, bg="#F5F5F5")
        btn.pack(side=tk.LEFT, padx=10)

    root.mainloop()
