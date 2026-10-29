#!/usr/bin/env python3
"""
Tự động vẽ Thẻ Bảng Điều Hành Tương Tác Native (Card Image) cho Sếp Hoàng.
Thiết kế chuẩn tỉ lệ Mobile Zalo, phong cách Dark Mode mạ vàng sang trọng.
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = Path(__file__).resolve().parent / "generated_cards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CARD_PATH = OUTPUT_DIR / "hermes_executive_card.png"

# Color Palette
BG_COLOR_TOP = (8, 12, 20)
BG_COLOR_BOTTOM = (15, 23, 42)
BORDER_COLOR = (245, 158, 11, 200) # Gold Amber
CARD_BG = (17, 27, 49)
ROW_BG = (22, 34, 61)
ROW_BORDER = (45, 62, 98)
TEXT_WHITE = (255, 255, 255)
TEXT_GOLD = (251, 191, 36)
TEXT_MUTED = (148, 163, 184)
GREEN_DOT = (52, 211, 153)

def get_font(name: str, size: int):
    font_paths = [
        f"C:\\Windows\\Fonts\\{name}",
        f"C:\\Windows\\Fonts\\arial.ttf",
        f"C:\\Windows\\Fonts\\segoeui.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def generate_card() -> str:
    W, H = 800, 1020
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background with Rounded Corners & Subtle Border
    margin = 16
    draw.rounded_rectangle(
        [margin, margin, W - margin, H - margin],
        radius=32,
        fill=CARD_BG,
        outline=(245, 158, 11),
        width=3,
    )

    # 2. Top Banner Header (Dark Gradient with Gold Accent)
    header_h = 230
    draw.rounded_rectangle(
        [margin + 3, margin + 3, W - margin - 3, margin + header_h],
        radius=28,
        fill=(10, 16, 28),
    )
    # Gold separator line under header
    draw.line([margin + 20, margin + header_h, W - margin - 20, margin + header_h], fill=(245, 158, 11, 160), width=2)

    # Header Content
    font_title = get_font("segoeuib.ttf", 36)
    font_sub = get_font("segoeui.ttf", 22)
    font_small = get_font("segoeuib.ttf", 18)

    # Crown & Title
    draw.text((margin + 35, margin + 38), "👑 SẾP HOÀNG (CEO)", font=font_title, fill=TEXT_GOLD)
    draw.text((margin + 35, margin + 92), "🔱 BẢNG ĐIỀU HÀNH HERMES 3.0", font=font_title, fill=TEXT_WHITE)
    draw.text((margin + 35, margin + 148), "Hệ thống Trợ Lý Toàn Năng & Kỹ Sư Trưởng @ATG", font=font_sub, fill=TEXT_MUTED)

    # Online Badge on top right
    badge_x = W - margin - 190
    badge_y = margin + 38
    draw.rounded_rectangle([badge_x, badge_y, badge_x + 155, badge_y + 40], radius=20, fill=(6, 78, 59), outline=(52, 211, 153), width=2)
    draw.ellipse([badge_x + 18, badge_y + 14, badge_x + 30, badge_y + 26], fill=GREEN_DOT)
    draw.text((badge_x + 40, badge_y + 8), "ONLINE 24/24", font=font_small, fill=(167, 243, 208))

    # 3. Four Interactive Action Rows (Like the screenshot)
    rows_data = [
        {
            "num": "1",
            "icon_bg": (37, 99, 235), # Blue
            "icon_text": "📋",
            "title": "BẢNG CÔNG VIỆC & TIẾN ĐỘ",
            "desc": "Quản lý việc cần làm, nhiệm vụ đang xử lý & đã xong",
            "tag": "GÕ 1",
        },
        {
            "num": "2",
            "icon_bg": (147, 51, 234), # Purple
            "icon_text": "🎬",
            "title": "KHO MEDIA ĐỒ HỌA & VIDEO AI",
            "desc": "Xem trước video TVC và ảnh nghệ thuật render 4K",
            "tag": "GÕ 2",
        },
        {
            "num": "3",
            "icon_bg": (16, 185, 129), # Emerald
            "icon_text": "⚡",
            "title": "NHỊP TIM SEVER HERMES",
            "desc": "Giám sát thời gian thực 4 cổng dịch vụ (:3050, :8770, :8999)",
            "tag": "GÕ 3",
        },
        {
            "num": "4",
            "icon_bg": (217, 119, 6), # Amber
            "icon_text": "🛠️",
            "title": "CHỈ THỊ KỸ SƯ TRƯỞNG @ATG",
            "desc": "Đọc mã nguồn, sửa bug & bảo trì hệ thống trực tiếp",
            "tag": "GÕ 4",
        },
    ]

    row_start_y = margin + header_h + 25
    row_height = 140
    row_gap = 18

    font_row_title = get_font("segoeuib.ttf", 26)
    font_row_desc = get_font("segoeui.ttf", 20)
    font_tag = get_font("segoeuib.ttf", 19)

    for i, r in enumerate(rows_data):
        curr_y = row_start_y + i * (row_height + row_gap)
        
        # Row card background with rounded borders
        draw.rounded_rectangle(
            [margin + 25, curr_y, W - margin - 25, curr_y + row_height],
            radius=20,
            fill=ROW_BG,
            outline=ROW_BORDER,
            width=2,
        )

        # Left Icon Box
        icon_x = margin + 45
        icon_y = curr_y + 25
        icon_w = 90
        icon_h = 90
        draw.rounded_rectangle(
            [icon_x, icon_y, icon_x + icon_w, icon_y + icon_h],
            radius=18,
            fill=r["icon_bg"],
        )
        # Icon Text or Emoji in Center
        draw.text((icon_x + 22, icon_y + 16), r["icon_text"], font=get_font("segoeui.ttf", 40), fill=TEXT_WHITE)

        # Title & Description
        text_x = icon_x + icon_w + 22
        draw.text((text_x, curr_y + 30), r["title"], font=font_row_title, fill=TEXT_WHITE)
        draw.text((text_x, curr_y + 78), r["desc"], font=font_row_desc, fill=TEXT_MUTED)

        # Right Tag Button (e.g. GÕ 1, GÕ 2)
        tag_w = 95
        tag_h = 44
        tag_x = W - margin - 45 - tag_w
        tag_y = curr_y + (row_height - tag_h) // 2
        draw.rounded_rectangle(
            [tag_x, tag_y, tag_x + tag_w, tag_y + tag_h],
            radius=12,
            fill=(30, 41, 59),
            outline=TEXT_GOLD,
            width=2,
        )
        draw.text((tag_x + 18, tag_y + 8), r["tag"], font=font_tag, fill=TEXT_GOLD)

    # 4. Footer Guide Text
    font_footer = get_font("segoeuib.ttf", 20)
    footer_text = "👉 CHẠM CÁC LỆNH BÊN DƯỚI ĐỂ ĐIỀU KHIỂN TỨC THÌ"
    draw.text((margin + 130, H - margin - 45), footer_text, font=font_footer, fill=(245, 158, 11))

    # Save to disk
    img.save(str(CARD_PATH), format="PNG", quality=95)
    return str(CARD_PATH)

if __name__ == "__main__":
    p = generate_card()
    print(f"✅ Generated Card at: {p}")
