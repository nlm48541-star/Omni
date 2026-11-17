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
    _stream_frames_to_ffmpeg
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

def _make_warm_icon(kind, pal, size=118):
    sp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.ellipse([4, 4, size - 4, size - 4], fill=pal["tint"] + (255,), outline=pal["accent"] + (200,), width=3)
    _draw_minimal_icon(d, size // 2, size // 2, kind, pal["accent"] + (255,))
    return sp

def render_motion_style_3(job_data, audio_path, output_path, fps=24, script_index=0):
    if not os.path.exists(audio_path):
        return False

    from video_engine import get_audio_duration
    duration = max(6.0, get_audio_duration(audio_path))
    W, H = 1080, 1920
    pal = random.choice(WARM_PALETTES)
    sb = build_dynamic_storyboard(job_data, audio_path, duration, script_index=script_index)
    core, beats = sb["core"], sb["beats"]

    print(f"  [🎨 Motion Style #3 (Warm Glass Editorial)] Palette={pal['name']}, Beats={len(beats)}, Duration={duration:.1f}s")

    bg_base = Image.new("RGB", (W, H), pal["bg"])
    curl_sp = _make_curl_sprite(H)
    wa_sp = _make_whatsapp_sprite()

    hdr_left = _make_minimal_card(695, 114, radius=57, fill=pal["card"], border=pal["hairline"], border_w=2)
    hl_d = ImageDraw.Draw(hdr_left)
    hf, hsz = fit_single_line_font(hl_d, core["org"], _get_style3_body_font, 44, 28, 575)
    draw_mixed_text(hl_d, 90, 79, core["org"], hf, hsz, pal["ink"], anchor="lm")

    hdr_right = _make_minimal_card(205, 114, radius=57, fill=pal["accent"], shadow_alpha=24)
    draw_mixed_text(ImageDraw.Draw(hdr_right), hdr_right.width // 2, hdr_right.height // 2, "বিজ্ঞপ্তি", _get_style3_body_font(36), 36, (255, 255, 255), anchor="mm")

    seal_sp = Image.new("RGBA", (280, 280), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal_sp)
    sd.rounded_rectangle([24, 24, 256, 256], radius=64, fill=pal["tint"] + (255,), outline=pal["accent"] + (255,), width=8)
    _draw_minimal_icon(sd, 140, 140, "fee", pal["accent"] + (255,))

    beat_assets = []
    bn_nums = ["০১", "০২", "০৩", "০৪"]
    countup_cache = {}

    for bt in beats:
        k = bt["kind"]
        a = {"kind": k, "hdr_sp": _make_text_sprite(bt.get("header", ""), _get_style3_display_font, 64, 44, 840, 1, pal["ink"])}
        if k == "intro":
            a["org_words"] = _make_word_sprites(core["org"], _get_style3_display_font, 90, 52, 940, 2, pal["ink"], W // 2, 685)
            b_sp = _make_minimal_card(620, 134, radius=67, fill=pal["tint"], border=pal["accent"], border_w=4)
            bf, bsz = fit_single_line_font(ImageDraw.Draw(b_sp), core["cat_badge"], _get_style3_body_font, 58, 38, 540)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, core["cat_badge"], bf, bsz, pal["accent"], anchor="mm")
            a["badge_sp"] = b_sp
            a["hook_words"] = _make_word_sprites(core["hook_short"], _get_style3_body_font, 54, 38, 900, 2, pal["muted"], W // 2, 1165)

        elif k == "vacancy":
            card_sp = _make_minimal_card(900, 440, radius=44, fill=pal["card"], border=pal["hairline"], border_w=2)
            s2d = ImageDraw.Draw(card_sp)
            s2d.rounded_rectangle([22, 22, 922, 140], radius=42, fill=pal["tint"] + (255,))
            s2d.rectangle([22, 84, 922, 140], fill=pal["tint"] + (255,))
            draw_mixed_text(s2d, card_sp.width // 2, 82, "মোট শূন্যপদ", _get_style3_body_font(52), 52, pal["accent"], anchor="mm")
            a["card_sp"] = card_sp
            a["static_num"] = _make_text_sprite(bt["value"], _get_style3_body_font, 172, 70, 800, 1, pal["ink"])
            t_sp = _make_minimal_card(860, 136, radius=68, fill=pal["accent"], shadow_alpha=28)
            tf2, tsz2, tl2 = fit_multiline_font(ImageDraw.Draw(t_sp), bt["tag"], _get_style3_body_font, 48, 32, 780, 2)
            ty2 = t_sp.height // 2 - ((len(tl2) - 1) * (tsz2 + 10)) // 2
            for l2 in tl2:
                draw_mixed_text(ImageDraw.Draw(t_sp), t_sp.width // 2, ty2, l2, tf2, tsz2, (255, 255, 255), anchor="mm")
                ty2 += tsz2 + 10
            a["tag_sp"] = t_sp
            a["chips"] = []
            for txt in bt.get("sub_chips", [])[:1]:
                csp = _make_minimal_card(860, 112, radius=28, fill=pal["tint"], border=pal["hairline"], border_w=2, shadow_alpha=20)
                cf, csz = fit_single_line_font(ImageDraw.Draw(csp), txt, _get_style3_body_font, 42, 28, 800)
                draw_mixed_text(ImageDraw.Draw(csp), csp.width // 2, csp.height // 2, txt, cf, csz, pal["accent"], anchor="mm")
                a["chips"].append(csp)

        elif k == "post_spotlight":
            it = bt["post"]
            a["card_bg"] = _make_minimal_card(930, 560, radius=42, fill=pal["card"], border=pal["hairline"], border_w=2)
            a["pill_idx"] = _make_minimal_card(110, 72, radius=22, fill=pal["tint"], pad=8, shadow_alpha=0)
            draw_mixed_text(ImageDraw.Draw(a["pill_idx"]), a["pill_idx"].width // 2, a["pill_idx"].height // 2, bn_nums[(bt["index"] - 1) % 4], _get_style3_body_font(38), 38, pal["accent"], anchor="mm")
            a["title_sp"] = _make_text_sprite(it["post_name"], _get_style3_body_font, 58, 34, 820, 2, pal["ink"])
            b_sp = _make_minimal_card(320, 118, radius=30, fill=pal["tint"], border=pal["accent"], border_w=2, pad=10, shadow_alpha=0)
            vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], _get_style3_body_font, 56, 32, 275)
            draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
            a["vac_sp"] = b_sp
            a["qual_sp"] = _make_minimal_card(840, 116, radius=28, fill=pal["bg"], border=pal["hairline"], border_w=2, pad=10, shadow_alpha=0)
            qf, qsz = fit_single_line_font(ImageDraw.Draw(a["qual_sp"]), f"যোগ্যতা: {it['qualification']}", _get_style3_body_font, 42, 28, 780)
            draw_mixed_text(ImageDraw.Draw(a["qual_sp"]), a["qual_sp"].width // 2, a["qual_sp"].height // 2, f"যোগ্যতা: {it['qualification']}", qf, qsz, pal["ink"], anchor="mm")
            a["grade_sp"] = _make_minimal_card(840, 116, radius=28, fill=pal["bg"], border=pal["hairline"], border_w=2, pad=10, shadow_alpha=0)
            gf, gsz = fit_single_line_font(ImageDraw.Draw(a["grade_sp"]), f"গ্রেড/বেতন: {it['salary_grade']}", _get_style3_body_font, 42, 28, 780)
            draw_mixed_text(ImageDraw.Draw(a["grade_sp"]), a["grade_sp"].width // 2, a["grade_sp"].height // 2, f"গ্রেড/বেতন: {it['salary_grade']}", gf, gsz, pal["muted"], anchor="mm")

        elif k == "post_pair":
            cards = []
            for idx_p, it in enumerate(bt["posts"]):
                cy = 670 if len(bt["posts"]) == 1 else ([660, 1020][idx_p])
                bg_c = _make_minimal_card(940, 300, radius=32, fill=pal["card"], border=pal["hairline"], border_w=2)
                idx_pill = _make_minimal_card(88, 70, radius=22, fill=pal["tint"], pad=8, shadow_alpha=0)
                draw_mixed_text(ImageDraw.Draw(idx_pill), idx_pill.width // 2, idx_pill.height // 2, bn_nums[idx_p % 4], _get_style3_body_font(36), 36, pal["accent"], anchor="mm")
                t_sp = _make_text_sprite(it["post_name"], _get_style3_body_font, 52, 32, 460, 2, pal["ink"], align="lm")
                b_sp = _make_minimal_card(255, 108, radius=26, fill=pal["tint"], border=pal["accent"], border_w=2, pad=10, shadow_alpha=0)
                vf_b, vsz_b = fit_single_line_font(ImageDraw.Draw(b_sp), it["vacancy"], _get_style3_body_font, 54, 30, 220)
                draw_mixed_text(ImageDraw.Draw(b_sp), b_sp.width // 2, b_sp.height // 2, it["vacancy"], vf_b, vsz_b, pal["accent"], anchor="mm")
                m_sp = _make_text_sprite(it["meta"], _get_style3_body_font, 42, 28, 830, 2, pal["muted"], align="lm")
                cards.append({"bg": bg_c, "idx": idx_pill, "title": t_sp, "badge": b_sp, "meta": m_sp, "cy": cy, "h": 300})
            a["cards"] = cards

        elif k in ("focus_card", "steps", "highlight"):
            a["hero_bg"] = _make_minimal_card(920, 265, radius=36, fill=pal["tint"] if k == "focus_card" else pal["card"], border=pal["hairline"], border_w=2)
            a["icon_sp"] = _make_warm_icon(bt.get("icon", "info"), pal, size=118)
            a["lbl_sp"] = _make_text_sprite(bt.get("main_label", ""), _get_style3_body_font, 40, 28, 680, 1, pal["accent"] if k == "focus_card" else pal["muted"], align="lm")
            a["val_sp"] = _make_text_sprite(bt.get("main_val", ""), _get_style3_body_font, 52, 32, 690, 2, pal["ink"], align="lm")
            chips = []
            for idx_c, ch_txt in enumerate(bt.get("sub_chips", [])[:3]):
                c_bg = _make_minimal_card(920, 134, radius=28, fill=pal["card"], border=pal["hairline"], border_w=2)
                n_bg = _make_minimal_card(74, 74, radius=22, fill=pal["tint"], border=pal["accent"], border_w=2, pad=8, shadow_alpha=0)
                draw_mixed_text(ImageDraw.Draw(n_bg), n_bg.width // 2, n_bg.height // 2, bn_nums[idx_c % 4], _get_style3_body_font(34), 34, pal["accent"], anchor="mm")
                t_sp = _make_text_sprite(ch_txt, _get_style3_body_font, 42, 28, 725, 2, pal["ink"], align="lm")
                chips.append({"bg": c_bg, "num": n_bg, "txt": t_sp})
            a["chips"] = chips

        elif k == "deadline":
            left_c = _make_minimal_card(420, 390, radius=38, fill=pal["card"], border=pal["hairline"], border_w=2)
            draw_mixed_text(ImageDraw.Draw(left_c), left_c.width // 2, 95, "শুরু", _get_style3_body_font(44), 44, pal["muted"], anchor="mm")
            lf5, lsz5, ll5 = fit_multiline_font(ImageDraw.Draw(left_c), bt["start_date"], _get_style3_body_font, 58, 34, 360, 2)
            ly5 = 255 - ((len(ll5) - 1) * (lsz5 + 12)) // 2
            for l in ll5:
                draw_mixed_text(ImageDraw.Draw(left_c), left_c.width // 2, ly5, l, lf5, lsz5, pal["ink"], anchor="mm")
                ly5 += lsz5 + 12
            a["left_c"] = left_c

            right_c = _make_minimal_card(420, 390, radius=38, fill=pal["tint"], border=pal["accent"], border_w=3)
            draw_mixed_text(ImageDraw.Draw(right_c), right_c.width // 2, 95, "শেষ তারিখ", _get_style3_body_font(44), 44, pal["accent"], anchor="mm")
            rf5, rsz5, rl5 = fit_multiline_font(ImageDraw.Draw(right_c), bt["end_date"], _get_style3_body_font, 58, 34, 360, 2)
            ry5 = 255 - ((len(rl5) - 1) * (rsz5 + 12)) // 2
            for l in rl5:
                draw_mixed_text(ImageDraw.Draw(right_c), right_c.width // 2, ry5, l, rf5, rsz5, pal["accent"], anchor="mm")
                ry5 += rsz5 + 12
            a["right_c"] = right_c

            urg_sp = _make_minimal_card(740, 126, radius=63, fill=pal["accent"], shadow_alpha=24)
            draw_mixed_text(ImageDraw.Draw(urg_sp), urg_sp.width // 2, urg_sp.height // 2, "সময়মতো আবেদন করুন", _get_style3_body_font(48), 48, (255, 255, 255), anchor="mm")
            a["urg_sp"] = urg_sp

        elif k == "overview_grid":
            g_cards = []
            for idx4, (kind_i, lbl_i, val_i) in enumerate(bt["items"]):
                is_tinted = idx4 in [1, 2]
                g_bg = _make_minimal_card(460, 445, radius=36, fill=pal["tint"] if is_tinted else pal["card"], border=pal["hairline"], border_w=2)
                g_cards.append({
                    "bg": g_bg,
                    "icon": _make_warm_icon(kind_i, pal, size=116),
                    "lbl": _make_text_sprite(lbl_i, _get_style3_body_font, 44, 32, 380, 1, pal["accent"] if is_tinted else pal["muted"]),
                    "val": _make_text_sprite(val_i, _get_style3_body_font, 52, 34, 405, 3, pal["ink"])
                })
            a["g_cards"] = g_cards

        elif k == "cta":
            a["card_bg"] = _make_minimal_card(900, 740, radius=48, fill=pal["card"], border=pal["hairline"], border_w=2)
            a["title_words"] = _make_word_sprites("যোগাযোগ (হোয়াটসঅ্যাপ)", _get_style3_display_font, 60, 42, 840, 1, pal["ink"], W // 2, 705)
            a["pill_bg"] = _make_minimal_card(820, 188, radius=94, fill=pal["accent"])
            a["num_sp"] = Image.new("RGBA", (780, 130), (0, 0, 0, 0))
            draw_mixed_text(ImageDraw.Draw(a["num_sp"]), 390, 65, bt["wa_formatted"], _get_style3_eng_font(82), 82, (255, 255, 255), anchor="mm")
            a["pill_mask"] = Image.new("L", a["pill_bg"].size, 0)
            ImageDraw.Draw(a["pill_mask"]).rounded_rectangle([22, 22, 842, 210], radius=94, fill=255)
            a["sheen_sp"] = Image.new("RGBA", (200, a["pill_bg"].height), (0, 0, 0, 0))
            ImageDraw.Draw(a["sheen_sp"]).polygon([(65, 0), (160, 0), (95, a["pill_bg"].height), (0, a["pill_bg"].height)], fill=(255, 255, 255, 65))
            a["sub_words"] = _make_word_sprites("আবেদনের জন্য মেসেজ দিন", _get_style3_body_font, 52, 36, 840, 1, pal["muted"], W // 2, 1065)

        beat_assets.append(a)

    trans_styles = ["push_left", "curl"]
    trans_sec = 0.34

    def render_beat_frame(b_idx, local_t, abs_t):
        bt = beats[b_idx]
        a = beat_assets[b_idx]
        k = bt["kind"]

        frame = bg_base.copy()
        fd = ImageDraw.Draw(frame)

        ax1 = int((abs_t * 50) % (W + 460)) - 230
        ax2 = int(W + 230 - ((abs_t * 42) % (W + 460)))
        fd.arc([ax1 - 105, 35, ax1 + 105, 245], start=20, end=210, fill=pal["shape"], width=5)
        fd.arc([ax2 - 115, H - 375, ax2 + 115, H - 145], start=190, end=370, fill=pal["shape"], width=5)
        fd.rounded_rectangle([ax1 + 40, 130, ax1 + 140, 142], radius=6, fill=pal["shape"])
        fd.rounded_rectangle([ax2 - 140, H - 315, ax2 - 40, H - 303], radius=6, fill=pal["shape"])

        if k not in ("intro", "cta"):
            hy = int(100 + 120 * ease_out_cubic(local_t / 0.35)) if (b_idx == 1 and local_t < 0.35) else 220
            _paste_sprite(frame, hdr_left, 425, hy)
            _paste_sprite(frame, hdr_right, 895, hy)
            fd.polygon([(120, hy - 11), (132, hy), (120, hy + 11), (108, hy)], fill=pal["accent"])

            _render_masked_rise(frame, a["hdr_sp"], W // 2, 365, local_t / 0.28, rise_px=34)
            hl_w = int(150 * ease_out_cubic(min(1.0, local_t / 0.40)))
            fd.rounded_rectangle([W // 2 - hl_w, 412, W // 2 + hl_w, 418], radius=3, fill=pal["accent"])

        if k == "intro":
            sp_p = ease_out_back(min(1.0, local_t / 0.42))
            ang = -10.0 * (1.0 - min(1.0, local_t / 0.42))
            rot_seal = seal_sp.rotate(ang, resample=Image.BICUBIC, expand=True)
            _paste_sprite(frame, rot_seal, W // 2, 415 + int(7 * math.sin(abs_t * 2.4)), scale=0.35 + 0.65 * sp_p, opacity=min(1.0, local_t / 0.20))
            for idx_w, (wsp, wx, wy) in enumerate(a["org_words"]):
                st = 0.12 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.30, rise_px=50)
            if local_t > 0.28:
                hl = int(185 * ease_out_cubic((local_t - 0.28) / 0.32))
                fd.rounded_rectangle([W // 2 - hl, 848, W // 2 + hl, 855], radius=3, fill=pal["accent"])
                fd.ellipse([W // 2 - 9, 842, W // 2 + 9, 860], fill=pal["accent"])
            if local_t > 0.38:
                bp = ease_out_back((local_t - 0.38) / 0.36)
                _paste_sprite(frame, a["badge_sp"], W // 2, 975, scale=0.68 + 0.32 * bp, opacity=min(1.0, (local_t - 0.38) / 0.18))
            for idx_h, (wsp, wx, wy) in enumerate(a["hook_words"]):
                st = 0.56 + idx_h * 0.07
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.28, rise_px=38)

        elif k == "vacancy":
            cp = ease_out_back(min(1.0, local_t / 0.38))
            _paste_sprite(frame, a["card_sp"], W // 2, 680, scale=0.80 + 0.20 * cp, opacity=min(1.0, local_t / 0.20))
            if bt["num"] > 0:
                cnt_p = ease_out_cubic(min(1.0, max(0.0, local_t - 0.12) / 1.15))
                cur_val = max(1, int(round(bt["num"] * cnt_p)))
                if cur_val not in countup_cache:
                    if len(countup_cache) > 45: countup_cache.clear()
                    countup_cache[cur_val] = _make_text_sprite(to_bn_num(cur_val) + "টি", _get_style3_body_font, 172, 70, 800, 1, pal["ink"])
                land_t = local_t - 1.27
                pop_sc = (1.0 + 0.12 * math.sin((land_t / 0.35) * math.pi)) if 0.0 <= land_t <= 0.35 else 1.0
                _paste_sprite(frame, countup_cache[cur_val], W // 2, 750, scale=pop_sc)
            else:
                _paste_sprite(frame, a["static_num"], W // 2, 750, scale=0.78 + 0.22 * cp, opacity=min(1.0, local_t / 0.25))
            if local_t > 0.65:
                tp = ease_out_back((local_t - 0.65) / 0.38)
                _paste_sprite(frame, a["tag_sp"], W // 2, 1055 + int(35 * (1.0 - min(1.0, tp))), scale=0.82 + 0.18 * tp, opacity=min(1.0, (local_t - 0.65) / 0.20))
            if a["chips"] and local_t > 1.35:
                chp = ease_out_back((local_t - 1.35) / 0.36)
                _paste_sprite(frame, a["chips"][0], W // 2, 1235 + int(25 * (1.0 - min(1.0, chp))), scale=0.88 + 0.12 * chp, opacity=min(1.0, (local_t - 1.35) / 0.20))

        elif k == "post_spotlight":
            cp = ease_out_back(min(1.0, local_t / 0.35))
            _paste_sprite(frame, a["card_bg"], W // 2, 840, scale=0.90 + 0.10 * cp, opacity=min(1.0, local_t / 0.20))
            if local_t > 0.10:
                _paste_sprite(frame, a["pill_idx"], 190, 675, scale=0.65 + 0.35 * ease_out_back((local_t - 0.10) / 0.30))
            if local_t > 0.20:
                _render_masked_rise(frame, a["title_sp"], 600, 675, (local_t - 0.20) / 0.30, rise_px=30)
            if local_t > 0.65:
                vp = ease_out_back((local_t - 0.65) / 0.34)
                pulse = 1.0 + (0.025 * math.sin(abs_t * 4.5) if local_t > 1.4 else 0.0)
                _paste_sprite(frame, a["vac_sp"], W // 2, 825, scale=(0.68 + 0.32 * vp) * pulse)
            if local_t > 1.15:
                qp = ease_out_cubic((local_t - 1.15) / 0.32)
                _paste_sprite(frame, a["qual_sp"], W // 2 + int(90 * (1.0 - qp)), 965, opacity=qp)
            if local_t > 1.75:
                gp = ease_out_cubic((local_t - 1.75) / 0.32)
                _paste_sprite(frame, a["grade_sp"], W // 2 - int(90 * (1.0 - gp)), 1098, opacity=gp)

        elif k == "post_pair":
            active_c = int(local_t / 1.4) % max(1, len(a["cards"]))
            for idx_p, c in enumerate(a["cards"]):
                st = 0.05 + idx_p * 0.72
                if local_t <= st: continue
                cp = ease_out_back((local_t - st) / 0.34)
                act_sc = 1.02 if (local_t > 1.5 and idx_p == active_c) else 1.0
                dx = int(((-1 if idx_p % 2 == 0 else 1) * 160) * (1.0 - min(1.0, cp)))
                cx = W // 2 + dx
                cy = c["cy"]
                op = min(1.0, (local_t - st) / 0.18)
                _paste_sprite(frame, c["bg"], cx, cy, scale=(0.92 + 0.08 * cp) * act_sc, opacity=op)
                _paste_sprite(frame, c["idx"], cx - 390, cy - 50, scale=0.6 + 0.4 * ease_out_back((local_t - st) / 0.28), opacity=op)
                if local_t > st + 0.12:
                    _render_masked_rise(frame, c["title"], cx - 55, cy - 45, (local_t - (st + 0.12)) / 0.26, rise_px=22)
                if local_t > st + 0.28:
                    _paste_sprite(frame, c["badge"], cx + 315, cy - 45, scale=0.55 + 0.45 * ease_out_back((local_t - (st + 0.28)) / 0.26))
                if local_t > st + 0.44:
                    _render_masked_rise(frame, c["meta"], cx + 15, cy + 68, (local_t - (st + 0.44)) / 0.26, rise_px=18)

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

            n_ch = len(a["chips"])
            active_chip = int(max(0, local_t - 1.8) / 1.1) % max(1, n_ch)
            for idx_c, ch in enumerate(a["chips"]):
                st = 0.70 + idx_c * 0.72
                if local_t <= st: continue
                cy = 875 + idx_c * 165
                chp = ease_out_cubic((local_t - st) / 0.32)
                dx = int(160 * (1.0 - chp)) * (-1 if idx_c % 2 == 0 else 1)
                act_sc = 1.022 if (local_t > 2.2 and idx_c == active_chip) else 1.0
                _paste_sprite(frame, ch["bg"], W // 2 + dx, cy, scale=act_sc, opacity=chp)
                _paste_sprite(frame, ch["num"], 158 + dx, cy, scale=0.65 + 0.35 * ease_out_back((local_t - st) / 0.30), opacity=chp)
                if local_t > st + 0.14:
                    _render_masked_rise(frame, ch["txt"], 600 + dx, cy, (local_t - (st + 0.14)) / 0.26, rise_px=20)

        elif k == "deadline":
            if local_t > 0.08:
                p1 = ease_out_back((local_t - 0.08) / 0.38)
                _paste_sprite(frame, a["left_c"], 290, 745, scale=0.78 + 0.22 * p1, opacity=min(1.0, (local_t - 0.08) / 0.20))
            if local_t > 0.22:
                p2 = ease_out_back((local_t - 0.22) / 0.38)
                _paste_sprite(frame, a["right_c"], 790, 745, scale=0.78 + 0.22 * p2, opacity=min(1.0, (local_t - 0.22) / 0.20))
            if local_t > 0.34:
                pulse_x = W // 2 + int(10 * math.sin(abs_t * 4.8))
                fd.ellipse([pulse_x - 38, 707, pulse_x + 38, 783], fill=pal["accent"])
                fd.line([(pulse_x - 10, 729), (pulse_x + 12, 745), (pulse_x - 10, 761)], fill=(255, 255, 255), width=7)
            if local_t > 0.50:
                up = ease_out_back((local_t - 0.50) / 0.36)
                _paste_sprite(frame, a["urg_sp"], W // 2, 1110, scale=(0.8 + 0.2 * up) * (1.0 + 0.025 * math.sin(abs_t * 4.2)), opacity=min(1.0, (local_t - 0.50) / 0.22))

        elif k == "overview_grid":
            positions = [(295, 700), (785, 700), (295, 1175), (785, 1175)]
            active_idx = int(abs_t * 0.9) % 4
            for idx, item in enumerate(a["g_cards"]):
                st = 0.08 + idx * 0.20
                if local_t <= st: continue
                gx, gy = positions[idx]
                cp = ease_out_back((local_t - st) / 0.32)
                act_sc = 1.028 if (local_t > 1.2 and idx == active_idx) else 1.0
                _paste_sprite(frame, item["bg"], gx, gy, scale=(0.78 + 0.22 * cp) * act_sc, opacity=min(1.0, (local_t - st) / 0.18))
                if local_t > st + 0.06:
                    _paste_sprite(frame, item["icon"], gx, gy - 115 + int(4 * math.sin(abs_t * 2.5 + idx)), scale=0.45 + 0.55 * ease_out_back((local_t - (st + 0.06)) / 0.30))
                if local_t > st + 0.12:
                    _render_masked_rise(frame, item["lbl"], gx, gy - 10, (local_t - (st + 0.12)) / 0.24, rise_px=20)
                if local_t > st + 0.18:
                    _paste_sprite(frame, item["val"], gx, gy + 94, scale=0.74 + 0.26 * ease_out_back((local_t - (st + 0.18)) / 0.30))

        elif k == "cta":
            fp = ease_out_back(min(1.0, local_t / 0.40))
            _paste_sprite(frame, a["card_bg"], W // 2, 760, scale=0.82 + 0.18 * fp, opacity=min(1.0, local_t / 0.20))
            wp = ease_out_back(min(1.0, max(0.0, local_t - 0.08) / 0.40))
            _paste_sprite(frame, wa_sp, W // 2, 505 + int(8 * math.sin(abs_t * 2.8)), scale=0.3 + 0.7 * wp, opacity=min(1.0, local_t / 0.22))
            for idx_w, (wsp, wx, wy) in enumerate(a["title_words"]):
                st = 0.14 + idx_w * 0.08
                if local_t > st:
                    _render_masked_rise(frame, wsp, wx, wy, (local_t - st) / 0.26, rise_px=32)
            if local_t > 0.32:
                pp = ease_out_back((local_t - 0.32) / 0.38)
                pill_sc = a["pill_bg"].resize((max(40, int(a["pill_bg"].width * max(0.15, min(1.0, pp)))), a["pill_bg"].height), Image.BILINEAR)
                _paste_sprite(frame, pill_sc, W // 2, 890, opacity=min(1.0, (local_t - 0.32) / 0.18))
            if local_t > 0.46:
                np = ease_out_cubic((local_t - 0.46) / 0.34)
                num_crop = a["num_sp"].crop((0, 0, max(12, int(a["num_sp"].width * np)), a["num_sp"].height))
                frame.paste(num_crop, ((W - a["num_sp"].width) // 2, 890 - a["num_sp"].height // 2), num_crop.getchannel("A"))
                if np >= 0.99:
                    cs = (local_t - 0.80) % 2.0
                    if 0.0 <= cs <= 0.75:
                        tmp_sh = Image.new("RGBA", a["pill_bg"].size, (0, 0, 0, 0))
                        tmp_sh.paste(a["sheen_sp"], (int(-200 + (a["pill_bg"].width + 200) * (cs / 0.75)), 0))
                        masked_sh = Image.new("RGBA", a["pill_bg"].size, (0, 0, 0, 0))
                        masked_sh.paste(tmp_sh, (0, 0), a["pill_mask"])
                        _paste_sprite(frame, masked_sh, W // 2, 890)
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
        frame_cur = render_beat_frame(b_idx, local_t, abs_t)
        if b_idx > 0 and local_t < trans_sec:
            prev_bt = beats[b_idx - 1]
            frame_prev = render_beat_frame(b_idx - 1, max(0.0, prev_bt["end"] - prev_bt["start"]), abs_t)
            return _apply_transition(frame_prev, frame_cur, local_t / trans_sec, trans_styles[(b_idx - 1) % 2], curl_sp)
        return frame_cur

    return _stream_frames_to_ffmpeg(total_frames, fps, W, H, audio_path, output_path, get_frame)
