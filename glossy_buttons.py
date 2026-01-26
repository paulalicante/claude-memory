"""
Glossy 3D Pill Buttons
The shiny, reflective style with strong highlights and depth
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter
from PIL import ImageTk


class GlossyButton(tk.Canvas):
    """
    Glossy 3D pill-shaped button with:
    - Strong top highlight (reflection)
    - Gradient from light to dark
    - White border
    - Deep shadow
    - Vibrant colors
    """

    PRESETS = {
        'cyan': ('#1DC9E8', '#0BA7C5'),
        'purple': ('#A855F7', '#7E22CE'),
        'gray': ('#D1D5DB', '#9CA3AF'),
        'green': ('#22C55E', '#16A34A'),
        'red': ('#DC2626', '#991B1B'),
        'pink': ('#EC4899', '#BE185D'),
        'orange': ('#F59E0B', '#D97706'),
        'blue': ('#3B82F6', '#1D4ED8'),
        'black': ('#374151', '#111827'),
        'lime': ('#84CC16', '#65A30D')
    }

    def __init__(self, parent, text="Button", command=None,
                 color='blue', width=280, height=80, **kwargs):

        padding = 30
        super().__init__(parent,
                        width=width + padding*2,
                        height=height + padding*2,
                        highlightthickness=0,
                        **kwargs)

        self.text = text
        self.command = command
        self.btn_width = width
        self.btn_height = height
        self.padding = padding
        self.color_name = color

        # Get color gradient
        if color in self.PRESETS:
            self.color_top, self.color_bottom = self.PRESETS[color]
        else:
            self.color_top = color
            self.color_bottom = color

        self.is_hovered = False
        self.is_pressed = False

        self.render()

        # Bind events
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def adjust_brightness(self, rgb, factor):
        """Adjust RGB brightness"""
        return tuple(min(255, int(c * factor)) for c in rgb)

    def render(self):
        """Draw the glossy button"""
        self.delete("all")

        # Position
        lift = 3 if self.is_hovered else 0
        press = 4 if self.is_pressed else 0

        x = self.padding
        y = self.padding - lift + press
        w = self.btn_width
        h = self.btn_height

        # Image size
        img_w = self.btn_width + self.padding * 2
        img_h = self.btn_height + self.padding * 2

        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw shadow
        shadow_y = y + 8
        shadow_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)

        shadow_draw.ellipse(
            [x, shadow_y, x + w, shadow_y + h],
            fill=(0, 0, 0, 100)
        )

        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(20))
        img = Image.alpha_composite(img, shadow_img)
        draw = ImageDraw.Draw(img)

        # Get color gradient
        top_rgb = self.hex_to_rgb(self.color_top)
        bottom_rgb = self.hex_to_rgb(self.color_bottom)

        # Main gradient (top to bottom)
        for i in range(h):
            ratio = i / h
            r = int(top_rgb[0] * (1-ratio) + bottom_rgb[0] * ratio)
            g = int(top_rgb[1] * (1-ratio) + bottom_rgb[1] * ratio)
            b = int(top_rgb[2] * (1-ratio) + bottom_rgb[2] * ratio)

            draw.line([(x, y+i), (x+w, y+i)], fill=(r, g, b, 255), width=1)

        # Create rounded mask
        mask = Image.new('L', (img_w, img_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([x, y, x + w, y + h], fill=255)

        # Apply mask
        output = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        output.paste(img, (0, 0), mask)

        draw = ImageDraw.Draw(output)

        # Add glossy highlight on top half
        highlight = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        hl_draw = ImageDraw.Draw(highlight)

        # Top shine (ellipse)
        shine_height = int(h * 0.45)
        for i in range(shine_height):
            # Fade from white to transparent
            opacity = int(180 * (1 - i/shine_height))
            if opacity > 0:
                hl_draw.line(
                    [(x, y+i), (x+w, y+i)],
                    fill=(255, 255, 255, opacity),
                    width=1
                )

        # Mask the highlight to button shape
        highlight_mask = Image.new('L', (img_w, img_h), 0)
        hm_draw = ImageDraw.Draw(highlight_mask)
        hm_draw.ellipse([x, y, x + w, y + h], fill=255)

        # Apply masks
        final = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        final.paste(output, (0, 0))
        final.paste(highlight, (0, 0), highlight_mask)

        draw = ImageDraw.Draw(final)

        # White border
        border_width = 3
        draw.ellipse(
            [x, y, x + w, y + h],
            outline=(255, 255, 255, 200),
            width=border_width
        )

        # Draw text
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("segoeuib.ttf", 16)  # Bold
        except:
            font = ImageFont.load_default()

        # Text shadow
        bbox = draw.textbbox((0, 0), self.text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        text_x = x + (w - text_w) // 2
        text_y = y + (h - text_h) // 2

        # Shadow
        draw.text(
            (text_x + 2, text_y + 2),
            self.text,
            fill=(0, 0, 0, 120),
            font=font
        )

        # Main text
        draw.text(
            (text_x, text_y),
            self.text,
            fill=(255, 255, 255, 255),
            font=font
        )

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(final)
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
    root.title("Glossy 3D Pill Buttons")
    root.geometry("800x900")
    root.configure(bg="#E5E7EB")

    title = tk.Label(
        root,
        text="Glossy 3D Button Gallery",
        font=("Segoe UI", 22, "bold"),
        bg="#E5E7EB",
        fg="#1F2937"
    )
    title.pack(pady=20)

    subtitle = tk.Label(
        root,
        text="Shiny, reflective, pill-shaped buttons with strong highlights",
        font=("Segoe UI", 11),
        bg="#E5E7EB",
        fg="#6B7280"
    )
    subtitle.pack(pady=(0, 20))

    # Create grid of buttons
    colors = [
        ('cyan', 'Cyan'),
        ('purple', 'Purple'),
        ('gray', 'Gray'),
        ('green', 'Green'),
        ('red', 'Red'),
        ('pink', 'Pink'),
        ('orange', 'Orange'),
        ('blue', 'Blue'),
        ('black', 'Black'),
        ('lime', 'Lime')
    ]

    # Two columns
    for i in range(0, len(colors), 2):
        row_frame = tk.Frame(root, bg="#E5E7EB")
        row_frame.pack(pady=8)

        # Left button
        color_id, color_name = colors[i]
        btn1 = GlossyButton(
            row_frame,
            text=color_name,
            command=lambda c=color_name: print(f"{c} clicked!"),
            color=color_id,
            width=280,
            height=80,
            bg="#E5E7EB"
        )
        btn1.pack(side=tk.LEFT, padx=15)

        # Right button
        if i + 1 < len(colors):
            color_id, color_name = colors[i+1]
            btn2 = GlossyButton(
                row_frame,
                text=color_name,
                command=lambda c=color_name: print(f"{c} clicked!"),
                color=color_id,
                width=280,
                height=80,
                bg="#E5E7EB"
            )
            btn2.pack(side=tk.LEFT, padx=15)

    info = tk.Label(
        root,
        text="Hover to see elevation • Click to see press effect",
        font=("Segoe UI", 10),
        bg="#E5E7EB",
        fg="#9CA3AF"
    )
    info.pack(pady=20)

    root.mainloop()
