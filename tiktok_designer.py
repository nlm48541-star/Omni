# -*- coding: utf-8 -*-
import os
import re
import math
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
ELEMENTS_DIR = "Element"

def find_whatsapp_logo():
    """রেপো বা Element ফোল্ডার থেকে ব্যবহারকারীর আপলোড করা হোয়াটসঅ্যাপ লোগো খুঁজে বের করে"""
    search_dirs = [ELEMENTS_DIR, "Elements", "element", "elements", ".", "Images", "images"]
    hints = ["whatsapp", "wa_logo", "whatsapp_logo", "whatsapp_icon", "wa"]
    for d in search_dirs:
        if os.path.exists(d) and os.path.isdir(d):
            for f in os.listdir(d):
                f_lower = f.lower()
                for hint in hints:
                    if hint in f_lower and f_lower.endswith(('.png', '.webp', '.jpg', '.jpeg')):
                        try:
                            im = Image.open(os.path.join(d, f)).convert("RGBA")
                            bbox = im.getbbox()
                            return im.crop(bbox) if bbox else im
                        except Exception: pass
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

# 🌟 সব ধরনের ইমোজি ও বিকৃত প্রতীক দূর করার ফিল্টার
def remove_emojis(text):
    if not text: return ""
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\u2b00-\u2bff\u2300-\u23ff\u200d\ufe0f]",
        flags=re.UNICODE
    )
    clean = emoji_pattern.sub('', str(text))
    return re.sub(r'[⎚💻👥📱📞🏢]+', '', clean).strip()

def split_text_by_script(text):
    clean = remove_emojis(text)
    tokens = re.split(r'([A-Za-z0-9\+\:\-\.\_\@\/\#\&\(\)\s]+)', str(clean))
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

# 🌟 অদৃশ্য সেফটি মার্জিন অনুযায়ী অটো-লাইনব্রেক ফাংশন
def wrap_mixed_text(draw, text, bn_font, font_size, max_width=880):
    if not text: return []
    clean = remove_emojis(text)
    words = str(clean).split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        width, _ = measure_mixed_text(draw, test, bn_font, font_size)
        if width <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(' '.join(cur))
            cur = [w]
    if cur:
        lines.append(' '.join(cur))
    return lines

def clean_org_name(org_name):
    if not org_name: return "নিয়োগ বিজ্ঞপ্তি"
    clean = re.sub(r'[\r\n\t]+', ' ', str(org_name)).strip()
    clean = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Job\s*Circular.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'সার্কুলার.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'202[0-9]|২০২[০-৯]', '', clean).strip(" -|,")
    return clean if len(clean) > 2 else org_name

