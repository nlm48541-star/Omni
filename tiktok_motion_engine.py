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

THEMES = [
    {
        "name": "EmeraldGold",
        "bg_top": (247, 250, 248), "bg_bot": (231, 240, 234),
        "primary": (6, 95, 70), "primary_dark": (6, 78, 59),
        "accent": (185, 28, 28), "gold": (212, 160, 23),
        "gold_light": (245, 196, 65), "soft_tint": (236, 253, 245),
        "line_gold": (212, 190, 130), "text_dark": (17, 24, 39), "text_muted": (75, 85, 99)
    },
    {
        "name": "NavyAmber",
        "bg_top": (248, 250, 252), "bg_bot": (228, 236, 245),
        "primary": (15, 41, 74), "primary_dark": (10, 29, 55),
        "accent": (220, 38, 38), "gold": (202, 138, 4),
        "gold_light": (250, 204, 21), "soft_tint": (239, 246, 255),
        "line_gold": (204, 186, 132), "text_dark": (15, 23, 42), "text_muted": (71, 85, 105)
    },
    {
        "name": "TealRuby",
        "bg_top": (252, 251, 247), "bg_bot": (238, 235, 224),
        "primary": (17, 94, 89), "primary_dark": (15, 76, 71),
        "accent": (190, 18, 60), "gold": (195, 138, 12),
        "gold_light": (234, 179, 8), "soft_tint": (240, 253, 250),
        "line_gold": (206, 188, 138), "text_dark": (24, 24, 27), "text_muted": (82, 82, 91)
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

def ease_out_back(t, s=1.65):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * ((t - 1.0) ** 3) + s * ((t - 1.0) ** 2)

def _paste_sprite(canvas, sprite_rgba, cx, cy, scale=1.0, opacity=1.0):
    if opacity <= 0.01 or scale <= 0.02 or sprite_rgba is None:
        return
    sp = sprite_rgba
    if abs(scale - 1.0) > 0.015:
        nw = max(2, int(round(sp.width * scale)))
        nh = max(2, int(round(sp.height * scale)))
        sp = sp.resize((nw, nh), Image.BILINEAR)
    alpha = sp.getchannel("A")
    if opacity < 0.99:
        lut = [int(i * opacity) for i in range(256)]
        alpha = alpha.point(lut)
    canvas.paste(sp, (int(round(cx - sp.width / 2)), int(round(cy - sp.height / 2))), alpha)

def _make_shadow_card(w, h, radius=32, fill=(255, 255, 255), outline=None, outline_w=3, pad=28):
    cw, ch = w + pad * 2, h + pad * 2
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([pad, pad + 8, pad + w, pad + h + 8], radius=radius, fill=(15, 23, 42, 36))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    cd = ImageDraw.Draw(sh)
    cd.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill + (255,), outline=(outline + (255,)) if outline else None, width=outline_w)
    return sh

def _build_luxury_bg(W, H, th):
    bg = Image.new("RGB", (W, H), th["bg_top"])
    d = ImageDraw.Draw(bg)
    r1, g1, b1 = th["bg_top"]
    r2, g2, b2 = th["bg_bot"]
    for y in range(0, H, 4):
        t = y / float(H)
        col = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
        d.rectangle([0, y, W, min(H, y + 4)], fill=col)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    lc = th["line_gold"] + (135,)
    dc = th["gold"] + (170,)
    polys = [
        [(0, 210), (180, 125), (340, 215), (510, 95)],
        [(70, 0), (180, 125), (120, 320), (0, 410)],
        [(W, 170), (W - 190, 95), (W - 310, 230), (W - 140, 340)],
        [(W - 90, 0), (W - 190, 95), (W, 290)],
        [(0, H - 380), (165, H - 270), (310, H - 360), (460, H - 210)],
        [(W, H - 420), (W - 190, H - 290), (W - 330, H - 380), (W - 470, H - 220)],
        [(40, H - 680), (140, H - 680), (175, H - 640), (260, H - 640)],
        [(W - 40, 620), (W - 150, 620), (W - 190, 665), (W - 280, 665)]
    ]
    for pts in polys:
        od.line(pts, fill=lc, width=3)
        for px, py in pts[1:-1]:
            od.ellipse([px - 6, py - 6, px + 6, py + 6], fill=dc)

    bg_rgba = bg.convert("RGBA")
    bg_rgba.alpha_composite(ov)
    return bg_rgba.convert("RGB")

def _make_curl_sprite(H):
    sp = Image.new("RGBA", (90, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    for x in range(45):
        a = int(85 * ((x / 45.0) ** 2))
        d.line([(x, 0), (x, H)], fill=(15, 23, 42, a))
    for x in range(45, 90):
        t = 1.0 - (x - 45) / 45.0
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, int(155 * (t ** 1.5))))
    return sp

def _apply_page_curl(frame_a, frame_b, prog):
    W, H = frame_a.size
    cut_x = int(round(W * (1.0 - ease_in_out_cubic(prog))))
    if cut_x <= 0:
        return frame_b
    if cut_x >= W:
        return frame_a
    out = frame_b.copy()
    out.paste(frame_a.crop((0, 0, cut_x, H)), (0, 0))
    return out

def _make_laurel_sprig(th, flip=False):
    w, h = 110, 170
    sp = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    col = th["gold"] + (215,)
    d.arc([40, 30, 180, 310], start=115, end=245, fill=col, width=7)
    for i, ly in enumerate([75, 118, 162, 206, 248]):
        lx = 62 - int(16 * math.sin(i * 0.65))
        d.polygon([(lx, ly), (lx - 32, ly - 16), (lx - 18, ly + 10)], fill=col)
        d.polygon([(lx + 6, ly + 8), (lx + 36, ly - 10), (lx + 24, ly + 18)], fill=col)
    sp = sp.resize((w, h), Image.LANCZOS)
    return sp.transpose(Image.FLIP_LEFT_RIGHT) if flip else sp

def _make_emblem_sprite(th):
    sz = 250
    sp = Image.new("RGBA", (sz * 2, sz * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    cx, cy = sz, sz
    d.ellipse([cx - 210, cy - 210, cx + 210, cy + 210], fill=(255, 255, 255, 245), outline=th["gold"] + (255,), width=10)
    d.ellipse([cx - 182, cy - 182, cx + 182, cy + 182], outline=th["primary"] + (220,), width=6)
    d.polygon([
        (cx, cy - 120), (cx + 100, cy - 75), (cx + 85, cy + 35),
        (cx, cy + 118), (cx - 85, cy + 35), (cx - 100, cy - 75)
    ], fill=th["primary"] + (255,), outline=th["gold_light"] + (255,), width=6)
    d.rectangle([cx - 38, cy - 46, cx + 38, cy + 44], fill=(255, 255, 255, 245))
    d.line([(cx - 22, cy - 20), (cx + 22, cy - 20)], fill=th["accent"] + (255,), width=8)
    d.line([(cx - 22, cy + 2), (cx + 22, cy + 2)], fill=th["primary"] + (255,), width=7)
    d.line([(cx - 22, cy + 22), (cx + 12, cy + 22)], fill=th["primary"] + (255,), width=7)
    return sp.resize((sz, sz), Image.LANCZOS)

def _make_whatsapp_sprite():
    logo = find_whatsapp_logo()
    if logo:
        return logo.resize((184, 184), Image.LANCZOS)
    sz = 190
    sp = Image.new("RGBA", (sz * 2, sz * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.rounded_rectangle([24, 34, 356, 366], radius=82, fill=(21, 128, 61, 255))
    d.rounded_rectangle([24, 20, 356, 352], radius=82, fill=(34, 197, 94, 255))
    d.ellipse([86, 82, 294, 290], outline=(255, 255, 255, 255), width=18)
    d.polygon([(92, 248), (74, 304), (132, 282)], fill=(255, 255, 255, 255))
    d.arc([132, 130, 248, 246], start=35, end=220, fill=(255, 255, 255, 255), width=22)
    return sp.resize((sz, sz), Image.LANCZOS)

def _make_chevron_sprite(th):
    sp = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.polygon([(35, 35), (85, 90), (35, 145), (65, 145), (115, 90), (65, 35)], fill=th["gold_light"] + (235,))
    d.polygon([(75, 35), (125, 90), (75, 145), (105, 145), (155, 90), (105, 35)], fill=th["gold"] + (255,))
    return sp.resize((92, 92), Image.LANCZOS)

def _draw_vector_icon(d, cx, cy, kind, col):
    if kind == "age":
        d.ellipse([cx - 14, cy - 28, cx + 14, cy], fill=col)
        d.pieslice([cx - 26, cy + 4, cx + 26, cy + 44], start=180, end=360, fill=col)
    elif kind == "salary":
        d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=col, width=5)
        d.line([(cx - 12, cy - 8), (cx + 12, cy - 8)], fill=col, width=5)
        d.line([(cx - 12, cy + 6), (cx + 12, cy + 6)], fill=col, width=5)
        d.line([(cx, cy - 16), (cx, cy + 16)], fill=col, width=5)
    elif kind == "fee":
        d.rounded_rectangle([cx - 20, cy - 24, cx + 20, cy + 24], radius=6, outline=col, width=5)
        d.line([(cx - 10, cy - 8), (cx + 10, cy - 8)], fill=col, width=4)
        d.line([(cx - 10, cy + 4), (cx + 10, cy + 4)], fill=col, width=4)
    else:
        d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], outline=col, width=5)
        d.line([(cx - 24, cy), (cx + 24, cy)], fill=col, width=4)
        d.ellipse([cx - 11, cy - 24, cx + 11, cy + 24], outline=col, width=4)

def _extract_motion_data(job_data):
    m = job_data.get("motion") if isinstance(job_data.get("motion"), dict) else {}
    p = job_data.get("poster") if isinstance(job_data.get("poster"), dict) else {}

    org = clean_org_name(m.get("org_name") or job_data.get("org_name") or "সরকারি ও বেসরকারি নিয়োগ")
    cat_badge = remove_emojis(m.get("category_badge") or "নিয়োগ বিজ্ঞপ্তি").strip()
    hook_sub = remove_emojis(m.get("hook_subtitle") or p.get("hero_single_line") or job_data.get("hook_full") or "আগ্রহী ও যোগ্য প্রার্থীদের জন্য সুবর্ণ সুযোগ").strip()

    vac_num = m.get("total_vacancy_num", 0)
    try:
        vac_num = int(str(vac_num).translate(EN_DIGITS)) if vac_num else 0
    except Exception:
        vac_num = 0

    vac_display = remove_emojis(m.get("total_vacancy_display") or "").strip()
    if not vac_num and not vac_display:
        summary_txt = str(p.get("main_summary") or job_data.get("poster_main_summary") or "")
        vm = re.search(r'([\d০-৯]+)\s*(?:টি|জন)?\s*পদে?', summary_txt)
        if vm:
            try:
                vac_num = int(vm.group(1).translate(EN_DIGITS))
                vac_display = to_bn_num(vac_num) + "টি"
            except Exception:
                pass
    if not vac_display:
        vac_display = (to_bn_num(vac_num) + "টি") if vac_num > 0 else "বিভিন্ন পদে"

    vac_label = remove_emojis(m.get("vacancy_label") or ("মোট পদসংখ্যা:" if vac_num > 0 else "নিয়োগ অবস্থা:")).strip()
    highlights = m.get("highlights") if isinstance(m.get("highlights"), list) else []
    highlights = [remove_emojis(h).strip() for h in highlights if h and str(h).strip()][:2]
    if len(highlights) < 2:
        cand = [p.get("hero_top", ""), p.get("highlight_1_badge", ""), p.get("highlight_2_badge", "")]
        for c in cand:
            cc = remove_emojis(c).strip()
            if cc and cc not in highlights:
                highlights.append(cc)
            if len(highlights) >= 2:
                break
    if not highlights:
        highlights = ["যোগ্যতা অনুযায়ী আবেদন", "দ্রুত আবেদন সম্পন্ন করুন"]

    raw_posts = m.get("posts") if isinstance(m.get("posts"), list) and m.get("posts") else job_data.get("posts", [])
    posts = []
    for item in raw_posts[:6]:
        if isinstance(item, dict) and item.get("post_name"):
            pv = remove_emojis(item.get("vacancy", "")).strip() or "বিভিন্ন"
            if re.fullmatch(r'[\d০-৯]+', pv):
                pv = pv + "টি"
            posts.append({
                "post_name": remove_emojis(item.get("post_name", "")).strip(),
                "vacancy": pv,
                "qualification": remove_emojis(item.get("qualification", "বিজ্ঞপ্তিমতে")).strip(),
                "salary_grade": remove_emojis(item.get("salary_grade", "")).strip()
            })

    if not posts:
        for idx_k, badge_k, txt_k in [(1, "highlight_1_badge", "highlight_1_text"), (2, "highlight_2_badge", "highlight_2_text")]:
            bt = remove_emojis(p.get(badge_k, "")).strip()
            dt = remove_emojis(p.get(txt_k, "")).strip()
            if dt:
                posts.append({"post_name": bt or f"পদ ও যোগ্যতা {idx_k}", "vacancy": "বিভিন্ন", "qualification": dt[:70], "salary_grade": ""})

    age_limit = remove_emojis(m.get("age_limit") or "১৮ থেকে ৩০/৩২ বছর (বিজ্ঞপ্তিমতে)").strip()
    salary_range = remove_emojis(m.get("salary_range") or "সরকারি / কোম্পানির নীতিমালা অনুযায়ী").strip()
    app_fee = remove_emojis(m.get("application_fee") or p.get("fee_box_text") or job_data.get("application_fee") or "বিজ্ঞপ্তি অনুযায়ী").strip()
    apply_method = remove_emojis(m.get("apply_method") or "অনলাইন / নির্দেশিত মাধ্যমে").strip()

    tl_title = remove_emojis(m.get("timeline_title") or "আবেদনের সময়সীমা:").strip()
    sd = remove_emojis(m.get("start_date") or job_data.get("start_date") or "চলমান").strip()
    ed = remove_emojis(m.get("end_date") or job_data.get("end_date") or "বিজ্ঞপ্তিমতে").strip()
    if sd == "চলমান" and p.get("date_box_text"):
        sd = "আবেদন শুরু"
        ed = remove_emojis(p.get("date_box_text")).strip()

    urgency = remove_emojis(m.get("urgency_note") or "সময় শেষ হওয়ার আগেই নির্ভুলভাবে আবেদন করুন").strip()
    wa_num = os.environ.get("WHATSAPP_NUMBER", "01540503092").strip() or "01540503092"
    if len(wa_num) == 11 and wa_num.startswith("01") and "-" not in wa_num:
        wa_formatted = wa_num[:5] + "-" + wa_num[5:]
    else:
        wa_formatted = wa_num

    return {
        "org": org, "cat_badge": cat_badge, "hook_sub": hook_sub,
        "vac_num": vac_num, "vac_display": vac_display, "vac_label": vac_label,
        "highlights": highlights, "posts": posts,
        "age_limit": age_limit, "salary_range": salary_range,
        "app_fee": app_fee, "apply_method": apply_method,
        "tl_title": tl_title, "start_date": sd, "end_date": ed,
        "urgency": urgency, "wa_formatted": wa_formatted
    }

def render_motion_graphics_video(job_data, audio_path, output_path, fps=24):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    th = random.choice(THEMES)
    data = _extract_motion_data(job_data)

    print(f"  [🎬 TikTok Motion Engine] Theme={th['name']}, Duration={duration:.1f}s, Org='{data['org'][:30]}'")

    bg_base = _build_luxury_bg(W, H, th)
    curl_sprite = _make_curl_sprite(H)
    emblem_sp = _make_emblem_sprite(th)
    laurel_l = _make_laurel_sprig(th, False)
    laurel_r = _make_laurel_sprig(th, True)
    wa_sp = _make_whatsapp_sprite()
    chevron_sp = _make_chevron_sprite(th)

    # Ambient gold particles
    rng = random.Random(hash(data["org"]))
    particles = [(rng.randint(80, W - 80), rng.randint(150, H - 150), rng.randint(4, 8), rng.uniform(18, 42), rng.uniform(0, 6.28)) for _ in range(12)]

    # --- Pre-baked Persistent Header Sprite ---
    hdr_sp = _make_shadow_card(900, 108, radius=30, fill=(255, 255, 255), outline=th["gold"], outline_w=3)
    hd = ImageDraw.Draw(hdr_sp)
    hf, hsz = fit_single_line_font(hd, data["org"], get_body_font, 36, 24, 570)
    draw_mixed_text(hd, 62, 82, data["org"], hf, hsz, th["primary"], anchor="lm")
    hd.rounded_rectangle([670, 50, 902, 114], radius=24, fill=th["accent"] + (255,))
    draw_mixed_text(hd, 786, 82, data["cat_badge"], get_body_font(28), 28, (255, 255, 255), anchor="mm")

    # --- Pre-baked Scene 1 Sprites ---
    s1_org_sp = Image.new("RGBA", (960, 190), (0, 0, 0, 0))
    od = ImageDraw.Draw(s1_org_sp)
    of, osz, olines = fit_multiline_font(od, data["org"], get_header_font, 64, 42, 900, 2)
    oy = 95 - ((len(olines) - 1) * (osz + 14)) // 2
    for ol in olines:
        draw_mixed_text(od, 480, oy, ol, of, osz, th["primary"], anchor="mm")
        oy += osz + 14

    s1_badge_sp = _make_shadow_card(560, 110, radius=24, fill=th["accent"], outline=th["gold_light"], outline_w=4)
    bd = ImageDraw.Draw(s1_badge_sp)
    bf, bsz = fit_single_line_font(bd, data["cat_badge"], get_body_font, 48, 34, 490)
    draw_mixed_text(bd, s1_badge_sp.width // 2, s1_badge_sp.height // 2, data["cat_badge"], bf, bsz, (255, 255, 255), anchor="mm")

    s1_hook_sp = Image.new("RGBA", (920, 170), (0, 0, 0, 0))
    hkd = ImageDraw.Draw(s1_hook_sp)
    hkd.line([(240, 16), (680, 16)], fill=th["gold"] + (230,), width=5)
    hkf, hksz, hklines = fit_multiline_font(hkd, data["hook_sub"], get_body_font, 44, 32, 860, 2)
    hy = 78
    for hl in hklines:
        draw_mixed_text(hkd, 460, hy, hl, hkf, hksz, th["text_dark"], anchor="mm")
        hy += hksz + 14

    # --- Pre-baked Scene 2 Card & Highlights ---
    s2_card_base = _make_shadow_card(840, 390, radius=40, fill=(255, 255, 255), outline=th["accent"], outline_w=4)
    s2d = ImageDraw.Draw(s2_card_base)
    draw_mixed_text(s2d, s2_card_base.width // 2, 115, data["vac_label"], get_body_font(48), 48, th["text_dark"], anchor="mm")

    s2_static_num_sp = Image.new("RGBA", (780, 170), (0, 0, 0, 0))
    snd = ImageDraw.Draw(s2_static_num_sp)
    vf, vsz = fit_single_line_font(snd, data["vac_display"], get_header_font, 112, 54, 740)
    draw_mixed_text(snd, 390, 85, data["vac_display"], vf, vsz, th["primary"], anchor="mm")

    s2_hl_sprites = []
    for hl_txt in data["highlights"][:2]:
        hl_sp = _make_shadow_card(820, 128, radius=32, fill=th["soft_tint"], outline=th["primary"], outline_w=3)
        hld = ImageDraw.Draw(hl_sp)
        hlf, hlsz = fit_single_line_font(hld, hl_txt, get_body_font, 40, 28, 740)
        draw_mixed_text(hld, hl_sp.width // 2, hl_sp.height // 2, hl_txt, hlf, hlsz, th["primary_dark"], anchor="mm")
        s2_hl_sprites.append(hl_sp)

    # --- Pre-baked Scene 3 Post Cards ---
    s3_title_sp = _make_shadow_card(620, 96, radius=48, fill=th["primary"], outline=th["gold_light"], outline_w=3)
    s3td = ImageDraw.Draw(s3_title_sp)
    draw_mixed_text(s3td, s3_title_sp.width // 2, s3_title_sp.height // 2, "পদের বিবরণ ও যোগ্যতা", get_body_font(40), 40, (255, 255, 255), anchor="mm")

    s3_post_sprites = []
    for p_item in data["posts"][:6]:
        csp = _make_shadow_card(900, 245, radius=32, fill=(255, 255, 255), outline=th["gold"], outline_w=3)
        cd = ImageDraw.Draw(csp)
        cd.rounded_rectangle([42, 42, 232, 258], radius=24, fill=th["primary"] + (255,))
        vf_p, vsz_p = fit_single_line_font(cd, p_item["vacancy"], get_body_font, 46, 28, 170)
        draw_mixed_text(cd, 137, 132, p_item["vacancy"], vf_p, vsz_p, (255, 255, 255), anchor="mm")
        draw_mixed_text(cd, 137, 198, "শূন্যপদ", get_body_font(26), 26, th["gold_light"], anchor="mm")

        pf_p, psz_p, plines = fit_multiline_font(cd, p_item["post_name"], get_body_font, 42, 30, 620, 2)
        py = 82 if len(plines) > 1 else 100
        for pl in plines:
            draw_mixed_text(cd, 260, py, pl, pf_p, psz_p, th["primary_dark"], anchor="lm")
            py += psz_p + 10
        cd.line([(260, 166), (885, 166)], fill=th["line_gold"] + (200,), width=3)

        sub_info = p_item["qualification"]
        if p_item["salary_grade"]:
            sub_info = sub_info + " | " + p_item["salary_grade"]
        qf_p, qsz_p, qlines = fit_multiline_font(cd, sub_info, get_body_font, 32, 24, 620, 2)
        qy = 198 if len(qlines) > 1 else 212
        for ql in qlines:
            draw_mixed_text(cd, 260, qy, ql, qf_p, qsz_p, th["text_muted"], anchor="lm")
            qy += qsz_p + 8
        s3_post_sprites.append(csp)

    # --- Pre-baked Scene 4 Grid Cards ---
    s4_title_sp = _make_shadow_card(620, 96, radius=48, fill=th["primary"], outline=th["gold_light"], outline_w=3)
    s4td = ImageDraw.Draw(s4_title_sp)
    draw_mixed_text(s4td, s4_title_sp.width // 2, s4_title_sp.height // 2, "গুরুত্বপূর্ণ তথ্যসমূহ", get_body_font(40), 40, (255, 255, 255), anchor="mm")

    grid_specs = [
        ("age", "বয়সসীমা", data["age_limit"], th["primary"]),
        ("salary", "বেতন ও গ্রেড", data["salary_range"], th["primary_dark"]),
        ("fee", "আবেদন ফি", data["app_fee"], th["accent"]),
        ("method", "আবেদন মাধ্যম", data["apply_method"], th["primary"]),
    ]
    s4_cards = []
    for kind, lbl, val, badge_col in grid_specs:
        gsp = _make_shadow_card(430, 385, radius=32, fill=(255, 255, 255), outline=th["gold"], outline_w=3)
        gd = ImageDraw.Draw(gsp)
        cx = gsp.width // 2
        gd.ellipse([cx - 46, 56, cx + 46, 148], fill=badge_col + (255,))
        _draw_vector_icon(gd, cx, 102, kind, (255, 255, 255, 255))
        draw_mixed_text(gd, cx, 196, lbl, get_body_font(36), 36, th["text_muted"], anchor="mm")
        gd.line([(cx - 80, 228), (cx + 80, 228)], fill=th["line_gold"] + (200,), width=3)
        vf_g, vsz_g, vlines = fit_multiline_font(gd, val, get_body_font, 40, 28, 370, 3)
        vy = 308 - ((len(vlines) - 1) * (vsz_g + 10)) // 2
        for vl in vlines:
            draw_mixed_text(gd, cx, vy, vl, vf_g, vsz_g, th["text_dark"], anchor="mm")
            vy += vsz_g + 10
        s4_cards.append(gsp)

    # --- Pre-baked Scene 5 Timeline Sprites ---
    s5_title_sp = Image.new("RGBA", (880, 100), (0, 0, 0, 0))
    draw_mixed_text(ImageDraw.Draw(s5_title_sp), 440, 50, data["tl_title"], get_body_font(54), 54, th["text_dark"], anchor="mm")

    s5_card_sp = _make_shadow_card(920, 390, radius=38, fill=(255, 255, 255), outline=th["gold"], outline_w=4)
    tcd = ImageDraw.Draw(s5_card_sp)
    tcd.rounded_rectangle([120, 65, 360, 125], radius=24, fill=th["soft_tint"] + (255,))
    draw_mixed_text(tcd, 240, 95, "শুরুর তারিখ", get_body_font(32), 32, th["primary"], anchor="mm")
    sf5, ssz5, slines5 = fit_multiline_font(tcd, data["start_date"], get_body_font, 46, 30, 350, 2)
    sy5 = 240 - ((len(slines5) - 1) * (ssz5 + 12)) // 2
    for sl in slines5:
        draw_mixed_text(tcd, 240, sy5, sl, sf5, ssz5, th["text_dark"], anchor="mm")
        sy5 += ssz5 + 12

    tcd.rounded_rectangle([610, 65, 850, 125], radius=24, fill=(254, 226, 226, 255))
    draw_mixed_text(tcd, 730, 95, "শেষ তারিখ", get_body_font(32), 32, th["accent"], anchor="mm")
    ef5, esz5, elines5 = fit_multiline_font(tcd, data["end_date"], get_body_font, 46, 30, 350, 2)
    ey5 = 240 - ((len(elines5) - 1) * (esz5 + 12)) // 2
    for el in elines5:
        draw_mixed_text(tcd, 730, ey5, el, ef5, esz5, th["accent"], anchor="mm")
        ey5 += esz5 + 12

    s5_warn_sp = _make_shadow_card(840, 118, radius=32, fill=(254, 242, 242), outline=th["accent"], outline_w=3)
    wd5 = ImageDraw.Draw(s5_warn_sp)
    wf5, wsz5 = fit_single_line_font(wd5, data["urgency"], get_body_font, 36, 26, 760)
    draw_mixed_text(wd5, s5_warn_sp.width // 2, s5_warn_sp.height // 2, data["urgency"], wf5, wsz5, th["accent"], anchor="mm")

    # --- Pre-baked Scene 6 WhatsApp Outro Sprites ---
    s6_title_sp = Image.new("RGBA", (880, 100), (0, 0, 0, 0))
    draw_mixed_text(ImageDraw.Draw(s6_title_sp), 440, 50, "যোগাযোগ (হোয়াটসঅ্যাপ):", get_body_font(48), 48, th["text_dark"], anchor="mm")

    s6_pill_sp = _make_shadow_card(820, 165, radius=82, fill=th["primary_dark"], outline=th["gold_light"], outline_w=4)
    p6d = ImageDraw.Draw(s6_pill_sp)
    draw_mixed_text(p6d, s6_pill_sp.width // 2, s6_pill_sp.height // 2, data["wa_formatted"], get_english_bold_font(68), 68, (255, 255, 255), anchor="mm")

    s6_sub_sp = Image.new("RGBA", (900, 110), (0, 0, 0, 0))
    draw_mixed_text(ImageDraw.Draw(s6_sub_sp), 450, 55, "বিস্তারিত তথ্যের জন্য ও নির্ভুলভাবে আবেদনের জন্য মেসেজ দিন", get_body_font(34), 34, th["text_dark"], anchor="mm")

    s6_cta_sp = _make_shadow_card(640, 102, radius=51, fill=th["gold"], outline=th["primary_dark"], outline_w=3)
    draw_mixed_text(ImageDraw.Draw(s6_cta_sp), s6_cta_sp.width // 2, s6_cta_sp.height // 2, "ঘরে বসেই নির্ভুল আবেদন সেবা", get_body_font(38), 38, th["primary_dark"], anchor="mm")

    # Scene intervals
    bounds = [0.0, 0.14, 0.31, 0.62, 0.78, 0.90, 1.0]
    trans_sec = min(0.42, duration * 0.03)
    countup_cache = {}

    def render_scene_frame(scene_id, local_t, abs_t):
        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)

        # Floating ambient gold dust particles
        for px0, py0, pr, spd, ph in particles:
            py = int((py0 - abs_t * spd) % (H - 300)) + 150
            px = int(px0 + 16 * math.sin(abs_t * 1.4 + ph))
            fd.ellipse([px - pr, py - pr, px + pr, py + pr], fill=th["gold_light"])

        # Persistent org header for scenes 2..5
        if scene_id in [2, 3, 4, 5]:
            hdr_y = 225
            if scene_id == 2 and local_t < 0.45:
                ep = ease_out_cubic(local_t / 0.45)
                hdr_y = int(110 + (225 - 110) * ep)
            _paste_sprite(frame, hdr_sp, W // 2, hdr_y)

        if scene_id == 1:
            e_p = ease_out_back(min(1.0, local_t / 0.55))
            float_y = int(6 * math.sin(abs_t * 2.2))
            _paste_sprite(frame, emblem_sp, W // 2, 540 + float_y, scale=0.25 + 0.75 * e_p, opacity=min(1.0, local_t / 0.3))
            if local_t > 0.2:
                op = ease_out_cubic((local_t - 0.2) / 0.45)
                _paste_sprite(frame, s1_org_sp, W // 2, int(840 + 70 * (1.0 - op)), opacity=op)
            if local_t > 0.45:
                bp = ease_out_back((local_t - 0.45) / 0.45)
                _paste_sprite(frame, s1_badge_sp, W // 2, 1020, scale=0.6 + 0.4 * bp, opacity=min(1.0, (local_t - 0.45) / 0.3))
            if local_t > 0.7:
                hp = ease_out_cubic((local_t - 0.7) / 0.45)
                _paste_sprite(frame, s1_hook_sp, W // 2, int(1190 + 35 * (1.0 - hp)), opacity=hp)

        elif scene_id == 2:
            cp = ease_out_back(min(1.0, local_t / 0.5))
            _paste_sprite(frame, s2_card_base, W // 2, 650, scale=0.75 + 0.25 * cp, opacity=min(1.0, local_t / 0.35))
            if local_t > 0.25:
                lop = min(1.0, (local_t - 0.25) / 0.4)
                _paste_sprite(frame, laurel_l, 200, 685, opacity=lop)
                _paste_sprite(frame, laurel_r, W - 200, 685, opacity=lop)
            if data["vac_num"] > 0:
                cnt_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.15) / 1.35))
                cur_val = max(1, int(round(data["vac_num"] * cnt_p)))
                if cur_val not in countup_cache:
                    nsp = Image.new("RGBA", (780, 170), (0, 0, 0, 0))
                    txt_v = to_bn_num(cur_val) + "টি"
                    vf_c, vsz_c = fit_single_line_font(ImageDraw.Draw(nsp), txt_v, get_header_font, 112, 54, 740)
                    draw_mixed_text(ImageDraw.Draw(nsp), 390, 85, txt_v, vf_c, vsz_c, th["primary"], anchor="mm")
                    if len(countup_cache) > 40:
                        countup_cache.clear()
                    countup_cache[cur_val] = nsp
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 710)
            else:
                _paste_sprite(frame, s2_static_num_sp, W // 2, 710, scale=0.8 + 0.2 * cp, opacity=min(1.0, local_t / 0.4))

            for idx, hl_sp in enumerate(s2_hl_sprites):
                start_t = 0.65 + idx * 0.4
                if local_t > start_t:
                    sp_p = ease_out_cubic((local_t - start_t) / 0.45)
                    dx = int(((-1 if idx % 2 == 0 else 1) * 160) * (1.0 - sp_p))
                    _paste_sprite(frame, hl_sp, W // 2 + dx, 995 + idx * 155, opacity=sp_p)

        elif scene_id == 3:
            _paste_sprite(frame, s3_title_sp, W // 2, 375, opacity=min(1.0, local_t / 0.3))
            scene_len = (bounds[3] - bounds[2]) * duration
            if len(s3_post_sprites) > 3 and local_t >= scene_len * 0.5:
                batch = s3_post_sprites[3:6]
                batch_t = local_t - scene_len * 0.5
            else:
                batch = s3_post_sprites[:3]
                batch_t = local_t

            for idx, psp in enumerate(batch):
                st = 0.15 + idx * 0.45
                if batch_t > st:
                    pp = ease_out_cubic((batch_t - st) / 0.45)
                    dx = int(((-1 if idx % 2 == 0 else 1) * 180) * (1.0 - pp))
                    _paste_sprite(frame, psp, W // 2 + dx, 585 + idx * 278, opacity=pp)

        elif scene_id == 4:
            _paste_sprite(frame, s4_title_sp, W // 2, 375, opacity=min(1.0, local_t / 0.3))
            positions = [(305, 675), (775, 675), (305, 1105), (775, 1105)]
            for idx, gsp in enumerate(s4_cards):
                st = 0.15 + idx * 0.32
                if local_t > st:
                    gp = ease_out_back((local_t - st) / 0.45)
                    _paste_sprite(frame, gsp, positions[idx][0], positions[idx][1], scale=0.65 + 0.35 * gp, opacity=min(1.0, (local_t - st) / 0.3))

        elif scene_id == 5:
            _paste_sprite(frame, s5_title_sp, W // 2, 435, opacity=min(1.0, local_t / 0.35))
            cp = ease_out_back(min(1.0, max(0.0, local_t - 0.1) / 0.45))
            _paste_sprite(frame, s5_card_sp, W // 2, 745, scale=0.82 + 0.18 * cp, opacity=min(1.0, local_t / 0.35))
            if local_t > 0.3:
                arr_x = W // 2 + int(10 * math.sin(abs_t * 5.0))
                _paste_sprite(frame, chevron_sp, arr_x, 785, opacity=min(1.0, (local_t - 0.3) / 0.3))
            if local_t > 0.6:
                wp = min(1.0, (local_t - 0.6) / 0.4)
                pulse = 1.0 + 0.025 * math.sin(abs_t * 4.5)
                _paste_sprite(frame, s5_warn_sp, W // 2, 1085, scale=pulse, opacity=wp)

        elif scene_id == 6:
            wp = ease_out_back(min(1.0, local_t / 0.5))
            _paste_sprite(frame, wa_sp, W // 2, 475, scale=0.3 + 0.7 * wp, opacity=min(1.0, local_t / 0.3))
            if local_t > 0.25:
                tp = ease_out_cubic((local_t - 0.25) / 0.35)
                _paste_sprite(frame, s6_title_sp, W // 2, 660, opacity=tp)
            if local_t > 0.45:
                rp = ease_out_cubic((local_t - 0.45) / 0.45)
                if rp < 0.99:
                    rw = max(20, int(s6_pill_sp.width * rp))
                    crop_pill = s6_pill_sp.crop((0, 0, rw, s6_pill_sp.height))
                    alpha = crop_pill.getchannel("A")
                    frame.paste(crop_pill, ((W - s6_pill_sp.width) // 2, 795 - s6_pill_sp.height // 2), alpha)
                else:
                    _paste_sprite(frame, s6_pill_sp, W // 2, 795)
            if local_t > 0.75:
                sp_o = ease_out_cubic((local_t - 0.75) / 0.4)
                _paste_sprite(frame, s6_sub_sp, W // 2, 955, opacity=sp_o)
                pulse = 1.0 + 0.025 * math.sin(abs_t * 4.2)
                _paste_sprite(frame, s6_cta_sp, W // 2, 1110, scale=pulse, opacity=sp_o)

        # Bottom Progress Bar (above TikTok UI)
        prog_ratio = max(0.0, min(1.0, abs_t / duration))
        fd.rounded_rectangle([140, 1495, 940, 1505], radius=5, fill=(203, 213, 225))
        fill_x = max(150, 140 + int(800 * prog_ratio))
        fd.rounded_rectangle([140, 1495, fill_x, 1505], radius=5, fill=th["primary"])
        return frame

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
        "-i", "-", "-i", audio_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ]

    total_frames = max(int(math.ceil(duration * fps)), fps * 5)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    try:
        for f_idx in range(total_frames):
            abs_t = f_idx / float(fps)
            u = min(0.9999, abs_t / duration)
            s_idx = 6
            for i in range(6):
                if bounds[i] <= u < bounds[i + 1]:
                    s_idx = i + 1
                    break

            s_start_t = bounds[s_idx - 1] * duration
            s_end_t = bounds[s_idx] * duration
            local_t = abs_t - s_start_t

            frame_cur = render_scene_frame(s_idx, local_t, abs_t)

            if s_idx < 6 and (s_end_t - abs_t) < trans_sec:
                tp = 1.0 - (s_end_t - abs_t) / trans_sec
                frame_nxt = render_scene_frame(s_idx + 1, 0.0, abs_t)
                cut_x = int(round(W * (1.0 - ease_in_out_cubic(tp))))
                frame_out = _apply_page_curl(frame_cur, frame_nxt, tp)
                _paste_sprite(frame_out, curl_sprite, cut_x, H // 2)
            else:
                frame_out = frame_cur

            proc.stdin.write(frame_out.tobytes())

        proc.stdin.close()
        err_msg = proc.stderr.read().decode("utf-8", errors="ignore")
        ret = proc.wait(timeout=300)
        if ret != 0 and err_msg:
            print(f"  ⚠️ [FFmpeg Notice] {err_msg[:160]}")
    except Exception as e:
        print(f"  ❌ [TikTok Motion Render Error] {e}")
        try: proc.kill()
        except Exception: pass
        return False

    ok = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    if ok:
        print(f"  ✅ [TikTok Motion SUCCESS] Rendered ({round(os.path.getsize(output_path)/(1024*1024), 2)} MB, {duration:.1f}s)")
    return ok