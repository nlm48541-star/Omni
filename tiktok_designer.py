# -*- coding: utf-8 -*-
import os
import random
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
BACKGROUNDS_DIR = "Backgrounds"

def find_font_file(font_hints, fallback_name="kalpurush.ttf"):
    if isinstance(font_hints, str):
        font_hints = [font_hints]

    search_dirs = [FONTS_DIR, ".", "fonts"]
    all_fonts = []
    for d in search_dirs:
        if os.path.exists(d) and os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith(('.ttf', '.otf')):
                    all_fonts.append(os.path.join(d, f))

    for hint in font_hints:
        clean_hint = hint.lower().replace(" ", "").replace("-", "").replace("_", "")
        for fpath in all_fonts:
            fname = os.path.basename(fpath).lower().replace(" ", "").replace("-", "").replace("_", "")
            if clean_hint in fname:
                return fpath

    return all_fonts[0] if all_fonts else fallback_name

def get_header_font(size):
    # উপরের হেডারের জন্য Shokuntola UNICODE
    path = find_font_file(["Shokuntola UNICODE", "Shokuntola", "shokuntola", "FN Shorif Opekkha"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_table_font(size):
    # মাঝখানের তালিকা / পদ / গ্রেড / সংখ্যার জন্য kalpurush
    path = find_font_file(["kalpurush", "Kalpurush"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_cta_font(size):
    # WhatsApp কল টু অ্যাকশনের জন্য AkhandBengali-Extrabold / Akhand
    path = find_font_file(["AkhandBengali-Extrabold", "Akhand", "akhand"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_dates_font(size):
    # আবেদনের তারিখের জন্য Li Ador Noirrit Bold
    path = find_font_file(["Li Ador Noirrit Bold", "Li Ador Noirrit", "LiAdorNoirrit"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_random_background(target_w=1080, target_h=1920):
    valid_bg_files = []
    if os.path.exists(BACKGROUNDS_DIR) and os.path.isdir(BACKGROUNDS_DIR):
        for f in os.listdir(BACKGROUNDS_DIR):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                valid_bg_files.append(os.path.join(BACKGROUNDS_DIR, f))

    if valid_bg_files:
        chosen_bg = random.choice(valid_bg_files)
        try:
            img = Image.open(chosen_bg).convert("RGBA")
            iw, ih = img.size
            ratio = max(target_w / iw, target_h / ih)
            new_w, new_h = int(iw * ratio), int(ih * ratio)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            x_offset = (new_w - target_w) // 2
            y_offset = (new_h - target_h) // 2
            return resized.crop((x_offset, y_offset, x_offset + target_w, y_offset + target_h))
        except Exception: pass

    # ব্যাকগ্রাউন্ড না থাকলে স্বয়ংক্রিয় ক্লিন সফট ব্যাকগ্রাউন্ড
    bg = Image.new("RGBA", (target_w, target_h), (240, 244, 248, 255))
    return bg

def render_circular_slide(job_data, bg_img, slide_idx=1, total_slides=1):
    W, H = 1080, 1920
    slide = bg_img.copy().convert("RGBA")
    
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # মডার্ন ডার্ক ফ্রস্টেড কার্ড (#181d26)
    card_x1, card_y1 = 40, 50
    card_x2, card_y2 = W - 40, H - 50
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=32, fill=(24, 29, 38, 242), outline=(55, 65, 81, 190), width=2)

    org_name = job_data.get("org_name", "মৎস্য ও প্রাণিসম্পদ তথ্য দপ্তর")
    headline = job_data.get("headline", "নিয়োগ বিজ্ঞপ্তি")
    circular_date = job_data.get("circular_date", "২৭ জুলাই ২০২৬")
    total_vacancies = job_data.get("total_vacancies", "১৯ টি")
    posts = job_data.get("posts", [])
    start_date = job_data.get("start_date", "০৩-০৭-২০২৬")
    start_time = job_data.get("start_time", "সকাল ১০:০০")
    end_date = job_data.get("end_date", "৩০-০৮-২০২৬")
    end_time = job_data.get("end_time", "বিকাল ৫:০০")
    cta_text = job_data.get("cta_text", "Whatsapp: +8801540503092")

    # ১. হেডার সেকশন (Shokuntola UNICODE)
    draw.text((75, 90), org_name, font=get_header_font(34), fill="#94A3B8", anchor="la")
    draw.text((75, 135), headline, font=get_header_font(56), fill="#FFFFFF", anchor="la")

    # সার্কুলার ডেট পিল ব্যাজ (ডানপাশে নীল ব্যাজ)
    draw.rounded_rectangle([W - 325, 100, W - 75, 155], radius=24, fill=(30, 58, 138, 230), outline=(59, 130, 246, 150), width=1)
    draw.text((W - 200, 127), circular_date, font=get_dates_font(26), fill="#60A5FA", anchor="mm")

    # ২. মোট শূন্য পদ সামারি কার্ড
    summary_y1, summary_y2 = 215, 305
    draw.rounded_rectangle([75, summary_y1, W - 75, summary_y2], radius=18, fill=(15, 20, 28, 255), outline=(39, 47, 61, 200), width=1)
    draw.text((105, summary_y1 + 45), "মোট শূন্য পদ", font=get_table_font(36), fill="#CBD5E1", anchor="lm")
    draw.text((W - 105, summary_y1 + 45), str(total_vacancies), font=get_table_font(52), fill="#F8FAFC", anchor="rm")

    # ৩. পদের তালিকা হেডার
    draw.text((75, 335), "পদের নাম ও সংখ্যা", font=get_table_font(30), fill="#94A3B8", anchor="la")

    # ৪. পদের তালিকা (kalpurush)
    list_top = 380
    list_bottom = 1430
    available_h = list_bottom - list_top
    
    num_posts = len(posts)
    row_h = available_h // max(1, min(num_posts, 8))
    row_h = min(115, max(85, row_h))

    p_name_font = get_table_font(32)
    p_grade_font = get_table_font(24)
    badge_font = get_table_font(28)

    cur_y = list_top
    for idx, p in enumerate(posts):
        if cur_y + row_h > list_bottom: break
        p_name = p.get("post_name", "")
        p_grade = p.get("grade", "")
        p_vac = str(p.get("vacancy", "১"))

        draw.text((75, cur_y + 12), p_name, font=p_name_font, fill="#FFFFFF", anchor="la")
        if p_grade:
            draw.text((75, cur_y + 52), p_grade, font=p_grade_font, fill="#64748B", anchor="la")

        # ডানপাশের সার্কুলার পিল ব্যাজ
        badge_cx = W - 110
        badge_cy = cur_y + (row_h // 2) - 5
        draw.rounded_rectangle([badge_cx - 24, badge_cy - 22, badge_cx + 24, badge_cy + 22], radius=16, fill=(30, 41, 59, 220), outline=(71, 85, 105, 120), width=1)
        draw.text((badge_cx, badge_cy), p_vac, font=badge_font, fill="#F1F5F9", anchor="mm")

        # ডিভাইডার লাইন
        draw.line([(75, cur_y + row_h - 4), (W - 75, cur_y + row_h - 4)], fill=(39, 47, 61, 140), width=1)
        cur_y += row_h

    # ৫. আবেদনের সময়সীমা কার্ড (Li Ador Noirrit Bold)
    draw.text((75, 1450), "আবেদনের সময়সীমা", font=get_dates_font(30), fill="#94A3B8", anchor="la")

    card_h = 160
    card_w = (W - 150 - 25) // 2
    c_top = 1495
    c_bot = c_top + card_h

    # শুরু কার্ড (সবুজ)
    left_x1 = 75
    left_x2 = left_x1 + card_w
    draw.rounded_rectangle([left_x1, c_top, left_x2, c_bot], radius=20, fill=(6, 78, 59, 160), outline=(16, 185, 129, 120), width=2)
    draw.text((left_x1 + 25, c_top + 30), "▷ শুরু", font=get_dates_font(26), fill="#34D399", anchor="la")
    draw.text((left_x1 + 25, c_top + 70), str(start_date), font=get_dates_font(36), fill="#FFFFFF", anchor="la")
    draw.text((left_x1 + 25, c_top + 115), str(start_time), font=get_dates_font(24), fill="#A7F3D0", anchor="la")

    # শেষ কার্ড (লাল/মেরুন)
    right_x1 = left_x2 + 25
    right_x2 = W - 75
    draw.rounded_rectangle([right_x1, c_top, right_x2, c_bot], radius=20, fill=(127, 29, 29, 160), outline=(239, 68, 68, 120), width=2)
    draw.text((right_x1 + 25, c_top + 30), "⚑ শেষ", font=get_dates_font(26), fill="#F87171", anchor="la")
    draw.text((right_x1 + 25, c_top + 70), str(end_date), font=get_dates_font(36), fill="#FFFFFF", anchor="la")
    draw.text((right_x1 + 25, c_top + 115), str(end_time), font=get_dates_font(24), fill="#FECACA", anchor="la")

    # ৬. হোয়াটসঅ্যাপ যোগাযোগ সেকশন (AkhandBengali-Extrabold)
    cta_y1 = 1680
    cta_y2 = 1815
    draw.rounded_rectangle([75, cta_y1, W - 75, cta_y2], radius=22, fill=(22, 163, 74, 230), outline=(34, 197, 94, 255), width=2)
    draw.text((W//2, cta_y1 + 40), "ঘরে বসে অনলাইনে আবেদন সম্পন্ন করতে যোগাযোগ করুন:", font=get_cta_font(28), fill="#F0FDF4", anchor="mm")
    draw.text((W//2, cta_y1 + 88), f"💬 {cta_text}", font=get_cta_font(38), fill="#FFFFFF", anchor="mm")

    if total_slides > 1:
        draw.text((W - 90, H - 75), f"পৃষ্ঠা {slide_idx}/{total_slides}", font=get_table_font(22), fill="#64748B", anchor="rm")

    combined = Image.alpha_composite(slide, overlay)
    return combined.convert("RGB")

def prepare_tiktok_slides(job_data, output_prefix="slide"):
    posts = job_data.get("posts", [])
    bg_img = get_random_background()
    out_paths = []
    
    # ৮টির বেশি পদ থাকলে ২টি স্লাইডে ভাগ হবে
    if len(posts) > 8:
        d1 = dict(job_data); d1["posts"] = posts[:8]
        d2 = dict(job_data); d2["posts"] = posts[8:16]
        
        s1 = render_circular_slide(d1, bg_img, slide_idx=1, total_slides=2)
        p1 = f"{output_prefix}_1.jpg"
        s1.save(p1, "JPEG", quality=92)
        out_paths.append(p1)
        
        s2 = render_circular_slide(d2, bg_img, slide_idx=2, total_slides=2)
        p2 = f"{output_prefix}_2.jpg"
        s2.save(p2, "JPEG", quality=92)
        out_paths.append(p2)
    else:
        s = render_circular_slide(job_data, bg_img, slide_idx=1, total_slides=1)
        p = f"{output_prefix}_1.jpg"
        s.save(p, "JPEG", quality=92)
        out_paths.append(p)
        
    return out_paths
