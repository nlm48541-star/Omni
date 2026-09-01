# -*- coding: utf-8 -*-
import os
import re
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
    path = find_font_file(["Shokuntola UNICODE", "Shokuntola", "shokuntola", "FN Shorif Opekkha"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_table_font(size):
    path = find_font_file(["kalpurush", "Kalpurush"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_cta_font(size):
    path = find_font_file(["AkhandBengali-Extrabold", "Akhand", "akhand"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_dates_font(size):
    path = find_font_file(["Li Ador Noirrit Bold", "Li Ador Noirrit", "LiAdorNoirrit"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

# 🌟 ইংরেজি শব্দের জন্য বোল্ড ইংরেজি ফন্ট লোডার
def get_english_bold_font(font_size):
    eng_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    ]
    for p in eng_paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, font_size)
            except Exception: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception: return ImageFont.load_default()

# 🌟 বাক্যকে বাংলা ও ইংরেজি অংশে ভাগ করার ইঞ্জিন
def split_text_by_script(text):
    tokens = re.split(r'([A-Za-z0-9\+\:\-\.\_\@\/\#\&\(\)\s]+)', str(text))
    segments = []
    for t in tokens:
        if not t: continue
        is_eng = bool(re.match(r'^[A-Za-z0-9\+\:\-\.\_\@\/\#\&\(\)\s]+$', t)) and any(c.isalnum() for c in t)
        segments.append((t, is_eng))
    return segments

def measure_mixed_text(draw, text, bn_font, font_size):
    eng_font = get_english_bold_font(font_size)
    segments = split_text_by_script(text)
    total_w, max_h = 0, 0
    for seg, is_eng in segments:
        f = eng_font if is_eng else bn_font
        try:
            bbox = f.getbbox(seg)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            w = len(seg) * int(font_size * 0.6)
            h = font_size
        total_w += w
        if h > max_h: max_h = h
    return total_w, max_h

# 🌟 বাংলা ও ইংরেজি মিশ্রিত বাক্য নিখুঁতভাবে ড্র করার ফাংশন
def draw_mixed_text(draw, x, y, text, bn_font, font_size, fill_color, anchor="lm"):
    eng_font = get_english_bold_font(font_size)
    segments = split_text_by_script(text)
    total_w, max_h = measure_mixed_text(draw, text, bn_font, font_size)
    
    if anchor in ["mm", "center"]:
        cur_x = x - (total_w // 2)
        cur_y = y
        f_anchor = "lm"
    elif anchor in ["rm", "right"]:
        cur_x = x - total_w
        cur_y = y
        f_anchor = "lm"
    elif anchor == "la":
        cur_x = x
        cur_y = y
        f_anchor = "la"
    else: # "lm"
        cur_x = x
        cur_y = y
        f_anchor = "lm"

    for seg, is_eng in segments:
        f = eng_font if is_eng else bn_font
        try:
            bbox = f.getbbox(seg)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(seg) * int(font_size * 0.6)
            
        draw.text((cur_x, cur_y), seg, font=f, fill=fill_color, anchor=f_anchor)
        cur_x += w

def wrap_mixed_text(draw, text, bn_font, font_size, max_width):
    if not text: return []
    words = str(text).split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        width, _ = measure_mixed_text(draw, test, bn_font, font_size)
        if width <= max_width: cur.append(w)
        else:
            if cur: lines.append(' '.join(cur))
            cur = [w]
    if cur: lines.append(' '.join(cur))
    return lines

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

    bg = Image.new("RGBA", (target_w, target_h), (245, 247, 250, 255))
    return bg

def render_circular_slide(job_data, bg_img, slide_idx=1, total_slides=1):
    W, H = 1080, 1920
    slide = bg_img.copy().convert("RGBA")
    
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # মূল ফ্রস্টেড কার্ড
    card_x1, card_y1 = 40, 45
    card_x2, card_y2 = W - 40, H - 45
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=32, fill=(255, 255, 255, 235), outline=(203, 213, 225, 240), width=2)

    org_name = job_data.get("org_name", "সরকারি নিয়োগ বিজ্ঞপ্তি")
    headline = job_data.get("headline", "নিয়োগ বিজ্ঞপ্তি")
    total_vacancies = job_data.get("total_vacancies", "বিজ্ঞপ্তি দেখুন")
    posts = job_data.get("posts", [])
    start_date = job_data.get("start_date", "চলমান")
    start_time = job_data.get("start_time", "সকাল ১০:০০")
    end_date = job_data.get("end_date", "শীঘ্রই শেষ হবে")
    end_time = job_data.get("end_time", "বিকাল ৫:০০")
    cta_text = job_data.get("cta_text", "WhatsApp: +8801540503092")

    # ১. হেডার সেকশন: প্রতিষ্ঠানের নাম বড় ও স্পষ্ট
    header_box = [60, 65, W - 60, 270]
    draw.rounded_rectangle(header_box, radius=24, fill=(240, 253, 250, 240), outline=(20, 184, 166, 140), width=2)

    # টপ হেডলাইন ব্যাজ
    draw.rounded_rectangle([W//2 - 130, 80, W//2 + 130, 125], radius=12, fill=(15, 118, 110, 255))
    draw_mixed_text(draw, W//2, 102, headline, get_header_font(28), 28, "#FFFFFF", anchor="mm")

    # প্রতিষ্ঠানের নাম (বড় সাইজে ও বাংলা-ইংরেজি মিক্সড সাপোর্টসহ)
    org_font_size = 44
    org_font = get_header_font(org_font_size)
    org_lines = wrap_mixed_text(draw, org_name, org_font, org_font_size, max_width=W - 160)
    start_oy = 150 if len(org_lines) == 1 else 138
    for line in org_lines[:2]:
        draw_mixed_text(draw, W//2, start_oy, line, org_font, org_font_size, "#0F172A", anchor="mm")
        start_oy += 52

    # ২. মোট শূন্য পদ কার্ড
    summary_y1, summary_y2 = 285, 375
    draw.rounded_rectangle([60, summary_y1, W - 60, summary_y2], radius=18, fill=(241, 245, 249, 240), outline=(226, 232, 240, 255), width=2)
    draw_mixed_text(draw, 95, summary_y1 + 45, "মোট শূন্য পদ", get_table_font(36), 36, "#334155", anchor="lm")
    draw_mixed_text(draw, W - 95, summary_y1 + 45, str(total_vacancies), get_table_font(48), 48, "#047857", anchor="rm")

    # ৩. পদের তালিকা সেকশন (সম্পূর্ণ কার্ড জুড়ে বড় ও স্পষ্ট অক্ষরে বিন্যস্ত)
    list_top = 395
    list_bottom = 1530
    available_h = list_bottom - list_top
    
    num_posts = max(1, len(posts))
    row_h = available_h // min(num_posts, 8)
    row_h = min(150, max(100, row_h))

    p_name_fs = 34
    p_grade_fs = 26
    badge_fs = 30

    p_name_font = get_table_font(p_name_fs)
    p_grade_font = get_table_font(p_grade_fs)
    badge_font = get_table_font(badge_fs)

    cur_y = list_top
    for idx, p in enumerate(posts):
        if cur_y + row_h > list_bottom + 10: break
        
        p_name = p.get("post_name", "")
        p_grade = p.get("grade", "")
        p_vac = str(p.get("vacancy", "১"))

        card_bg = (248, 250, 252, 220) if idx % 2 == 0 else (255, 255, 255, 200)
        draw.rounded_rectangle([60, cur_y, W - 60, cur_y + row_h - 12], radius=16, fill=card_bg, outline=(226, 232, 240, 180), width=1)

        # পদের নাম ও গ্রেড
        draw_mixed_text(draw, 85, cur_y + (row_h // 2) - 18, p_name, p_name_font, p_name_fs, "#0F172A", anchor="lm")
        if p_grade:
            draw_mixed_text(draw, 85, cur_y + (row_h // 2) + 20, p_grade, p_grade_font, p_grade_fs, "#64748B", anchor="lm")

        # পদ সংখ্যার ব্যাজ
        badge_cx = W - 115
        badge_cy = cur_y + (row_h // 2) - 6
        draw.rounded_rectangle([badge_cx - 28, badge_cy - 24, badge_cx + 28, badge_cy + 24], radius=16, fill=(15, 23, 42, 240), outline=(51, 65, 85, 120), width=1)
        draw_mixed_text(draw, badge_cx, badge_cy, p_vac, badge_font, badge_fs, "#FFFFFF", anchor="mm")

        cur_y += row_h

    # ৪. আবেদনের সময়সীমা কার্ড
    dates_top = 1550
    dates_bottom = 1705
    card_w = (W - 120 - 20) // 2

    # শুরু কার্ড
    left_x1 = 60
    left_x2 = left_x1 + card_w
    draw.rounded_rectangle([left_x1, dates_top, left_x2, dates_bottom], radius=20, fill=(220, 252, 231, 240), outline=(34, 197, 94, 200), width=2)
    draw_mixed_text(draw, left_x1 + 25, dates_top + 32, "আবেদন শুরু:", get_dates_font(26), 26, "#15803D", anchor="la")
    draw_mixed_text(draw, left_x1 + 25, dates_top + 74, str(start_date), get_dates_font(36), 36, "#064E3B", anchor="la")
    draw_mixed_text(draw, left_x1 + 25, dates_top + 118, str(start_time), get_dates_font(24), 24, "#166534", anchor="la")

    # শেষ কার্ড
    right_x1 = left_x2 + 20
    right_x2 = W - 60
    draw.rounded_rectangle([right_x1, dates_top, right_x2, dates_bottom], radius=20, fill=(254, 226, 226, 240), outline=(239, 68, 68, 200), width=2)
    draw_mixed_text(draw, right_x1 + 25, dates_top + 32, "আবেদনের শেষ তারিখ:", get_dates_font(26), 26, "#B91C1C", anchor="la")
    draw_mixed_text(draw, right_x1 + 25, dates_top + 74, str(end_date), get_dates_font(36), 36, "#991B1B", anchor="la")
    draw_mixed_text(draw, right_x1 + 25, dates_top + 118, str(end_time), get_dates_font(24), 24, "#7F1D1D", anchor="la")

    # ৫. হোয়াটসঅ্যাপ যোগাযোগ সেকশন (বাংলা ও ইংরেজি মিশ্রিত নিখুঁত টেক্সট)
    cta_top = 1725
    cta_bottom = 1845
    draw.rounded_rectangle([60, cta_top, W - 60, cta_bottom], radius=22, fill=(22, 163, 74, 255), outline=(21, 128, 61, 255), width=2)
    
    draw_mixed_text(draw, W//2, cta_top + 36, "ঘরে বসে অনলাইনে আবেদন সম্পন্ন করতে যোগাযোগ করুন", get_cta_font(28), 28, "#F0FDF4", anchor="mm")
    draw_mixed_text(draw, W//2, cta_top + 84, f"WhatsApp: 01540503092", get_cta_font(38), 38, "#FFFFFF", anchor="mm")

    if total_slides > 1:
        draw_mixed_text(draw, W - 75, H - 25, f"পৃষ্ঠা {slide_idx}/{total_slides}", get_table_font(20), 20, "#64748B", anchor="rm")

    combined = Image.alpha_composite(slide, overlay)
    return combined.convert("RGB")

def prepare_tiktok_slides(job_data, output_prefix="slide"):
    posts = job_data.get("posts", [])
    bg_img = get_random_background()
    out_paths = []
    
    if len(posts) > 8:
        d1 = dict(job_data); d1["posts"] = posts[:8]
        d2 = dict(job_data); d2["posts"] = posts[8:16]
        
        s1 = render_circular_slide(d1, bg_img, slide_idx=1, total_slides=2)
        p1 = f"{output_prefix}_1.jpg"
        s1.save(p1, "JPEG", quality=95)
        out_paths.append(p1)
        
        s2 = render_circular_slide(d2, bg_img, slide_idx=2, total_slides=2)
        p2 = f"{output_prefix}_2.jpg"
        s2.save(p2, "JPEG", quality=95)
        out_paths.append(p2)
    else:
        s = render_circular_slide(job_data, bg_img, slide_idx=1, total_slides=1)
        p = f"{output_prefix}_1.jpg"
        s.save(p, "JPEG", quality=95)
        out_paths.append(p)
        
    return out_paths
