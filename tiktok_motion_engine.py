# -*- coding: utf-8 -*-
import os
import re
import math
import random
import subprocess
from PIL import Image, ImageDraw, ImageFilter

from tiktok_designer import (
    find_whatsapp_logo, get_header_font, get_body_font, get_english_bold_font,
    remove_emojis, measure_mixed_text, draw_mixed_text, wrap_mixed_text,
    fit_single_line_font, fit_multiline_font, clean_org_name
)

MINIMAL_PALETTES = [
    {
        "name": "MistCrimson",
        "bg": (248, 248, 250), "shape": (244, 224, 228),
        "ink": (24, 24, 27), "muted": (100, 102, 114),
        "accent": (190, 18, 60), "accent_soft": (255, 241, 242), "hairline": (228, 228, 232),
    },
    {
        "name": "PearlEmerald",
        "bg": (249, 250, 251), "shape": (224, 240, 233),
        "ink": (17, 24, 39), "muted": (96, 108, 126),
        "accent": (5, 122, 85), "accent_soft": (236, 253, 245), "hairline": (226, 232, 236),
    },
    {
        "name": "IvoryCobalt",
        "bg": (250, 249, 246), "shape": (228, 236, 250),
        "ink": (15, 23, 42), "muted": (96, 108, 126),
        "accent": (29, 78, 216), "accent_soft": (239, 246, 255), "hairline": (226, 232, 240),
    }
]

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def to_bn_num(n):
    return str(int(n)).translate(BN_DIGITS)

def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3

def ease_in_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1.0 - ((-2 * t + 2) ** 3) / 2.0

def ease_out_back(t, s=1.55):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * ((t - 1.0) ** 3) + s * ((t - 1.0) ** 2)

def split_posts_uniformly(posts):
    items = list(posts[:20])
    n = len(items)
    if n == 0:
        return [[{"post_name": "বিভিন্ন পদ", "vacancy": "নিয়োগ", "meta": "বিজ্ঞপ্তি অনুযায়ী"}]]
    if n <= 4:
        return [items]
    if n == 5:
        return [items[0:3], items[3:5]]
    if n == 6:
        return [items[0:3], items[3:6]]
    return [items[i:i + 4] for i in range(0, n, 4)]

def uniform_batch_y_positions(batch_len, max_per_b=None):
    m = max_per_b or batch_len
    if m <= 1:
        return [840]
    if m == 2:
        return [735, 1085][:batch_len]
    if m == 3:
        if batch_len == 1: return [935]
        if batch_len == 2: return [780, 1090]
        return [625, 935, 1245][:batch_len]
    if batch_len == 1: return [946]
    if batch_len == 2: return [824, 1068]
    if batch_len == 3: return [702, 946, 1190]
    return [580, 824, 1068, 1312]

def _paste_sprite(canvas, sp, cx, cy, scale=1.0, opacity=1.0):
    if opacity <= 0.02 or scale <= 0.02 or sp is None:
        return
    if abs(scale - 1.0) > 0.015:
        sp = sp.resize((max(2, int(round(sp.width * scale))), max(2, int(round(sp.height * scale)))), Image.BILINEAR)
    alpha = sp.getchannel("A")
    if opacity < 0.99:
        alpha = alpha.point([int(i * opacity) for i in range(256)])
    canvas.paste(sp, (int(round(cx - sp.width / 2)), int(round(cy - sp.height / 2))), alpha)

def _render_masked_rise(canvas, sp, cx, cy, prog, rise_px=50):
    p = ease_out_cubic(prog)
    if p <= 0.02 or sp is None:
        return
    vis_h = max(2, int(round(sp.height * min(1.0, p * 1.15))))
    dy = int(round(rise_px * (1.0 - p)))
    cropped = sp.crop((0, 0, sp.width, vis_h))
    alpha = cropped.getchannel("A")
    if p < 0.72:
        f = p / 0.72
        alpha = alpha.point([int(i * f) for i in range(256)])
    canvas.paste(cropped, (int(round(cx - sp.width / 2)), int(round(cy - sp.height / 2 + dy))), alpha)

def _make_minimal_card(w, h, radius=36, fill=(255, 255, 255), border=None, border_w=2, pad=22, shadow_alpha=24):
    cw, ch = w + pad * 2, h + pad * 2
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    if shadow_alpha > 0:
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 5, pad + w, pad + h + 5], radius=radius, fill=(15, 23, 42, shadow_alpha + 14))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill + (255,), outline=(border + (255,)) if border else None, width=border_w)
    return sh

