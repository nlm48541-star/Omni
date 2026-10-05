# -*- coding: utf-8 -*-
import os
import re
import math
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
ELEMENTS_DIR = "Element"

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

def get_body_font(size):
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
    total_w, _ = measure_mixed_text(draw, text, bn_font, font_size)

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

def draw_whatsapp_icon(draw, cx, cy, radius=36):
    """সুন্দর ভেক্টর হোয়াটসঅ্যাপ আইকন তৈরি করে"""
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(37, 211, 102))
    # ছোট অভ্যন্তরীণ সাদা বৃত্ত ও হ্যান্ডসেট সিম্বল
    in_r = int(radius * 0.72)
    draw.ellipse([cx - in_r, cy - in_r, cx + in_r, cy + in_r], outline=(255, 255, 255), width=int(radius*0.14))
    # টেলিকম সাইন
    draw.arc([cx - in_r + 4, cy - in_r + 4, cx + in_r - 4, cy + in_r - 4], start=120, end=300, fill=(255, 255, 255), width=int(radius*0.2))

# =========================================================================
# 🌟 আপনার দেওয়া নমুনার সাথে ১০০% মিল রেখে পোস্টার রেন্ডারার
# =========================================================================
def render_poster_image(job_data, output_path):
    W, H = 1080, 1920
    # 🌟 আপনার ছবির ব্যাকগ্রাউন্ডের এক্সাক্ট কালার (Pale Warm Cream)
    BG_COLOR = (253, 247, 215) # #FDF7D7
    
    im = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(im)

    # ---------------------------------------------------------------------
    # ১. হেডলাইন সেকশন (গাঢ় সবুজ রঙ + আন্ডারলাইন)
    # ---------------------------------------------------------------------
    h1 = job_data.get("poster_headline_1", "")
    h2 = job_data.get("poster_headline_2", "সুযোগ!")
    if not h1:
        org = clean_org_name(job_data.get("org_name", "সরকারি প্রতিষ্ঠান"))
        h1 = f"{org}র বিশাল নিয়োগ"

    head_font = get_header_font(70)
    GREEN_COLOR = (20, 90, 40) # #145A28

    # লাইন ১
    w1, h1_box = measure_mixed_text(draw, h1, head_font, 70)
    y1 = 345
    draw_mixed_text(draw, W // 2, y1, h1, head_font, 70, GREEN_COLOR, anchor="mm")
    # লাইন ১ এর নিচে ডিভাইডার আন্ডারলাইন
    line1_left = max(60, (W - w1) // 2 - 15)
    line1_right = min(W - 60, (W + w1) // 2 + 15)
    draw.line([(line1_left, y1 + 48), (line1_right, y1 + 48)], fill=GREEN_COLOR, width=4)

    # লাইন ২
    w2, _ = measure_mixed_text(draw, h2, head_font, 70)
    y2 = y1 + 105
    draw_mixed_text(draw, W // 2, y2, h2, head_font, 70, GREEN_COLOR, anchor="mm")
    # লাইন ২ এর নিচে ছোট আন্ডারলাইন
    line2_left = max(100, (W - w2) // 2 - 10)
    line2_right = min(W - 100, (W + w2) // 2 + 10)
    draw.line([(line2_left, y2 + 48), (line2_right, y2 + 48)], fill=GREEN_COLOR, width=4)

    # ---------------------------------------------------------------------
    # ২. মাঝখানের তথ্যসমূহ (সংক্ষিপ্ত ও পরিচ্ছন্ন বুলেট পয়েন্ট)
    # ---------------------------------------------------------------------
    body_font = get_body_font(52)
    BLACK_COLOR = (17, 24, 39)
    RED_COLOR = (185, 28, 28)     # #B91C1C
    CRIMSON_COLOR = (153, 27, 27) # #991B1B

    # পয়েন্ট ১: শিক্ষাগত যোগ্যতা ও মোট পদ
    p1_lines = job_data.get("poster_p1_lines", [])
    if not p1_lines:
        posts = job_data.get("posts", [])
        total_vac = sum([int(re.findall(r'\d+', p.get('vacancy', '1'))[0]) for p in posts if re.findall(r'\d+', p.get('vacancy', ''))] or [len(posts)])
        vac_bn = re.sub(r'(\d)', lambda m: "০১২৩৪৫৬৭৮৯"[int(m.group(1))], str(total_vac))
        qual = posts[0].get('qualification', 'যোগ্যতা অনুযায়ী') if posts else "যোগ্যতানুযায়ী"
        p1_text = f"{qual} পদে {vac_bn} পদে আবেদনের সুযোগ।"
        p1_lines = wrap_mixed_text(draw, p1_text, body_font, 52, max_width=920)

    cur_y = 600
    for l in p1_lines[:2]:
        draw_mixed_text(draw, W // 2, cur_y, l, body_font, 52, BLACK_COLOR, anchor="mm")
        cur_y += 70

    # পয়েন্ট ২: আবেদনের শেষ তারিখ ও ফি (💻 আইকনসহ)
    cur_y += 50
    ed_date = str(job_data.get("end_date", "শীঘ্রই শেষ হবে"))
    p2_line1 = f"💻 আবেদনের শেষ তারিখ: {ed_date}"
    p2_line2 = job_data.get("poster_fee_line", "আবেদন ফি বিজ্ঞপ্তিমতে।")

    # ডেট লাল রঙে হাইলাইট করে ড্র করা
    draw_mixed_text(draw, W // 2, cur_y, p2_line1, body_font, 50, BLACK_COLOR, anchor="mm")
    cur_y += 70
    draw_mixed_text(draw, W // 2, cur_y, p2_line2, body_font, 48, BLACK_COLOR, anchor="mm")

    # পয়েন্ট ৩: পদের তালিকা ও পদ সংখ্যা (👥 আইকনসহ লাল রঙ)
    cur_y += 65
    p3_lines = job_data.get("poster_p3_lines", [])
    if not p3_lines:
        posts = job_data.get("posts", [])
        if posts:
            p_sample = " এবং ".join([f"{p.get('post_name','')} – {p.get('vacancy','০১')} টি" for p in posts[:2]])
            p3_text = f"👥 {p_sample} পদে আবেদন করা যাবে।"
        else:
            p3_text = "👥 বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে আবেদন করা যাবে।"
        p3_lines = wrap_mixed_text(draw, p3_text, body_font, 48, max_width=920)

    for l in p3_lines[:3]:
        draw_mixed_text(draw, W // 2, cur_y, l, body_font, 48, CRIMSON_COLOR, anchor="mm")
        cur_y += 68

    # ---------------------------------------------------------------------
    # ৩. নিচের ফিক্সড হোয়াটসঅ্যাপ কল-টু-অ্যাকশন (CTA)
    # ---------------------------------------------------------------------
    wa_y = 1205
    # হোয়াটসঅ্যাপ আইকন + নম্বর
    icon_x = 295
    draw_whatsapp_icon(draw, icon_x, wa_y, radius=38)

    num_font = get_english_bold_font(62)
    draw.text((icon_x + 60, wa_y), "01540503092", font=num_font, fill=BLACK_COLOR, anchor="lm")

    # নিচে আবেদন করার আহ্বান
    cta_font = get_body_font(44)
    draw_mixed_text(draw, W // 2, wa_y + 90, "আবেদন করতে হোয়াটসঅ্যাপে", cta_font, 44, BLACK_COLOR, anchor="mm")
    draw_mixed_text(draw, W // 2, wa_y + 155, "যোগাযোগ করুন।", cta_font, 44, BLACK_COLOR, anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

def prepare_tiktok_slides(job_data, output_prefix="poster"):
    out_path = f"{output_prefix}_1.png"
    render_poster_image(job_data, out_path)
    return [out_path]
