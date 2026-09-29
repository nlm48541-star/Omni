# -*- coding: utf-8 -*-
import os
import re
import math
import shutil
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
ELEMENTS_DIR = "Element"

def find_element_image(hint_names):
    """Element ফোল্ডার থেকে নির্দিষ্ট পিএনজি খুঁজে বের করে ক্রপ করে রিটার্ন করে"""
    if isinstance(hint_names, str): hint_names = [hint_names]
    search_dirs = [ELEMENTS_DIR, "Elements", "element", "elements", "."]
    for d in search_dirs:
        if os.path.exists(d) and os.path.isdir(d):
            for f in os.listdir(d):
                f_lower = f.lower()
                for hint in hint_names:
                    if hint.lower() in f_lower and f_lower.endswith(('.png', '.webp')):
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

def draw_mixed_text(draw, x, y, text, bn_font, font_size, fill_color, anchor="lm", stroke=True):
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

    stroke_w = 3 if stroke else 0
    stroke_c = (0, 0, 0, 240) if stroke else None

    for seg, is_eng in segments:
        f = eng_font if is_eng else bn_font
        try:
            bbox = f.getbbox(seg)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(seg) * int(font_size * 0.6)
            
        if stroke:
            draw.text((cur_x, cur_y), seg, font=f, fill=fill_color, anchor=f_anchor, stroke_width=stroke_w, stroke_fill=stroke_c)
        else:
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

