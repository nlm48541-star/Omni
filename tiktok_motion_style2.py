# -*- coding: utf-8 -*-
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont

from tiktok_designer import (
    find_font_file, draw_mixed_text, fit_single_line_font, fit_multiline_font
)
from tiktok_motion_engine import (
    ease_out_cubic, ease_in_out_cubic, ease_out_back, to_bn_num,
    compute_motion_scene_bounds, split_posts_uniformly, uniform_batch_y_positions,
    _paste_sprite, _render_masked_rise, _make_minimal_card,
    _make_text_sprite, _make_word_sprites, _make_whatsapp_sprite,
    _draw_minimal_icon, _make_curl_sprite, _apply_transition,
    _extract_minimal_data, _stream_frames_to_ffmpeg
)

DARK_PALETTES = [
    {
        "name": "MidnightCyan",
        "bg": (11, 17, 32), "card": (23, 35, 58), "border": (48, 72, 110),
        "track": (32, 48, 76), "ink": (248, 250, 252), "muted": (158, 174, 196),
        "accent": (56, 189, 248), "accent_soft": (18, 52, 78)
    },
    {
        "name": "ObsidianMint",
        "bg": (9, 19, 17), "card": (18, 38, 33), "border": (38, 76, 66),
        "track": (28, 56, 48), "ink": (240, 253, 244), "muted": (152, 202, 180),
        "accent": (16, 185, 129), "accent_soft": (14, 56, 44)
    },
    {
        "name": "CarbonAmber",
        "bg": (15, 15, 19), "card": (29, 29, 38), "border": (56, 56, 72),
        "track": (42, 42, 56), "ink": (250, 250, 250), "muted": (166, 166, 178),
        "accent": (245, 158, 11), "accent_soft": (60, 42, 14)
    }
]

