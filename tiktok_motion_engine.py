# -*- coding: utf-8 -*-
import os
import math
import random
import subprocess
from PIL import Image, ImageDraw, ImageFilter

from tiktok_designer import (
    find_whatsapp_logo, get_header_font, get_body_font, get_english_bold_font,
    measure_mixed_text, draw_mixed_text, fit_single_line_font, fit_multiline_font
)
from motion_storyboard import build_dynamic_storyboard, to_bn_num

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

def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3

def ease_in_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1.0 - ((-2 * t + 2) ** 3) / 2.0

def ease_out_back(t, s=1.55):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * ((t - 1.0) ** 3) + s * ((t - 1.0) ** 2)

def compute_motion_scene_bounds(duration):
    s1_t = min(7.0, duration * 0.14)
    s2_t = min(8.5, duration * 0.16)
    s5_t = min(10.5, duration * 0.13)
    s6_t = max(4.5, min(9.5, duration * 0.11))
    mid_t = max(2.0, duration - (s1_t + s2_t + s5_t + s6_t))
    s3_t, s4_t = mid_t * 0.56, mid_t * 0.44
    return [0.0, s1_t / duration, (s1_t + s2_t) / duration, (s1_t + s2_t + s3_t) / duration, (s1_t + s2_t + s3_t + s4_t) / duration, min(0.96, (duration - s6_t) / duration), 1.0]

def split_posts_uniformly(posts):
    items = list(posts[:20])
    if not items:
        return [[{"post_name": "বিভিন্ন পদ", "vacancy": "নিয়োগ", "meta": "বিজ্ঞপ্তি অনুযায়ী"}]]
    return [items[i:i + 2] for i in range(0, len(items), 2)]

def uniform_batch_y_positions(batch_len, max_per_b=None):
    return [840] if batch_len <= 1 else [705, 1055][:batch_len]

def _paste_sprite(canvas, sp, cx, cy, scale=1.0, opacity=1.0):
    if opacity <= 0.02 or scale <= 0.02 or sp is None:
        return
    if abs(scale - 1.0) > 0.015:
        sp = sp.resize((max(2, int(round(sp.width * scale))), max(2, int(round(sp.height * scale)))), Image.BILINEAR)
    alpha = sp.getchannel("A")
    if opacity < 0.99:
        alpha = alpha.point([int(i * opacity) for i in range(256)])
    canvas.paste(sp, (int(round(cx - sp.width / 2)), int(round(cy - sp.height / 2))), alpha)

def _render_masked_rise(canvas, sp, cx, cy, prog, rise_px=38):
    p = ease_out_cubic(prog)
    if p <= 0.02 or sp is None:
        return
    dy = int(round(rise_px * (1.0 - p)))
    op = min(1.0, p * 1.35)
    _paste_sprite(canvas, sp, cx, cy + dy, opacity=op)

def _make_minimal_card(w, h, radius=36, fill=(255, 255, 255), border=None, border_w=2, pad=22, shadow_alpha=24):
    cw, ch = w + pad * 2, h + pad * 2
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    if shadow_alpha > 0:
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 5, pad + w, pad + h + 5], radius=radius, fill=(15, 23, 42, shadow_alpha + 14))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill + (255,), outline=(border + (255,)) if border else None, width=border_w)
    return sh

def _make_text_sprite(text, font_fn, start_sz, min_sz, max_w, max_lines, color, align="mm"):
    tmp = Image.new("RGBA", (max_w + 40, 480), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    f, sz, lines = fit_multiline_font(td, text, font_fn, start_sz, min_sz, max_w, max_lines)
    lh = sz + 16
    h = max(sz + 44, len(lines) * lh + 34)
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
            pad_w, pad_h = ww + 28, sz + 40
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
    elif kind == "qual":
        d.polygon([(cx, cy - 26), (cx + 34, cy - 8), (cx, cy + 10), (cx - 34, cy - 8)], outline=col, width=6)
        d.line([(cx - 18, cy + 4), (cx - 18, cy + 22), (cx + 18, cy + 22), (cx + 18, cy + 4)], fill=col, width=6)
    elif kind == "exam":
        d.rounded_rectangle([cx - 26, cy - 28, cx + 26, cy + 28], radius=8, outline=col, width=6)
        d.line([(cx - 12, cy + 2), (cx - 2, cy + 14), (cx + 16, cy - 10)], fill=col, width=6)
    elif kind == "info":
        d.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], outline=col, width=6)
        d.line([(cx, cy - 14), (cx, cy + 6)], fill=col, width=7)
        d.ellipse([cx - 4, cy + 12, cx + 4, cy + 20], fill=col)
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

