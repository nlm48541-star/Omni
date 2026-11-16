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

WARM_PALETTES = [
    {
        "name": "CreamTerracotta",
        "bg": (251, 248, 243), "shape": (244, 224, 212),
        "card": (255, 255, 255), "tint": (253, 237, 228),
        "ink": (34, 24, 20), "muted": (118, 102, 94),
        "accent": (217, 78, 31), "hairline": (238, 226, 216)
    },
    {
        "name": "SageBotanical",
        "bg": (246, 249, 244), "shape": (218, 236, 220),
        "card": (255, 255, 255), "tint": (231, 245, 234),
        "ink": (18, 36, 24), "muted": (90, 112, 98),
        "accent": (21, 128, 61), "hairline": (220, 232, 222)
    },
    {
        "name": "LilacIndigo",
        "bg": (248, 247, 252), "shape": (228, 223, 247),
        "card": (255, 255, 255), "tint": (238, 234, 253),
        "ink": (30, 27, 46), "muted": (106, 102, 128),
        "accent": (79, 70, 229), "hairline": (228, 223, 242)
    }
]

def _get_style3_display_font(size):
    path = find_font_file(["Shokuntola UNICODE", "Shokuntola", "Siyamrupali", "NotoSansBengali-Bold", "Li Ador Noirrit Bold"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def _get_style3_body_font(size):
    path = find_font_file(["Li Ador Noirrit Bold", "NotoSansBengali-Bold", "kalpurush", "SolaimanLipi"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def _get_style3_eng_font(size):
    for p in ["/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def render_motion_style_3(job_data, audio_path, output_path, fps=24):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    pal = random.choice(WARM_PALETTES)
    data = _extract_minimal_data(job_data)

    print(f"  [🎨 Motion Style #3 (Warm Glass Editorial)] Palette={pal['name']}, Duration={duration:.1f}s")

    bg_base = Image.new("RGB", (W, H), pal["bg"])
    curl_sp = _make_curl_sprite(H)
    wa_sp = _make_whatsapp_sprite()

    hdr_left = _make_minimal_card(695, 114, radius=57, fill=pal["card"], border=pal["hairline"], border_w=2)
    hl_d = ImageDraw.Draw(hdr_left)
    hf, hsz = fit_single_line_font(hl_d, data["org"], _get_style3_body_font, 44, 28, 575)
    draw_mixed_text(hl_d, 90, 79, data["org"], hf, hsz, pal["ink"], anchor="lm")

    hdr_right = _make_minimal_card(205, 114, radius=57, fill=pal["accent"], shadow_alpha=24)
    draw_mixed_text(ImageDraw.Draw(hdr_right), hdr_right.width // 2, hdr_right.height // 2, "বিজ্ঞপ্তি", _get_style3_body_font(36), 36, (255, 255, 255), anchor="mm")

    seal_sp = Image.new("RGBA", (280, 280), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal_sp)
    sd.rounded_rectangle([24, 24, 256, 256], radius=64, fill=pal["tint"] + (255,), outline=pal["accent"] + (255,), width=8)
    _draw_minimal_icon(sd, 140, 140, "fee", pal["accent"] + (255,))

    s1_org_words = _make_word_sprites(data["org"], _get_style3_display_font, 90, 52, 940, 2, pal["ink"], W // 2, 685)
    s1_badge_sp = _make_minimal_card(620, 134, radius=67, fill=pal["tint"], border=pal["accent"], border_w=4)
    bf, bsz = fit_single_line_font(ImageDraw.Draw(s1_badge_sp), data["cat_badge"], _get_style3_body_font, 58, 38, 540)
    draw_mixed_text(ImageDraw.Draw(s1_badge_sp), s1_badge_sp.width // 2, s1_badge_sp.height // 2, data["cat_badge"], bf, bsz, pal["accent"], anchor="mm")
    s1_hook_words = _make_word_sprites(data["hook_short"], _get_style3_body_font, 54, 38, 900, 2, pal["muted"], W // 2, 1165)

    s2_card_sp = _make_minimal_card(900, 450, radius=44, fill=pal["card"], border=pal["hairline"], border_w=2)
    s2d = ImageDraw.Draw(s2_card_sp)
    s2d.rounded_rectangle([22, 22, 922, 146], radius=42, fill=pal["tint"] + (255,))
    s2d.rectangle([22, 84, 922, 146], fill=pal["tint"] + (255,))
    draw_mixed_text(s2d, s2_card_sp.width // 2, 86, "মোট শূন্যপদ", _get_style3_body_font(54), 54, pal["accent"], anchor="mm")
    s2_static_num = _make_text_sprite(data["vac_display"], _get_style3_body_font, 175, 72, 820, 1, pal["ink"])

    s2_tag_sp = _make_minimal_card(860, 142, radius=71, fill=pal["accent"], shadow_alpha=28)
    tf2, tsz2, tl2 = fit_multiline_font(ImageDraw.Draw(s2_tag_sp), data["short_tag"], _get_style3_body_font, 48, 32, 780, 2)
    ty2 = s2_tag_sp.height // 2 - ((len(tl2) - 1) * (tsz2 + 10)) // 2
    for l2 in tl2:
        draw_mixed_text(ImageDraw.Draw(s2_tag_sp), s2_tag_sp.width // 2, ty2, l2, tf2, tsz2, (255, 255, 255), anchor="mm")
        ty2 += tsz2 + 10

    s3_hdr_sp = _make_text_sprite("পদ ও যোগ্যতা", _get_style3_display_font, 66, 48, 700, 1, pal["ink"])
    batches_raw = split_posts_uniformly(data["posts"])
    max_per_b = max(len(b) for b in batches_raw)
    if max_per_b == 1:
        u_ch, t_sz, v_sz, m_sz, b_h, idx_h = 380, 64, 72, 46, 124, 74
    elif max_per_b == 2:
        u_ch, t_sz, v_sz, m_sz, b_h, idx_h = 320, 56, 60, 44, 108, 70
    elif max_per_b == 3:
        u_ch, t_sz, v_sz, m_sz, b_h, idx_h = 282, 52, 54, 40, 104, 68
    else:
        u_ch, t_sz, v_sz, m_sz, b_h, idx_h = 224, 46, 48, 38, 88, 60

    s3_batches = []
    bn_nums = ["০১", "০২", "০৩", "০৪", "০৫", "০৬", "০৭", "০৮", "০৯", "১০", "১১", "১২", "১৩", "১৪", "১৫", "১৬", "১৭", "১৮", "১৯", "২০"]
    g_i = 0
    for batch_items in batches_raw:
        ys = uniform_batch_y_positions(len(batch_items), max_per_b)
        entries = []
        for idx_c, it in enumerate(batch_items):
            bg_c = _make_minimal_card(940, u_ch, radius=32 if u_ch > 240 else 28, fill=pal["card"], border=pal["hairline"], border_w=2)
            idx_pill = _make_minimal_card(88, idx_h, radius=22, fill=pal["tint"], pad=8, shadow_alpha=0)
            draw_mixed_text(ImageDraw.Draw(idx_pill), idx_pill.width // 2, idx_pill.height // 2, bn_nums[g_i % 20], _get_style3_body_font(36), 36, pal["accent"], anchor="mm")
            t_sp = _make_text_sprite(it["post_name"], _get_style3_body_font, t_sz, 32, 460, 2, pal["ink"], align="lm")
            b_sp = _make_minimal_card(255, b_h, radius=26, fill=pal["tint"], border=pal["accent"], border_w=2, pad=10, shadow_alpha=0)
            vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], _get_style3_body_font, v_sz, 30, 220)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
            m_sp = _make_text_sprite(it["meta"], _get_style3_body_font, m_sz, 30, 840, 2 if max_per_b <= 2 else 1, pal["muted"], align="lm")
            entries.append({"bg": bg_c, "idx": idx_pill, "title": t_sp, "badge": b_sp, "meta": m_sp, "h": u_ch, "cy": ys[idx_c]})
            g_i += 1
        s3_batches.append(entries)

    s4_hdr_sp = _make_text_sprite("মূল তথ্য", _get_style3_display_font, 66, 48, 700, 1, pal["ink"])
    s4_cards = []
    for idx4, (kind, lbl, val) in enumerate([("age", "বয়স", data["age_limit"]), ("salary", "বেতন", data["salary_range"]), ("fee", "আবেদন ফি", data["app_fee"]), ("method", "মাধ্যম", data["apply_method"])]):
        is_tinted = idx4 in [1, 2]
        g_bg = _make_minimal_card(460, 445, radius=36, fill=pal["tint"] if is_tinted else pal["card"], border=pal["hairline"], border_w=2)
        icon_sp = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(icon_sp).ellipse([6, 6, 114, 114], fill=(pal["card"] if is_tinted else pal["tint"]) + (255,))
        _draw_minimal_icon(ImageDraw.Draw(icon_sp), 60, 60, kind, pal["accent"] + (255,))
        s4_cards.append({
            "bg": g_bg, "icon": icon_sp,
            "lbl": _make_text_sprite(lbl, _get_style3_body_font, 46, 34, 380, 1, pal["accent"] if is_tinted else pal["muted"]),
            "val": _make_text_sprite(val, _get_style3_body_font, 54, 34, 405, 3, pal["ink"])
        })

    s5_hdr_sp = _make_text_sprite("আবেদনের সময়সীমা", _get_style3_display_font, 66, 48, 860, 1, pal["ink"])
    s5_left_c = _make_minimal_card(420, 390, radius=38, fill=pal["card"], border=pal["hairline"], border_w=2)
    draw_mixed_text(ImageDraw.Draw(s5_left_c), s5_left_c.width // 2, 95, "শুরু", _get_style3_body_font(44), 44, pal["muted"], anchor="mm")
    lf5, lsz5, ll5 = fit_multiline_font(ImageDraw.Draw(s5_left_c), data["start_date"], _get_style3_body_font, 58, 34, 360, 2)
    ly5 = 255 - ((len(ll5) - 1) * (lsz5 + 12)) // 2
    for l in ll5:
        draw_mixed_text(ImageDraw.Draw(s5_left_c), s5_left_c.width // 2, ly5, l, lf5, lsz5, pal["ink"], anchor="mm")
        ly5 += lsz5 + 12

    s5_right_c = _make_minimal_card(420, 390, radius=38, fill=pal["tint"], border=pal["accent"], border_w=3)
    draw_mixed_text(ImageDraw.Draw(s5_right_c), s5_right_c.width // 2, 95, "শেষ তারিখ", _get_style3_body_font(44), 44, pal["accent"], anchor="mm")
    rf5, rsz5, rl5 = fit_multiline_font(ImageDraw.Draw(s5_right_c), data["end_date"], _get_style3_body_font, 58, 34, 360, 2)
    ry5 = 255 - ((len(rl5) - 1) * (rsz5 + 12)) // 2
    for l in rl5:
        draw_mixed_text(ImageDraw.Draw(s5_right_c), s5_right_c.width // 2, ry5, l, rf5, rsz5, pal["accent"], anchor="mm")
        ry5 += rsz5 + 12

    s5_urg_sp = _make_minimal_card(740, 126, radius=63, fill=pal["accent"], shadow_alpha=24)
    draw_mixed_text(ImageDraw.Draw(s5_urg_sp), s5_urg_sp.width // 2, s5_urg_sp.height // 2, "সময়মতো আবেদন করুন", _get_style3_body_font(48), 48, (255, 255, 255), anchor="mm")

    s6_card_bg = _make_minimal_card(900, 740, radius=48, fill=pal["card"], border=pal["hairline"], border_w=2)
    s6_title_words = _make_word_sprites("যোগাযোগ (হোয়াটসঅ্যাপ)", _get_style3_display_font, 60, 42, 840, 1, pal["ink"], W // 2, 705)
    s6_pill_empty = _make_minimal_card(820, 188, radius=94, fill=pal["accent"])
    s6_num_sp = Image.new("RGBA", (780, 130), (0, 0, 0, 0))
    draw_mixed_text(ImageDraw.Draw(s6_num_sp), 390, 65, data["wa_formatted"], _get_style3_eng_font(82), 82, (255, 255, 255), anchor="mm")
    s6_pill_mask = Image.new("L", s6_pill_empty.size, 0)
    ImageDraw.Draw(s6_pill_mask).rounded_rectangle([22, 22, 842, 210], radius=94, fill=255)
    sheen_sp = Image.new("RGBA", (200, s6_pill_empty.height), (0, 0, 0, 0))
    ImageDraw.Draw(sheen_sp).polygon([(65, 0), (160, 0), (95, s6_pill_empty.height), (0, s6_pill_empty.height)], fill=(255, 255, 255, 65))
    s6_sub_words = _make_word_sprites("আবেদনের জন্য মেসেজ দিন", _get_style3_body_font, 52, 36, 840, 1, pal["muted"], W // 2, 1065)

    bounds = compute_motion_scene_bounds(duration)
    trans_styles = ["push_left", "curl", "push_left", "curl", "push_left"]
    trans_sec = min(0.42, duration * 0.03)
    countup_cache = {}

    def render_scene_frame(scene_id, local_t, abs_t):
        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)

        ax1 = int((abs_t * 50) % (W + 460)) - 230
        ax2 = int(W + 230 - ((abs_t * 42) % (W + 460)))
        fd.arc([ax1 - 105, 35, ax1 + 105, 245], start=20, end=210, fill=pal["shape"], width=5)
        fd.arc([ax2 - 115, H - 375, ax2 + 115, H - 145], start=190, end=370, fill=pal["shape"], width=5)
        fd.rounded_rectangle([ax1 + 40, 130, ax1 + 140, 142], radius=6, fill=pal["shape"])
        fd.rounded_rectangle([ax2 - 140, H - 315, ax2 - 40, H - 303], radius=6, fill=pal["shape"])

        if scene_id in [2, 3, 4, 5]:
            hy = int(100 + 120 * ease_out_cubic(local_t / 0.38)) if (scene_id == 2 and local_t < 0.38) else 220
            _paste_sprite(frame, hdr_left, 425, hy)
            _paste_sprite(frame, hdr_right, 895, hy)
            fd.polygon([(120, hy - 11), (132, hy), (120, hy + 11), (108, hy)], fill=pal["accent"])

        if scene_id == 1:
            sp_p = ease_out_back(min(1.0, local_t / 0.45))
            ang = -10.0 * (1.0 - min(1.0, local_t / 0.45))
            rot_seal = seal_sp.rotate(ang, resample=Image.BICUBIC, expand=True)
            _paste_sprite(frame, rot_seal, W // 2, 415 + int(7 * math.sin(abs_t * 2.4)), scale=0.35 + 0.65 * sp_p, opacity=min(1.0, local_t / 0.22))
            for idx_w, (wsp, wx, wy) in enumerate(s1_org_words):
                st = 0.14 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.32, rise_px=52)
            if local_t > 0.32:
                hl = int(185 * ease_out_cubic((local_t - 0.32) / 0.35))
                fd.rounded_rectangle([W // 2 - hl, 848, W // 2 + hl, 855], radius=3, fill=pal["accent"])
                fd.ellipse([W // 2 - 9, 842, W // 2 + 9, 860], fill=pal["accent"])
            if local_t > 0.42:
                bp = ease_out_back((local_t - 0.42) / 0.38)
                _paste_sprite(frame, s1_badge_sp, W // 2, 975, scale=0.68 + 0.32 * bp, opacity=min(1.0, (local_t - 0.42) / 0.2))
            for idx_h, (wsp, wx, wy) in enumerate(s1_hook_words):
                st = 0.60 + idx_h * 0.07
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.30, rise_px=40)

        elif scene_id == 2:
            cp = ease_out_back(min(1.0, local_t / 0.45))
            _paste_sprite(frame, s2_card_sp, W // 2, 685, scale=0.78 + 0.22 * cp, opacity=min(1.0, local_t / 0.22))
            if data["vac_num"] > 0:
                cnt_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.14) / 1.25))
                cur_val = max(1, int(round(data["vac_num"] * cnt_p)))
                if cur_val not in countup_cache:
                    if len(countup_cache) > 45: countup_cache.clear()
                    countup_cache[cur_val] = _make_text_sprite(to_bn_num(cur_val) + "টি", _get_style3_body_font, 175, 72, 820, 1, pal["ink"])
                land_t = local_t - 1.39
                pop_sc = (1.0 + 0.12 * math.sin((land_t / 0.35) * math.pi)) if 0.0 <= land_t <= 0.35 else 1.0
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 755, scale=pop_sc)
            else:
                _paste_sprite(frame, s2_static_num, W // 2, 755, scale=0.78 + 0.22 * cp, opacity=min(1.0, local_t / 0.28))

            if local_t > 0.65:
                tp = ease_out_back((local_t - 0.65) / 0.40)
                _paste_sprite(frame, s2_tag_sp, W // 2, 1085 + int(45 * (1.0 - min(1.0, tp))), scale=0.82 + 0.18 * tp, opacity=min(1.0, (local_t - 0.65) / 0.22))

        elif scene_id == 3:
            _render_masked_rise(frame, s3_hdr_sp, W // 2, 372, local_t / 0.30, rise_px=36)
            hl_w = int(150 * ease_out_cubic(min(1.0, local_t / 0.42)))
            fd.rounded_rectangle([W // 2 - hl_w, 422, W // 2 + hl_w, 428], radius=3, fill=pal["accent"])

            top_band = frame.crop((0, 0, W, 452))
            bot_band = frame.crop((0, 1465, W, H))

            scene_len = (bounds[3] - bounds[2]) * duration
            num_b = len(s3_batches)
            slice_t = scene_len / float(num_b)
            b_idx = min(num_b - 1, int(local_t / slice_t))
            bt = local_t - b_idx * slice_t
            batch_trans = 0.40

            def draw_b(entries, cur_bt, extra_dy=0, fade_m=1.0):
                active_c = int(abs_t * 0.45) % max(1, len(entries))
                for idx_c, c in enumerate(entries):
                    st = 0.06 + idx_c * 0.20
                    if cur_bt <= st: continue
                    cp = ease_out_back((cur_bt - st) / 0.34)
                    act_sc = 1.018 if (cur_bt > 1.3 and idx_c == active_c and extra_dy == 0) else 1.0
                    dx = int(((-1 if idx_c % 2 == 0 else 1) * 180) * (1.0 - min(1.0, cp)))
                    cx = W // 2 + dx
                    cy = c["cy"] + extra_dy
                    op = min(1.0, (cur_bt - st) / 0.18) * fade_m
                    _paste_sprite(frame, c["bg"], cx, cy, scale=(0.94 + 0.06 * cp) * act_sc, opacity=op)
                    _paste_sprite(frame, c["idx"], cx - 390, cy - int(c["h"] * 0.20), scale=0.6 + 0.4 * ease_out_back((cur_bt - st) / 0.30), opacity=op)
                    if cur_bt > st + 0.05:
                        _render_masked_rise(frame, c["title"], cx - 55, cy - int(c["h"] * 0.18), (cur_bt - st - 0.05) / 0.26, rise_px=24)
                    if cur_bt > st + 0.10:
                        _paste_sprite(frame, c["badge"], cx + 315, cy - int(c["h"] * 0.16), scale=0.55 + 0.45 * ease_out_back((cur_bt - st - 0.10) / 0.28), opacity=fade_m)
                    if cur_bt > st + 0.15:
                        _render_masked_rise(frame, c["meta"], cx + 15, cy + int(c["h"] * 0.24), (cur_bt - st - 0.15) / 0.24, rise_px=20)

            if b_idx > 0 and bt < batch_trans:
                tp = ease_in_out_cubic(bt / batch_trans)
                draw_b(s3_batches[b_idx - 1], slice_t, extra_dy=-int(960 * tp), fade_m=1.0 - tp)
                draw_b(s3_batches[b_idx], bt, extra_dy=int(960 * (1.0 - tp)), fade_m=tp)
            else:
                draw_b(s3_batches[b_idx], bt)

            frame.paste(top_band, (0, 0))
            frame.paste(bot_band, (0, 1465))

        elif scene_id == 4:
            _render_masked_rise(frame, s4_hdr_sp, W // 2, 372, local_t / 0.30, rise_px=36)
            hl_w = int(120 * ease_out_cubic(min(1.0, local_t / 0.42)))
            fd.rounded_rectangle([W // 2 - hl_w, 422, W // 2 + hl_w, 428], radius=3, fill=pal["accent"])
            positions = [(295, 700), (785, 700), (295, 1175), (785, 1175)]
            active_idx = int(abs_t * 0.9) % 4
            for idx, item in enumerate(s4_cards):
                st = 0.08 + idx * 0.16
                if local_t <= st: continue
                gx, gy = positions[idx]
                cp = ease_out_back((local_t - st) / 0.34)
                op = min(1.0, (local_t - st) / 0.18)
                act_sc = 1.028 if (local_t > 1.2 and idx == active_idx) else 1.0
                _paste_sprite(frame, item["bg"], gx, gy, scale=(0.78 + 0.22 * cp) * act_sc, opacity=op)
                if local_t > st + 0.06:
                    _paste_sprite(frame, item["icon"], gx, gy - 115 + int(4 * math.sin(abs_t * 2.5 + idx)), scale=0.45 + 0.55 * ease_out_back((local_t - st - 0.06) / 0.30))
                if local_t > st + 0.12:
                    _render_masked_rise(frame, item["lbl"], gx, gy - 10, (local_t - st - 0.12) / 0.24, rise_px=20)
                if local_t > st + 0.18:
                    _paste_sprite(frame, item["val"], gx, gy + 94, scale=0.74 + 0.26 * ease_out_back((local_t - st - 0.18) / 0.30), opacity=op)

        elif scene_id == 5:
            _render_masked_rise(frame, s5_hdr_sp, W // 2, 410, local_t / 0.30, rise_px=38)
            if local_t > 0.08:
                p1 = ease_out_back((local_t - 0.08) / 0.40)
                _paste_sprite(frame, s5_left_c, 290, 745, scale=0.78 + 0.22 * p1, opacity=min(1.0, (local_t - 0.08) / 0.22))
            if local_t > 0.22:
                p2 = ease_out_back((local_t - 0.22) / 0.40)
                _paste_sprite(frame, s5_right_c, 790, 745, scale=0.78 + 0.22 * p2, opacity=min(1.0, (local_t - 0.22) / 0.22))
            if local_t > 0.34:
                pulse_x = W // 2 + int(10 * math.sin(abs_t * 4.8))
                fd.ellipse([pulse_x - 38, 707, pulse_x + 38, 783], fill=pal["accent"])
                fd.line([(pulse_x - 10, 729), (pulse_x + 12, 745), (pulse_x - 10, 761)], fill=(255, 255, 255), width=7)
            if local_t > 0.50:
                up = ease_out_back((local_t - 0.50) / 0.38)
                _paste_sprite(frame, s5_urg_sp, W // 2, 1110, scale=(0.8 + 0.2 * up) * (1.0 + 0.025 * math.sin(abs_t * 4.2)), opacity=min(1.0, (local_t - 0.50) / 0.24))

        elif scene_id == 6:
            fp = ease_out_back(min(1.0, local_t / 0.42))
            _paste_sprite(frame, s6_card_bg, W // 2, 760, scale=0.82 + 0.18 * fp, opacity=min(1.0, local_t / 0.22))
            wp = ease_out_back(min(1.0, max(0.0, local_t - 0.08) / 0.42))
            _paste_sprite(frame, wa_sp, W // 2, 505 + int(8 * math.sin(abs_t * 2.8)), scale=0.3 + 0.7 * wp, opacity=min(1.0, local_t / 0.24))
            for idx_w, (wsp, wx, wy) in enumerate(s6_title_words):
                st = 0.16 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.28, rise_px=34)
            if local_t > 0.34:
                pp = ease_out_back((local_t - 0.34) / 0.40)
                pill_sc = s6_pill_empty.resize((max(40, int(s6_pill_empty.width * max(0.15, min(1.0, pp)))), s6_pill_empty.height), Image.BILINEAR)
                _paste_sprite(frame, pill_sc, W // 2, 890, opacity=min(1.0, (local_t - 0.34) / 0.18))
            if local_t > 0.48:
                np = ease_out_cubic((local_t - 0.48) / 0.36)
                num_crop = s6_num_sp.crop((0, 0, max(12, int(s6_num_sp.width * np)), s6_num_sp.height))
                frame.paste(num_crop, ((W - s6_num_sp.width) // 2, 890 - s6_num_sp.height // 2), num_crop.getchannel("A"))
                if np >= 0.99:
                    cs = (local_t - 0.84) % 2.1
                    if 0.0 <= cs <= 0.75:
                        tmp_sh = Image.new("RGBA", s6_pill_empty.size, (0, 0, 0, 0))
                        tmp_sh.paste(sheen_sp, (int(-200 + (s6_pill_empty.width + 200) * (cs / 0.75)), 0))
                        masked_sh = Image.new("RGBA", s6_pill_empty.size, (0, 0, 0, 0))
                        masked_sh.paste(tmp_sh, (0, 0), s6_pill_mask)
                        _paste_sprite(frame, masked_sh, W // 2, 890)
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