def _get_style2_font(size):
    path = find_font_file(["kalpurush", "SolaimanLipi", "Siyamrupali", "NotoSansBengali-Bold", "Li Ador Noirrit Bold"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def _get_style2_eng_font(size):
    for p in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf"
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def _make_aa_gauge_sprite(radius, track_col, accent_col, card_col, arc_p):
    sz = (radius + 36) * 2
    s = 2
    ov = Image.new("RGBA", (sz * s, sz * s), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    cx = cy = (sz * s) // 2
    r = radius * s
    od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=card_col + (255,), outline=track_col + (255,), width=20 * s)
    end_ang = -90 + 360.0 * arc_p
    if arc_p > 0.01:
        od.arc([cx - r, cy - r, cx + r, cy + r], start=-90, end=end_ang, fill=accent_col + (255,), width=20 * s)
        rad = math.radians(end_ang)
        tx, ty = cx + r * math.cos(rad), cy + r * math.sin(rad)
        od.ellipse([tx - 20 * s, ty - 20 * s, tx + 20 * s, ty + 20 * s], fill=accent_col + (180,))
        od.ellipse([tx - 11 * s, ty - 11 * s, tx + 11 * s, ty + 11 * s], fill=(255, 255, 255, 255))
    return ov.resize((sz, sz), Image.BILINEAR)

def render_motion_style_2(job_data, audio_path, output_path, fps=24):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    pal = random.choice(DARK_PALETTES)
    data = _extract_minimal_data(job_data)

    print(f"  [🌌 Motion Style #2 (Dark Executive)] Palette={pal['name']}, Duration={duration:.1f}s")

    bg_base = Image.new("RGB", (W, H), pal["bg"])
    curl_sp = _make_curl_sprite(H)
    wa_sp = _make_whatsapp_sprite()

    hdr_sp = _make_minimal_card(920, 122, radius=28, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
    hd = ImageDraw.Draw(hdr_sp)
    hf, hsz = fit_single_line_font(hd, data["org"], _get_style2_font, 46, 28, 600)
    draw_mixed_text(hd, 94, 83, data["org"], hf, hsz, pal["ink"], anchor="lm")
    hd.rounded_rectangle([714, 48, 916, 118], radius=20, fill=pal["accent_soft"] + (255,), outline=pal["accent"] + (255,), width=2)
    draw_mixed_text(hd, 815, 83, "বিজ্ঞপ্তি", _get_style2_font(34), 34, pal["accent"], anchor="mm")

    emblem_core = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    ed = ImageDraw.Draw(emblem_core)
    ed.ellipse([20, 20, 220, 220], fill=pal["card"] + (255,), outline=pal["accent"] + (255,), width=6)
    _draw_minimal_icon(ed, 120, 120, "method", pal["accent"] + (255,))

    s1_org_words = _make_word_sprites(data["org"], _get_style2_font, 90, 52, 940, 2, pal["ink"], W // 2, 685)
    s1_badge_sp = _make_minimal_card(600, 130, radius=65, fill=pal["accent"], shadow_alpha=45)
    bf, bsz = fit_single_line_font(ImageDraw.Draw(s1_badge_sp), data["cat_badge"], _get_style2_font, 58, 38, 520)
    draw_mixed_text(ImageDraw.Draw(s1_badge_sp), s1_badge_sp.width // 2, s1_badge_sp.height // 2, data["cat_badge"], bf, bsz, pal["bg"], anchor="mm")
    s1_hook_words = _make_word_sprites(data["hook_short"], _get_style2_font, 54, 36, 880, 2, pal["muted"], W // 2, 1155)

    s2_lbl_sp = _make_text_sprite("মোট শূন্যপদ", _get_style2_font, 62, 46, 700, 1, pal["muted"])
    s2_static_num = _make_text_sprite(data["vac_display"], _get_style2_font, 162, 68, 420, 1, pal["ink"])
    s2_tag_sp = _make_minimal_card(860, 144, radius=32, fill=pal["card"], border=pal["accent"], border_w=2, shadow_alpha=45)
    tf2, tsz2, tl2 = fit_multiline_font(ImageDraw.Draw(s2_tag_sp), data["short_tag"], _get_style2_font, 48, 32, 780, 2)
    ty2 = s2_tag_sp.height // 2 - ((len(tl2) - 1) * (tsz2 + 10)) // 2
    for l2 in tl2:
        draw_mixed_text(ImageDraw.Draw(s2_tag_sp), s2_tag_sp.width // 2, ty2, l2, tf2, tsz2, pal["accent"], anchor="mm")
        ty2 += tsz2 + 10

    s3_hdr_sp = _make_text_sprite("পদের বিবরণ", _get_style2_font, 62, 46, 700, 1, pal["ink"])
    batches_raw = split_posts_uniformly(data["posts"])
    max_per_b = max(len(b) for b in batches_raw)
    if max_per_b == 1:
        u_ch, t_sz, v_sz, m_sz, idx_sz = 365, 64, 74, 46, 106
    elif max_per_b == 2:
        u_ch, t_sz, v_sz, m_sz, idx_sz = 310, 56, 60, 42, 102
    elif max_per_b == 3:
        u_ch, t_sz, v_sz, m_sz, idx_sz = 274, 52, 54, 40, 96
    else:
        u_ch, t_sz, v_sz, m_sz, idx_sz = 224, 46, 48, 38, 86

    s3_batches = []
    bn_idx_labels = ["০১", "০২", "০৩", "০৪", "০৫", "০৬", "০৭", "০৮", "০৯", "১০", "১১", "১২", "১৩", "১৪", "১৫", "১৬", "১৭", "১৮", "১৯", "২০"]
    global_idx = 0
    for batch_items in batches_raw:
        ys = uniform_batch_y_positions(len(batch_items), max_per_b)
        entries = []
        for idx_c, it in enumerate(batch_items):
            bg_c = _make_minimal_card(940, u_ch, radius=28, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
            num_badge = _make_minimal_card(idx_sz, idx_sz, radius=22, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=8, shadow_alpha=0)
            draw_mixed_text(ImageDraw.Draw(num_badge), num_badge.width // 2, num_badge.height // 2, bn_idx_labels[global_idx % 20], _get_style2_font(40), 40, pal["accent"], anchor="mm")
            t_sp = _make_text_sprite(it["post_name"], _get_style2_font, t_sz, 32, 465, 2, pal["ink"], align="lm")
            v_sp = _make_text_sprite(it["vacancy"], _get_style2_font, v_sz, 30, 225, 1, pal["accent"], align="rm")
            m_sp = _make_text_sprite(it["meta"], _get_style2_font, m_sz, 30, 725, 2 if max_per_b <= 2 else 1, pal["muted"], align="lm")
            entries.append({"bg": bg_c, "idx": num_badge, "title": t_sp, "vac": v_sp, "meta": m_sp, "h": u_ch, "cy": ys[idx_c]})
            global_idx += 1
        s3_batches.append(entries)

    s4_hdr_sp = _make_text_sprite("মূল তথ্য", _get_style2_font, 62, 46, 700, 1, pal["ink"])
    s4_rows = []
    for kind, lbl, val in [("age", "বয়স", data["age_limit"]), ("salary", "বেতন", data["salary_range"]), ("fee", "আবেদন ফি", data["app_fee"]), ("method", "মাধ্যম", data["apply_method"])]:
        r_bg = _make_minimal_card(930, 205, radius=28, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
        icon_sp = Image.new("RGBA", (112, 112), (0, 0, 0, 0))
        idraw = ImageDraw.Draw(icon_sp)
        idraw.rounded_rectangle([4, 4, 108, 108], radius=24, fill=pal["accent_soft"] + (255,), outline=pal["accent"] + (255,), width=3)
        _draw_minimal_icon(idraw, 56, 56, kind, pal["accent"] + (255,))
        s4_rows.append({
            "bg": r_bg, "icon": icon_sp,
            "lbl": _make_text_sprite(lbl, _get_style2_font, 44, 30, 230, 1, pal["muted"], align="lm"),
            "val": _make_text_sprite(val, _get_style2_font, 52, 34, 495, 2, pal["ink"], align="rm")
        })

    s5_hdr_sp = _make_text_sprite("আবেদনের সময়সীমা", _get_style2_font, 64, 46, 860, 1, pal["ink"])
    s5_card_bg = _make_minimal_card(920, 520, radius=36, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
    s5_lbl1 = _make_text_sprite("শুরুর তারিখ", _get_style2_font, 38, 28, 320, 1, pal["muted"], align="lm")
    s5_d1 = _make_text_sprite(data["start_date"], _get_style2_font, 58, 36, 620, 2, pal["ink"], align="lm")
    s5_lbl2 = _make_text_sprite("শেষ তারিখ", _get_style2_font, 38, 28, 320, 1, pal["accent"], align="lm")
    s5_d2 = _make_text_sprite(data["end_date"], _get_style2_font, 58, 36, 620, 2, pal["accent"], align="lm")
    s5_urg_sp = _make_minimal_card(760, 122, radius=61, fill=pal["accent_soft"], border=pal["accent"], border_w=3, shadow_alpha=35)
    draw_mixed_text(ImageDraw.Draw(s5_urg_sp), s5_urg_sp.width // 2, s5_urg_sp.height // 2, "সময়মতো আবেদন করুন", _get_style2_font(46), 46, pal["accent"], anchor="mm")

    s6_title_words = _make_word_sprites("যোগাযোগ (হোয়াটসঅ্যাপ)", _get_style2_font, 64, 42, 920, 1, pal["ink"], W // 2, 660)
    s6_pill_empty = _make_minimal_card(910, 204, radius=102, fill=pal["accent"], shadow_alpha=45)
    s6_num_sp = Image.new("RGBA", (850, 130), (0, 0, 0, 0))
    draw_mixed_text(ImageDraw.Draw(s6_num_sp), 425, 65, data["wa_formatted"], _get_style2_eng_font(84), 84, pal["bg"], anchor="mm")
    s6_pill_mask = Image.new("L", s6_pill_empty.size, 0)
    ImageDraw.Draw(s6_pill_mask).rounded_rectangle([22, 22, 932, 226], radius=102, fill=255)
    sheen_sp = Image.new("RGBA", (220, s6_pill_empty.height), (0, 0, 0, 0))
    ImageDraw.Draw(sheen_sp).polygon([(70, 0), (170, 0), (100, s6_pill_empty.height), (0, s6_pill_empty.height)], fill=(255, 255, 255, 85))
    s6_sub_words = _make_word_sprites("আবেদনের জন্য মেসেজ দিন", _get_style2_font, 54, 36, 900, 1, pal["ink"], W // 2, 1075)

    bounds = compute_motion_scene_bounds(duration)
    trans_styles = ["push_left", "curl", "push_left", "curl", "push_left"]
    trans_sec = min(0.42, duration * 0.03)
    countup_cache, gauge_cache = {}, {}

    def render_scene_frame(scene_id, local_t, abs_t):
        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)

        bx1 = int((abs_t * 68) % (W + 380)) - 260
        bx2 = int(W + 260 - ((abs_t * 52) % (W + 380)))
        fd.rounded_rectangle([bx1, 130, bx1 + 220, 135], radius=2, fill=pal["track"])
        fd.rounded_rectangle([bx2, H - 310, bx2 + 200, H - 305], radius=2, fill=pal["track"])
        fd.ellipse([bx1 + 235, 127, bx1 + 247, 139], fill=pal["accent"])
        fd.ellipse([bx2 - 28, H - 313, bx2 - 16, H - 301], fill=pal["accent"])

        if scene_id in [2, 3, 4, 5]:
            hdr_y = int(105 + 120 * ease_out_cubic(local_t / 0.38)) if (scene_id == 2 and local_t < 0.38) else 225
            _paste_sprite(frame, hdr_sp, W // 2, hdr_y)
            dot_r = 9 + int(3 * math.sin(abs_t * 5.0))
            fd.ellipse([124 - dot_r, hdr_y - dot_r, 124 + dot_r, hdr_y + dot_r], fill=pal["accent"])

        if scene_id == 1:
            ep = ease_out_back(min(1.0, local_t / 0.45))
            _paste_sprite(frame, emblem_core, W // 2, 415, scale=0.3 + 0.7 * ep, opacity=min(1.0, local_t / 0.22))
            orb_r = 148
            fd.ellipse([W // 2 - orb_r, 415 - orb_r, W // 2 + orb_r, 415 + orb_r], outline=pal["border"], width=3)
            ang = abs_t * 1.6
            ox, oy = W // 2 + int(orb_r * math.cos(ang)), 415 + int(orb_r * math.sin(ang))
            fd.ellipse([ox - 10, oy - 10, ox + 10, oy + 10], fill=pal["accent"])

            for idx_w, (wsp, wx, wy) in enumerate(s1_org_words):
                st = 0.14 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.32, rise_px=52)
            if local_t > 0.30:
                hl = int(210 * ease_out_cubic((local_t - 0.30) / 0.35))
                fd.rounded_rectangle([W // 2 - hl, 845, W // 2 + hl, 852], radius=3, fill=pal["accent"])
            if local_t > 0.40:
                bp = ease_out_back((local_t - 0.40) / 0.38)
                _paste_sprite(frame, s1_badge_sp, W // 2, 975, scale=0.65 + 0.35 * bp, opacity=min(1.0, (local_t - 0.40) / 0.2))
            for idx_h, (wsp, wx, wy) in enumerate(s1_hook_words):
                st = 0.58 + idx_h * 0.07
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.30, rise_px=40)

        elif scene_id == 2:
            _render_masked_rise(frame, s2_lbl_sp, W // 2, 420, local_t / 0.32, rise_px=42)
            arc_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.1) / 1.35))
            g_key = int(round(arc_p * 60))
            if g_key not in gauge_cache:
                if len(gauge_cache) > 65: gauge_cache.clear()
                gauge_cache[g_key] = _make_aa_gauge_sprite(235, pal["track"], pal["accent"], pal["card"], g_key / 60.0)
            _paste_sprite(frame, gauge_cache[g_key], W // 2, 745)

            if data["vac_num"] > 0:
                cur_val = max(1, int(round(data["vac_num"] * arc_p)))
                if cur_val not in countup_cache:
                    if len(countup_cache) > 45: countup_cache.clear()
                    countup_cache[cur_val] = _make_text_sprite(to_bn_num(cur_val) + "টি", _get_style2_font, 162, 68, 420, 1, pal["ink"])
                land_t = local_t - 1.45
                pop_sc = (1.0 + 0.12 * math.sin((land_t / 0.35) * math.pi)) if 0.0 <= land_t <= 0.35 else 1.0
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 745, scale=pop_sc)
            else:
                _paste_sprite(frame, s2_static_num, W // 2, 745, scale=0.75 + 0.25 * ease_out_back(min(1.0, local_t / 0.45)))

            if local_t > 0.65:
                tp = ease_out_back((local_t - 0.65) / 0.40)
                _paste_sprite(frame, s2_tag_sp, W // 2, 1135 + int(45 * (1.0 - min(1.0, tp))), scale=0.82 + 0.18 * tp, opacity=min(1.0, (local_t - 0.65) / 0.22))

        elif scene_id == 3:
            _render_masked_rise(frame, s3_hdr_sp, W // 2, 370, local_t / 0.30, rise_px=36)
            hl_w = int(130 * ease_out_cubic(min(1.0, local_t / 0.42)))
            fd.rounded_rectangle([W // 2 - hl_w, 420, W // 2 + hl_w, 426], radius=3, fill=pal["accent"])

            top_band = frame.crop((0, 0, W, 452))
            bot_band = frame.crop((0, 1465, W, H))

            scene_len = (bounds[3] - bounds[2]) * duration
            num_b = len(s3_batches)
            slice_t = scene_len / float(num_b)
            b_idx = min(num_b - 1, int(local_t / slice_t))
            bt = local_t - b_idx * slice_t
            batch_trans = 0.40

            def draw_b(entries, cur_bt, extra_dx=0, fade_m=1.0):
                active_c = int(abs_t * 0.45) % max(1, len(entries))
                for idx_c, c in enumerate(entries):
                    st = 0.06 + idx_c * 0.20
                    if cur_bt <= st: continue
                    cp = ease_out_cubic((cur_bt - st) / 0.34)
                    act_sc = 1.018 if (cur_bt > 1.3 and idx_c == active_c and extra_dx == 0) else 1.0
                    cx = W // 2 + int(220 * (1.0 - cp)) + extra_dx
                    cy = c["cy"]
                    op = min(1.0, (cur_bt - st) / 0.18) * fade_m
                    _paste_sprite(frame, c["bg"], cx, cy, scale=act_sc, opacity=op)
                    bar_p = ease_out_cubic((cur_bt - st - 0.04) / 0.28)
                    if bar_p > 0.02:
                        y_tb = cy - c["h"] // 2 + 22
                        fd.rounded_rectangle([cx - 455, y_tb, cx - 445, y_tb + max(8, int((c["h"] - 44) * bar_p))], radius=5, fill=pal["accent"])
                    _paste_sprite(frame, c["idx"], cx - 365, cy, scale=0.7 + 0.3 * ease_out_back((cur_bt - st) / 0.30), opacity=op)
                    if cur_bt > st + 0.05:
                        _render_masked_rise(frame, c["title"], cx - 40, cy - int(c["h"] * 0.17), (cur_bt - st - 0.05) / 0.26, rise_px=22)
                    if cur_bt > st + 0.10:
                        _paste_sprite(frame, c["vac"], cx + 315, cy - int(c["h"] * 0.17), scale=0.6 + 0.4 * ease_out_back((cur_bt - st - 0.10) / 0.26), opacity=fade_m)
                    if cur_bt > st + 0.15:
                        _render_masked_rise(frame, c["meta"], cx + 85, cy + int(c["h"] * 0.24), (cur_bt - st - 0.15) / 0.26, rise_px=18)

            if b_idx > 0 and bt < batch_trans:
                tp = ease_in_out_cubic(bt / batch_trans)
                draw_b(s3_batches[b_idx - 1], slice_t, extra_dx=-int(1080 * tp), fade_m=1.0 - tp)
                draw_b(s3_batches[b_idx], bt, extra_dx=int(1080 * (1.0 - tp)), fade_m=tp)
            else:
                draw_b(s3_batches[b_idx], bt)

            frame.paste(top_band, (0, 0))
            frame.paste(bot_band, (0, 1465))

        elif scene_id == 4:
            _render_masked_rise(frame, s4_hdr_sp, W // 2, 370, local_t / 0.30, rise_px=36)
            hl_w = int(120 * ease_out_cubic(min(1.0, local_t / 0.42)))
            fd.rounded_rectangle([W // 2 - hl_w, 420, W // 2 + hl_w, 426], radius=3, fill=pal["accent"])
            ys4 = [565, 792, 1019, 1246]
            for idx, r in enumerate(s4_rows):
                st = 0.06 + idx * 0.16
                if local_t <= st: continue
                rp = ease_out_cubic((local_t - st) / 0.32)
                dx = int(((-1 if idx % 2 == 0 else 1) * 240) * (1.0 - rp))
                ry = ys4[idx]
                op = min(1.0, (local_t - st) / 0.16)
                _paste_sprite(frame, r["bg"], W // 2 + dx, ry, opacity=op)
                _paste_sprite(frame, r["icon"], 155 + dx, ry, scale=0.55 + 0.45 * ease_out_back((local_t - st) / 0.30), opacity=op)
                _render_masked_rise(frame, r["lbl"], 355 + dx, ry, (local_t - st - 0.05) / 0.24, rise_px=20)
                _paste_sprite(frame, r["val"], 725 + dx, ry, scale=0.75 + 0.25 * ease_out_back((local_t - st - 0.08) / 0.26), opacity=op)
                uw = int(850 * ease_out_cubic((local_t - st - 0.08) / 0.36))
                if uw > 8:
                    fd.rounded_rectangle([W // 2 + dx - 425, ry + 92, W // 2 + dx - 425 + uw, ry + 97], radius=2, fill=pal["accent"])

        elif scene_id == 5:
            _render_masked_rise(frame, s5_hdr_sp, W // 2, 390, local_t / 0.30, rise_px=38)
            hl_w = int(180 * ease_out_cubic(min(1.0, local_t / 0.42)))
            fd.rounded_rectangle([W // 2 - hl_w, 444, W // 2 + hl_w, 450], radius=3, fill=pal["accent"])
            cp = ease_out_back(min(1.0, max(0.0, local_t - 0.06) / 0.40))
            _paste_sprite(frame, s5_card_bg, W // 2, 765, scale=0.82 + 0.18 * cp, opacity=min(1.0, local_t / 0.22))

            if local_t > 0.15:
                fd.rounded_rectangle([182, 625, 190, 905], radius=4, fill=pal["track"])
                tp_line = ease_out_cubic((local_t - 0.15) / 0.55)
                fd.rounded_rectangle([182, 625, 190, 625 + int(280 * tp_line)], radius=4, fill=pal["accent"])
                fd.ellipse([162, 601, 210, 649], fill=pal["accent"])
                fd.ellipse([174, 613, 198, 637], fill=pal["ink"])
                _render_masked_rise(frame, s5_lbl1, 415, 592, (local_t - 0.15) / 0.26, rise_px=20)
                _render_masked_rise(frame, s5_d1, 565, 658, (local_t - 0.22) / 0.30, rise_px=30)

            if local_t > 0.32:
                flow_y = int(625 + 280 * ((abs_t * 0.9) % 1.0))
                fd.ellipse([174, flow_y - 12, 198, flow_y + 12], fill=(255, 255, 255))
                fd.ellipse([162, 881, 210, 929], fill=pal["accent"])
                _render_masked_rise(frame, s5_lbl2, 415, 872, (local_t - 0.32) / 0.26, rise_px=20)
                dp2 = ease_out_back((local_t - 0.38) / 0.34)
                _paste_sprite(frame, s5_d2, 565, 938, scale=0.78 + 0.22 * dp2)

            if local_t > 0.52:
                up = ease_out_back((local_t - 0.52) / 0.36)
                _paste_sprite(frame, s5_urg_sp, W // 2, 1175, scale=(0.82 + 0.18 * up) * (1.0 + 0.025 * math.sin(abs_t * 4.2)), opacity=min(1.0, (local_t - 0.52) / 0.24))

        elif scene_id == 6:
            for ri in range(2):
                rp = ((abs_t * 0.65) + ri * 0.5) % 1.0
                rr = int(125 + 150 * rp)
                fd.ellipse([W // 2 - rr, 435 - rr, W // 2 + rr, 435 + rr], outline=pal["border"], width=3)
            ang = abs_t * 1.8
            ox, oy = W // 2 + int(165 * math.cos(ang)), 435 + int(165 * math.sin(ang))
            fd.ellipse([ox - 8, oy - 8, ox + 8, oy + 8], fill=pal["accent"])

            wp = ease_out_back(min(1.0, local_t / 0.42))
            _paste_sprite(frame, wa_sp, W // 2, 435 + int(8 * math.sin(abs_t * 2.8)), scale=0.25 + 0.75 * wp, opacity=min(1.0, local_t / 0.22))
            for idx_w, (wsp, wx, wy) in enumerate(s6_title_words):
                st = 0.16 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.28, rise_px=34)
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
        fd.rounded_rectangle([140, 1506, 940, 1516], radius=5, fill=pal["track"])
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