def _extract_minimal_data(job_data):
    from motion_storyboard import extract_motion_core
    return extract_motion_core(job_data)

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

def _make_icon_badge(kind, pal, size=118):
    sp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.ellipse([4, 4, size - 4, size - 4], fill=pal["accent_soft"] + (255,), outline=pal["accent"] + (180,), width=3)
    _draw_minimal_icon(d, size // 2, size // 2, kind, pal["accent"] + (255,))
    return sp

def _draw_box_text(box_w, box_h, text, font_fn, start_sz, min_sz, color, fill, border, max_lines=2, pad=10, radius=28):
    sp = _make_minimal_card(box_w, box_h, radius=radius, fill=fill, border=border, border_w=2, pad=pad, shadow_alpha=0)
    d = ImageDraw.Draw(sp)
    f, sz, lines = fit_multiline_font(d, text, font_fn, start_sz, min_sz, box_w - 44, max_lines)
    lh = sz + 10
    y = sp.height // 2 - ((len(lines) - 1) * lh) // 2
    for l in lines:
        draw_mixed_text(d, sp.width // 2, y, l, f, sz, color, anchor="mm")
        y += lh
    return sp

def render_motion_graphics_video(job_data, audio_path, output_path, fps=24, script_index=0):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    pal = random.choice(MINIMAL_PALETTES)
    sb = build_dynamic_storyboard(job_data, audio_path, duration, script_index=script_index)
    core, beats = sb["core"], sb["beats"]

    print(f"  [✨ Motion Style #1 (Minimal Light)] Palette={pal['name']}, Beats={len(beats)}, Duration={duration:.1f}s")

    bg_base = Image.new("RGB", (W, H), pal["bg"])
    curl_sp = _make_curl_sprite(H)
    emblem_sp = _make_minimal_emblem(pal)
    wa_sp = _make_whatsapp_sprite()

    hdr_sp = _make_minimal_card(920, 124, radius=32, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
    hd = ImageDraw.Draw(hdr_sp)
    hf, hsz = fit_single_line_font(hd, core["org"], get_body_font, 48, 30, 610)
    draw_mixed_text(hd, 86, 84, core["org"], hf, hsz, pal["ink"], anchor="lm")
    hd.rounded_rectangle([714, 48, 916, 120], radius=24, fill=pal["accent_soft"] + (255,))
    draw_mixed_text(hd, 815, 84, "বিজ্ঞপ্তি", get_body_font(34), 34, pal["accent"], anchor="mm")

    beat_assets = []
    bn_step_nums = ["০১", "০২", "০৩", "০৪"]
    countup_cache = {}

    for bt in beats:
        k = bt["kind"]
        a = {"kind": k, "hdr_sp": _make_text_sprite(bt.get("header", ""), get_body_font, 62, 42, 840, 1, pal["ink"])}
        if k == "intro":
            a["org_words"] = _make_word_sprites(core["org"], get_header_font, 88, 52, 940, 2, pal["ink"], W // 2, 700)
            b_sp = _make_minimal_card(620, 134, radius=67, fill=pal["accent"])
            bf, bsz = fit_single_line_font(ImageDraw.Draw(b_sp), core["cat_badge"], get_body_font, 60, 40, 540)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, core["cat_badge"], bf, bsz, (255, 255, 255), anchor="mm")
            a["badge_sp"] = b_sp
            a["hook_words"] = _make_word_sprites(core["hook_short"], get_body_font, 56, 36, 900, 2, pal["muted"], W // 2, 1170)

        elif k == "vacancy":
            a["card_sp"] = _make_minimal_card(900, 380, radius=44, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
            a["static_num"] = _make_text_sprite(bt["value"], get_body_font, 190, 74, 820, 1, pal["accent"])
            tag_sp = _make_minimal_card(880, 138, radius=69, fill=pal["accent_soft"], border=pal["accent"], border_w=2)
            tf2, tsz2, tl2 = fit_multiline_font(ImageDraw.Draw(tag_sp), bt["tag"], get_body_font, 48, 32, 800, 2)
            ty2 = tag_sp.height // 2 - ((len(tl2) - 1) * (tsz2 + 10)) // 2
            for l2 in tl2:
                draw_mixed_text(ImageDraw.Draw(tag_sp), tag_sp.width // 2, ty2, l2, tf2, tsz2, pal["accent"], anchor="mm")
                ty2 += tsz2 + 10
            a["tag_sp"] = tag_sp
            a["chips"] = [_draw_box_text(880, 126, txt, get_body_font, 40, 26, pal["muted"], (255, 255, 255), pal["hairline"], max_lines=2, pad=22) for txt in bt.get("sub_chips", [])[:1]]

        elif k == "post_spotlight":
            it = bt["post"]
            a["card_bg"] = _make_minimal_card(930, 610, radius=42, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
            a["title_sp"] = _make_text_sprite(it["post_name"], get_body_font, 54, 28, 830, 3, pal["ink"])
            b_sp = _make_minimal_card(320, 118, radius=59, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=12, shadow_alpha=0)
            vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], get_body_font, 58, 32, 275)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
            a["vac_sp"] = b_sp
            a["qual_sp"] = _draw_box_text(840, 118, f"যোগ্যতা: {it['qualification']}", get_body_font, 40, 26, pal["ink"], pal["bg"], pal["hairline"], max_lines=2)
            a["grade_sp"] = _draw_box_text(840, 118, f"গ্রেড/বেতন: {it['salary_grade']}", get_body_font, 40, 26, pal["muted"], pal["bg"], pal["hairline"], max_lines=2)

        elif k == "post_pair":
            cards = []
            for idx_p, it in enumerate(bt["posts"]):
                cy = 670 if len(bt["posts"]) == 1 else ([660, 1020][idx_p])
                bg_c = _make_minimal_card(940, 300, radius=34, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
                t_sp = _make_text_sprite(it["post_name"], get_body_font, 50, 28, 535, 2, pal["ink"], align="lm")
                b_sp = _make_minimal_card(255, 108, radius=26, fill=pal["accent_soft"], pad=12, shadow_alpha=0)
                vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], get_body_font, 54, 28, 225)
                draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
                m_sp = _make_text_sprite(it["meta"], get_body_font, 40, 26, 820, 2, pal["muted"], align="lm")
                cards.append({"bg": bg_c, "title": t_sp, "badge": b_sp, "meta": m_sp, "cy": cy, "h": 300})
            a["cards"] = cards

        elif k in ("focus_card", "steps", "highlight"):
            a["hero_bg"] = _make_minimal_card(920, 270, radius=38, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
            a["icon_sp"] = _make_icon_badge(bt.get("icon", "info"), pal, size=124)
            a["lbl_sp"] = _make_text_sprite(bt.get("main_label", ""), get_body_font, 40, 28, 680, 1, pal["muted"], align="lm")
            a["val_sp"] = _make_text_sprite(bt.get("main_val", ""), get_body_font, 52, 30, 690, 2, pal["accent"] if k == "focus_card" else pal["ink"], align="lm")
            chip_entries = []
            for idx_c, ch_txt in enumerate(bt.get("sub_chips", [])[:3]):
                c_bg = _make_minimal_card(920, 142, radius=30, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
                num_bg = _make_minimal_card(74, 74, radius=20, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=8, shadow_alpha=0)
                draw_mixed_text(ImageDraw.Draw(num_bg), num_bg.width // 2, num_bg.height // 2, bn_step_nums[idx_c % 4], get_body_font(34), 34, pal["accent"], anchor="mm")
                t_sp = _make_text_sprite(ch_txt, get_body_font, 40, 26, 735, 2, pal["ink"], align="lm")
                chip_entries.append({"bg": c_bg, "num": num_bg, "txt": t_sp})
            a["chips"] = chip_entries

        elif k == "deadline":
            a["card_bg"] = _make_minimal_card(940, 440, radius=42, fill=(255, 255, 255), border=pal["hairline"], border_w=2)
            a["lbl1"] = _make_text_sprite("শুরু", get_body_font, 44, 32, 300, 1, pal["muted"])
            a["lbl2"] = _make_text_sprite("শেষ তারিখ", get_body_font, 44, 32, 300, 1, pal["accent"])
            a["d1"] = _make_text_sprite(bt["start_date"], get_body_font, 58, 34, 370, 2, pal["ink"])
            a["d2"] = _make_text_sprite(bt["end_date"], get_body_font, 58, 34, 370, 2, pal["accent"])
            a["urg_sp"] = _make_minimal_card(740, 120, radius=60, fill=pal["accent_soft"], border=pal["accent"], border_w=2)
            draw_mixed_text(ImageDraw.Draw(a["urg_sp"]), a["urg_sp"].width // 2, a["urg_sp"].height // 2, "সময়মতো আবেদন করুন", get_body_font(46), 46, pal["accent"], anchor="mm")

        elif k == "overview_grid":
            g_cards = []
            for kind_i, lbl_i, val_i in bt["items"]:
                g_cards.append({
                    "bg": _make_minimal_card(460, 440, radius=38, fill=(255, 255, 255), border=pal["hairline"], border_w=2),
                    "icon": _make_icon_badge(kind_i, pal, size=116),
                    "lbl": _make_text_sprite(lbl_i, get_body_font, 44, 32, 380, 1, pal["muted"]),
                    "val": _make_text_sprite(val_i, get_body_font, 54, 34, 405, 3, pal["ink"])
                })
            a["g_cards"] = g_cards

        elif k == "cta":
            a["title_words"] = _make_word_sprites("যোগাযোগ (হোয়াটসঅ্যাপ)", get_body_font, 64, 44, 920, 1, pal["ink"], W // 2, 660)
            a["pill_bg"] = _make_minimal_card(920, 206, radius=103, fill=pal["accent"])
            a["num_sp"] = Image.new("RGBA", (860, 140), (0, 0, 0, 0))
            draw_mixed_text(ImageDraw.Draw(a["num_sp"]), 430, 70, bt["wa_formatted"], get_english_bold_font(88), 88, (255, 255, 255), anchor="mm")
            a["pill_mask"] = Image.new("L", a["pill_bg"].size, 0)
            ImageDraw.Draw(a["pill_mask"]).rounded_rectangle([22, 22, 942, 228], radius=103, fill=255)
            a["sheen_sp"] = Image.new("RGBA", (220, a["pill_bg"].height), (0, 0, 0, 0))
            ImageDraw.Draw(a["sheen_sp"]).polygon([(70, 0), (170, 0), (100, a["pill_bg"].height), (0, a["pill_bg"].height)], fill=(255, 255, 255, 65))
            a["sub_words"] = _make_word_sprites("আবেদনের জন্য মেসেজ দিন", get_body_font, 54, 38, 900, 1, pal["muted"], W // 2, 1080)

        beat_assets.append(a)

    trans_styles = ["curl", "push_left"]
    trans_sec = 0.34

    def render_beat_frame(b_idx, local_t, abs_t):
        bt = beats[b_idx]
        a = beat_assets[b_idx]
        k = bt["kind"]

        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)
        _draw_clean_sliding_bg_elements(fd, W, H, abs_t, pal["shape"], pal["accent"])

        if k not in ("intro", "cta"):
            hdr_y = int(105 + 120 * ease_out_cubic(local_t / 0.35)) if (b_idx == 1 and local_t < 0.35) else 225
            _paste_sprite(frame, hdr_sp, W // 2, hdr_y)
            dot_r = 10 + int(3 * math.sin(abs_t * 5.0))
            fd.ellipse([122 - dot_r, hdr_y - dot_r, 122 + dot_r, hdr_y + dot_r], fill=pal["accent"])

            _render_masked_rise(frame, a["hdr_sp"], W // 2, 365, local_t / 0.28, rise_px=34)
            hl_w = int(150 * ease_out_cubic(min(1.0, local_t / 0.40)))
            fd.rounded_rectangle([W // 2 - hl_w, 412, W // 2 + hl_w, 418], radius=3, fill=pal["accent"])

        if k == "intro":
            ep = ease_out_back(min(1.0, local_t / 0.40))
            _paste_sprite(frame, emblem_sp, W // 2, 420 + int(8 * math.sin(abs_t * 2.4)), scale=0.25 + 0.75 * ep, opacity=min(1.0, local_t / 0.20))
            for idx_w, (wsp, wx, wy) in enumerate(a["org_words"]):
                st = 0.12 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.30, rise_px=42)
            if local_t > 0.28:
                hl = int(190 * ease_out_cubic((local_t - 0.28) / 0.32))
                fd.rounded_rectangle([W // 2 - hl, 868, W // 2 + hl, 875], radius=3, fill=pal["accent"])
            if local_t > 0.40:
                bp = ease_out_back((local_t - 0.40) / 0.35)
                _paste_sprite(frame, a["badge_sp"], W // 2, 995, scale=0.65 + 0.35 * bp, opacity=min(1.0, (local_t - 0.40) / 0.18))
            for idx_h, (wsp, wx, wy) in enumerate(a["hook_words"]):
                st = 0.58 + idx_h * 0.07
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.28, rise_px=34)

        elif k == "vacancy":
            cp = ease_out_back(min(1.0, local_t / 0.38))
            _paste_sprite(frame, a["card_sp"], W // 2, 660, scale=0.80 + 0.20 * cp, opacity=min(1.0, local_t / 0.20))
            if bt["num"] > 0:
                cnt_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.12) / 1.15))
                cur_val = max(1, int(round(bt["num"] * cnt_p)))
                if cur_val not in countup_cache:
                    if len(countup_cache) > 45: countup_cache.clear()
                    countup_cache[cur_val] = _make_text_sprite(to_bn_num(cur_val) + "টি", get_body_font, 190, 74, 820, 1, pal["accent"])
                land_t = local_t - 1.27
                pop_sc = (1.0 + 0.12 * math.sin((land_t / 0.35) * math.pi)) if 0.0 <= land_t <= 0.35 else 1.0
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 660, scale=pop_sc)
            else:
                _paste_sprite(frame, a["static_num"], W // 2, 660, scale=0.75 + 0.25 * cp, opacity=min(1.0, local_t / 0.25))
            if local_t > 0.65:
                tp = ease_out_back((local_t - 0.65) / 0.38)
                _paste_sprite(frame, a["tag_sp"], W // 2, 975 + int(35 * (1.0 - min(1.0, tp))), scale=0.82 + 0.18 * tp, opacity=min(1.0, (local_t - 0.65) / 0.20))
            if a["chips"] and local_t > 1.35:
                chp = ease_out_back((local_t - 1.35) / 0.36)
                _paste_sprite(frame, a["chips"][0], W // 2, 1185 + int(28 * (1.0 - min(1.0, chp))), scale=0.88 + 0.12 * chp, opacity=min(1.0, (local_t - 1.35) / 0.20))

        elif k == "post_spotlight":
            cp = ease_out_back(min(1.0, local_t / 0.35))
            _paste_sprite(frame, a["card_bg"], W // 2, 855, scale=0.88 + 0.12 * cp, opacity=min(1.0, local_t / 0.20))
            bar_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.12) / 0.38))
            if bar_p > 0.02:
                fd.rounded_rectangle([96, 595, 112, 595 + max(12, int(515 * bar_p))], radius=8, fill=pal["accent"])
            if local_t > 0.18:
                _render_masked_rise(frame, a["title_sp"], W // 2, 650, (local_t - 0.18) / 0.30, rise_px=30)
            if local_t > 0.65:
                vp = ease_out_back((local_t - 0.65) / 0.34)
                pulse = 1.0 + (0.025 * math.sin(abs_t * 4.5) if local_t > 1.4 else 0.0)
                _paste_sprite(frame, a["vac_sp"], W // 2, 815, scale=(0.65 + 0.35 * vp) * pulse, opacity=min(1.0, (local_t - 0.65) / 0.18))
            if local_t > 1.15:
                qp = ease_out_cubic((local_t - 1.15) / 0.32)
                _paste_sprite(frame, a["qual_sp"], W // 2 + int(80 * (1.0 - qp)), 958, opacity=qp)
            if local_t > 1.75:
                gp = ease_out_cubic((local_t - 1.75) / 0.32)
                _paste_sprite(frame, a["grade_sp"], W // 2 - int(80 * (1.0 - gp)), 1092, opacity=gp)

        elif k == "post_pair":
            active_c = int(local_t / 1.4) % max(1, len(a["cards"]))
            for idx_c, c in enumerate(a["cards"]):
                st = 0.05 + idx_c * 0.75
                if local_t <= st: continue
                cp = ease_out_back((local_t - st) / 0.34)
                act_sc = 1.02 if (local_t > 1.6 and idx_c == active_c) else 1.0
                cy = c["cy"] + int(45 * (1.0 - min(1.0, cp)))
                _paste_sprite(frame, c["bg"], W // 2, cy, scale=(0.90 + 0.10 * cp) * act_sc, opacity=min(1.0, (local_t - st) / 0.18))
                bar_p = ease_out_cubic((local_t - (st + 0.06)) / 0.30)
                if bar_p > 0.02:
                    y_tb = cy - c["h"] // 2 + 24
                    fd.rounded_rectangle([92, y_tb, 106, y_tb + max(8, int((c["h"] - 48) * bar_p))], radius=7, fill=pal["accent"])
                if local_t > st + 0.12:
                    _render_masked_rise(frame, c["title"], 400, cy - 45, (local_t - (st + 0.12)) / 0.28, rise_px=24)
                if local_t > st + 0.28:
                    bp = ease_out_back((local_t - (st + 0.28)) / 0.28)
                    _paste_sprite(frame, c["badge"], 842, cy - 45, scale=0.6 + 0.4 * bp)
                if local_t > st + 0.44:
                    _render_masked_rise(frame, c["meta"], 542, cy + 68, (local_t - (st + 0.44)) / 0.28, rise_px=20)

        elif k in ("focus_card", "steps", "highlight"):
            cp = ease_out_back(min(1.0, local_t / 0.36))
            _paste_sprite(frame, a["hero_bg"], W // 2, 610, scale=0.88 + 0.12 * cp, opacity=min(1.0, local_t / 0.20))
            if local_t > 0.08:
                ip = ease_out_back((local_t - 0.08) / 0.32)
                _paste_sprite(frame, a["icon_sp"], 178, 610 + int(5 * math.sin(abs_t * 3.0)), scale=0.5 + 0.5 * ip)
            if local_t > 0.18:
                _render_masked_rise(frame, a["lbl_sp"], 625, 545, (local_t - 0.18) / 0.26, rise_px=22)
            if local_t > 0.32:
                _render_masked_rise(frame, a["val_sp"], 625, 640, (local_t - 0.32) / 0.32, rise_px=28)

            n_ch = len(a["chips"])
            active_chip = int(max(0, local_t - 1.8) / 1.1) % max(1, n_ch)
            for idx_c, ch in enumerate(a["chips"]):
                st = 0.72 + idx_c * 0.75
                if local_t <= st: continue
                cy = 880 + idx_c * 170
                chp = ease_out_cubic((local_t - st) / 0.32)
                dx = int(120 * (1.0 - chp)) * (-1 if idx_c % 2 == 0 else 1)
                act_sc = 1.022 if (local_t > 2.2 and idx_c == active_chip) else 1.0
                _paste_sprite(frame, ch["bg"], W // 2 + dx, cy, scale=act_sc, opacity=chp)
                _paste_sprite(frame, ch["num"], 158 + dx, cy, scale=0.65 + 0.35 * ease_out_back((local_t - st) / 0.30), opacity=chp)
                if local_t > st + 0.14:
                    _render_masked_rise(frame, ch["txt"], 605 + dx, cy, (local_t - (st + 0.14)) / 0.26, rise_px=20)

        elif k == "deadline":
            cp = ease_out_back(min(1.0, local_t / 0.38))
            _paste_sprite(frame, a["card_bg"], W // 2, 725, scale=0.84 + 0.16 * cp, opacity=min(1.0, local_t / 0.22))
            if local_t > 0.18:
                _render_masked_rise(frame, a["lbl1"], 255, 605, (local_t - 0.18) / 0.26, rise_px=24)
                _render_masked_rise(frame, a["d1"], 255, 765, (local_t - 0.32) / 0.30, rise_px=34)
            if local_t > 0.50:
                _render_masked_rise(frame, a["lbl2"], 825, 605, (local_t - 0.50) / 0.26, rise_px=24)
                dp2 = ease_out_back((local_t - 0.65) / 0.34)
                _paste_sprite(frame, a["d2"], 825, 765, scale=0.75 + 0.25 * dp2)
            if local_t > 0.40:
                phase = (abs_t * 2.8) % 1.0
                for ci, cx_off in enumerate([-36, 0, 36]):
                    col_c = pal["accent"] if abs(((phase * 3.0) - ci) % 3.0) < 0.85 else pal["hairline"]
                    cx_a, cy_a = W // 2 + cx_off, 755
                    fd.line([(cx_a - 14, cy_a - 24), (cx_a + 12, cy_a), (cx_a - 14, cy_a + 24)], fill=col_c, width=8)
            if local_t > 1.10:
                up = ease_out_back((local_t - 1.10) / 0.38)
                _paste_sprite(frame, a["urg_sp"], W // 2, 1085, scale=(0.82 + 0.18 * up) * (1.0 + 0.025 * math.sin(abs_t * 4.5)), opacity=min(1.0, (local_t - 1.10) / 0.22))

        elif k == "overview_grid":
            positions = [(295, 705), (785, 705), (295, 1185), (785, 1185)]
            active_idx = int(abs_t * 0.9) % 4
            for idx, item in enumerate(a["g_cards"]):
                st = 0.08 + idx * 0.25
                if local_t <= st: continue
                gx, gy = positions[idx]
                cp = ease_out_back((local_t - st) / 0.34)
                act_sc = 1.028 if (local_t > 1.2 and idx == active_idx) else 1.0
                _paste_sprite(frame, item["bg"], gx, gy, scale=(0.78 + 0.22 * cp) * act_sc, opacity=min(1.0, (local_t - st) / 0.18))
                if local_t > st + 0.08:
                    _paste_sprite(frame, item["icon"], gx, gy - 115 + int(4 * math.sin(abs_t * 2.5 + idx)), scale=0.5 + 0.5 * ease_out_back((local_t - (st + 0.08)) / 0.30))
                if local_t > st + 0.16:
                    _render_masked_rise(frame, item["lbl"], gx, gy - 8, (local_t - (st + 0.16)) / 0.24, rise_px=20)
                if local_t > st + 0.24:
                    _paste_sprite(frame, item["val"], gx, gy + 95, scale=0.72 + 0.28 * ease_out_back((local_t - (st + 0.24)) / 0.30))

        elif k == "cta":
            wp = ease_out_back(min(1.0, local_t / 0.40))
            _paste_sprite(frame, wa_sp, W // 2, 435 + int(8 * math.sin(abs_t * 2.8)), scale=0.25 + 0.75 * wp, opacity=min(1.0, local_t / 0.22))
            for idx_w, (wsp, wx, wy) in enumerate(a["title_words"]):
                st = 0.14 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.26, rise_px=30)
            if local_t > 0.30:
                pp = ease_out_back((local_t - 0.30) / 0.38)
                pill_sc = a["pill_bg"].resize((max(40, int(a["pill_bg"].width * max(0.15, min(1.0, pp)))), a["pill_bg"].height), Image.BILINEAR)
                _paste_sprite(frame, pill_sc, W // 2, 855, opacity=min(1.0, (local_t - 0.30) / 0.18))
            if local_t > 0.46:
                np = ease_out_cubic((local_t - 0.46) / 0.34)
                num_crop = a["num_sp"].crop((0, 0, max(12, int(a["num_sp"].width * np)), a["num_sp"].height))
                frame.paste(num_crop, ((W - a["num_sp"].width) // 2, 855 - a["num_sp"].height // 2), num_crop.getchannel("A"))
                if np >= 0.99:
                    cs = (local_t - 0.80) % 2.0
                    if 0.0 <= cs <= 0.75:
                        tmp_sh = Image.new("RGBA", a["pill_bg"].size, (0, 0, 0, 0))
                        tmp_sh.paste(a["sheen_sp"], (int(-200 + (a["pill_bg"].width + 200) * (cs / 0.75)), 0))
                        masked_sh = Image.new("RGBA", a["pill_bg"].size, (0, 0, 0, 0))
                        masked_sh.paste(tmp_sh, (0, 0), a["pill_mask"])
                        _paste_sprite(frame, masked_sh, W // 2, 855)
            for idx_s, (wsp, wx, wy) in enumerate(a["sub_words"]):
                st = 0.65 + idx_s * 0.06
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
        b_idx = len(beats) - 1
        for i, bt in enumerate(beats):
            if bt["start"] <= abs_t < bt["end"]:
                b_idx = i
                break
        local_t = max(0.0, abs_t - beats[b_idx]["start"])
        if b_idx > 0 and local_t < trans_sec:
            prev_bt = beats[b_idx - 1]
            frame_prev = render_beat_frame(b_idx - 1, max(0.0, prev_bt["end"] - prev_bt["start"]), abs_t)
            frame_settled = render_beat_frame(b_idx, max(local_t, 0.38), abs_t)
            return _apply_transition(frame_prev, frame_settled, local_t / trans_sec, trans_styles[(b_idx - 1) % 2], curl_sp)
        return render_beat_frame(b_idx, local_t, abs_t)

    return _stream_frames_to_ffmpeg(total_frames, fps, W, H, audio_path, output_path, get_frame)
