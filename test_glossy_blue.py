"""
Simple test - ONE deep blue glossy button
Forces window to front so you can actually see it
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk
import ctypes


def make_glossy_button(parent, text, color_top, color_bottom, width=300, height=70):
    """Create a glossy button"""
    padding = 25
    canvas = tk.Canvas(parent,
                      width=width + padding*2,
                      height=height + padding*2,
                      highlightthickness=0,
                      bg='#F0F0F0')

    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def render(is_hovered=False, is_pressed=False):
        """Render the button"""
        canvas.delete("all")

        lift = 4 if is_hovered else 0
        press = 3 if is_pressed else 0

        x = padding
        y = padding - lift + press
        w = width
        h = height

        img_w = width + padding * 2
        img_h = height + padding * 2

        img = Image.new('RGBA', (img_w, img_h), (240, 240, 240, 0))
        draw = ImageDraw.Draw(img)

        # Stronger shadow for more depth
        shadow_y = y + 12
        shadow_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)
        shadow_draw.ellipse([x, shadow_y, x+w, shadow_y+h], fill=(0, 0, 0, 150))
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(25))
        img = Image.alpha_composite(img, shadow_img)
        draw = ImageDraw.Draw(img)

        # Gradient
        top_rgb = hex_to_rgb(color_top)
        bottom_rgb = hex_to_rgb(color_bottom)

        for i in range(h):
            ratio = i / h
            r = int(top_rgb[0] * (1-ratio) + bottom_rgb[0] * ratio)
            g = int(top_rgb[1] * (1-ratio) + bottom_rgb[1] * ratio)
            b = int(top_rgb[2] * (1-ratio) + bottom_rgb[2] * ratio)
            draw.line([(x, y+i), (x+w, y+i)], fill=(r, g, b, 255), width=1)

        # Mask for rounded shape
        mask = Image.new('L', (img_w, img_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([x, y, x+w, y+h], fill=255)

        output = Image.new('RGBA', (img_w, img_h), (240, 240, 240, 0))
        output.paste(img, (0, 0), mask)

        # Create glossy highlight layer
        highlight = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        hl_draw = ImageDraw.Draw(highlight)

        # MUCH stronger glossy shine on top 50%
        shine_height = int(h * 0.5)
        for i in range(shine_height):
            # Much stronger opacity gradient - make it really visible
            ratio = i / shine_height
            # Quadratic falloff for stronger highlight
            opacity = int(255 * (1 - ratio * ratio))
            if opacity > 0:
                hl_draw.line([(x, y+i), (x+w, y+i)], fill=(255, 255, 255, opacity), width=1)

        # Composite highlight onto button
        final = Image.alpha_composite(output, highlight)

        draw = ImageDraw.Draw(final)

        # Brighter, thicker white border
        draw.ellipse([x, y, x+w, y+h], outline=(255, 255, 255, 255), width=4)

        # Text
        try:
            font = ImageFont.truetype("segoeuib.ttf", 18)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = x + (w - text_w) // 2
        text_y = y + (h - text_h) // 2

        # Text shadow
        draw.text((text_x+2, text_y+2), text, fill=(0, 0, 0, 150), font=font)
        # Main text
        draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)

        canvas.photo = ImageTk.PhotoImage(final)
        canvas.create_image(0, 0, anchor='nw', image=canvas.photo)

    # State tracking
    canvas.is_hovered = False
    canvas.is_pressed = False

    def on_click(e):
        canvas.is_pressed = True
        render(canvas.is_hovered, True)

    def on_release(e):
        canvas.is_pressed = False
        render(canvas.is_hovered, False)
        print(f"Button '{text}' clicked!")

    def on_hover(e):
        canvas.is_hovered = True
        render(True, canvas.is_pressed)
        canvas.config(cursor="hand2")

    def on_leave(e):
        canvas.is_hovered = False
        render(False, canvas.is_pressed)
        canvas.config(cursor="")

    canvas.bind("<Button-1>", on_click)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Enter>", on_hover)
    canvas.bind("<Leave>", on_leave)

    render()
    return canvas


# Create window
root = tk.Tk()
root.title("Deep Blue Glossy Button Test")
root.geometry("500x300")
root.configure(bg='#F0F0F0')

# Force to front
root.attributes('-topmost', True)
root.after(100, lambda: root.attributes('-topmost', False))
root.focus_force()

# Try to bring to foreground on Windows
try:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SetForegroundWindow(int(root.wm_frame(), 16))
except:
    pass

# Title
title = tk.Label(root,
                text="Deep Blue Glossy Button",
                font=("Segoe UI", 16, "bold"),
                bg='#F0F0F0',
                fg='#2c3e50')
title.pack(pady=20)

subtitle = tk.Label(root,
                   text="Hover and click to test interactivity",
                   font=("Segoe UI", 10),
                   bg='#F0F0F0',
                   fg='#7f8c8d')
subtitle.pack(pady=(0, 20))

# The glossy button - BLUE with more contrast
btn = make_glossy_button(root,
                         text="Click Me!",
                         color_top='#60A5FA',    # Lighter blue top (more visible gradient)
                         color_bottom='#1E3A8A',  # Deep blue bottom
                         width=300,
                         height=70)
btn.pack()

info = tk.Label(root,
               text="This is how it renders in desktop Python/tkinter",
               font=("Segoe UI", 9),
               bg='#F0F0F0',
               fg='#95a5a6')
info.pack(pady=20)

root.mainloop()