def render_motion_graphic_frame(job_data, slide_posts, frame_idx=60, total_frames=120, fps=24):
    W, H = 1080, 1920
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    outro_frames = int(fps * 1.2)
    outro_start = max(60, total_frames - outro_frames)
    is_outro = frame_idx >= outro_start
    if is_outro:
        exit_t = (frame_idx - outro_start) / float(outro_frames)
        global_alpha = int(255 * (1.0 - ease_in_cubic(exit_t)))
        exit_offset_y = int(ease_in_cubic(exit_t) * 90)
    else:
        global_alpha = 255
        exit_offset_y = 0

    if global_alpha <= 0:
        return overlay

    # ১. emblem.png (পপ-আপ)
    emblem_img = find_element_image(["emblem", "input_file_5", "logo", "govt"])
    emblem_prog = ease_out_back(get_progress(frame_idx, 0, 14)) if not is_outro else (1.0 - exit_t)
    if emblem_img and emblem_prog > 0:
        dim = int(130 * emblem_prog)
        if dim > 10:
            scaled = emblem_img.resize((dim, dim), Image.LANCZOS)
            ex = (W - dim) // 2
            ey = 125 - (dim // 2) - exit_offset_y
            overlay.paste(scaled, (ex, ey), scaled)

    # 🌟 ২. প্রতিষ্ঠানের নাম (সাইজ বৃদ্ধি করা হয়েছে: ৭০px / ৫৪px)
    org_prog = ease_out_cubic(get_progress(frame_idx, 6, 20)) if not is_outro else (1.0 - exit_t)
    if org_prog > 0:
        org_name = clean_org_name(job_data.get("org_name", "নিয়োগ বিজ্ঞপ্তি"))
        test_font = get_header_font(70)
        test_lines = wrap_mixed_text(draw, org_name, test_font, 70, max_width=950)
        y_slide = int((1.0 - org_prog) * -35) - exit_offset_y

        if len(test_lines) == 1:
            draw_mixed_text(draw, W // 2, 245 + y_slide, test_lines[0], test_font, 70, "#FFFFFF", anchor="mm", stroke=True)
        else:
            org_fs = 54
            org_font = get_header_font(org_fs)
            org_lines = wrap_mixed_text(draw, org_name, org_font, org_fs, max_width=950)
            oy = 220 + y_slide
            for ol in org_lines[:2]:
                draw_mixed_text(draw, W // 2, oy, ol, org_font, org_fs, "#FFFFFF", anchor="mm", stroke=True)
                oy += 56

    # ৩. headline_badge.png ("নিয়োগ বিজ্ঞপ্তি" ব্যানার)
    badge_img = find_element_image(["headline_badge", "badge", "input_file_0"])
    badge_prog = ease_out_back(get_progress(frame_idx, 10, 24)) if not is_outro else (1.0 - exit_t)
    if badge_img and badge_prog > 0:
        target_w = int(780 * badge_prog)
        target_h = int(215 * badge_prog)
        if target_w > 20 and target_h > 10:
            scaled_b = badge_img.resize((target_w, target_h), Image.LANCZOS)
            bx = (W - target_w) // 2
            by = 405 - (target_h // 2) - exit_offset_y
            overlay.paste(scaled_b, (bx, by), scaled_b)

    # 🌟 ৪. আবেদন শুরু ও আবেদন শেষ বক্স (তারিখের সাইজ বৃদ্ধি করে ৫২px করা হয়েছে)
    cal_prog = ease_out_cubic(get_progress(frame_idx, 16, 28)) if not is_outro else (1.0 - exit_t)
    if cal_prog > 0:
        start_img = find_element_image(["start_box", "start", "input_file_4"])
        end_img = find_element_image(["end_box", "end", "input_file_3"])
        
        slide_offset = int((1.0 - cal_prog) * 70)
        box_w, box_h = 460, 185
        by_pos = 535 - exit_offset_y

        # আবেদন শুরু (বাম বক্স)
        if start_img:
            scaled_s = start_img.resize((box_w, box_h), Image.LANCZOS)
            overlay.paste(scaled_s, (65 - slide_offset, by_pos), scaled_s)
        st_text = str(job_data.get("start_date", "চলমান"))
        st_fs = 52 if len(st_text) <= 15 else 44
        draw_mixed_text(draw, 295 - slide_offset, by_pos + 120, st_text, get_dates_font(st_fs), st_fs, "#FFFFFF", anchor="mm", stroke=True)

        # আবেদন শেষ (ডান বক্স)
        if end_img:
            scaled_e = end_img.resize((box_w, box_h), Image.LANCZOS)
            overlay.paste(scaled_e, (555 + slide_offset, by_pos), scaled_e)
        ed_text = str(job_data.get("end_date", "শীঘ্রই শেষ হবে"))
        ed_fs = 52 if len(ed_text) <= 15 else 44
        draw_mixed_text(draw, 785 + slide_offset, by_pos + 120, ed_text, get_dates_font(ed_fs), ed_fs, "#FFFFFF", anchor="mm", stroke=True)

    # ৫. table_header.png রিবন বার
    th_img = find_element_image(["table_header", "table", "header", "input_file_1"])
    th_prog = ease_out_back(get_progress(frame_idx, 22, 34)) if not is_outro else (1.0 - exit_t)
    if th_img and th_prog > 0:
        tw = int(960 * th_prog)
        th = int(184 * th_prog)
        if tw > 20 and th > 10:
            scaled_th = th_img.resize((tw, th), Image.LANCZOS)
            tx = (W - tw) // 2
            ty = 832 - (th // 2) - exit_offset_y
            overlay.paste(scaled_th, (tx, ty), scaled_th)

    # ৬. পদের ৮টি রো
    p_name_font = get_table_font(34)
    p_vac_font = get_table_font(38)
    p_qual_font = get_table_font(28)

    row_top_y = 940 - exit_offset_y
    row_height = 88

    for i in range(8):
        row_start_f = 26 + i * 3
        row_end_f = row_start_f + 8
        r_prog = ease_out_cubic(get_progress(frame_idx, row_start_f, row_end_f)) if not is_outro else (1.0 - exit_t)

        if r_prog > 0 and i < len(slide_posts):
            p = slide_posts[i]
            p_name = p.get("post_name", "")
            p_vac = str(p.get("vacancy", "০১"))
            p_qual = p.get("qualification", "")

            if len(p_vac) == 1 and p_vac in "১২৩৪৫৬৭৮৯123456789":
                bn_map = {"1":"০১","2":"০২","3":"০৩","4":"০৪","5":"০৫","6":"০৬","7":"০৭","8":"০৮","9":"০৯",
                          "১":"০১","২":"০২","৩":"০৩","৪":"০৪","৫":"০৫","৬":"০৬","৭":"০৭","৮":"০৮","৯":"০৯"}
                p_vac = bn_map.get(p_vac, p_vac)

            cy = int(row_top_y + i * row_height + (row_height / 2))
            rx_offset = int((1.0 - r_prog) * -40)

            name_lines = wrap_mixed_text(draw, p_name, p_name_font, 34, max_width=390)
            if len(name_lines) == 1:
                draw_mixed_text(draw, 85 + rx_offset, cy, name_lines[0], p_name_font, 34, "#FFFFFF", anchor="lm", stroke=True)
            else:
                ny = cy - 16
                for nl in name_lines[:2]:
                    draw_mixed_text(draw, 85 + rx_offset, ny, nl, p_name_font, 30, "#FFFFFF", anchor="lm", stroke=True)
                    ny += 32

            draw_mixed_text(draw, 585, cy, p_vac, p_vac_font, 38, "#FDE047", anchor="mm", stroke=True)

            qual_lines = wrap_mixed_text(draw, p_qual, p_qual_font, 28, max_width=290)
            if len(qual_lines) == 1:
                draw_mixed_text(draw, 710, cy, qual_lines[0], p_qual_font, 28, "#FFFFFF", anchor="lm", stroke=True)
            else:
                qy = cy - 15
                for ql in qual_lines[:2]:
                    draw_mixed_text(draw, 710, qy, ql, p_qual_font, 24, "#FFFFFF", anchor="lm", stroke=True)
                    qy += 30

    # ৭. whatsapp_bar.png
    wa_img = find_element_image(["whatsapp_bar", "whatsapp", "wa", "input_file_2"])
    wa_prog = ease_out_back(get_progress(frame_idx, 42, 56)) if not is_outro else (1.0 - exit_t)
    if wa_img and wa_prog > 0:
        wy = int((1.0 - wa_prog) * 80) - exit_offset_y
        w_w = 960
        w_h = 218
        scaled_w = wa_img.resize((w_w, w_h), Image.LANCZOS)
        overlay.paste(scaled_w, (60, 1680 + wy), scaled_w)

    return overlay

def prepare_tiktok_slides(job_data, output_prefix="slide"):
    posts = job_data.get("posts", [])
    out_paths = []
    if len(posts) > 8:
        for idx, chunk_start in enumerate(range(0, len(posts), 8), start=1):
            chunk = posts[chunk_start : chunk_start + 8]
            frame = render_motion_graphic_frame(job_data, chunk, frame_idx=60, total_frames=120)
            p = f"{output_prefix}_{idx}.png"
            frame.save(p, "PNG")
            out_paths.append(p)
    else:
        frame = render_motion_graphic_frame(job_data, posts, frame_idx=60, total_frames=120)
        p = f"{output_prefix}_1.png"
        frame.save(p, "PNG")
        out_paths.append(p)
    return out_paths

def generate_tiktok_animated_overlay_frames(job_data, temp_frames_dir, total_frames=120, fps=24):
    os.makedirs(temp_frames_dir, exist_ok=True)
    posts = job_data.get("posts", [])
    slide_posts = posts[:8]

    outro_frames = int(fps * 1.2)
    outro_start = max(65, total_frames - outro_frames)
    intro_settle_f = 60
    static_frame_path = None

    for f in range(total_frames):
        target_path = os.path.join(temp_frames_dir, f"overlay_{f:04d}.png")
        if f <= intro_settle_f:
            img_frame = render_motion_graphic_frame(job_data, slide_posts, frame_idx=f, total_frames=total_frames, fps=fps)
            img_frame.save(target_path, "PNG")
            if f == intro_settle_f:
                static_frame_path = target_path
        elif f < outro_start:
            if static_frame_path and os.path.exists(static_frame_path):
                shutil.copyfile(static_frame_path, target_path)
            else:
                img_frame = render_motion_graphic_frame(job_data, slide_posts, frame_idx=intro_settle_f, total_frames=total_frames, fps=fps)
                img_frame.save(target_path, "PNG")
                static_frame_path = target_path
        else:
            img_frame = render_motion_graphic_frame(job_data, slide_posts, frame_idx=f, total_frames=total_frames, fps=fps)
            img_frame.save(target_path, "PNG")
