# -*- coding: utf-8 -*-
import os
import re
import random
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
BACKGROUNDS_DIR = "Backgrounds"

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
            if clean_hint in fname:
                return fpath
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
    elif anchor == "la":
        cur_x = x
        cur_y = y
        f_anchor = "la"
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

def get_blank_template(target_w=1080, target_h=1920):
    possible_names = ["Template.png", "template.png", "Template.jpg", "template.jpg", "input_file_0.png", "blank.png"]
    search_dirs = [BACKGROUNDS_DIR, ".", "Backgrounds"]
    for d in search_dirs:
        for name in possible_names:
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    img = Image.open(p).convert("RGBA")
                    return img.resize((target_w, target_h), Image.LANCZOS)
                except Exception: pass

    if os.path.exists(BACKGROUNDS_DIR):
        for f in os.listdir(BACKGROUNDS_DIR):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    img = Image.open(os.path.join(BACKGROUNDS_DIR, f)).convert("RGBA")
                    return img.resize((target_w, target_h), Image.LANCZOS)
                except Exception: pass

    return Image.new("RGBA", (target_w, target_h), (255, 255, 255, 255))

def render_template_slide(job_data, template_img, slide_posts):
    W, H = 1080, 1920
    slide = template_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(slide)

    org_name = clean_org_name(job_data.get("org_name", "নিয়োগ বিজ্ঞপ্তি"))
    start_date = job_data.get("start_date", "চলমান")
    end_date = job_data.get("end_date", "শীঘ্রই শেষ হবে")

    # 🌟 ১. প্রতিষ্ঠানের নাম (১ লাইন হলে বড় ৬৮ পিক্সেল, ২ লাইন হলে ৪৮ পিক্সেল)
    test_fs = 68
    test_font = get_header_font(test_fs)
    test_lines = wrap_mixed_text(draw, org_name, test_font, test_fs, max_width=920)

    if len(test_lines) == 1:
        draw_mixed_text(draw, W // 2, 310, test_lines[0], test_font, test_fs, "#047857", anchor="mm")
    else:
        org_fs = 48
        org_font = get_header_font(org_fs)
        org_lines = wrap_mixed_text(draw, org_name, org_font, org_fs, max_width=920)
        oy = 285
        for ol in org_lines[:2]:
            draw_mixed_text(draw, W // 2, oy, ol, org_font, org_fs, "#047857", anchor="mm")
            oy += 56

    # 🌟 ২. আবেদন শুরু ও আবেদন শেষ তারিখ (সঠিক পজিশন ও ডিপ কালো #000000)
    dates_font = get_dates_font(38)
    draw_mixed_text(draw, 305, 685, str(start_date), dates_font, 38, "#000000", anchor="mm")
    draw_mixed_text(draw, 765, 685, str(end_date), dates_font, 38, "#000000", anchor="mm")

    # 🌟 ৩. আটটি ঘরের টেবিল (ডিপ কালো #000000 ও বড় সাইজে)
    p_name_fs = 36
    p_vac_fs = 42
    p_qual_fs = 32

    p_name_font = get_table_font(p_name_fs)
    p_vac_font = get_table_font(p_vac_fs)
    p_qual_font = get_table_font(p_qual_fs)

    row_starts_y = [880 + i * 98 for i in range(8)]
    row_height = 98

    for i in range(8):
        if i < len(slide_posts):
            p = slide_posts[i]
            p_name = p.get("post_name", "")
            p_vac = str(p.get("vacancy", "০১"))
            p_qual = p.get("qualification", "")

            # একক সংখ্যার আগে শূন্য যোগ (০১, ০২)
            if len(p_vac) == 1 and p_vac in "১২৩৪৫৬৭৮৯123456789":
                bn_map = {"1":"০১","2":"০২","3":"০৩","4":"০৪","5":"০৫","6":"০৬","7":"০৭","8":"০৮","9":"০৯",
                          "১":"০১","২":"০২","৩":"০৩","৪":"০৪","৫":"০৫","৬":"০৬","৭":"০৭","৮":"০৮","৯":"০৯"}
                p_vac = bn_map.get(p_vac, p_vac)

            cy = row_starts_y[i] + (row_height // 2)

            # কলাম ১: পদের নাম (Left X = 110, ডিপ কালো #000000)
            name_lines = wrap_mixed_text(draw, p_name, p_name_font, p_name_fs, max_width=400)
            if len(name_lines) == 1:
                draw_mixed_text(draw, 110, cy, name_lines[0], p_name_font, p_name_fs, "#000000", anchor="lm")
            else:
                ny = cy - 20
                for nl in name_lines[:2]:
                    draw_mixed_text(draw, 110, ny, nl, p_name_font, p_name_fs - 4, "#000000", anchor="lm")
                    ny += 38

            # কলাম ২: পদ সংখ্যা (Center X = 590, ডিপ কালো #000000)
            draw_mixed_text(draw, 590, cy, p_vac, p_vac_font, p_vac_fs, "#000000", anchor="mm")

            # কলাম ৩: শিক্ষাগত যোগ্যতা (Center X = 825, ডিপ কালো #000000)
            qual_lines = wrap_mixed_text(draw, p_qual, p_qual_font, p_qual_fs, max_width=300)
            if len(qual_lines) == 1:
                draw_mixed_text(draw, 825, cy, qual_lines[0], p_qual_font, p_qual_fs, "#000000", anchor="mm")
            else:
                qy = cy - 18
                for ql in qual_lines[:2]:
                    draw_mixed_text(draw, 825, qy, ql, p_qual_font, p_qual_fs - 4, "#000000", anchor="mm")
                    qy += 36

    return slide.convert("RGB")

def prepare_tiktok_slides(job_data, output_prefix="slide"):
    posts = job_data.get("posts", [])
    template_img = get_blank_template()
    out_paths = []

    if len(posts) > 8:
        for idx, chunk_start in enumerate(range(0, len(posts), 8), start=1):
            chunk = posts[chunk_start : chunk_start + 8]
            s = render_template_slide(job_data, template_img, chunk)
            p = f"{output_prefix}_{idx}.jpg"
            s.save(p, "JPEG", quality=95)
            out_paths.append(p)
    else:
        s = render_template_slide(job_data, template_img, posts)
        p = f"{output_prefix}_1.jpg"
        s.save(p, "JPEG", quality=95)
        out_paths.append(p)

    return out_paths