# =========================================================================
# 🌟 প্রিমিয়াম পোস্টার রেন্ডারার (অদৃশ্য সেফটি মার্জিন ও ফিক্সড লেআউট)
# =========================================================================
def render_poster_image(job_data, output_path):
    W, H = 1080, 1920
    BG_COLOR = (253, 247, 215) # #FDF7D7

    im = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(im)

    # 🌟 অদৃশ্য সেফটি মার্জিন: দুই পাশে ১০০px করে জায়গা সুরক্ষিত থাকবে (লেখা কখনো কাটবে না)
    SAFE_MAX_WIDTH = 880

    # ---------------------------------------------------------------------
    # ১. হেডলাইন সেকশন (সবুজ রঙ + অটো র‍্যাপ + আন্ডারলাইন)
    # ---------------------------------------------------------------------
    h1 = remove_emojis(job_data.get("poster_headline_1", ""))
    h2 = remove_emojis(job_data.get("poster_headline_2", "সুযোগ!"))
    if not h1:
        org = clean_org_name(job_data.get("org_name", "সরকারি প্রতিষ্ঠান"))
        h1 = f"{org} বিশাল নিয়োগ"

    head_font = get_header_font(68)
    GREEN_COLOR = (20, 90, 40)

    # হেডলাইন যেন দুই পাশে কেটে না যায় তাই অটো-র‍্যাপ
    h1_lines = wrap_mixed_text(draw, h1, head_font, 68, max_width=SAFE_MAX_WIDTH)
    cur_y = 330
    for idx, line in enumerate(h1_lines):
        draw_mixed_text(draw, W // 2, cur_y, line, head_font, 68, GREEN_COLOR, anchor="mm")
        if idx == len(h1_lines) - 1:
            w1, _ = measure_mixed_text(draw, line, head_font, 68)
            l_left = max(100, (W - w1) // 2 - 15)
            l_right = min(W - 100, (W + w1) // 2 + 15)
            draw.line([(l_left, cur_y + 48), (l_right, cur_y + 48)], fill=GREEN_COLOR, width=4)
        cur_y += 85

    # ২য় হেডলাইন (হুক)
    cur_y += 15
    h2_lines = wrap_mixed_text(draw, h2, head_font, 66, max_width=SAFE_MAX_WIDTH)
    for idx, line in enumerate(h2_lines):
        draw_mixed_text(draw, W // 2, cur_y, line, head_font, 66, GREEN_COLOR, anchor="mm")
        w2, _ = measure_mixed_text(draw, line, head_font, 66)
        l2_left = max(120, (W - w2) // 2 - 10)
        l2_right = min(W - 120, (W + w2) // 2 + 10)
        draw.line([(l2_left, cur_y + 48), (l2_right, cur_y + 48)], fill=GREEN_COLOR, width=4)
        cur_y += 80

    # ---------------------------------------------------------------------
    # ২. বডি সেকশন (সংক্ষিপ্ত, আকর্ষণীয় এবং অদৃশ্য বর্ডারের ভেতরে)
    # ---------------------------------------------------------------------
    body_font = get_body_font(50)
    BLACK_COLOR = (17, 24, 39)
    CRIMSON_COLOR = (153, 27, 27)

    # পয়েন্ট ১: যোগ্যতা ও মোট পদ
    p1_raw = job_data.get("poster_p1_lines", [])
    if not p1_raw:
        posts = job_data.get("posts", [])
        total_vac = sum([int(re.findall(r'\d+', p.get('vacancy', '1'))[0]) for p in posts if re.findall(r'\d+', p.get('vacancy', ''))] or [len(posts)])
        vac_bn = re.sub(r'(\d)', lambda m: "০১২৩৪৫৬৭৮৯"[int(m.group(1))], str(total_vac))
        qual = posts[0].get('qualification', 'যোগ্যতা অনুযায়ী') if posts else "যোগ্যতানুযায়ী"
        p1_text = f"{qual} পদে {vac_bn} পদে আবেদনের সুযোগ।"
        p1_lines = wrap_mixed_text(draw, p1_text, body_font, 50, max_width=SAFE_MAX_WIDTH)
    else:
        p1_lines = []
        for line in p1_raw:
            p1_lines.extend(wrap_mixed_text(draw, line, body_font, 50, max_width=SAFE_MAX_WIDTH))

    cur_y += 35
    for l in p1_lines:
        draw_mixed_text(draw, W // 2, cur_y, l, body_font, 50, BLACK_COLOR, anchor="mm")
        cur_y += 68

    # 🌟 পয়েন্ট ২: তারিখসমূহ (আবেদন শুরুর তারিখ এবং আবেদনের শেষ তারিখ আলাদা)
    cur_y += 30
    st_date = str(job_data.get("start_date", "চলমান")).strip()
    ed_date = str(job_data.get("end_date", "শীঘ্রই শেষ হবে")).strip()
    fee_line = str(job_data.get("poster_fee_line", "আবেদন ফি বিজ্ঞপ্তিমতে।")).strip()

    # ১. আবেদন শুরুর তারিখ (উপরে থাকবে)
    start_line_text = f"আবেদন শুরুর তারিখ: {st_date}"
    start_lines = wrap_mixed_text(draw, start_line_text, body_font, 48, max_width=SAFE_MAX_WIDTH)
    for sl in start_lines:
        draw_mixed_text(draw, W // 2, cur_y, sl, body_font, 48, BLACK_COLOR, anchor="mm")
        cur_y += 65

    # ২. আবেদনের শেষ তারিখ ও ফি (নিচে থাকবে - কোনো ডুপ্লিকেট হবে না)
    end_line_text = f"আবেদনের শেষ তারিখ: {ed_date}। {fee_line}"
    end_lines = wrap_mixed_text(draw, end_line_text, body_font, 48, max_width=SAFE_MAX_WIDTH)
    for el in end_lines:
        draw_mixed_text(draw, W // 2, cur_y, el, body_font, 48, BLACK_COLOR, anchor="mm")
        cur_y += 65

    # 🌟 পয়েন্ট ৩: প্রধান প্রধান পদের তালিকা (লাল রঙে আকর্ষণীয় উপস্থাপনা)
    cur_y += 25
    p3_raw = job_data.get("poster_p3_lines", [])
    if not p3_raw:
        posts = job_data.get("posts", [])
        if posts:
            p_sample = " এবং ".join([f"{p.get('post_name','')} – {p.get('vacancy','০১')} টি" for p in posts[:2]])
            p3_text = f"{p_sample} পদে আবেদন করা যাবে।"
        else:
            p3_text = "বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে আবেদন করা যাবে।"
        p3_lines = wrap_mixed_text(draw, p3_text, body_font, 48, max_width=SAFE_MAX_WIDTH)
    else:
        p3_lines = []
        for line in p3_raw:
            # যদি এআই ভুলে শেষ তারিখ এখানেও ঢুকিয়ে দেয় তা বাদ দেওয়া
            clean_l = re.sub(r'আবেদনের শেষ তারিখ.*$', '', line).strip()
            if clean_l:
                p3_lines.extend(wrap_mixed_text(draw, clean_l, body_font, 48, max_width=SAFE_MAX_WIDTH))

    for l in p3_lines:
        draw_mixed_text(draw, W // 2, cur_y, l, body_font, 48, CRIMSON_COLOR, anchor="mm")
        cur_y += 65

    # ---------------------------------------------------------------------
    # ৩. নিচের ফিক্সড হোয়াটসঅ্যাপ কল-টু-অ্যাকশন (CTA)
    # ---------------------------------------------------------------------
    wa_y = 1240
    num_font = get_english_bold_font(66)
    num_w, _ = measure_mixed_text(draw, "01540503092", num_font, 66)

    # 🌟 রেপোজিটরি থেকে ব্যবহারকারীর দেওয়া হোয়াটসঅ্যাপ লোগো লোড করা
    wa_img = find_whatsapp_logo()
    if wa_img:
        wa_size = 72
        wa_scaled = wa_img.resize((wa_size, wa_size), Image.LANCZOS)
        total_block_w = wa_size + 20 + num_w
        start_x = (W - total_block_w) // 2

        im.paste(wa_scaled, (start_x, wa_y - (wa_size // 2)), wa_scaled)
        draw.text((start_x + wa_size + 20, wa_y), "01540503092", font=num_font, fill=BLACK_COLOR, anchor="lm")
    else:
        # রেপোতে কোনো লোগো না পাওয়া গেলে ক্রিস্প ভেক্টর আইকন
        draw.ellipse([W // 2 - 250, wa_y - 36, W // 2 - 178, wa_y + 36], fill=(37, 211, 102))
        draw_mixed_text(draw, W // 2 - 214, wa_y, "WA", get_english_bold_font(32), 32, "#FFFFFF", anchor="mm")
        draw.text((W // 2 - 160, wa_y), "01540503092", font=num_font, fill=BLACK_COLOR, anchor="lm")

    # 🌟 কল টু অ্যাকশন টেক্সট বড় ও বোল্ড করা হয়েছে (ফন্ট সাইজ ৫২)
    cta_font = get_body_font(52)
    draw_mixed_text(draw, W // 2, wa_y + 90, "আবেদন করতে হোয়াটসঅ্যাপে", cta_font, 52, BLACK_COLOR, anchor="mm")
    draw_mixed_text(draw, W // 2, wa_y + 160, "যোগাযোগ করুন।", cta_font, 52, BLACK_COLOR, anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

def prepare_tiktok_slides(job_data, output_prefix="poster"):
    out_path = f"{output_prefix}_1.png"
    render_poster_image(job_data, out_path)
    return [out_path]
