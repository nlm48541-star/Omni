# -*- coding: utf-8 -*-
import os
import re
import math
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"

def find_logo_file():
    """রিপোজিটরি থেকে Logo.png ফাইল খুঁজে বের করে"""
    for p in ["Logo.png", "logo.png", "LOGO.PNG", "Photos/Logo.png", "Photos/logo.png"]:
        if os.path.exists(p): return p
    return None

def find_font_file(font_hints, fallback_name="kalpurush.ttf"):
    if isinstance(font_hints, str): font_hints = [font_hints]
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
            if clean_hint in fname: return fpath
    return all_fonts[0] if all_fonts else fallback_name

def get_header_font(size):
    path = find_font_file(["Shokuntola UNICODE", "Shokuntola", "shokuntola", "kalpurush"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_table_font(size):
    path = find_font_file(["kalpurush", "Kalpurush"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_dates_font(size):
    path = find_font_file(["Li Ador Noirrit Bold", "Li Ador Noirrit", "kalpurush"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_cta_font(size):
    path = find_font_file(["AkhandBengali-Extrabold", "Akhand", "akhand", "kalpurush"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_english_bold_font(font_size):
    eng_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for p in eng_paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, font_size)
            except Exception: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception: return ImageFont.load_default()

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
    else:
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

def clean_org_name(org_name):
    if not org_name: return "নিয়োগ বিজ্ঞপ্তি"
    clean = re.sub(r'[\r\n\t]+', ' ', str(org_name)).strip()
    clean = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Job\s*Circular.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'সার্কুলার.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'202[0-9]|২০২[০-৯]', '', clean).strip(" -|,")
    return clean if len(clean) > 2 else org_name

# 🌟 মোশন গ্রাফিক্স ইজিং ফাংশন
def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)

def ease_out_back(t, s=1.4):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * math.pow(t - 1.0, 3) + s * math.pow(t - 1.0, 2)

def get_progress(frame_num, start_f, end_f):
    if frame_num < start_f: return 0.0
    if frame_num >= end_f: return 1.0
    return (frame_num - start_f) / float(end_f - start_f)

# 🌟 মোশন গ্রাফিক্স অ্যানিমেশন ফ্রেম জেনারেটর
def render_motion_graphic_frame(job_data, slide_posts, frame_idx=60, total_anim_frames=60):
    W, H = 1080, 1920
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ১. মূল ফ্রস্টেড কার্ড অ্যানিমেশন (Fade-in)
    card_prog = ease_out_cubic(get_progress(frame_idx, 0, 12))
    card_alpha = int(246 * card_prog)
    if card_alpha > 0:
        draw.rounded_rectangle([45, 55, W - 45, H - 55], radius=32, fill=(255, 255, 255, card_alpha), outline=(203, 213, 225, card_alpha), width=2)

    # ২. লোগো অ্যানিমেশন (Logo.png পপ-ইন স্কেল)
    logo_prog = ease_out_back(get_progress(frame_idx, 2, 16))
    if logo_prog > 0:
        logo_file = find_logo_file()
        if logo_file:
            try:
                raw_logo = Image.open(logo_file).convert("RGBA")
                target_dim = int(120 * logo_prog)
                if target_dim > 10:
                    scaled_logo = raw_logo.resize((target_dim, target_dim), Image.LANCZOS)
                    lx = (W - target_dim) // 2
                    ly = 130 - (target_dim // 2)
                    overlay.paste(scaled_logo, (lx, ly), scaled_logo)
            except Exception: pass
        else:
            rad = int(55 * logo_prog)
            if rad > 5:
                draw.ellipse([W//2 - rad, 130 - rad, W//2 + rad, 130 + rad], fill=(22, 101, 52, int(255 * logo_prog)))

    # ৩. প্রতিষ্ঠানের নাম অ্যানিমেশন (Slide down & Fade)
    org_prog = ease_out_cubic(get_progress(frame_idx, 6, 20))
    if org_prog > 0:
        org_name = clean_org_name(job_data.get("org_name", "নিয়োগ বিজ্ঞপ্তি"))
        test_font = get_header_font(68)
        test_lines = wrap_mixed_text(draw, org_name, test_font, 68, max_width=920)
        y_offset = int((1.0 - org_prog) * -25)

        if len(test_lines) == 1:
            draw_mixed_text(draw, W // 2, 260 + y_offset, test_lines[0], test_font, 68, "#047857", anchor="mm")
        else:
            org_fs = 48
            org_font = get_header_font(org_fs)
            org_lines = wrap_mixed_text(draw, org_name, org_font, org_fs, max_width=920)
            oy = 235 + y_offset
            for ol in org_lines[:2]:
                draw_mixed_text(draw, W // 2, oy, ol, org_font, org_fs, "#047857", anchor="mm")
                oy += 56

    # ৪. "নিয়োগ বিজ্ঞপ্তি" ব্যানার (Zoom/Pop with bounce)
    banner_prog = ease_out_back(get_progress(frame_idx, 10, 24))
    if banner_prog > 0:
        bw = int(390 * banner_prog)
        bh = int(65 * banner_prog)
        if bw > 20 and bh > 10:
            draw.rounded_rectangle([W//2 - bw, 395 - bh, W//2 + bw, 395 + bh], radius=28, fill=(15, 46, 90, 255), outline=(30, 58, 138, 255), width=2)
            if banner_prog >= 0.8:
                draw_mixed_text(draw, W // 2, 395, "নিয়োগ বিজ্ঞপ্তি", get_header_font(72), 72, "#FFFFFF", anchor="mm")

    # ৫. ক্যালেন্ডার বক্স অ্যানিমেশন (বাম ও ডান থেকে স্লাইড)
    cal_prog = ease_out_cubic(get_progress(frame_idx, 16, 28))
    if cal_prog > 0:
        c_top, c_bot = 490, 640
        box_w = (W - 170 - 25) // 2
        slide_offset = int((1.0 - cal_prog) * 60)

        # আবেদন শুরু (বাম বক্স)
        b1_x1 = 85 - slide_offset
        b1_x2 = b1_x1 + box_w
        draw.rounded_rectangle([b1_x1, c_top, b1_x2, c_bot], radius=20, fill=(255, 255, 255, 255), outline=(37, 99, 235, 180), width=2)
        draw.rounded_rectangle([b1_x1 + 105, c_top + 16, b1_x2 - 35, c_top + 56], radius=12, fill=(22, 101, 52, 255))
        draw_mixed_text(draw, (b1_x1 + 105 + b1_x2 - 35) // 2, c_top + 36, "আবেদন শুরু", get_dates_font(24), 24, "#FFFFFF", anchor="mm")
        draw_mixed_text(draw, (b1_x1 + b1_x2) // 2 + 20, c_top + 100, str(job_data.get("start_date", "চলমান")), get_dates_font(38), 38, "#000000", anchor="mm")

        # আবেদন শেষ (ডান বক্স)
        b2_x1 = b1_x2 + 25 + slide_offset
        b2_x2 = W - 85 + slide_offset
        draw.rounded_rectangle([b2_x1, c_top, b2_x2, c_bot], radius=20, fill=(255, 255, 255, 255), outline=(37, 99, 235, 180), width=2)
        draw.rounded_rectangle([b2_x1 + 105, c_top + 16, b2_x2 - 35, c_top + 56], radius=12, fill=(30, 64, 175, 255))
        draw_mixed_text(draw, (b2_x1 + 105 + b2_x2 - 35) // 2, c_top + 36, "আবেদন শেষ", get_dates_font(24), 24, "#FFFFFF", anchor="mm")
        draw_mixed_text(draw, (b2_x1 + b2_x2) // 2 + 20, c_top + 100, str(job_data.get("end_date", "শীঘ্রই শেষ হবে")), get_dates_font(38), 38, "#000000", anchor="mm")

    # ৬. "পদসমূহ" লাল রিবন (Expand)
    rib_prog = ease_out_back(get_progress(frame_idx, 22, 34))
    if rib_prog > 0:
        rw = int(270 * rib_prog)
        if rw > 20:
            draw.rounded_rectangle([W//2 - rw, 675, W//2 + rw, 755], radius=18, fill=(185, 28, 28, 255))
            if rib_prog >= 0.7:
                draw_mixed_text(draw, W // 2, 715, "পদসমূহ", get_header_font(38), 38, "#FFFFFF", anchor="mm")

    # ৭. টেবিল কার্ড ও গ্রিড লাইন
    table_prog = ease_out_cubic(get_progress(frame_idx, 24, 36))
    table_top, table_bottom = 755, 1540
    row_h = (table_bottom - table_top) / 8.0

    if table_prog > 0:
        t_alpha = int(248 * table_prog)
        draw.rounded_rectangle([85, table_top, W - 85, table_bottom], radius=18, fill=(248, 245, 240, t_alpha), outline=(203, 213, 225, t_alpha), width=1)
        draw.line([(520, table_top), (520, table_bottom)], fill=(203, 213, 225, t_alpha), width=1)
        draw.line([(660, table_top), (660, table_bottom)], fill=(203, 213, 225, t_alpha), width=1)
        for r in range(1, 8):
            ry = int(table_top + r * row_h)
            draw.line([(85, ry), (W - 85, ry)], fill=(226, 232, 240, t_alpha), width=1)

    # 🌟 ৮. পদের সারিগুলোর ক্যাসকেড অ্যানিমেশন (Staggered Row-by-Row Entry)
    p_name_font = get_table_font(34)
    p_vac_font = get_table_font(40)
    p_qual_font = get_table_font(30)

    for i in range(8):
        # প্রতিটি সারি ৩ ফ্রেম পর পর স্লাইড করে ঢুকবে
        row_start_f = 26 + i * 3
        row_end_f = row_start_f + 8
        r_prog = ease_out_cubic(get_progress(frame_idx, row_start_f, row_end_f))

        if r_prog > 0 and i < len(slide_posts):
            p = slide_posts[i]
            p_name = p.get("post_name", "")
            p_vac = str(p.get("vacancy", "০১"))
            p_qual = p.get("qualification", "")

            if len(p_vac) == 1 and p_vac in "১২৩৪৫৬৭৮৯123456789":
                bn_map = {"1":"০১","2":"০২","3":"০৩","4":"০৪","5":"০৫","6":"০৬","7":"০৭","8":"০৮","9":"০৯",
                          "১":"০১","২":"০২","৩":"০৩","৪":"০৪","৫":"০৫","৬":"০৬","৭":"০৭","৮":"০৮","৯":"০৯"}
                p_vac = bn_map.get(p_vac, p_vac)

            cy = int(table_top + i * row_h + (row_h / 2))
            rx_offset = int((1.0 - r_prog) * -40)

            # কলাম ১: পদের নাম
            name_lines = wrap_mixed_text(draw, p_name, p_name_font, 34, max_width=390)
            if len(name_lines) == 1:
                draw_mixed_text(draw, 110 + rx_offset, cy, name_lines[0], p_name_font, 34, "#000000", anchor="lm")
            else:
                ny = cy - 18
                for nl in name_lines[:2]:
                    draw_mixed_text(draw, 110 + rx_offset, ny, nl, p_name_font, 30, "#000000", anchor="lm")
                    ny += 36

            # কলাম ২: পদ সংখ্যা
            draw_mixed_text(draw, 590, cy, p_vac, p_vac_font, 40, "#000000", anchor="mm")

            # কলাম ৩: শিক্ষাগত যোগ্যতা
            qual_lines = wrap_mixed_text(draw, p_qual, p_qual_font, 30, max_width=300)
            if len(qual_lines) == 1:
                draw_mixed_text(draw, 825, cy, qual_lines[0], p_qual_font, 30, "#000000", anchor="mm")
            else:
                qy = cy - 18
                for ql in qual_lines[:2]:
                    draw_mixed_text(draw, 825, qy, ql, p_qual_font, 26, "#000000", anchor="mm")
                    qy += 34

    # ৯. নিচে সবুজ WhatsApp কন্টাক্ট বার (Slide Up from Bottom with Spring Bounce)
    wa_prog = ease_out_back(get_progress(frame_idx, 44, 58))
    if wa_prog > 0:
        wa_y_offset = int((1.0 - wa_prog) * 60)
        cta_y1 = 1595 + wa_y_offset
        cta_y2 = 1735 + wa_y_offset
        draw.rounded_rectangle([85, cta_y1, W - 85, cta_y2], radius=24, fill=(0, 92, 41, 255), outline=(22, 163, 74, 255), width=2)
        draw_mixed_text(draw, W // 2 + 40, cta_y1 + 42, "আবেদন করতে যোগাযোগ করুন", get_cta_font(32), 32, "#FFEB3B", anchor="mm")
        draw_mixed_text(draw, W // 2 + 40, cta_y1 + 92, "WhatsApp: 01540503092", get_cta_font(42), 42, "#FFFFFF", anchor="mm")

    return overlay

# 🌟 সম্পূর্ণ অ্যানিমেশন ফ্রেম প্যাক তৈরি করে রিটার্ন করে
def generate_tiktok_animated_overlay_frames(job_data, temp_frames_dir, num_frames=60, fps=24):
    os.makedirs(temp_frames_dir, exist_ok=True)
    posts = job_data.get("posts", [])
    slide_posts = posts[:8]

    # ৬০টি মোশন ফ্রেম রেন্ডার করা (২.৫ সেকেন্ডের ইন্ট্রো মোশন)
    for f in range(num_frames):
        img_frame = render_motion_graphic_frame(job_data, slide_posts, frame_idx=f, total_anim_frames=num_frames)
        img_frame.save(os.path.join(temp_frames_dir, f"overlay_{f:04d}.png"), "PNG")

    # বাকি সময়ের জন্য স্থির ফাইনাল ফ্রেম
    final_frame = render_motion_graphic_frame(job_data, slide_posts, frame_idx=num_frames, total_anim_frames=num_frames)
    final_path = os.path.join(temp_frames_dir, "hold_frame.png")
    final_frame.save(final_path, "PNG")

    return final_path
