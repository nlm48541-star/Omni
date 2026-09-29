# -*- coding: utf-8 -*-
import os
import re
import math
import shutil
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
ELEMENTS_DIR = "Element"

def find_element_image(hint_names):
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

# 🌟 কোনো কালো স্ট্রোক ছাড়া শতভাগ পরিষ্কার ও সলিড কালারে টেক্সট ড্র
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

# 🌟 ৩টির বেশি শব্দ হলে সমান দুই লাইনে ভাগ করার নিখুঁত ফাংশন
def split_title_words(text):
    words = str(text).split()
    if len(words) <= 3:
        return [text]
    mid = math.ceil(len(words) / 2.0)
    line1 = " ".join(words[:mid])
    line2 = " ".join(words[mid:])
    return [line1, line2]

def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)

def ease_in_cubic(t):
    t = max(0.0, min(1.0, t))
    return math.pow(t, 3)

def ease_out_back(t, s=1.2):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * math.pow(t - 1.0, 3) + s * math.pow(t - 1.0, 2)

def get_progress(frame_num, start_f, end_f):
    if frame_num < start_f: return 0.0
    if frame_num >= end_f: return 1.0
    return (frame_num - start_f) / float(end_f - start_f)

def render_motion_graphic_frame(job_data, slide_posts, frame_idx=60, total_frames=120, fps=24, slide_entry_prog=1.0, slide_exit_prog=0.0):
    W, H = 1080, 1920
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ভিডিওর শেষ ১.২ সেকেন্ডে সার্বিক আউটরো
    outro_frames = int(fps * 1.2)
    outro_start = max(115, total_frames - outro_frames)
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

    # ১. emblem.png (ফ্রেম ০ থেকে ২০)
    emblem_img = find_element_image(["emblem", "input_file_5", "logo", "govt"])
    emblem_prog = ease_out_back(get_progress(frame_idx, 0, 20)) if not is_outro else (1.0 - exit_t)
    if emblem_img and emblem_prog > 0:
        dim = int(135 * emblem_prog)
        if dim > 10:
            scaled = emblem_img.resize((dim, dim), Image.LANCZOS)
            ex = (W - dim) // 2
            ey = 125 - (dim // 2) - exit_offset_y
            overlay.paste(scaled, (ex, ey), scaled)

    # 🌟 ২. প্রতিষ্ঠানের নাম (৩টির বেশি শব্দ হলে সমান ২ ভাগে ভাগ ও বড় ফন্ট)
    org_prog = ease_out_cubic(get_progress(frame_idx, 10, 32)) if not is_outro else (1.0 - exit_t)
    if org_prog > 0:
        org_name = clean_org_name(job_data.get("org_name", "নিয়োগ বিজ্ঞপ্তি"))
        title_lines = split_title_words(org_name)
        y_slide = int((1.0 - org_prog) * -35) - exit_offset_y

        if len(title_lines) == 1:
            org_font = get_header_font(76)
            draw_mixed_text(draw, W // 2, 250 + y_slide, title_lines[0], org_font, 76, "#FFFFFF", anchor="mm")
        else:
            org_font = get_header_font(62)
            oy = 222 + y_slide
            for ol in title_lines:
                draw_mixed_text(draw, W // 2, oy, ol, org_font, 62, "#FFFFFF", anchor="mm")
                oy += 65

    # 🌟 ৩. headline_badge.png ("নিয়োগ বিজ্ঞপ্তি" ব্যানারটি আকারে একটু ছোট করা হয়েছে: ৬৪০px)
    badge_img = find_element_image(["headline_badge", "badge", "input_file_0"])
    badge_prog = ease_out_back(get_progress(frame_idx, 20, 42)) if not is_outro else (1.0 - exit_t)
    if badge_img and badge_prog > 0:
        target_w = int(640 * badge_prog)
        aspect = badge_img.size[1] / float(badge_img.size[0])
        target_h = max(1, int(target_w * aspect))
        if target_w > 20 and target_h > 10:
            scaled_b = badge_img.resize((target_w, target_h), Image.LANCZOS)
            bx = (W - target_w) // 2
            by = 415 - (target_h // 2) - exit_offset_y
            overlay.paste(scaled_b, (bx, by), scaled_b)

    # ৪. আবেদন শুরু ও আবেদন শেষ বক্স (ফ্রেম ৩০ থেকে ৫২)
    cal_prog = ease_out_cubic(get_progress(frame_idx, 30, 52)) if not is_outro else (1.0 - exit_t)
    if cal_prog > 0:
        start_img = find_element_image(["start_box", "start", "input_file_4"])
        end_img = find_element_image(["end_box", "end", "input_file_3"])
        
        slide_offset = int((1.0 - cal_prog) * 80)
        box_w = 460
        by_pos = 535 - exit_offset_y

        # আবেদন শুরু
        if start_img:
            aspect_s = start_img.size[1] / float(start_img.size[0])
            box_h_s = int(box_w * aspect_s)
            scaled_s = start_img.resize((box_w, box_h_s), Image.LANCZOS)
            overlay.paste(scaled_s, (65 - slide_offset, by_pos), scaled_s)
            
        st_text = str(job_data.get("start_date", "চলমান"))
        st_fs = 52 if len(st_text) <= 15 else 44
        draw_mixed_text(draw, 295 - slide_offset, by_pos + 138, st_text, get_dates_font(st_fs), st_fs, "#FFFFFF", anchor="mm")

        # আবেদন শেষ
        if end_img:
            aspect_e = end_img.size[1] / float(end_img.size[0])
            box_h_e = int(box_w * aspect_e)
            scaled_e = end_img.resize((box_w, box_h_e), Image.LANCZOS)
            overlay.paste(scaled_e, (555 + slide_offset, by_pos), scaled_e)
            
        ed_text = str(job_data.get("end_date", "শীঘ্রই শেষ হবে"))
        ed_fs = 52 if len(ed_text) <= 15 else 44
        draw_mixed_text(draw, 785 + slide_offset, by_pos + 138, ed_text, get_dates_font(ed_fs), ed_fs, "#FFFFFF", anchor="mm")

    # ৫. table_header.png (লাল রিবন - স্বাভাবিক অনুপাত)
    th_img = find_element_image(["table_header", "table", "header", "input_file_1"])
    th_prog = ease_out_back(get_progress(frame_idx, 40, 62)) if not is_outro else (1.0 - exit_t)
    if th_img and th_prog > 0:
        tw = int(980 * th_prog)
        aspect_th = th_img.size[1] / float(th_img.size[0])
        th = max(1, int(tw * aspect_th))
        if tw > 20 and th > 10:
            scaled_th = th_img.resize((tw, th), Image.LANCZOS)
            tx = (W - tw) // 2
            ty = 832 - (th // 2) - exit_offset_y
            overlay.paste(scaled_th, (tx, ty), scaled_th)

    # 🌟 ৬. পদের তালিকা (প্রতি স্লাইডে সর্বোচ্চ ৫টি পদ, আরও প্রশস্ত ও স্পেসিয়াস রেন্ডারিং)
    p_name_font = get_table_font(36)
    p_vac_font = get_table_font(42)
    p_qual_font = get_table_font(30)

    row_top_y = 945 - exit_offset_y
    row_height = 120  # ৫টি পদের জন্য ১২০px চমৎকার উচ্চতা

    # স্লাইড ট্রানজিশন ফেড ও স্লাইড অফসেট
    slide_alpha_mult = 1.0 - ease_in_cubic(slide_exit_prog)
    slide_exit_shift_x = int(ease_in_cubic(slide_exit_prog) * -40)

    for i in range(min(5, len(slide_posts))):
        row_enter_f = 0.0 + (i * 0.15)
        r_prog = ease_out_cubic(max(0.0, min(1.0, (slide_entry_prog - row_enter_f) / 0.4))) if not is_outro else (1.0 - exit_t)

        if r_prog > 0 and slide_alpha_mult > 0:
            p = slide_posts[i]
            p_name = p.get("post_name", "")
            p_vac = str(p.get("vacancy", "০১"))
            p_qual = p.get("qualification", "")

            if len(p_vac) == 1 and p_vac in "১২৩৪৫৬৭৮৯123456789":
                bn_map = {"1":"০১","2":"০২","3":"০৩","4":"০৪","5":"০৫","6":"০৬","7":"০৭","8":"০৮","9":"০৯",
                          "১":"০১","২":"০২","৩":"০৩","৪":"০৪","৫":"০৫","৬":"০৬","৭":"০৭","৮":"০৮","৯":"০৯"}
                p_vac = bn_map.get(p_vac, p_vac)

            cy = int(row_top_y + (i * row_height) + (row_height / 2))
            rx_offset = int((1.0 - r_prog) * -45) + slide_exit_shift_x

            # কলাম ১: পদের নাম (Left X = 80)
            name_lines = wrap_mixed_text(draw, p_name, p_name_font, 36, max_width=410)
            if len(name_lines) == 1:
                draw_mixed_text(draw, 80 + rx_offset, cy, name_lines[0], p_name_font, 36, "#FFFFFF", anchor="lm")
            else:
                ny = cy - 20
                for nl in name_lines[:2]:
                    draw_mixed_text(draw, 80 + rx_offset, ny, nl, p_name_font, 32, "#FFFFFF", anchor="lm")
                    ny += 38

            # 🌟 কলাম ২: পদ সংখ্যা ("সংখ্যা" লেখার ঠিক মাঝ বরাবর: Center X = 550)
            draw_mixed_text(draw, 550 + rx_offset, cy, p_vac, p_vac_font, 42, "#FDE047", anchor="mm")

            # 🌟 কলাম ৩: শিক্ষাগত যোগ্যতা ("যোগ্যতা" লেখার শুরু বরাবর: Left X = 740)
            qual_lines = wrap_mixed_text(draw, p_qual, p_qual_font, 30, max_width=280)
            if len(qual_lines) == 1:
                draw_mixed_text(draw, 740 + rx_offset, cy, qual_lines[0], p_qual_font, 30, "#FFFFFF", anchor="lm")
            else:
                qy = cy - 18
                for ql in qual_lines[:2]:
                    draw_mixed_text(draw, 740 + rx_offset, qy, ql, p_qual_font, 26, "#FFFFFF", anchor="lm")
                    qy += 34

    # ৭. whatsapp_bar.png (ফ্রেম ৮৫ থেকে ১০৮)
    wa_img = find_element_image(["whatsapp_bar", "whatsapp", "wa", "input_file_2"])
    wa_prog = ease_out_back(get_progress(frame_idx, 85, 108)) if not is_outro else (1.0 - exit_t)
    if wa_img and wa_prog > 0:
        wy = int((1.0 - wa_prog) * 80) - exit_offset_y
        w_w = 960
        aspect_wa = wa_img.size[1] / float(wa_img.size[0])
        w_h = max(1, int(w_w * aspect_wa))
        scaled_w = wa_img.resize((w_w, w_h), Image.LANCZOS)
        wx = (W - w_w) // 2
        overlay.paste(scaled_w, (wx, 1680 + wy), scaled_w)

    return overlay

# 🌟 ৫টি ৫টি করে পদের নাম স্লাইড করার জন্য ফ্রেম জেনারেটর
def generate_tiktok_animated_overlay_frames(job_data, temp_frames_dir, total_frames=120, fps=24):
    os.makedirs(temp_frames_dir, exist_ok=True)
    posts = job_data.get("posts", [])
    
    PAGE_SIZE = 5
    chunks = [posts[i:i + PAGE_SIZE] for i in range(0, len(posts), PAGE_SIZE)]
    if not chunks:
        chunks = [[]]
        
    num_slides = len(chunks)
    frames_per_slide = total_frames / float(num_slides)
    outro_frames = int(fps * 1.2)
    outro_start = max(115, total_frames - outro_frames)

    for f in range(total_frames):
        target_path = os.path.join(temp_frames_dir, f"overlay_{f:04d}.png")
        
        # বর্তমান স্লাইড নির্ধারণ
        slide_idx = min(int(f / frames_per_slide), num_slides - 1)
        current_slide_posts = chunks[slide_idx]
        
        slide_start_f = slide_idx * frames_per_slide
        local_f = f - slide_start_f
        slide_len = frames_per_slide
        
        # স্লাইড এন্ট্রি প্রগ্রেস
        if slide_idx == 0:
            # প্রথম স্লাইড: হেডার এলিমেন্টগুলো আসার পর (ফ্রেম ৫০ থেকে ১০০)
            s_entry = max(0.0, min(1.0, (f - 50) / 45.0))
        else:
            # পরবর্তী স্লাইড: নতুন স্লাইড আসার সাথে সাথে
            s_entry = max(0.0, min(1.0, local_f / 25.0))
            
        # স্লাইড এক্সিট প্রগ্রেস (শেষ ১৬ ফ্রেমে ট্রানজিশন)
        transition_f = 16.0
        if slide_idx < num_slides - 1 and local_f >= (slide_len - transition_f):
            s_exit = max(0.0, min(1.0, (local_f - (slide_len - transition_f)) / transition_f))
        else:
            s_exit = 0.0

        img_frame = render_motion_graphic_frame(
            job_data=job_data,
            slide_posts=current_slide_posts,
            frame_idx=f,
            total_frames=total_frames,
            fps=fps,
            slide_entry_prog=s_entry,
            slide_exit_prog=s_exit
        )
        img_frame.save(target_path, "PNG")

def prepare_tiktok_slides(job_data, output_prefix="slide"):
    posts = job_data.get("posts", [])
    out_paths = []
    PAGE_SIZE = 5
    chunks = [posts[i:i + PAGE_SIZE] for i in range(0, len(posts), PAGE_SIZE)]
    if not chunks: chunks = [[]]
    
    for idx, chunk in enumerate(chunks, start=1):
        frame = render_motion_graphic_frame(job_data, chunk, frame_idx=110, total_frames=150, slide_entry_prog=1.0)
        p = f"{output_prefix}_{idx}.png"
        frame.save(p, "PNG")
        out_paths.append(p)
    return out_paths
