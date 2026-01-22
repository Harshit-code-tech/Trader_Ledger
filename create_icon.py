"""
Create application icon for Trader Ledger
Simple fallback if PIL not available
"""

import struct

def create_basic_ico():
    """Create a minimal valid .ico file"""
    # 32x32 green icon
    width, height = 32, 32
    
    # ICO header
    ico_header = struct.pack('<HHH', 0, 1, 1)  # Reserved, Type, Count
    
    # Image directory entry
    img_dir = struct.pack('<BBBBHHII',
        width,      # Width
        height,     # Height
        0,          # Color palette
        0,          # Reserved
        1,          # Color planes
        32,         # Bits per pixel
        0,          # Image size (calculated later)
        22          # Image offset
    )
    
    # Create simple green bitmap
    green = b'\x00\x80\x00\xff'  # BGRA: Green with full opacity
    pixels = green * (width * height)
    
    # Update image size
    img_dir = struct.pack('<BBBBHHII',
        width, height, 0, 0, 1, 32,
        len(pixels),
        22
    )
    
    # Write ICO file
    with open('icon.ico', 'wb') as f:
        f.write(ico_header)
        f.write(img_dir)
        f.write(pixels)
    
    print("✓ Basic icon created: icon.ico")

try:
    from PIL import Image, ImageDraw, ImageFont
    
    # Create a 256x256 image with gradient background
    size = 256
    img = Image.new('RGB', (size, size), color='#2c3e50')
    draw = ImageDraw.Draw(img)
    
    # Draw gradient
    for i in range(size):
        color_value = int(44 + (i / size) * 40)
        draw.rectangle([(0, i), (size, i+1)], fill=(color_value, 62, 80))
    
    # Draw border
    border_width = 8
    draw.rectangle(
        [(border_width, border_width), (size-border_width, size-border_width)],
        outline='#27ae60',
        width=border_width
    )
    
    # Draw rupee symbol
    try:
        font = ImageFont.truetype("arial.ttf", 120)
    except:
        try:
            font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 120)
        except:
            font = ImageFont.load_default()
    
    text = "₹"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((size - text_width) // 2, (size - text_height) // 2 - 20)
    
    # Draw text with shadow
    draw.text((position[0]+4, position[1]+4), text, font=font, fill='#000000')
    draw.text(position, text, font=font, fill='#27ae60')
    
    # Save as ICO with multiple sizes
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save('icon.ico', format='ICO', sizes=icon_sizes)
    
    print("✓ Professional icon created: icon.ico")
    
except ImportError:
    print("⚠ Pillow not available, creating basic icon...")
    create_basic_ico()
    
except Exception as e:
    print(f"⚠ PIL failed ({e}), creating basic icon...")
    create_basic_ico()
