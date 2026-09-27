# -*- coding: utf-8 -*-
import os
import re
import math
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"

def find_logo_file():
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

# ইজিং ফাংশন
def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)

def ease_in_cubic(t):
    t = max(0.0, min(1.0, t))
    return math.pow(t, 3)

def ease_out_back(t, s=1.4):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * math.pow(t - 1.0, 3) + s * math.pow(t - 1.0, 2)

def get_progress(frame_num, start_f, end_f):
    if frame_num < start_f: return 0.0
    if frame_num >= end_f: return 1.0
    return (frame_num - start_f) / float(end_f - start_f)

# 🌟 প্রিমিয়াম মিনিমালিস্টিক ডার্ক গ্লাস ফ্রেম রেন্ডারার (In এবং Out অ্যানিমেশনসহ)
def render_modern_minimalist_frame(job_data, slide_posts, frame_idx=60, total_frames=120, fps=24):
    W, H = 1080, 1920
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # অ্যানিমেশন পর্যায় নির্ধারণ (ইনট্রো, স্ট্যাটিক, আউটরো)
    intro_frames = int(fps * 1.8)   # প্রথম ১.৮ সেকেন্ড ইনট্রো
    outro_frames = int(fps * 1.4)   # শেষ ১.৪ সেকেন্ড আউটরো
    outro_start = max(intro_frames + 5, total_frames - outro_frames)

    is_outro = frame_idx >= outro_start
    if is_outro:
        exit_t = (frame_idx - outro_start) / float(outro_frames)
        global_alpha = int(255 * (1.0 - ease_in_cubic(exit_t)))
        exit_offset_y = int(ease_in_cubic(exit_t) * 120)
    else:
        global_alpha = 255
        exit_offset_y = 0

    if global_alpha <= 0:
        return overlay

    # ১. ভাসমান ট্রান্সলুসেন্ট ডার্ক গ্লাস কনটেইনার
    card_prog = ease_out_cubic(get_progress(frame_idx, 0, 14)) if not is_outro else (1.0 - exit_t)
    c_alpha = int(215 * card_prog * (global_alpha / 255.0))
    if c_alpha > 0:
        draw.rounded_rectangle([45, 60 - exit_offset_y, W - 45, H - 60 - exit_offset_y], radius=36, fill=(15, 23, 42, c_alpha), outline=(56, 189, 248, int(160 * card_prog)), width=2)

    # ২. লোগো অ্যানিমেশন (Logo.png পপ-ইন স্কেল)
    logo_prog = ease_out_back(get_progress(frame_idx, 2, 18)) if not is_outro else (1.0 - exit_t)
    if logo_prog > 0:
        logo_file = find_logo_file()
        if logo_file:
            try:
                raw_logo = Image.open(logo_file).convert("RGBA")
                dim = int(125 * logo_prog)
                if dim > 10:
                    scaled = raw_logo.resize((dim, dim), Image.LANCZOS)
                    lx = (W - dim) // 2
                    ly = 135 - (dim // 2) - exit_offset_y
                    overlay.paste(scaled, (lx, ly), scaled)
            except Exception: pass
        else:
            rad = int(55 * logo_prog)
            if rad > 5:
                draw.ellipse([W//2 - rad, 135 - rad - exit_offset_y, W//2 + rad, 135 + rad - exit_offset_y], fill=(16, 185, 129, int(230 * logo_prog)), outline=(52, 211, 153, 255), width=3)

    # ৩. মিনিমালিস্টিক টপ ট্যাগ পিল
    tag_prog = ease_out_cubic(get_progress(frame_idx, 6, 20)) if not is_outro else (1.0 - exit_t)
    if tag_prog > 0:
        draw.rounded_rectangle([W//2 - 210, 215 - exit_offset_y, W//2 + 210, 260 - exit_offset_y], radius=14, fill=(30, 41, 59, int(220 * tag_prog)), outline=(56, 189, 248, int(180 * tag_prog)), width=1)
        draw_mixed_text(draw, W // 2, 237 - exit_offset_y, "✦ সরকারি চাকরির নতুন নিয়োগ বিজ্ঞপ্তি ✦", get_header_font(24), 24, "#38BDF8", anchor="mm")

    # ৪. প্রতিষ্ঠানের নাম (বড় আকর্ষণীয় হেডলাইন)
    org_prog = ease_out_cubic(get_progress(frame_idx, 10, 24)) if not is_outro else (1.0 - exit_t)
    if org_prog > 0:
        org_name = clean_org_name(job_data.get("org_name", "নিয়োগ বিজ্ঞপ্তি"))
        test_font = get_header_font(64)
        test_lines = wrap_mixed_text(draw, org_name, test_font, 64, max_width=920)
        y_slide = int((1.0 - org_prog) * -30) - exit_offset_y

        if len(test_lines) == 1:
            draw_mixed_text(draw, W // 2, 310 + y_slide, test_lines[0], test_font, 64, "#FFFFFF", anchor="mm")
        else:
            org_fs = 46
            org_font = get_header_font(org_fs)
            org_lines = wrap_mixed_text(draw, org_name, org_font, org_fs, max_width=920)
            oy = 285 + y_slide
            for ol in org_lines[:2]:
                draw_mixed_text(draw, W // 2, oy, ol, org_font, org_fs, "#FFFFFF", anchor="mm")
                oy += 54

    # ৫. হাইলাইটস বার (মোট পদ ও শেষ তারিখ)
    stat_prog = ease_out_cubic(get_progress(frame_idx, 16, 28)) if not is_outro else (1.0 - exit_t)
    if stat_prog > 0:
        tot_vac = str(job_data.get("total_vacancies", "একাধিক পদ"))
        ed_date = str(job_data.get("end_date", "চলমান"))
        sy = 390 - exit_offset_y
        draw.rounded_rectangle([75, sy, W - 75, sy + 75], radius=16, fill=(30, 41, 59, int(200 * stat_prog)), outline=(71, 85, 105, int(150 * stat_prog)), width=1)
        draw_mixed_text(draw, 100, sy + 37, f"👥 মোট শূন্যপদ: {tot_vac}", get_table_font(30), 30, "#38BDF8", anchor="lm")
        draw_mixed_text(draw, W - 100, sy + 37, f"📅 শেষ তারিখ: {ed_date}", get_dates_font(30), 30, "#F87171", anchor="rm")

    # 🌟 ৬. মডুলার জব কার্ড (Modular Cards - কোনো লেখা ওভারল্যাপ হবে না!)
    card_start_y = 485 - exit_offset_y
    card_h = 245
    card_spacing = 22

    num_render_posts = min(4, len(slide_posts))
    for i in range(num_render_posts):
        p = slide_posts[i]
        p_name = p.get("post_name", "")
        p_vac = str(p.get("vacancy", "০১"))
        p_qual = p.get("qualification", "")

        # সারিগুলো ক্যাসকেড হয়ে মসৃণভাবে ইনট্রো নেবে
        row_start_f = 20 + i * 4
        row_end_f = row_start_f + 10
        r_prog = ease_out_cubic(get_progress(frame_idx, row_start_f, row_end_f)) if not is_outro else (1.0 - exit_t)

        if r_prog > 0:
            cy1 = card_start_y + i * (card_h + card_spacing)
            cy2 = cy1 + card_h
            slide_x = int((1.0 - r_prog) * -60)

            # সাব-কার্ড ব্যাকগ্রাউন্ড
            draw.rounded_rectangle([75 + slide_x, cy1, W - 75 + slide_x, cy2], radius=22, fill=(30, 41, 59, int(210 * r_prog)), outline=(56, 189, 248, int(100 * r_prog)), width=1)

            # ১) পদের নাম (বড় বোল্ড সাদা হরফে)
            draw_mixed_text(draw, 105 + slide_x, cy1 + 45, f"📌 {p_name}", get_table_font(34), 34, "#FFFFFF", anchor="lm")

            # ২) পদ সংখ্যা পিল ব্যাজ (Electric Cyan)
            draw.rounded_rectangle([105 + slide_x, cy1 + 95, 330 + slide_x, cy1 + 145], radius=12, fill=(8, 145, 178, int(220 * r_prog)))
            draw_mixed_text(draw, 217 + slide_x, cy1 + 120, f"পদ: {p_vac} জন", get_table_font(24), 24, "#FFFFFF", anchor="mm")

            # ৩) শিক্ষাগত যোগ্যতা (মিনিমালিস্টিক গোল্ডেন/সাদা লাইন)
            qual_clean = p_qual if len(p_qual) <= 45 else p_qual[:42] + "..."
            draw_mixed_text(draw, 105 + slide_x, cy1 + 190, f"🎓 যোগ্যতা: {qual_clean}", get_table_font(26), 26, "#FDE047", anchor="lm")

    # 🌟 ৭. নিচে ভাসমান WhatsApp ক্যাপসুল (Spring Bounce Animation)
    wa_prog = ease_out_back(get_progress(frame_idx, 36, 52)) if not is_outro else (1.0 - exit_t)
    if wa_prog > 0:
        wy = int((1.0 - wa_prog) * 70) - exit_offset_y
        cta_y1 = 1680 + wy
        cta_y2 = 1815 + wy
        draw.rounded_rectangle([75, cta_y1, W - 75, cta_y2], radius=26, fill=(16, 185, 129, int(245 * wa_prog)), outline=(52, 211, 153, 255), width=2)
        draw_mixed_text(draw, W // 2, cta_y1 + 42, "ঘরে বসে অনলাইনে আবেদন সম্পন্ন করতে আজই যোগাযোগ করুন", get_cta_font(28), 28, "#F0FDF4", anchor="mm")
        draw_mixed_text(draw, W // 2, cta_y1 + 90, "💬 WhatsApp: 01540503092", get_cta_font(42), 42, "#FFFFFF", anchor="mm")

    return overlay

# 🌟 মাল্টি-স্লাইড ও স্ট্যাটিক ফ্রেম প্রস্তুতকারক
def prepare_tiktok_slides(job_data, output_prefix="slide"):
    posts = job_data.get("posts", [])
    out_paths = []

    if len(posts) > 4:
        for idx, chunk_start in enumerate(range(0, len(posts), 4), start=1):
            chunk = posts[chunk_start : chunk_start + 4]
            frame = render_modern_minimalist_frame(job_data, chunk, frame_idx=60, total_frames=120)
            p = f"{output_prefix}_{idx}.png"
            frame.save(p, "PNG")
            out_paths.append(p)
    else:
        frame = render_modern_minimalist_frame(job_data, posts, frame_idx=60, total_frames=120)
        p = f"{output_prefix}_1.png"
        frame.save(p, "PNG")
        out_paths.append(p)

    return out_paths

# 🌟 সম্পূর্ণ ভিডিওর জন্য ডাইনামিক ফ্রেম অ্যানিমেশন রেন্ডারার
def generate_tiktok_animated_overlay_frames(job_data, temp_frames_dir, total_frames=120, fps=24):
    os.makedirs(temp_frames_dir, exist_ok=True)
    posts = job_data.get("posts", [])
    slide_posts = posts[:4]

    for f in range(total_frames):
        img_frame = render_modern_minimalist_frame(job_data, slide_posts, frame_idx=f, total_frames=total_frames, fps=fps)
        img_frame.save(os.path.join(temp_frames_dir, f"overlay_{f:04d}.png"), "PNG")
