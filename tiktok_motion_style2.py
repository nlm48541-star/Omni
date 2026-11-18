# -*- coding: utf-8 -*-
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont

from tiktok_designer import (
    find_font_file, draw_mixed_text, fit_single_line_font, fit_multiline_font
)
from motion_storyboard import build_dynamic_storyboard, to_bn_num
from tiktok_motion_engine import (
    ease_out_cubic, ease_out_back,
    _paste_sprite, _render_masked_rise, _make_minimal_card,
    _make_text_sprite, _make_word_sprites, _make_whatsapp_sprite,
    _draw_minimal_icon, _make_curl_sprite, _apply_transition,
    _stream_frames_to_ffmpeg, _draw_box_text
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

def _make_dark_icon(kind, pal, size=116):
    sp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.rounded_rectangle([4, 4, size - 4, size - 4], radius=26, fill=pal["accent_soft"] + (255,), outline=pal["accent"] + (255,), width=3)
    _draw_minimal_icon(d, size // 2, size // 2, kind, pal["accent"] + (255,))
    return sp

def render_motion_style_2(job_data, audio_path, output_path, fps=24, script_index=0):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    pal = random.choice(DARK_PALETTES)
    sb = build_dynamic_storyboard(job_data, audio_path, duration, script_index=script_index)
    core, beats = sb["core"], sb["beats"]

    print(f"  [🌌 Motion Style #2 (Dark Executive)] Palette={pal['name']}, Beats={len(beats)}, Duration={duration:.1f}s")

    bg_base = Image.new("RGB", (W, H), pal["bg"])
    curl_sp = _make_curl_sprite(H)
    wa_sp = _make_whatsapp_sprite()

    hdr_sp = _make_minimal_card(920, 122, radius=28, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
    hd = ImageDraw.Draw(hdr_sp)
    hf, hsz = fit_single_line_font(hd, core["org"], _get_style2_font, 46, 28, 600)
    draw_mixed_text(hd, 94, 83, core["org"], hf, hsz, pal["ink"], anchor="lm")
    hd.rounded_rectangle([714, 48, 916, 118], radius=20, fill=pal["accent_soft"] + (255,), outline=pal["accent"] + (255,), width=2)
    draw_mixed_text(hd, 815, 83, "বিজ্ঞপ্তি", _get_style2_font(34), 34, pal["accent"], anchor="mm")

    emblem_core = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    ed = ImageDraw.Draw(emblem_core)
    ed.ellipse([20, 20, 220, 220], fill=pal["card"] + (255,), outline=pal["accent"] + (255,), width=6)
    _draw_minimal_icon(ed, 120, 120, "method", pal["accent"] + (255,))

    beat_assets = []
    bn_nums = ["০১", "০২", "০৩", "০৪"]
    countup_cache, gauge_cache = {}, {}

    for bt in beats:
        k = bt["kind"]
        a = {"kind": k, "hdr_sp": _make_text_sprite(bt.get("header", ""), _get_style2_font, 60, 42, 840, 1, pal["ink"])}
        if k == "intro":
            a["org_words"] = _make_word_sprites(core["org"], _get_style2_font, 90, 52, 940, 2, pal["ink"], W // 2, 685)
            b_sp = _make_minimal_card(600, 130, radius=65, fill=pal["accent"], shadow_alpha=45)
            bf, bsz = fit_single_line_font(ImageDraw.Draw(b_sp), core["cat_badge"], _get_style2_font, 58, 38, 520)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, core["cat_badge"], bf, bsz, pal["bg"], anchor="mm")
            a["badge_sp"] = b_sp
            a["hook_words"] = _make_word_sprites(core["hook_short"], _get_style2_font, 54, 34, 880, 2, pal["muted"], W // 2, 1155)

        elif k == "vacancy":
            a["static_num"] = _make_text_sprite(bt["value"], _get_style2_font, 158, 66, 410, 1, pal["ink"])
            t_sp = _make_minimal_card(860, 132, radius=32, fill=pal["card"], border=pal["accent"], border_w=2, shadow_alpha=45)
            tf2, tsz2, tl2 = fit_multiline_font(ImageDraw.Draw(t_sp), bt["tag"], _get_style2_font, 46, 30, 780, 2)
            ty2 = t_sp.height // 2 - ((len(tl2) - 1) * (tsz2 + 10)) // 2
            for l2 in tl2:
                draw_mixed_text(ImageDraw.Draw(t_sp), t_sp.width // 2, ty2, l2, tf2, tsz2, pal["accent"], anchor="mm")
                ty2 += tsz2 + 10
            a["tag_sp"] = t_sp
            a["chips"] = [_draw_box_text(860, 122, txt, _get_style2_font, 38, 26, pal["muted"], pal["card"], pal["border"], max_lines=2, pad=22, radius=26) for txt in bt.get("sub_chips", [])[:1]]

        elif k == "post_spotlight":
            it = bt["post"]
            a["card_bg"] = _make_minimal_card(920, 610, radius=36, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
            a["idx_badge"] = _make_minimal_card(104, 104, radius=24, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=8, shadow_alpha=0)
            draw_mixed_text(ImageDraw.Draw(a["idx_badge"]), a["idx_badge"].width // 2, a["idx_badge"].height // 2, bn_nums[(bt["index"] - 1) % 4], _get_style2_font(42), 42, pal["accent"], anchor="mm")
            a["title_sp"] = _make_text_sprite(it["post_name"], _get_style2_font, 52, 28, 670, 3, pal["ink"], align="lm")
            b_sp = _make_minimal_card(320, 114, radius=28, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=10, shadow_alpha=0)
            vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], _get_style2_font, 56, 30, 275)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
            a["vac_sp"] = b_sp
            a["qual_sp"] = _draw_box_text(830, 118, f"যোগ্যতা: {it['qualification']}", _get_style2_font, 38, 26, pal["ink"], pal["bg"], pal["border"], max_lines=2, pad=8, radius=24)
            a["grade_sp"] = _draw_box_text(830, 118, f"গ্রেড/বেতন: {it['salary_grade']}", _get_style2_font, 38, 26, pal["muted"], pal["bg"], pal["border"], max_lines=2, pad=8, radius=24)

        elif k == "post_pair":
            cards = []
            for idx_p, it in enumerate(bt["posts"]):
                cy = 670 if len(bt["posts"]) == 1 else ([660, 1015][idx_p])
                bg_c = _make_minimal_card(930, 295, radius=28, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
                num_b = _make_minimal_card(96, 96, radius=22, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=8, shadow_alpha=0)
                draw_mixed_text(ImageDraw.Draw(num_b), num_b.width // 2, num_b.height // 2, bn_nums[idx_p % 4], _get_style2_font(38), 38, pal["accent"], anchor="mm")
                t_sp = _make_text_sprite(it["post_name"], _get_style2_font, 48, 28, 465, 2, pal["ink"], align="lm")
                v_sp = _make_text_sprite(it["vacancy"], _get_style2_font, 52, 28, 225, 1, pal["accent"], align="rm")
                m_sp = _make_text_sprite(it["meta"], _get_style2_font, 38, 26, 720, 2, pal["muted"], align="lm")
                cards.append({"bg": bg_c, "idx": num_b, "title": t_sp, "vac": v_sp, "meta": m_sp, "cy": cy, "h": 295})
            a["cards"] = cards

        elif k in ("focus_card", "steps", "highlight"):
            a["hero_bg"] = _make_minimal_card(920, 265, radius=32, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
            a["icon_sp"] = _make_dark_icon(bt.get("icon", "info"), pal, size=116)
            a["lbl_sp"] = _make_text_sprite(bt.get("main_label", ""), _get_style2_font, 38, 28, 670, 1, pal["muted"], align="lm")
            a["val_sp"] = _make_text_sprite(bt.get("main_val", ""), _get_style2_font, 50, 30, 680, 2, pal["accent"] if k == "focus_card" else pal["ink"], align="lm")
            chips = []
            for idx_c, ch_txt in enumerate(bt.get("sub_chips", [])[:3]):
                c_bg = _make_minimal_card(920, 142, radius=26, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=40)
                n_bg = _make_minimal_card(74, 74, radius=20, fill=pal["accent_soft"], border=pal["accent"], border_w=2, pad=8, shadow_alpha=0)
                draw_mixed_text(ImageDraw.Draw(n_bg), n_bg.width // 2, n_bg.height // 2, bn_nums[idx_c % 4], _get_style2_font(34), 34, pal["accent"], anchor="mm")
                t_sp = _make_text_sprite(ch_txt, _get_style2_font, 40, 26, 735, 2, pal["ink"], align="lm")
                chips.append({"bg": c_bg, "num": n_bg, "txt": t_sp})
            a["chips"] = chips

        elif k == "deadline":
            a["card_bg"] = _make_minimal_card(920, 500, radius=36, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45)
            a["lbl1"] = _make_text_sprite("শুরুর তারিখ", _get_style2_font, 38, 28, 320, 1, pal["muted"], align="lm")
            a["d1"] = _make_text_sprite(bt["start_date"], _get_style2_font, 56, 34, 620, 2, pal["ink"], align="lm")
            a["lbl2"] = _make_text_sprite("শেষ তারিখ", _get_style2_font, 38, 28, 320, 1, pal["accent"], align="lm")
            a["d2"] = _make_text_sprite(bt["end_date"], _get_style2_font, 56, 34, 620, 2, pal["accent"], align="lm")
            a["urg_sp"] = _make_minimal_card(760, 120, radius=60, fill=pal["accent_soft"], border=pal["accent"], border_w=3, shadow_alpha=35)
            draw_mixed_text(ImageDraw.Draw(a["urg_sp"]), a["urg_sp"].width // 2, a["urg_sp"].height // 2, "সময়মতো আবেদন করুন", _get_style2_font(46), 46, pal["accent"], anchor="mm")

        elif k == "overview_grid":
            rows = []
            for kind_i, lbl_i, val_i in bt["items"]:
                rows.append({
                    "bg": _make_minimal_card(930, 200, radius=28, fill=pal["card"], border=pal["border"], border_w=2, shadow_alpha=45),
                    "icon": _make_dark_icon(kind_i, pal, size=112),
                    "lbl": _make_text_sprite(lbl_i, _get_style2_font, 42, 30, 230, 1, pal["muted"], align="lm"),
                    "val": _make_text_sprite(val_i, _get_style2_font, 50, 34, 495, 2, pal["ink"], align="rm")
                })
            a["rows"] = rows

        elif k == "cta":
            a["title_words"] = _make_word_sprites("যোগাযোগ (হোয়াটসঅ্যাপ)", _get_style2_font, 64, 42, 920, 1, pal["ink"], W // 2, 660)
            a["pill_bg"] = _make_minimal_card(910, 204, radius=102, fill=pal["accent"], shadow_alpha=45)
            a["num_sp"] = Image.new("RGBA", (850, 130), (0, 0, 0, 0))
            draw_mixed_text(ImageDraw.Draw(a["num_sp"]), 425, 65, bt["wa_formatted"], _get_style2_eng_font(84), 84, pal["bg"], anchor="mm")
            a["pill_mask"] = Image.new("L", a["pill_bg"].size, 0)
            ImageDraw.Draw(a["pill_mask"]).rounded_rectangle([22, 22, 932, 226], radius=102, fill=255)
            a["sheen_sp"] = Image.new("RGBA", (220, a["pill_bg"].height), (0, 0, 0, 0))
            ImageDraw.Draw(a["sheen_sp"]).polygon([(70, 0), (170, 0), (100, a["pill_bg"].height), (0, a["pill_bg"].height)], fill=(255, 255, 255, 85))
            a["sub_words"] = _make_word_sprites("আবেদনের জন্য মেসেজ দিন", _get_style2_font, 54, 36, 900, 1, pal["ink"], W // 2, 1075)

        beat_assets.append(a)

    trans_styles = ["push_left", "curl"]
    trans_sec = 0.34

    def render_beat_frame(b_idx, local_t, abs_t):
        bt = beats[b_idx]
        a = beat_assets[b_idx]
        k = bt["kind"]

        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)

        bx1 = int((abs_t * 68) % (W + 380)) - 260
        bx2 = int(W + 260 - ((abs_t * 52) % (W + 380)))
        fd.rounded_rectangle([bx1, 130, bx1 + 220, 135], radius=2, fill=pal["track"])
        fd.rounded_rectangle([bx2, H - 310, bx2 + 200, H - 305], radius=2, fill=pal["track"])
        fd.ellipse([bx1 + 235, 127, bx1 + 247, 139], fill=pal["accent"])
        fd.ellipse([bx2 - 28, H - 313, bx2 - 16, H - 301], fill=pal["accent"])

        if k not in ("intro", "cta"):
            hdr_y = int(105 + 120 * ease_out_cubic(local_t / 0.35)) if (b_idx == 1 and local_t < 0.35) else 225
            _paste_sprite(frame, hdr_sp, W // 2, hdr_y)
            dot_r = 9 + int(3 * math.sin(abs_t * 5.0))
            fd.ellipse([124 - dot_r, hdr_y - dot_r, 124 + dot_r, hdr_y + dot_r], fill=pal["accent"])

            _render_masked_rise(frame, a["hdr_sp"], W // 2, 360, local_t / 0.28, rise_px=34)
            hl_w = int(145 * ease_out_cubic(min(1.0, local_t / 0.40)))
            fd.rounded_rectangle([W // 2 - hl_w, 408, W // 2 + hl_w, 414], radius=3, fill=pal["accent"])

        if k == "intro":
            ep = ease_out_back(min(1.0, local_t / 0.42))
            _paste_sprite(frame, emblem_core, W // 2, 415, scale=0.3 + 0.7 * ep, opacity=min(1.0, local_t / 0.20))
            orb_r = 148
            fd.ellipse([W // 2 - orb_r, 415 - orb_r, W // 2 + orb_r, 415 + orb_r], outline=pal["border"], width=3)
            ang = abs_t * 1.6
            ox, oy = W // 2 + int(orb_r * math.cos(ang)), 415 + int(orb_r * math.sin(ang))
            fd.ellipse([ox - 10, oy - 10, ox + 10, oy + 10], fill=pal["accent"])
            for idx_w, (wsp, wx, wy) in enumerate(a["org_words"]):
                st = 0.12 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.30, rise_px=42)
            if local_t > 0.28:
                hl = int(210 * ease_out_cubic((local_t - 0.28) / 0.32))
                fd.rounded_rectangle([W // 2 - hl, 845, W // 2 + hl, 852], radius=3, fill=pal["accent"])
            if local_t > 0.38:
                bp = ease_out_back((local_t - 0.38) / 0.36)
                _paste_sprite(frame, a["badge_sp"], W // 2, 975, scale=0.65 + 0.35 * bp, opacity=min(1.0, (local_t - 0.38) / 0.18))
            for idx_h, (wsp, wx, wy) in enumerate(a["hook_words"]):
                st = 0.56 + idx_h * 0.07
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.28, rise_px=34)

        elif k == "vacancy":
            arc_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.08) / 1.25))
            g_key = int(round(arc_p * 60))
            if g_key not in gauge_cache:
                if len(gauge_cache) > 65: gauge_cache.clear()
                gauge_cache[g_key] = _make_aa_gauge_sprite(225, pal["track"], pal["accent"], pal["card"], g_key / 60.0)
            _paste_sprite(frame, gauge_cache[g_key], W // 2, 695)
            if bt["num"] > 0:
                cur_val = max(1, int(round(bt["num"] * arc_p)))
                if cur_val not in countup_cache:
                    if len(countup_cache) > 45: countup_cache.clear()
                    countup_cache[cur_val] = _make_text_sprite(to_bn_num(cur_val) + "টি", _get_style2_font, 158, 66, 410, 1, pal["ink"])
                land_t = local_t - 1.33
                pop_sc = (1.0 + 0.12 * math.sin((land_t / 0.35) * math.pi)) if 0.0 <= land_t <= 0.35 else 1.0
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 695, scale=pop_sc)
            else:
                _paste_sprite(frame, a["static_num"], W // 2, 695, scale=0.78 + 0.22 * ease_out_back(min(1.0, local_t / 0.40)))
            if local_t > 0.65:
                tp = ease_out_back((local_t - 0.65) / 0.38)
                _paste_sprite(frame, a["tag_sp"], W // 2, 1055 + int(35 * (1.0 - min(1.0, tp))), scale=0.84 + 0.16 * tp, opacity=min(1.0, (local_t - 0.65) / 0.20))
            if a["chips"] and local_t > 1.35:
                chp = ease_out_back((local_t - 1.35) / 0.36)
                _paste_sprite(frame, a["chips"][0], W // 2, 1235 + int(25 * (1.0 - min(1.0, chp))), scale=0.88 + 0.12 * chp, opacity=min(1.0, (local_t - 1.35) / 0.20))

        elif k == "post_spotlight":
            cp = ease_out_back(min(1.0, local_t / 0.35))
            _paste_sprite(frame, a["card_bg"], W // 2, 855, scale=0.90 + 0.10 * cp, opacity=min(1.0, local_t / 0.20))
            bar_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.12) / 0.38))
            if bar_p > 0.02:
                fd.rounded_rectangle([96, 595, 108, 595 + max(12, int(515 * bar_p))], radius=6, fill=pal["accent"])
            if local_t > 0.10:
                _paste_sprite(frame, a["idx_badge"], 195, 660, scale=0.65 + 0.35 * ease_out_back((local_t - 0.10) / 0.30))
            if local_t > 0.20:
                _render_masked_rise(frame, a["title_sp"], 610, 660, (local_t - 0.20) / 0.30, rise_px=28)
            if local_t > 0.65:
                vp = ease_out_back((local_t - 0.65) / 0.34)
                pulse = 1.0 + (0.025 * math.sin(abs_t * 4.5) if local_t > 1.4 else 0.0)
                _paste_sprite(frame, a["vac_sp"], W // 2, 822, scale=(0.68 + 0.32 * vp) * pulse)
            if local_t > 1.15:
                qp = ease_out_cubic((local_t - 1.15) / 0.32)
                _paste_sprite(frame, a["qual_sp"], W // 2 + int(90 * (1.0 - qp)), 965, opacity=qp)
            if local_t > 1.75:
                gp = ease_out_cubic((local_t - 1.75) / 0.32)
                _paste_sprite(frame, a["grade_sp"], W // 2 - int(90 * (1.0 - gp)), 1098, opacity=gp)

        elif k == "post_pair":
            active_c = int(local_t / 1.4) % max(1, len(a["cards"]))
            for idx_c, c in enumerate(a["cards"]):
                st = 0.05 + idx_c * 0.72
                if local_t <= st: continue
                cp = ease_out_cubic((local_t - st) / 0.32)
                act_sc = 1.02 if (local_t > 1.5 and idx_c == active_c) else 1.0
                cx = W // 2 + int(180 * (1.0 - cp))
                cy = c["cy"]
                op = min(1.0, (local_t - st) / 0.18)
                _paste_sprite(frame, c["bg"], cx, cy, scale=act_sc, opacity=op)
                bar_p = ease_out_cubic((local_t - (st + 0.06)) / 0.28)
                if bar_p > 0.02:
                    y_tb = cy - c["h"] // 2 + 22
                    fd.rounded_rectangle([cx - 450, y_tb, cx - 440, y_tb + max(8, int((c["h"] - 44) * bar_p))], radius=5, fill=pal["accent"])
                _paste_sprite(frame, c["idx"], cx - 365, cy, scale=0.7 + 0.3 * ease_out_back((local_t - st) / 0.28), opacity=op)
                if local_t > st + 0.12:
                    _render_masked_rise(frame, c["title"], cx - 40, cy - 45, (local_t - (st + 0.12)) / 0.26, rise_px=22)
                if local_t > st + 0.28:
                    _paste_sprite(frame, c["vac"], cx + 315, cy - 45, scale=0.6 + 0.4 * ease_out_back((local_t - (st + 0.28)) / 0.26))
                if local_t > st + 0.44:
                    _render_masked_rise(frame, c["meta"], cx + 85, cy + 68, (local_t - (st + 0.44)) / 0.26, rise_px=18)

        elif k in ("focus_card", "steps", "highlight"):
            cp = ease_out_back(min(1.0, local_t / 0.36))
            _paste_sprite(frame, a["hero_bg"], W // 2, 605, scale=0.88 + 0.12 * cp, opacity=min(1.0, local_t / 0.20))
            if local_t > 0.08:
                ip = ease_out_back((local_t - 0.08) / 0.32)
                _paste_sprite(frame, a["icon_sp"], 178, 605 + int(4 * math.sin(abs_t * 3.0)), scale=0.5 + 0.5 * ip)
            if local_t > 0.18:
                _render_masked_rise(frame, a["lbl_sp"], 625, 540, (local_t - 0.18) / 0.26, rise_px=20)
            if local_t > 0.32:
                _render_masked_rise(frame, a["val_sp"], 625, 635, (local_t - 0.32) / 0.30, rise_px=28)
            uw = int(840 * ease_out_cubic(min(1.0, max(0.0, local_t - 0.20) / 0.45)))
            if uw > 10:
                fd.rounded_rectangle([W // 2 - 420, 720, W // 2 - 420 + uw, 725], radius=2, fill=pal["accent"])

            n_ch = len(a["chips"])
            active_chip = int(max(0, local_t - 1.8) / 1.1) % max(1, n_ch)
            for idx_c, ch in enumerate(a["chips"]):
                st = 0.70 + idx_c * 0.72
                if local_t <= st: continue
                cy = 880 + idx_c * 170
                chp = ease_out_cubic((local_t - st) / 0.32)
                dx = int(160 * (1.0 - chp)) * (-1 if idx_c % 2 == 0 else 1)
                act_sc = 1.022 if (local_t > 2.2 and idx_c == active_chip) else 1.0
                _paste_sprite(frame, ch["bg"], W // 2 + dx, cy, scale=act_sc, opacity=chp)
                _paste_sprite(frame, ch["num"], 158 + dx, cy, scale=0.65 + 0.35 * ease_out_back((local_t - st) / 0.30), opacity=chp)
                if local_t > st + 0.14:
                    _render_masked_rise(frame, ch["txt"], 605 + dx, cy, (local_t - (st + 0.14)) / 0.26, rise_px=20)

        elif k == "deadline":
            cp = ease_out_back(min(1.0, local_t / 0.38))
            _paste_sprite(frame, a["card_bg"], W // 2, 745, scale=0.84 + 0.16 * cp, opacity=min(1.0, local_t / 0.22))
            if local_t > 0.14:
                fd.rounded_rectangle([182, 610, 190, 880], radius=4, fill=pal["track"])
                tp_line = ease_out_cubic((local_t - 0.14) / 0.50)
                fd.rounded_rectangle([182, 610, 190, 610 + int(270 * tp_line)], radius=4, fill=pal["accent"])
                fd.ellipse([162, 586, 210, 634], fill=pal["accent"])
                fd.ellipse([174, 598, 198, 622], fill=pal["ink"])
                _render_masked_rise(frame, a["lbl1"], 415, 578, (local_t - 0.14) / 0.24, rise_px=20)
                _render_masked_rise(frame, a["d1"], 565, 644, (local_t - 0.22) / 0.28, rise_px=28)
            if local_t > 0.48:
                flow_y = int(610 + 270 * ((abs_t * 0.95) % 1.0))
                fd.ellipse([174, flow_y - 12, 198, flow_y + 12], fill=(255, 255, 255))
                fd.ellipse([162, 856, 210, 904], fill=pal["accent"])
                _render_masked_rise(frame, a["lbl2"], 415, 848, (local_t - 0.48) / 0.24, rise_px=20)
                dp2 = ease_out_back((local_t - 0.58) / 0.32)
                _paste_sprite(frame, a["d2"], 565, 914, scale=0.78 + 0.22 * dp2)
            if local_t > 1.05:
                up = ease_out_back((local_t - 1.05) / 0.36)
                _paste_sprite(frame, a["urg_sp"], W // 2, 1145, scale=(0.82 + 0.18 * up) * (1.0 + 0.025 * math.sin(abs_t * 4.5)), opacity=min(1.0, (local_t - 1.05) / 0.22))

        elif k == "overview_grid":
            ys4 = [565, 792, 1019, 1246]
            for idx, r in enumerate(a["rows"]):
                st = 0.06 + idx * 0.20
                if local_t <= st: continue
                rp = ease_out_cubic((local_t - st) / 0.30)
                dx = int(((-1 if idx % 2 == 0 else 1) * 200) * (1.0 - rp))
                ry = ys4[idx]
                _paste_sprite(frame, r["bg"], W // 2 + dx, ry, opacity=rp)
                _paste_sprite(frame, r["icon"], 155 + dx, ry, scale=0.55 + 0.45 * ease_out_back((local_t - st) / 0.28), opacity=rp)
                _render_masked_rise(frame, r["lbl"], 355 + dx, ry, (local_t - st - 0.05) / 0.24, rise_px=20)
                _paste_sprite(frame, r["val"], 725 + dx, ry, scale=0.75 + 0.25 * ease_out_back((local_t - st - 0.08) / 0.26), opacity=rp)

        elif k == "cta":
            for ri in range(2):
                rp = ((abs_t * 0.65) + ri * 0.5) % 1.0
                rr = int(125 + 150 * rp)
                fd.ellipse([W // 2 - rr, 435 - rr, W // 2 + rr, 435 + rr], outline=pal["border"], width=3)
            ang = abs_t * 1.8
            ox, oy = W // 2 + int(165 * math.cos(ang)), 435 + int(165 * math.sin(ang))
            fd.ellipse([ox - 8, oy - 8, ox + 8, oy + 8], fill=pal["accent"])
            wp = ease_out_back(min(1.0, local_t / 0.40))
            _paste_sprite(frame, wa_sp, W // 2, 435 + int(8 * math.sin(abs_t * 2.8)), scale=0.25 + 0.75 * wp, opacity=min(1.0, local_t / 0.20))
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
        fd.rounded_rectangle([140, 1506, 940, 1516], radius=5, fill=pal["track"])
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