def _make_text_sprite(text, font_fn, start_sz, min_sz, max_w, max_lines, color, align="mm"):
    tmp = Image.new("RGBA", (max_w + 40, 420), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    f, sz, lines = fit_multiline_font(td, text, font_fn, start_sz, min_sz, max_w, max_lines)
    lh = sz + 14
    h = max(sz + 30, len(lines) * lh + 24)
    sp = Image.new("RGBA", (max_w + 40, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sp)
    cx = sp.width // 2 if align == "mm" else (sp.width - 14 if align == "rm" else 14)
    y = (h - len(lines) * lh) // 2 + lh // 2
    for l in lines:
        draw_mixed_text(sd, cx, y, l, f, sz, color, anchor=align)
        y += lh
    return sp

def _make_word_sprites(text, font_fn, start_sz, min_sz, max_w, max_lines, color, center_x, center_y):
    tmp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    f, sz, lines = fit_multiline_font(td, text, font_fn, start_sz, min_sz, max_w, max_lines)
    lh = sz + 18
    total_h = len(lines) * lh
    cur_y = center_y - total_h // 2 + lh // 2
    word_items = []
    for line in lines:
        words = line.split()
        sp_w = measure_mixed_text(td, " ", f, sz)[0] or int(sz * 0.28)
        widths = [measure_mixed_text(td, w, f, sz)[0] for w in words]
        line_w = sum(widths) + sp_w * max(0, len(words) - 1)
        cur_x = center_x - line_w / 2.0
        for w, ww in zip(words, widths):
            pad_w, pad_h = ww + 28, sz + 36
            wsp = Image.new("RGBA", (max(16, pad_w), max(24, pad_h)), (0, 0, 0, 0))
            draw_mixed_text(ImageDraw.Draw(wsp), pad_w // 2, pad_h // 2, w, f, sz, color, anchor="mm")
            word_items.append((wsp, cur_x + ww / 2.0, cur_y))
            cur_x += ww + sp_w
        cur_y += lh
    return word_items

def _make_minimal_emblem(pal):
    sz = 260
    sp = Image.new("RGBA", (sz * 2, sz * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    cx, cy = sz, sz
    d.ellipse([cx - 210, cy - 210, cx + 210, cy + 210], fill=(255, 255, 255, 255), outline=pal["accent"] + (255,), width=10)
    d.ellipse([cx - 178, cy - 178, cx + 178, cy + 178], outline=pal["hairline"] + (255,), width=5)
    d.rounded_rectangle([cx - 72, cy - 88, cx + 72, cy + 88], radius=18, fill=pal["accent_soft"] + (255,), outline=pal["accent"] + (255,), width=8)
    d.line([(cx - 38, cy - 32), (cx + 38, cy - 32)], fill=pal["accent"] + (255,), width=10)
    d.line([(cx - 38, cy), (cx + 38, cy)], fill=pal["ink"] + (220,), width=9)
    d.line([(cx - 38, cy + 32), (cx + 16, cy + 32)], fill=pal["ink"] + (220,), width=9)
    return sp.resize((sz, sz), Image.LANCZOS)

def _make_whatsapp_sprite():
    logo = find_whatsapp_logo()
    if logo:
        return logo.resize((245, 245), Image.LANCZOS)
    sz = 246
    sp = Image.new("RGBA", (sz * 2, sz * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.rounded_rectangle([30, 44, 462, 476], radius=108, fill=(21, 128, 61, 255))
    d.rounded_rectangle([30, 24, 462, 456], radius=108, fill=(34, 197, 94, 255))
    d.ellipse([114, 108, 378, 372], outline=(255, 255, 255, 255), width=24)
    d.polygon([(122, 318), (98, 390), (174, 362)], fill=(255, 255, 255, 255))
    d.arc([174, 170, 318, 314], start=35, end=220, fill=(255, 255, 255, 255), width=28)
    return sp.resize((sz, sz), Image.LANCZOS)

def _draw_minimal_icon(d, cx, cy, kind, col):
    if kind == "age":
        d.ellipse([cx - 16, cy - 32, cx + 16, cy], fill=col)
        d.pieslice([cx - 30, cy + 6, cx + 30, cy + 50], start=180, end=360, fill=col)
    elif kind == "salary":
        d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=col, width=6)
        d.line([(cx - 14, cy - 10), (cx + 14, cy - 10)], fill=col, width=6)
        d.line([(cx - 14, cy + 8), (cx + 14, cy + 8)], fill=col, width=6)
        d.line([(cx, cy - 18), (cx, cy + 18)], fill=col, width=6)
    elif kind == "fee":
        d.rounded_rectangle([cx - 24, cy - 28, cx + 24, cy + 28], radius=8, outline=col, width=6)
        d.line([(cx - 12, cy - 8), (cx + 12, cy - 8)], fill=col, width=5)
        d.line([(cx - 12, cy + 8), (cx + 12, cy + 8)], fill=col, width=5)
    else:
        d.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], outline=col, width=6)
        d.line([(cx - 28, cy), (cx + 28, cy)], fill=col, width=5)
        d.ellipse([cx - 13, cy - 28, cx + 13, cy + 28], outline=col, width=5)

def _make_curl_sprite(H):
    sp = Image.new("RGBA", (88, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    for x in range(44):
        d.line([(x, 0), (x, H)], fill=(15, 23, 42, int(72 * ((x / 44.0) ** 2))))
    for x in range(44, 88):
        t = 1.0 - (x - 44) / 44.0
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, int(150 * (t ** 1.5))))
    return sp

def _apply_transition(frame_a, frame_b, prog, style, curl_sp):
    W, H = frame_a.size
    p = ease_in_out_cubic(prog)
    if style == "curl":
        cut_x = int(round(W * (1.0 - p)))
        if cut_x <= 0: return frame_b
        if cut_x >= W: return frame_a
        out = frame_b.copy()
        out.paste(frame_a.crop((0, 0, cut_x, H)), (0, 0))
        _paste_sprite(out, curl_sp, cut_x, H // 2)
        return out
    elif style == "push_left":
        shift = int(round(W * p))
        if shift <= 0: return frame_a
        if shift >= W: return frame_b
        out = frame_a.copy()
        out.paste(frame_b.crop((0, 0, shift, H)), (W - shift, 0))
        _paste_sprite(out, curl_sp, W - shift, H // 2)
        return out
    else:
        return Image.blend(frame_a, frame_b, p)

def _shorten_hook(txt):
    t = remove_emojis(txt).strip()
    t = re.sub(r'(?:বিশাল\s*)?(?:সরকারি|বেসরকারি)?\s*(?:চাকরি|সুযোগ|নিয়োগ\s*বিজ্ঞপ্তি)!?$', '', t).strip(" -–—,")
    return t if len(t) >= 5 else remove_emojis(txt).strip()

def _extract_minimal_data(job_data):
    m = job_data.get("motion") if isinstance(job_data.get("motion"), dict) else {}
    p = job_data.get("poster") if isinstance(job_data.get("poster"), dict) else {}

    org = clean_org_name(m.get("org_name") or job_data.get("org_name") or "নিয়োগ বিজ্ঞপ্তি")
    cat_badge = remove_emojis(m.get("category_badge") or "নিয়োগ বিজ্ঞপ্তি").strip()
    raw_hook = remove_emojis(m.get("hook_subtitle") or p.get("hero_top") or job_data.get("hook_top") or "যোগ্যতানুযায়ী আবেদন").strip()
    hook_short = raw_hook if len(raw_hook.split()) <= 5 else _shorten_hook(raw_hook)

    vac_num = m.get("total_vacancy_num", 0)
    try:
        vac_num = int(str(vac_num).translate(EN_DIGITS)) if vac_num else 0
    except Exception:
        vac_num = 0

    vac_display = remove_emojis(m.get("total_vacancy_display") or "").strip()
    if not vac_num and not vac_display:
        vm = re.search(r'([\d০-৯]+)\s*(?:টি|জন)?\s*পদে?', str(p.get("main_summary") or ""))
        if vm:
            try:
                vac_num = int(vm.group(1).translate(EN_DIGITS))
                vac_display = to_bn_num(vac_num) + "টি"
            except Exception:
                pass
    if not vac_display:
        vac_display = (to_bn_num(vac_num) + "টি") if vac_num > 0 else "বিভিন্ন পদ"

    highlights = m.get("highlights") if isinstance(m.get("highlights"), list) else []
    short_tag = ""
    for h in highlights:
        hh = remove_emojis(h).strip()
        if hh:
            short_tag = hh[:36]
            break
    if not short_tag:
        short_tag = remove_emojis(p.get("hero_bottom") or "আকর্ষণীয় ক্যারিয়ার").strip()

    raw_posts = m.get("posts") if isinstance(m.get("posts"), list) and m.get("posts") else job_data.get("posts", [])
    posts = []
    for item in raw_posts[:20]:
        if isinstance(item, dict) and item.get("post_name"):
            pv = remove_emojis(item.get("vacancy", "")).strip() or "বিভিন্ন"
            if re.fullmatch(r'[\d০-৯]+', pv):
                pv = pv + "টি"
            qual = remove_emojis(item.get("qualification", "")).strip()
            grade = remove_emojis(item.get("salary_grade", "")).strip()
            meta = " | ".join([x for x in [qual, grade] if x]) or "বিজ্ঞপ্তি অনুযায়ী"
            posts.append({"post_name": remove_emojis(item.get("post_name")).strip(), "vacancy": pv, "meta": meta})

    if not posts:
        for k1, k2 in [("highlight_1_badge", "highlight_1_text"), ("highlight_2_badge", "highlight_2_text")]:
            b, t = remove_emojis(p.get(k1, "")).strip(), remove_emojis(p.get(k2, "")).strip()
            if b or t:
                posts.append({"post_name": b or "প্রধান পদ", "vacancy": "নিয়োগ", "meta": t[:48]})

    age_limit = remove_emojis(m.get("age_limit") or "১৮–৩০/৩২ বছর").strip()
    age_limit = re.sub(r'\s*\(.*?\)', '', age_limit).strip()
    salary_range = remove_emojis(m.get("salary_range") or "বিজ্ঞপ্তি অনুযায়ী").strip()
    app_fee = remove_emojis(m.get("application_fee") or p.get("fee_box_text") or "বিজ্ঞপ্তিমতে").strip()
    apply_method = remove_emojis(m.get("apply_method") or "অনলাইন").strip()

    sd = remove_emojis(m.get("start_date") or job_data.get("start_date") or "চলমান").strip()
    ed = remove_emojis(m.get("end_date") or job_data.get("end_date") or "শীঘ্রই").strip()
    if sd == "চলমান" and p.get("date_box_text"):
        sd = "চলমান"
        ed = remove_emojis(p.get("date_box_text")).strip()

    wa_num = os.environ.get("WHATSAPP_NUMBER", "01540503092").strip() or "01540503092"
    wa_formatted = (wa_num[:5] + "-" + wa_num[5:]) if (len(wa_num) == 11 and wa_num.startswith("01") and "-" not in wa_num) else wa_num

    return {
        "org": org, "cat_badge": cat_badge, "hook_short": hook_short,
        "vac_num": vac_num, "vac_display": vac_display, "short_tag": short_tag,
        "posts": posts, "age_limit": age_limit, "salary_range": salary_range,
        "app_fee": app_fee, "apply_method": apply_method,
        "start_date": sd, "end_date": ed, "wa_formatted": wa_formatted
    }

def _stream_frames_to_ffmpeg(total_frames, fps, W, H, audio_path, output_path, frame_fn):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
        "-i", "-", "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", output_path
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for f_idx in range(total_frames):
            proc.stdin.write(frame_fn(f_idx).tobytes())
        proc.stdin.close()
        err_msg = proc.stderr.read().decode("utf-8", errors="ignore")
        ret = proc.wait(timeout=300)
        if ret != 0 and err_msg:
            print(f"  ⚠️ [FFmpeg Notice] {err_msg[:180]}")
    except Exception as e:
        print(f"  ❌ [Motion Render Error] {e}")
        try: proc.kill()
        except Exception: pass
        return False

    ok = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    if ok:
        try:
            chk = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", output_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            has_audio = "audio" in chk.stdout
            print(f"  ✅ [Motion SUCCESS] Rendered ({round(os.path.getsize(output_path)/(1024*1024), 2)} MB, Audio={'YES' if has_audio else 'MISSING'})")
        except Exception:
            print(f"  ✅ [Motion SUCCESS] Rendered ({round(os.path.getsize(output_path)/(1024*1024), 2)} MB)")
    return ok

def _draw_clean_sliding_bg_elements(fd, W, H, abs_t, shape_col, accent_col):
    lx1 = int((abs_t * 65) % (W + 300)) - 220
    lx2 = int(W + 200 - ((abs_t * 55) % (W + 300)))
    fd.rounded_rectangle([lx1, 130, lx1 + 160, 136], radius=3, fill=shape_col)
    fd.rounded_rectangle([lx2, H - 315, lx2 + 150, H - 309], radius=3, fill=shape_col)
    fd.ellipse([lx1 + 175, 127, lx1 + 187, 139], fill=accent_col)
    fd.ellipse([lx2 - 24, H - 318, lx2 - 12, H - 306], fill=accent_col)

    cx1 = int((abs_t * 48) % (W + 320)) - 160
    cx2 = int(W + 160 - ((abs_t * 38) % (W + 320)))
    fd.ellipse([cx1 - 95, 45, cx1 + 95, 235], outline=shape_col, width=3)
    fd.ellipse([cx2 - 110, H - 360, cx2 + 110, H - 140], outline=shape_col, width=3)

def render_motion_graphics_video(job_data, audio_path, output_path, fps=24):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    pal = random.choice(MINIMAL_PALETTES)
    data = _extract_minimal_data(job_data)

    print(f"  [✨ Motion Style #1 (Minimal Light)] Palette={pal['name']}, Duration={duration:.1f}s")

    bg_base = Image.new("RGB", (W, H), pal["bg"])
    curl_sp = _make_curl_sprite(H)
    emblem_sp = _make_minimal_emblem(pal)
    wa_sp = _make_whatsapp_sprite()

    hdr_sp = _make_minimal_card(920, 124, radius=32, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
    hd = ImageDraw.Draw(hdr_sp)
    hf, hsz = fit_single_line_font(hd, data["org"], get_body_font, 48, 30, 610)
    draw_mixed_text(hd, 86, 84, data["org"], hf, hsz, pal["ink"], anchor="lm")
    hd.rounded_rectangle([714, 48, 916, 120], radius=24, fill=pal["accent_soft"] + (255,))
    draw_mixed_text(hd, 815, 84, "বিজ্ঞপ্তি", get_body_font(34), 34, pal["accent"], anchor="mm")

    s1_org_words = _make_word_sprites(data["org"], get_header_font, 88, 52, 940, 2, pal["ink"], W // 2, 700)
    s1_badge_sp = _make_minimal_card(620, 134, radius=67, fill=pal["accent"])
    bf, bsz = fit_single_line_font(ImageDraw.Draw(s1_badge_sp), data["cat_badge"], get_body_font, 60, 40, 540)
    draw_mixed_text(ImageDraw.Draw(s1_badge_sp), s1_badge_sp.width // 2, s1_badge_sp.height // 2, data["cat_badge"], bf, bsz, (255, 255, 255), anchor="mm")
    s1_hook_words = _make_word_sprites(data["hook_short"], get_body_font, 56, 38, 900, 2, pal["muted"], W // 2, 1170)

    s2_lbl_sp = _make_text_sprite("মোট শূন্যপদ", get_body_font, 64, 48, 700, 1, pal["muted"])
    s2_card_sp = _make_minimal_card(900, 390, radius=44, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
    s2_static_num = _make_text_sprite(data["vac_display"], get_body_font, 195, 76, 840, 1, pal["accent"])
    s2_tag_sp = _make_minimal_card(880, 150, radius=75, fill=pal["accent_soft"], border=pal["accent"], border_w=2)
    tf2, tsz2, tlines2 = fit_multiline_font(ImageDraw.Draw(s2_tag_sp), data["short_tag"], get_body_font, 50, 34, 800, 2)
    ty2 = s2_tag_sp.height // 2 - ((len(tlines2) - 1) * (tsz2 + 10)) // 2
    for tl2 in tlines2:
        draw_mixed_text(ImageDraw.Draw(s2_tag_sp), s2_tag_sp.width // 2, ty2, tl2, tf2, tsz2, pal["accent"], anchor="mm")
        ty2 += tsz2 + 10

    s3_hdr_sp = _make_text_sprite("প্রধান পদসমূহ", get_body_font, 62, 46, 700, 1, pal["ink"])
    batches_raw = split_posts_uniformly(data["posts"])
    max_per_b = max(len(b) for b in batches_raw)
    if max_per_b == 1:
        u_ch, t_sz, v_sz, m_sz, b_h = 380, 64, 72, 46, 128
    elif max_per_b == 2:
        u_ch, t_sz, v_sz, m_sz, b_h = 320, 56, 62, 44, 114
    elif max_per_b == 3:
        u_ch, t_sz, v_sz, m_sz, b_h = 282, 54, 56, 42, 108
    else:
        u_ch, t_sz, v_sz, m_sz, b_h = 224, 46, 48, 38, 90

    s3_batches = []
    for batch_items in batches_raw:
        ys = uniform_batch_y_positions(len(batch_items), max_per_b)
        card_entries = []
        for idx_c, it in enumerate(batch_items):
            bg_c = _make_minimal_card(940, u_ch, radius=32 if u_ch > 240 else 28, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
            t_sp = _make_text_sprite(it["post_name"], get_body_font, t_sz, 32, 535, 2, pal["ink"], align="lm")
            b_sp = _make_minimal_card(255, b_h, radius=26, fill=pal["accent_soft"], pad=12, shadow_alpha=0)
            vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], get_body_font, v_sz, 30, 225)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
            m_sp = _make_text_sprite(it["meta"], get_body_font, m_sz, 30, 820, 2 if max_per_b <= 2 else 1, pal["muted"], align="lm")
            card_entries.append({"bg": bg_c, "title": t_sp, "badge": b_sp, "meta": m_sp, "h": u_ch, "cy": ys[idx_c]})
        s3_batches.append(card_entries)

    s4_hdr_sp = _make_text_sprite("মূল তথ্য", get_body_font, 62, 46, 700, 1, pal["ink"])
    s4_cards = []
    for kind, lbl, val in [("age", "বয়স", data["age_limit"]), ("salary", "বেতন", data["salary_range"]), ("fee", "আবেদন ফি", data["app_fee"]), ("method", "মাধ্যম", data["apply_method"])]:
        g_bg = _make_minimal_card(460, 445, radius=38, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
        icon_sp = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        idraw = ImageDraw.Draw(icon_sp)
        idraw.ellipse([6, 6, 114, 114], fill=pal["accent_soft"] + (255,))
        _draw_minimal_icon(idraw, 60, 60, kind, pal["accent"] + (255,))
        s4_cards.append({
            "bg": g_bg, "icon": icon_sp,
            "lbl": _make_text_sprite(lbl, get_body_font, 46, 34, 380, 1, pal["muted"]),
            "val": _make_text_sprite(val, get_body_font, 56, 36, 405, 3, pal["ink"])
        })

    s5_hdr_sp = _make_text_sprite("আবেদনের সময়সীমা", get_body_font, 66, 48, 860, 1, pal["ink"])
    s5_card_bg = _make_minimal_card(940, 460, radius=42, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
    s5_lbl1 = _make_text_sprite("শুরু", get_body_font, 44, 34, 300, 1, pal["muted"])
    s5_lbl2 = _make_text_sprite("শেষ তারিখ", get_body_font, 44, 34, 300, 1, pal["accent"])
    s5_d1 = _make_text_sprite(data["start_date"], get_body_font, 62, 38, 370, 2, pal["ink"])
    s5_d2 = _make_text_sprite(data["end_date"], get_body_font, 62, 38, 370, 2, pal["accent"])
    s5_urg_sp = _make_minimal_card(720, 122, radius=61, fill=pal["accent_soft"], border=pal["accent"], border_w=2)
    draw_mixed_text(ImageDraw.Draw(s5_urg_sp), s5_urg_sp.width // 2, s5_urg_sp.height // 2, "সময়মতো আবেদন করুন", get_body_font(48), 48, pal["accent"], anchor="mm")

    s6_title_words = _make_word_sprites("যোগাযোগ (হোয়াটসঅ্যাপ)", get_body_font, 64, 44, 920, 1, pal["ink"], W // 2, 660)
    s6_pill_empty = _make_minimal_card(920, 206, radius=103, fill=pal["accent"])
    s6_num_sp = Image.new("RGBA", (860, 140), (0, 0, 0, 0))
    draw_mixed_text(ImageDraw.Draw(s6_num_sp), 430, 70, data["wa_formatted"], get_english_bold_font(88), 88, (255, 255, 255), anchor="mm")
    s6_pill_mask = Image.new("L", s6_pill_empty.size, 0)
    ImageDraw.Draw(s6_pill_mask).rounded_rectangle([22, 22, 942, 228], radius=103, fill=255)
    sheen_sp = Image.new("RGBA", (220, s6_pill_empty.height), (0, 0, 0, 0))
    ImageDraw.Draw(sheen_sp).polygon([(70, 0), (170, 0), (100, s6_pill_empty.height), (0, s6_pill_empty.height)], fill=(255, 255, 255, 65))
    s6_sub_words = _make_word_sprites("আবেদনের জন্য মেসেজ দিন", get_body_font, 54, 38, 900, 1, pal["muted"], W // 2, 1080)

    bounds = [0.0, 0.14, 0.30, 0.62, 0.78, 0.90, 1.0]
    trans_styles = ["curl", "push_left", "curl", "push_left", "curl"]
    trans_sec = min(0.42, duration * 0.03)
    countup_cache = {}

    def render_scene_frame(scene_id, local_t, abs_t):
        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)
        _draw_clean_sliding_bg_elements(fd, W, H, abs_t, pal["shape"], pal["accent"])

        if scene_id in [2, 3, 4, 5]:
            hdr_y = int(105 + 120 * ease_out_cubic(local_t / 0.38)) if (scene_id == 2 and local_t < 0.38) else 225
            _paste_sprite(frame, hdr_sp, W // 2, hdr_y)
            dot_r = 10 + int(3 * math.sin(abs_t * 5.0))
            fd.ellipse([122 - dot_r, hdr_y - dot_r, 122 + dot_r, hdr_y + dot_r], fill=pal["accent"])

        if scene_id == 1:
            ep = ease_out_back(min(1.0, local_t / 0.42))
            _paste_sprite(frame, emblem_sp, W // 2, 420 + int(8 * math.sin(abs_t * 2.4)), scale=0.25 + 0.75 * ep, opacity=min(1.0, local_t / 0.22))
            for idx_w, (wsp, wx, wy) in enumerate(s1_org_words):
                st = 0.14 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.32, rise_px=54)
            if local_t > 0.30:
                half_l = int(190 * ease_out_cubic((local_t - 0.30) / 0.35))
                fd.rounded_rectangle([W // 2 - half_l, 868, W // 2 + half_l, 875], radius=3, fill=pal["accent"])
            if local_t > 0.42:
                bp = ease_out_back((local_t - 0.42) / 0.38)
                _paste_sprite(frame, s1_badge_sp, W // 2, 995, scale=0.65 + 0.35 * bp, opacity=min(1.0, (local_t - 0.42) / 0.2))
            for idx_h, (wsp, wx, wy) in enumerate(s1_hook_words):
                st = 0.62 + idx_h * 0.07
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.30, rise_px=42)

        elif scene_id == 2:
            _render_masked_rise(frame, s2_lbl_sp, W // 2, 470, local_t / 0.35, rise_px=45)
            cp = ease_out_back(min(1.0, max(0.0, local_t - 0.06) / 0.42))
            _paste_sprite(frame, s2_card_sp, W // 2, 740, scale=0.80 + 0.20 * cp, opacity=min(1.0, local_t / 0.22))
            if data["vac_num"] > 0:
                cnt_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.15) / 1.25))
                cur_val = max(1, int(round(data["vac_num"] * cnt_p)))
                if cur_val not in countup_cache:
                    if len(countup_cache) > 45: countup_cache.clear()
                    countup_cache[cur_val] = _make_text_sprite(to_bn_num(cur_val) + "টি", get_body_font, 195, 76, 840, 1, pal["accent"])
                land_t = local_t - 1.40
                pop_sc = (1.0 + 0.12 * math.sin((land_t / 0.35) * math.pi)) if 0.0 <= land_t <= 0.35 else 1.0
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 740, scale=pop_sc)
            else:
                _paste_sprite(frame, s2_static_num, W // 2, 740, scale=0.75 + 0.25 * cp, opacity=min(1.0, local_t / 0.28))
            if local_t > 0.65:
                tp = ease_out_back((local_t - 0.65) / 0.42)
                _paste_sprite(frame, s2_tag_sp, W // 2, 1085 + int(40 * (1.0 - min(1.0, tp))), scale=0.8 + 0.2 * tp, opacity=min(1.0, (local_t - 0.65) / 0.25))

        elif scene_id == 3:
            _render_masked_rise(frame, s3_hdr_sp, W // 2, 375, local_t / 0.32, rise_px=38)
            hl_w = int(140 * ease_out_cubic(min(1.0, local_t / 0.45)))
            fd.rounded_rectangle([W // 2 - hl_w, 424, W // 2 + hl_w, 430], radius=3, fill=pal["accent"])

            top_band = frame.crop((0, 0, W, 452))
            bot_band = frame.crop((0, 1465, W, H))

            scene_len = (bounds[3] - bounds[2]) * duration
            num_b = len(s3_batches)
            slice_t = scene_len / float(num_b)
            b_idx = min(num_b - 1, int(local_t / slice_t))
            bt = local_t - b_idx * slice_t
            batch_trans = 0.40

            def draw_batch(entries, cur_bt, extra_dy=0, fade_mult=1.0):
                for idx_c, c in enumerate(entries):
                    st = 0.06 + idx_c * 0.20
                    if cur_bt <= st: continue
                    cp = ease_out_back((cur_bt - st) / 0.34)
                    cy = c["cy"] + int(60 * (1.0 - min(1.0, cp))) + extra_dy
                    _paste_sprite(frame, c["bg"], W // 2, cy, scale=0.92 + 0.08 * cp, opacity=min(1.0, (cur_bt - st) / 0.18) * fade_mult)
                    bar_p = ease_out_cubic((cur_bt - (st + 0.04)) / 0.30)
                    if bar_p > 0.02:
                        y_tb = cy - c["h"] // 2 + 24
                        fd.rounded_rectangle([92, y_tb, 106, y_tb + max(8, int((c["h"] - 48) * bar_p))], radius=7, fill=pal["accent"])
                    if cur_bt > st + 0.05:
                        _render_masked_rise(frame, c["title"], 400, cy - int(c["h"] * 0.17), (cur_bt - (st + 0.05)) / 0.26, rise_px=24)
                    if cur_bt > st + 0.10:
                        bp = ease_out_back((cur_bt - (st + 0.10)) / 0.28)
                        _paste_sprite(frame, c["badge"], 842, cy - int(c["h"] * 0.17), scale=0.55 + 0.45 * bp, opacity=fade_mult)
                    if cur_bt > st + 0.15:
                        _render_masked_rise(frame, c["meta"], 542, cy + int(c["h"] * 0.24), (cur_bt - (st + 0.15)) / 0.26, rise_px=20)

            if b_idx > 0 and bt < batch_trans:
                tp = ease_in_out_cubic(bt / batch_trans)
                draw_batch(s3_batches[b_idx - 1], slice_t, extra_dy=-int(960 * tp), fade_mult=1.0 - tp)
                draw_batch(s3_batches[b_idx], bt, extra_dy=int(960 * (1.0 - tp)), fade_mult=tp)
            else:
                draw_batch(s3_batches[b_idx], bt)

            frame.paste(top_band, (0, 0))
            frame.paste(bot_band, (0, 1465))

        elif scene_id == 4:
            _render_masked_rise(frame, s4_hdr_sp, W // 2, 375, local_t / 0.32, rise_px=38)
            hl_w = int(120 * ease_out_cubic(min(1.0, local_t / 0.45)))
            fd.rounded_rectangle([W // 2 - hl_w, 424, W // 2 + hl_w, 430], radius=3, fill=pal["accent"])
            positions = [(295, 705), (785, 705), (295, 1185), (785, 1185)]
            active_idx = int(abs_t * 1.1) % 4
            for idx, item in enumerate(s4_cards):
                st = 0.08 + idx * 0.16
                if local_t <= st: continue
                gx, gy = positions[idx]
                cp = ease_out_back((local_t - st) / 0.34)
                act_sc = 1.025 if (local_t > 1.2 and idx == active_idx) else 1.0
                _paste_sprite(frame, item["bg"], gx, gy, scale=(0.78 + 0.22 * cp) * act_sc, opacity=min(1.0, (local_t - st) / 0.18))
                if local_t > st + 0.06:
                    ip = ease_out_back((local_t - (st + 0.06)) / 0.30)
                    _paste_sprite(frame, item["icon"], gx, gy - 115 + int(4 * math.sin(abs_t * 2.5 + idx)), scale=0.45 + 0.55 * ip)
                if local_t > st + 0.12:
                    _render_masked_rise(frame, item["lbl"], gx, gy - 8, (local_t - (st + 0.12)) / 0.24, rise_px=20)
                if local_t > st + 0.18:
                    vp = ease_out_back((local_t - (st + 0.18)) / 0.30)
                    _paste_sprite(frame, item["val"], gx, gy + 95, scale=0.72 + 0.28 * vp, opacity=min(1.0, (local_t - (st + 0.18)) / 0.18))

        elif scene_id == 5:
            _render_masked_rise(frame, s5_hdr_sp, W // 2, 425, local_t / 0.32, rise_px=42)
            hl_w = int(190 * ease_out_cubic(min(1.0, local_t / 0.45)))
            fd.rounded_rectangle([W // 2 - hl_w, 480, W // 2 + hl_w, 486], radius=3, fill=pal["accent"])
            cp = ease_out_back(min(1.0, max(0.0, local_t - 0.08) / 0.40))
            _paste_sprite(frame, s5_card_bg, W // 2, 775, scale=0.82 + 0.18 * cp, opacity=min(1.0, local_t / 0.24))
            if local_t > 0.18:
                _render_masked_rise(frame, s5_lbl1, 255, 650, (local_t - 0.18) / 0.28, rise_px=24)
                _render_masked_rise(frame, s5_d1, 255, 815, (local_t - 0.25) / 0.32, rise_px=38)
            if local_t > 0.32:
                _render_masked_rise(frame, s5_lbl2, 825, 650, (local_t - 0.32) / 0.28, rise_px=24)
                dp2 = ease_out_back((local_t - 0.38) / 0.36)
                _paste_sprite(frame, s5_d2, 825, 815, scale=0.75 + 0.25 * dp2)
            if local_t > 0.26:
                phase = (abs_t * 2.6) % 1.0
                for ci, cx_off in enumerate([-36, 0, 36]):
                    col_c = pal["accent"] if abs(((phase * 3.0) - ci) % 3.0) < 0.8 else pal["hairline"]
                    cx_a, cy_a = W // 2 + cx_off, 805
                    fd.line([(cx_a - 14, cy_a - 24), (cx_a + 12, cy_a), (cx_a - 14, cy_a + 24)], fill=col_c, width=8)
            if local_t > 0.52:
                up = ease_out_back((local_t - 0.52) / 0.38)
                _paste_sprite(frame, s5_urg_sp, W // 2, 1145, scale=(0.8 + 0.2 * up) * (1.0 + 0.025 * math.sin(abs_t * 4.2)), opacity=min(1.0, (local_t - 0.52) / 0.25))

        elif scene_id == 6:
            wp = ease_out_back(min(1.0, local_t / 0.42))
            _paste_sprite(frame, wa_sp, W // 2, 435 + int(8 * math.sin(abs_t * 2.8)), scale=0.25 + 0.75 * wp, opacity=min(1.0, local_t / 0.22))
            for idx_w, (wsp, wx, wy) in enumerate(s6_title_words):
                st = 0.16 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.28, rise_px=38)
            if local_t > 0.32:
                pp = ease_out_back((local_t - 0.32) / 0.40)
                pill_sc = s6_pill_empty.resize((max(40, int(s6_pill_empty.width * max(0.15, min(1.0, pp)))), s6_pill_empty.height), Image.BILINEAR)
                _paste_sprite(frame, pill_sc, W // 2, 855, opacity=min(1.0, (local_t - 0.32) / 0.18))
            if local_t > 0.48:
                np = ease_out_cubic((local_t - 0.48) / 0.36)
                num_crop = s6_num_sp.crop((0, 0, max(12, int(s6_num_sp.width * np)), s6_num_sp.height))
                frame.paste(num_crop, ((W - s6_num_sp.width) // 2, 855 - s6_num_sp.height // 2), num_crop.getchannel("A"))
                if np >= 0.99:
                    cs = (local_t - 0.84) % 2.1
                    if 0.0 <= cs <= 0.75:
                        tmp_sh = Image.new("RGBA", s6_pill_empty.size, (0, 0, 0, 0))
                        tmp_sh.paste(sheen_sp, (int(-200 + (s6_pill_empty.width + 200) * (cs / 0.75)), 0))
                        masked_sh = Image.new("RGBA", s6_pill_empty.size, (0, 0, 0, 0))
                        masked_sh.paste(tmp_sh, (0, 0), s6_pill_mask)
                        _paste_sprite(frame, masked_sh, W // 2, 855)
            for idx_s, (wsp, wx, wy) in enumerate(s6_sub_words):
                st = 0.66 + idx_s * 0.06
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.24, rise_px=24)

        prog_ratio = max(0.0, min(1.0, abs_t / duration))
        fd.rounded_rectangle([140, 1506, 940, 1516], radius=5, fill=pal["hairline"])
        fill_x = max(150, 140 + int(800 * prog_ratio))
        fd.rounded_rectangle([140, 1506, fill_x, 1516], radius=5, fill=pal["accent"])
        fd.ellipse([fill_x - 9, 1502, fill_x + 9, 1520], fill=pal["accent"])
        return frame

    total_frames = max(int(math.ceil(duration * fps)), fps * 5)
    def get_frame(f_idx):
        abs_t = f_idx / float(fps)
        u = min(0.9999, abs_t / duration)
        s_idx = 6
        for i in range(6):
            if bounds[i] <= u < bounds[i + 1]:
                s_idx = i + 1
                break
        s_start_t, s_end_t = bounds[s_idx - 1] * duration, bounds[s_idx] * duration
        frame_cur = render_scene_frame(s_idx, abs_t - s_start_t, abs_t)
        if s_idx < 6 and (s_end_t - abs_t) < trans_sec:
            tp = 1.0 - (s_end_t - abs_t) / trans_sec
            return _apply_transition(frame_cur, render_scene_frame(s_idx + 1, 0.35, abs_t), tp, trans_styles[s_idx - 1], curl_sp)
        return frame_cur

    return _stream_frames_to_ffmpeg(total_frames, fps, W, H, audio_path, output_path, get_frame)