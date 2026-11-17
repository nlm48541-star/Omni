# -*- coding: utf-8 -*-
import os
import math
from PIL import Image, ImageDraw

from tiktok_designer import (
    get_body_font, get_english_bold_font, get_advance_width,
    measure_mixed_text, draw_mixed_text, draw_colored_spans_line,
    wrap_colored_spans, fit_single_line_font, fit_multiline_font,
    quad_bezier, _aa_overlay_draw, _highlight_numbers_and_dates,
    _parse_bracket_highlights, _draw_wave_corners, _draw_summary,
    _draw_date_fee_box
)

def _split_two_tone(text):
    words = str(text).strip().split()
    return (" ".join(words[:-1]) + " ", words[-1]) if len(words) >= 2 else ("", str(text).strip())

def _draw_two_tone_fitted(draw, cx, cy, p1, p2, c1, c2, font_fn, start_sz, min_sz, max_w):
    spans = ([(p1, c1)] if p1 else []) + ([(p2, c2)] if p2 else [])
    if not spans: return
    full = (p1 or "") + (p2 or "")
    for sz in range(start_sz, min_sz - 1, -2):
        f = font_fn(sz)
        if measure_mixed_text(draw, full, f, sz)[0] <= max_w:
            draw_colored_spans_line(draw, cx, cy, spans, f, sz); return
    f = font_fn(min_sz); lines = wrap_colored_spans(draw, spans, f, min_sz, max_width=max_w); lh = min_sz + 10
    ty = cy - ((len(lines) - 1) * lh) // 2
    for lt in lines[:2]: draw_colored_spans_line(draw, cx, ty, lt, f, min_sz); ty += lh

def _draw_dot_grid(od, x0, y0, cols, rows, step_px, r_px, col, s):
    for r in range(rows):
        for c in range(cols):
            cx = (x0 + c * step_px) * s
            cy = (y0 + r * step_px) * s
            od.ellipse([cx - r_px * s, cy - r_px * s, cx + r_px * s, cy + r_px * s], fill=col)

def _draw_radiating_rays(od, x_left, x_right, cy, s, ray_cols, length=68, spread=36, w_out=11, w_in=5):
    cols = ray_cols if isinstance(ray_cols, list) else [ray_cols, ray_cols, ray_cols]
    for (dy_i, dy_o), col in zip([(-20, -spread), (0, 0), (20, spread)], cols):
        xl1, yl1, xl2, yl2 = x_left * s, (cy + dy_i) * s, (x_left - length) * s, (cy + dy_i + dy_o) * s
        od.polygon([(xl1, yl1 - w_in * s / 2), (xl2, yl2 - w_out * s / 2), (xl2, yl2 + w_out * s / 2), (xl1, yl1 + w_in * s / 2)], fill=col)
        od.ellipse([xl2 - w_out * s / 2, yl2 - w_out * s / 2, xl2 + w_out * s / 2, yl2 + w_out * s / 2], fill=col)
        xr1, yr1, xr2, yr2 = x_right * s, (cy + dy_i) * s, (x_right + length) * s, (cy + dy_i + dy_o) * s
        od.polygon([(xr1, yr1 - w_in * s / 2), (xr2, yr2 - w_out * s / 2), (xr2, yr2 + w_out * s / 2), (xr1, yr1 + w_in * s / 2)], fill=col)
        od.ellipse([xr2 - w_out * s / 2, yr2 - w_out * s / 2, xr2 + w_out * s / 2, yr2 + w_out * s / 2], fill=col)

def _draw_tri_bars(draw, xl_end, xr_start, cy, bar_len, l_col, r_col, gap=24, width=7):
    for dy in [-gap, 0, gap]:
        bl = bar_len if dy == 0 else int(bar_len * 0.85)
        draw.line([(xl_end - bl, cy + dy), (xl_end, cy + dy)], fill=l_col, width=width)
        draw.line([(xr_start, cy + dy), (xr_start + bl, cy + dy)], fill=r_col, width=width)

def _draw_dashed_rrect(draw, box, r, width, col, dash=24, gap=14):
    x0, y0, x1, y1 = box
    r = min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0)
    pts = [(x0 + r, y0), (x1 - r, y0)]
    for cx, cy, a0 in [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]:
        for i in range(1, 17):
            a = math.radians(a0 + 90 * (i / 16.0))
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0]); sampled = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]; steps = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 4.0))
        for k in range(steps): sampled.append((p0[0] + (p1[0] - p0[0]) * k / steps, p0[1] + (p1[1] - p0[1]) * k / steps))
    acc, per = 0.0, dash + gap
    for i in range(len(sampled)):
        p0, p1 = sampled[i], sampled[(i + 1) % len(sampled)]; sl = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if (acc % per) < dash: draw.line([p0, p1], fill=col, width=width)
        acc += sl

def _draw_tilted_box_hero(im, y_top, info, bg_col, top_col=(255, 255, 255), bot_col=(250, 204, 21), angle=2.8, dashed=False, shadow_col=None):
    s = 2; pw, ph = 890 * s, 232 * s; cw, ch = pw + 70 * s, ph + 70 * s
    ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    bx0, by0, bx1, by1 = 30 * s, 24 * s, 30 * s + pw, 24 * s + ph
    if shadow_col: od.rounded_rectangle([bx0 + 10 * s, by0 + 12 * s, bx1 + 10 * s, by1 + 12 * s], radius=44 * s, fill=shadow_col + (255,))
    od.rounded_rectangle([bx0, by0, bx1, by1], radius=44 * s, fill=bg_col + (255,))
    if dashed: _draw_dashed_rrect(od, [bx0 + 14 * s, by0 + 14 * s, bx1 - 14 * s, by1 - 14 * s], 34 * s, 3 * s, (255, 255, 255, 230), 24 * s, 14 * s)
    tf, tsz = fit_single_line_font(od, info["hook_top"], get_body_font, 46 * s, 28 * s, pw - 90 * s)
    bf, bsz = fit_single_line_font(od, info["hook_bottom"], get_body_font, 78 * s, 42 * s, pw - 90 * s)
    draw_mixed_text(od, bx0 + pw // 2, by0 + 72 * s, info["hook_top"], tf, tsz, top_col, anchor="mm")
    draw_mixed_text(od, bx0 + pw // 2, by0 + 156 * s, info["hook_bottom"], bf, bsz, bot_col, anchor="mm")
    rot = ov.rotate(angle, resample=Image.BICUBIC, expand=True)
    rot_1x = rot.resize((max(1, rot.width // s), max(1, rot.height // s)), Image.LANCZOS)
    im.paste(rot_1x, ((im.width - rot_1x.width) // 2, y_top), rot_1x)
    return y_top + rot_1x.height

def _draw_brush_hero(im, y_top, info, bg_col, top_col=(255, 255, 255), bot_col=(250, 204, 21), angle=1.4):
    s = 2; cw, ch = 960 * s, 270 * s
    ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    tp, bp = [], []
    for i in range(49):
        t = i / 48.0; x = (95 + 770 * t) * s; arch = math.sin(math.pi * t)
        tp.append((x, (42 - 18 * arch + 4.0 * math.sin(i * 1.9)) * s))
        bp.append((x, (226 - 14 * arch + 4.0 * math.cos(i * 2.1)) * s))
    od.polygon(tp + list(reversed(bp)), fill=bg_col + (255,))
    for sx, sy, slen, sh in [(54, 48, 86, 16), (34, 72, 110, 14), (48, 98, 96, 18), (26, 126, 115, 14), (42, 154, 102, 16), (62, 180, 92, 14), (78, 202, 76, 12)]:
        od.polygon([(sx * s, (sy + sh * 0.5) * s), ((sx + slen) * s, sy * s), ((sx + slen) * s, (sy + sh) * s)], fill=bg_col + (255,))
        rx = 960 - sx
        od.polygon([(rx * s, (sy + sh * 0.5) * s), ((rx - slen) * s, sy * s), ((rx - slen) * s, (sy + sh) * s)], fill=bg_col + (255,))
    tf, tsz = fit_single_line_font(od, info["hook_top"], get_body_font, 46 * s, 28 * s, 700 * s)
    bf, bsz = fit_single_line_font(od, info["hook_bottom"], get_body_font, 76 * s, 42 * s, 720 * s)
    draw_mixed_text(od, cw // 2, 92 * s, info["hook_top"], tf, tsz, top_col, anchor="mm")
    draw_mixed_text(od, cw // 2, 168 * s, info["hook_bottom"], bf, bsz, bot_col, anchor="mm")
    rot = ov.rotate(angle, resample=Image.BICUBIC, expand=True)
    rot_1x = rot.resize((max(1, rot.width // s), max(1, rot.height // s)), Image.LANCZOS)
    im.paste(rot_1x, ((im.width - rot_1x.width) // 2, y_top), rot_1x)
    return y_top + rot_1x.height

def _draw_layered_tilted_hero(im, y_top, info, cream_col, green_col, navy_col, angle=2.5):
    s = 2; cw, ch = 900 * s, 320 * s
    ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.rounded_rectangle([120 * s, 16 * s, 780 * s, 144 * s], radius=42 * s, fill=cream_col + (255,), outline=green_col + (255,), width=3 * s)
    tf, tsz = fit_single_line_font(od, info["hook_top"], get_body_font, 42 * s, 26 * s, 590 * s)
    draw_mixed_text(od, cw // 2, 66 * s, info["hook_top"], tf, tsz, green_col, anchor="mm")
    od.rounded_rectangle([32 * s, 106 * s, 868 * s, 270 * s], radius=40 * s, fill=navy_col + (255,))
    p1, p2 = _split_two_tone(info["hook_bottom"])
    _draw_two_tone_fitted(od, cw // 2, 188 * s, p1, p2, (255, 255, 255), (250, 204, 21), get_body_font, 74 * s, 40 * s, 770 * s)
    ts, bs = [], []
    for i in range(41):
        t = i / 40.0; xx = (170 + 560 * t) * s; arch = math.sin(math.pi * t); yt = (284 - 10 * arch) * s
        ts.append((xx, yt)); bs.append((xx, yt + 10 * s * (arch ** 0.7)))
    od.polygon(ts + list(reversed(bs)), fill=green_col + (255,))
    rot = ov.rotate(angle, resample=Image.BICUBIC, expand=True)
    rot_1x = rot.resize((max(1, rot.width // s), max(1, rot.height // s)), Image.LANCZOS)
    im.paste(rot_1x, ((im.width - rot_1x.width) // 2, y_top), rot_1x)
    return y_top + rot_1x.height

def _draw_two_tier_hero(draw, info, top_col, pill_col, y_top=175):
    W = 1080
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 52, 34, 620)
    tw, _ = measure_mixed_text(draw, info["hook_top"], tf, tsz)
    draw_mixed_text(draw, W // 2, y_top + 22, info["hook_top"], tf, tsz, top_col, anchor="mm")
    lx_gap = max(55, (W - tw) // 2 - 28)
    if lx_gap > 80:
        draw.line([(68, y_top + 22), (lx_gap, y_top + 22)], fill=top_col, width=4)
        draw.line([(W - lx_gap, y_top + 22), (W - 68, y_top + 22)], fill=top_col, width=4)
    py0, py1 = y_top + 70, y_top + 258
    draw.rounded_rectangle([58, py0, 1022, py1], radius=82, fill=pill_col)
    p1, p2 = _split_two_tone(info["hook_bottom"])
    _draw_two_tone_fitted(draw, W // 2, (py0 + py1) // 2, p1, p2, (255, 255, 255), (250, 204, 21), get_body_font, 86, 44, 880)
    return py1

def _draw_split_card(im, x0, y0, x1, left_w, left_text, right_spans_list, fill_col, border_col, left_col, div_col, radius=34, chevron=False, left_two_tone=False, border_w=3, min_h=168):
    rx0, rx1 = x0 + left_w + (54 if chevron else 44), x1 - 24
    right_w = max(240, rx1 - rx0)
    tmp_d = ImageDraw.Draw(im); rsz, rf, all_lines = 28, get_body_font(28), []
    for cand_sz in range(42, 27, -2):
        cand_f = get_body_font(cand_sz); cand_l = []
        for sp in right_spans_list: cand_l.extend(wrap_colored_spans(tmp_d, sp, cand_f, cand_sz, max_width=right_w))
        if len(cand_l) <= 4: rsz, rf, all_lines = cand_sz, cand_f, cand_l; break
    if not all_lines:
        rf = get_body_font(28)
        for sp in right_spans_list: all_lines.extend(wrap_colored_spans(tmp_d, sp, rf, 28, max_width=right_w))
    lh = rsz + 13; ch = max(min_h, len(all_lines) * lh + 48)
    s = 2; cw_s, ch_s = (x1 - x0 + 8) * s, (ch + 8) * s
    bx0, by0, bx1, by1 = 4 * s, 4 * s, (x1 - x0 + 4) * s, (ch + 4) * s; rad_s = min(radius * s, (ch * s) // 2)
    mask = Image.new("L", (cw_s, ch_s), 0); ImageDraw.Draw(mask).rounded_rectangle([bx0, by0, bx1, by1], radius=rad_s, fill=255)
    layer = Image.new("RGBA", (cw_s, ch_s), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    ld.rectangle([bx0, by0, bx1, by1], fill=fill_col + (255,))
    if chevron: ld.polygon([(bx0, by0), (bx0 + left_w * s, by0), (bx0 + (left_w + 34) * s, by0 + (ch * s) // 2), (bx0 + left_w * s, by1), (bx0, by1)], fill=left_col + (255,))
    else: ld.rectangle([bx0, by0, bx0 + left_w * s, by1], fill=left_col + (255,))
    ov = Image.new("RGBA", (cw_s, ch_s), (0, 0, 0, 0)); ov.paste(layer, (0, 0), mask)
    if border_col and border_w > 0: ImageDraw.Draw(ov).rounded_rectangle([bx0, by0, bx1, by1], radius=rad_s, outline=border_col + (255,), width=border_w * s)
    ov_1x = ov.resize((x1 - x0 + 8, ch + 8), Image.LANCZOS); im.paste(ov_1x, (x0 - 4, y0 - 4), ov_1x)
    draw = ImageDraw.Draw(im)
    if div_col:
        dx = x0 + left_w + (44 if chevron else 24)
        draw.line([(dx, y0 + 24), (dx, y0 + ch - 24)], fill=div_col, width=4)
    lcx, lcy = x0 + (left_w + (6 if chevron else 0)) // 2, y0 + ch // 2
    lf, lsz, llines = fit_multiline_font(draw, left_text, get_body_font, 42, 26, left_w - 30, 2); llh = lsz + 10
    if left_two_tone and len(llines) >= 2:
        ly = lcy - ((len(llines) - 1) * llh) // 2
        for idx_l, ll in enumerate(llines): draw_mixed_text(draw, lcx, ly, ll, lf, lsz, (255, 255, 255) if idx_l == 0 else (250, 204, 21), anchor="mm"); ly += llh
    elif left_two_tone:
        p1, p2 = _split_two_tone(llines[0] if llines else left_text)
        _draw_two_tone_fitted(draw, lcx, lcy, p1, p2, (255, 255, 255), (250, 204, 21), get_body_font, lsz, 26, left_w - 30)
    else:
        ly = lcy - ((len(llines) - 1) * llh) // 2
        for ll in llines: draw_mixed_text(draw, lcx, ly, ll, lf, lsz, (255, 255, 255), anchor="mm"); ly += llh
    rcx, ry = (rx0 + rx1) // 2, y0 + (ch - len(all_lines) * lh) // 2 + lh // 2
    for lt in all_lines: draw_colored_spans_line(draw, rcx, ry, lt, rf, rsz); ry += lh
    return y0 + ch

def _draw_df_split(im, x0, y0, x1, lw, info, fill_c, border_c, left_c, div_c, ink_c, hl_c, radius=34, chevron=False, left_two_tone=False, border_w=3):
    return _draw_split_card(
        im, x0, y0, x1, lw, info["date_title"],
        [_highlight_numbers_and_dates(info["date_text"], ink_c, hl_c), [(info["fee_title"] + " ", ink_c), (info["fee_text"], hl_c)]],
        fill_c, border_c, left_c, div_c, radius=radius, chevron=chevron, left_two_tone=left_two_tone, border_w=border_w
    )

def _draw_pill_cta(draw, info, y0, x0, x1, outer_fill, outer_outline, line1_col, inner_fill, pfx_col, num_col, radius=105, border_w=5):
    y1 = y0 + 220; cx = 540
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=outer_fill, outline=outer_outline, width=border_w if outer_outline else 0)
    draw_mixed_text(draw, cx, y0 + 54, "আবেদন করতে যোগাযোগ করুন।", get_body_font(44), 44, line1_col, anchor="mm")
    ix0, ix1 = x0 + 44, x1 - 44
    draw.rounded_rectangle([ix0, y0 + 100, ix1, y0 + 196], radius=48, fill=inner_fill)
    wf, wsz = fit_single_line_font(draw, "whatsapp: " + info["wa_number"], get_english_bold_font, 58, 36, (ix1 - ix0) - 48)
    p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf); wx = cx - (w1 + w2) / 2.0
    draw_mixed_text(draw, wx, y0 + 148, p1, wf, wsz, pfx_col, anchor="lm")
    draw_mixed_text(draw, wx + w1, y0 + 148, p2, wf, wsz, num_col, anchor="lm")
    return y1

def _draw_white_wa_icon(im, cx, cy, size=104):
    s = 2; sz = size * s; ov = Image.new("RGBA", (sz, sz), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); pad = int(sz * 0.12)
    d.ellipse([pad, pad, sz - pad, sz - pad], outline=(255, 255, 255, 255), width=int(sz * 0.085))
    d.polygon([(int(sz * 0.18), int(sz * 0.67)), (int(sz * 0.12), int(sz * 0.89)), (int(sz * 0.35), int(sz * 0.81))], fill=(255, 255, 255, 255))
    d.arc([int(sz * 0.32), int(sz * 0.32), int(sz * 0.68), int(sz * 0.68)], start=40, end=215, fill=(255, 255, 255, 255), width=int(sz * 0.11))
    ov_1x = ov.resize((size, size), Image.LANCZOS); im.paste(ov_1x, (cx - size // 2, cy - size // 2), ov_1x)

def _render_design_11(info, output_path):
    W, H = 1080, 1920
    GREEN, SAGE, RED, BLACK = (4, 88, 18), (163, 201, 154), (215, 25, 25), (17, 24, 39)
    im = Image.new("RGB", (W, H), (249, 250, 249)); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([42, 165, 1038, 315], radius=46, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 34, 910)
    draw_mixed_text(draw, W // 2, 240, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.line([(42, 346), (1038, 346)], fill=GREEN, width=4)
    cur_y = _draw_summary(draw, info, 415, BLACK) + 18
    spans = _parse_bracket_highlights(info["combined_df"], BLACK, RED)
    sz, f, lines = 48, get_body_font(48), []
    for sz in range(48, 32, -2):
        f = get_body_font(sz); lines = wrap_colored_spans(draw, spans, f, sz, max_width=940)
        if len(lines) <= 3: break
    for lt in lines: draw_colored_spans_line(draw, W // 2, cur_y, lt, f, sz); cur_y += sz + 16
    draw.line([(48, cur_y + 12), (1032, cur_y + 12)], fill=SAGE, width=3); cur_y += 58
    for idx, row in enumerate(info["rows"]):
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 46, 34, 940, 3)
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm"); cur_y += rsz + 16
        if idx == 0: draw.line([(135, cur_y + 8), (945, cur_y + 8)], fill=SAGE, width=3); cur_y += 52
    cta_y0 = cur_y + 28
    draw.rounded_rectangle([42, cta_y0, 1038, cta_y0 + 215], radius=52, fill=(254, 243, 206), outline=(234, 88, 12), width=5)
    draw_mixed_text(draw, W // 2, cta_y0 + 62, "আবেদন করতে যোগাযোগ করুন।", get_body_font(48), 48, BLACK, anchor="mm")
    wf, wsz = fit_single_line_font(draw, "whatsapp: " + info["wa_number"], get_english_bold_font, 62, 40, 910)
    draw_mixed_text(draw, W // 2, cta_y0 + 146, "whatsapp: " + info["wa_number"], wf, wsz, GREEN, anchor="mm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_12(info, output_path):
    W, H = 1080, 1920
    PURPLE, GOLD, RED, BLACK = (76, 11, 110), (250, 204, 21), (204, 17, 0), (17, 24, 39)
    im = Image.new("RGB", (W, H), (253, 252, 255))
    def decor(od, SW, SH, s):
        od.polygon([(0, 0), (225 * s, 0), (0, 225 * s)], fill=(76, 11, 110, 255))
        od.polygon([(225 * s, 0), (345 * s, 0), (0, 345 * s), (0, 225 * s)], fill=(250, 204, 21, 255))
        od.ellipse([SW - 250 * s, 45 * s, SW + 80 * s, 375 * s], fill=(235, 222, 252, 190))
        od.ellipse([-120 * s, SH - 480 * s, 240 * s, SH - 120 * s], fill=(235, 222, 252, 190))
        _draw_wave_corners(od, SW, SH, s, [], [
            ((520, 200, 65, 240), (235, 222, 252, 230)),
            ((480, 180, 50, 195), (250, 204, 21, 255)),
            ((430, 155, 40, 155), (76, 11, 110, 255))
        ])
        _draw_radiating_rays(od, 88, 992, 262, s, (76, 11, 110, 255), length=52, spread=30)
    im = _aa_overlay_draw(im, decor)
    hero_end = _draw_brush_hero(im, 128, info, PURPLE)
    draw = ImageDraw.Draw(im)
    div_y = max(408, hero_end + 10)
    draw.line([(125, div_y), (955, div_y)], fill=PURPLE, width=3)
    draw.ellipse([530, div_y - 10, 550, div_y + 10], fill=PURPLE)
    cur_y = _draw_summary(draw, info, div_y + 52, BLACK) + 12
    draw.line([(105, cur_y), (975, cur_y)], fill=PURPLE, width=3)
    box_y0 = cur_y + 24; box_y1 = box_y0 + 235
    draw.rounded_rectangle([65, box_y0 + 34, 1015, box_y1], radius=36, fill=(254, 246, 212), outline=PURPLE, width=4)
    draw.rounded_rectangle([255, box_y0, 825, box_y0 + 68], radius=34, fill=PURPLE)
    dtf, dtsz = fit_single_line_font(draw, info["date_title"], get_body_font, 40, 26, 510)
    draw_mixed_text(draw, W // 2, box_y0 + 34, info["date_title"], dtf, dtsz, (255, 255, 255), anchor="mm")
    draw.line([(508, box_y0 + 84), (508, box_y1 - 20)], fill=PURPLE, width=4)
    d_spans = _highlight_numbers_and_dates(info["date_text"], BLACK, RED)
    df, dsz, dlines = get_body_font(44), 44, []
    for dsz in range(44, 27, -2):
        df = get_body_font(dsz); dlines = wrap_colored_spans(draw, d_spans, df, dsz, max_width=385)
        if len(dlines) <= 3: break
    dlh = dsz + 10; dy = box_y0 + 70 + (162 - len(dlines) * dlh) // 2 + dlh // 2
    for dl in dlines: draw_colored_spans_line(draw, 286, dy, dl, df, dsz); dy += dlh
    ft_f, ft_sz = fit_single_line_font(draw, info["fee_title"], get_body_font, 40, 26, 430)
    draw_mixed_text(draw, 760, box_y0 + 108, info["fee_title"], ft_f, ft_sz, BLACK, anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 52, 28, 430, 2)
    fy = box_y0 + (164 if len(flines) == 1 else 150)
    for fl in flines: draw_mixed_text(draw, 760, fy, fl, ff, fsz, RED, anchor="mm"); fy += fsz + 8
    cur_y = box_y1 + 26
    card_themes = [((225, 247, 218), (21, 128, 61), (6, 78, 21)), ((221, 239, 254), (3, 64, 120), (0, 56, 112))]
    for idx, row in enumerate(info["rows"]):
        fill_c, out_c, pill_c = card_themes[idx]
        bf, bsz = fit_single_line_font(draw, row["badge"], get_body_font, 40, 26, 290)
        pw = max(260, min(335, measure_mixed_text(draw, row["badge"], bf, bsz)[0] + 54))
        rx0 = 62 + pw + 34; rw = 1008 - rx0
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 42, 28, rw, 3)
        lh = rsz + 11; ch = max(142, len(rlines) * lh + 40)
        draw.rounded_rectangle([42, cur_y, 1038, cur_y + ch], radius=40, fill=fill_c, outline=out_c, width=4)
        draw.rounded_rectangle([58, cur_y + 20, 58 + pw, cur_y + ch - 20], radius=(ch - 40) // 2, fill=pill_c)
        draw_mixed_text(draw, 58 + pw // 2, cur_y + ch // 2, row["badge"], bf, bsz, (255, 255, 255), anchor="mm")
        draw.line([(58 + pw + 18, cur_y + 22), (58 + pw + 18, cur_y + ch - 22)], fill=out_c, width=4)
        ty = cur_y + (ch - len(rlines) * lh) // 2 + lh // 2; rcx = (rx0 + 1018) // 2
        for rl in rlines: draw_mixed_text(draw, rcx, ty, rl, rf, rsz, BLACK, anchor="mm"); ty += lh
        cur_y += ch + 22
    cta_y0 = cur_y + 18
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_radiating_rays(od, 128, 952, cta_y0 + 110, s, [(76, 11, 110, 255), (250, 204, 21, 255), (76, 11, 110, 255)], length=74, spread=36))
    draw = ImageDraw.Draw(im)
    _draw_pill_cta(draw, info, cta_y0, 138, 942, PURPLE, GOLD, (255, 255, 255), GOLD, BLACK, BLACK, radius=110, border_w=6)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_13(info, output_path):
    W, H = 1080, 1920
    GREEN, GOLD, ORANGE, RED, BLACK = (6, 78, 21), (250, 204, 21), (234, 88, 12), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (250, 250, 248))
    def decor(od, SW, SH, s):
        od.polygon([(0, 0), (195 * s, 0), (0, 195 * s)], fill=GREEN + (255,))
        od.polygon([(220 * s, 0), (300 * s, 0), (0, 300 * s), (0, 220 * s)], fill=GOLD + (255,))
        _draw_wave_corners(od, SW, SH, s, [], [
            ((1080, 520, 180, 260), (234, 88, 12, 255)),
            ((960, 440, 145, 220), (250, 204, 21, 255)),
            ((360, 140, 55, 190), (6, 78, 21, 255))
        ])
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([42, 152, 1038, 304], radius=54, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 34, 910)
    draw_mixed_text(draw, W // 2, 228, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.rectangle([72, 326, 1008, 338], fill=GOLD)
    cur_y = _draw_summary(draw, info, 402, BLACK) + 20
    cur_y = _draw_date_fee_box(draw, info, cur_y, (254, 243, 199), BLACK, RED, left_stripe_col=ORANGE, radius=28) + 24
    for idx, row in enumerate(info["rows"]):
        fill_c = (220, 247, 232) if idx == 0 else (254, 232, 208)
        spans = [(row["badge"] + " – " + row["details"], GREEN)] if idx == 0 else [(row["badge"] + " – ", GREEN), (row["details"], BLACK)]
        sz, f, lines = 44, get_body_font(44), []
        for sz in range(44, 30, -2):
            f = get_body_font(sz); lines = wrap_colored_spans(draw, spans, f, sz, max_width=910)
            if len(lines) <= 3: break
        lh = sz + 14; ch = max(148, len(lines) * lh + 48)
        draw.rounded_rectangle([42, cur_y, 1038, cur_y + ch], radius=28, fill=fill_c)
        ty = cur_y + (ch - len(lines) * lh) // 2 + lh // 2
        for lt in lines: draw_colored_spans_line(draw, W // 2, ty, lt, f, sz); ty += lh
        cur_y += ch + 24
    cta_y0 = cur_y + 18
    draw.rounded_rectangle([34, cta_y0 - 6, 1046, cta_y0 + 226], radius=116, fill=GOLD)
    _draw_pill_cta(draw, info, cta_y0, 42, 1038, GREEN, None, (255, 255, 255), GOLD, GREEN, GREEN, radius=110, border_w=0)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_14(info, output_path):
    W, H = 1080, 1920
    NAVY, CRIMSON, GOLD, RED = (0, 42, 92), (140, 8, 12), (250, 204, 21), (220, 20, 20)
    im = Image.new("RGB", (W, H), (252, 250, 250))
    def decor(od, SW, SH, s):
        od.polygon([(0, 0), (190 * s, 0), (0, 190 * s)], fill=NAVY + (255,))
        od.polygon([(190 * s, 0), (265 * s, 0), (0, 265 * s), (0, 190 * s)], fill=CRIMSON + (255,))
        od.polygon([(SW, SH), (SW - 250 * s, SH), (SW, SH - 250 * s)], fill=NAVY + (255,))
        od.polygon([(SW - 250 * s, SH), (SW - 335 * s, SH), (SW, SH - 335 * s), (SW, SH - 250 * s)], fill=CRIMSON + (255,))
        od.ellipse([SW - 210 * s, 120 * s, SW + 110 * s, 440 * s], fill=(250, 228, 232, 165))
        od.ellipse([-140 * s, SH - 420 * s, 210 * s, SH - 70 * s], fill=(250, 228, 232, 165))
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([36, 146, 1044, 310], radius=82, fill=CRIMSON)
    draw.rounded_rectangle([42, 152, 1038, 304], radius=76, fill=CRIMSON, outline=(255, 255, 255), width=4)
    _draw_two_tone_fitted(draw, W // 2, 228, info["hook_top"] + " ", info["hook_bottom"], (255, 255, 255), GOLD, get_body_font, 56, 32, 880)
    draw.line([(105, 338), (975, 338)], fill=CRIMSON, width=3)
    draw.rectangle([524, 322, 556, 354], fill=CRIMSON)
    cur_y = _draw_summary(draw, info, 405, (10, 32, 68)) + 20
    cur_y = _draw_date_fee_box(draw, info, cur_y, (252, 232, 236), (10, 32, 68), RED, outline_col=(225, 29, 72), radius=48) + 28
    cur_y = _draw_split_card(im, 48, cur_y, 1032, 345, info["rows"][0]["badge"], [[(info["rows"][0]["details"], (0, 51, 102))]], (226, 240, 254), (0, 51, 102), (0, 51, 102), None, radius=32, chevron=True) + 24
    cur_y = _draw_split_card(im, 48, cur_y, 1032, 345, info["rows"][1]["badge"], [[(info["rows"][1]["details"], (88, 12, 80))]], (250, 232, 255), (107, 15, 107), (102, 12, 92), None, radius=32, chevron=True) + 28
    draw = ImageDraw.Draw(im)
    _draw_tri_bars(draw, 106, 974, cur_y + 110, 82, NAVY, GOLD, gap=24, width=7)
    _draw_pill_cta(draw, info, cur_y, 122, 958, NAVY, GOLD, (255, 255, 255), GOLD, (17, 24, 39), (17, 24, 39), radius=110, border_w=5)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_15(info, output_path):
    W, H = 1080, 1920
    GREEN, GOLD, RED, BLACK = (6, 78, 21), (250, 204, 21), (204, 17, 0), (17, 24, 39)
    im = Image.new("RGB", (W, H), (249, 251, 246))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_wave_corners(od, SW, SH, s,
        [((320, 120, 50, 200), (185, 224, 120, 220)), ((220, 85, 36, 130), (130, 190, 68, 240))],
        [((380, 140, 60, 230), (185, 224, 120, 220)), ((260, 95, 42, 155), (130, 190, 68, 240))]))
    draw = ImageDraw.Draw(im)
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 56, 36, 860)
    draw_mixed_text(draw, W // 2, 192, info["hook_top"], tf, tsz, GREEN, anchor="mm")
    draw.rounded_rectangle([68, 246, 1012, 434], radius=94, fill=GREEN)
    p1, p2 = _split_two_tone(info["hook_bottom"])
    _draw_two_tone_fitted(draw, W // 2, 340, p1, p2, (255, 255, 255), GOLD, get_body_font, 88, 44, 860)
    draw.line([(125, 464), (955, 464)], fill=GREEN, width=3)
    cur_y = _draw_summary(draw, info, 522, BLACK) + 18
    cur_y = _draw_df_split(im, 42, cur_y, 1038, 340, info, (226, 245, 218), (22, 101, 52), GREEN, GREEN, BLACK, RED, radius=84) + 20
    cur_y = _draw_split_card(im, 42, cur_y, 1038, 340, info["rows"][0]["badge"], [[(info["rows"][0]["details"], BLACK)]], (226, 245, 218), (22, 101, 52), GREEN, GREEN, radius=84) + 20
    cur_y = _draw_split_card(im, 42, cur_y, 1038, 340, info["rows"][1]["badge"], [[(info["rows"][1]["details"], BLACK)]], (226, 245, 218), (22, 101, 52), GREEN, GREEN, radius=84) + 24
    draw = ImageDraw.Draw(im)
    draw.line([(32, cur_y + 108), (134, cur_y + 108)], fill=GREEN, width=4)
    draw.line([(946, cur_y + 108), (1048, cur_y + 108)], fill=GREEN, width=4)
    _draw_pill_cta(draw, info, cur_y, 146, 934, GREEN, None, (255, 255, 255), GOLD, GREEN, GREEN, radius=108, border_w=0)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_16(info, output_path):
    W, H = 1080, 1920
    GREEN, GOLD, RED, BLACK = (6, 78, 21), (250, 204, 21), (215, 20, 20), (17, 24, 39)
    im = Image.new("RGB", (W, H), (251, 252, 244))
    def decor(od, SW, SH, s):
        _draw_wave_corners(od, SW, SH, s,
            [((340, 120, 50, 220), (190, 242, 100, 255)), ((235, 85, 38, 155), (250, 204, 21, 255)), ((145, 52, 24, 95), (6, 78, 21, 255))],
            [((410, 150, 62, 255), (190, 242, 100, 255)), ((295, 105, 45, 190), (250, 204, 21, 255)), ((185, 65, 28, 115), (6, 78, 21, 255))])
        _draw_radiating_rays(od, 88, 992, 306, s, (250, 204, 21, 255), length=58, spread=34)
    im = _aa_overlay_draw(im, decor)
    hero_end = _draw_tilted_box_hero(im, 134, info, GREEN, dashed=True)
    draw = ImageDraw.Draw(im)
    div_y = max(412, hero_end + 8); draw.line([(165, div_y), (915, div_y)], fill=GREEN, width=3)
    draw.ellipse([530, div_y - 10, 550, div_y + 10], fill=GREEN)
    cur_y = _draw_summary(draw, info, div_y + 52, BLACK) + 18
    cur_y = _draw_df_split(im, 42, cur_y, 1038, 345, info, (232, 248, 229), (22, 101, 52), GREEN, None, BLACK, RED, radius=34, chevron=True, left_two_tone=True) + 20
    cur_y = _draw_split_card(im, 42, cur_y, 1038, 345, info["rows"][0]["badge"], [[(info["rows"][0]["details"], (0, 51, 102))]], (221, 239, 254), (29, 78, 216), (0, 56, 112), (0, 56, 112), radius=34) + 20
    cur_y = _draw_split_card(im, 42, cur_y, 1038, 345, info["rows"][1]["badge"], [[(info["rows"][1]["details"], (88, 12, 80))]], (250, 232, 255), (126, 34, 206), (102, 12, 92), (102, 12, 92), radius=34) + 24
    draw = ImageDraw.Draw(im)
    _draw_tri_bars(draw, 126, 954, cur_y + 106, 86, GREEN, GREEN, gap=24, width=7)
    draw.rounded_rectangle([144, cur_y, 936, cur_y + 102], radius=51, fill=GOLD)
    draw_mixed_text(draw, W // 2, cur_y + 51, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, BLACK, anchor="mm")
    draw.rounded_rectangle([144, cur_y + 96, 936, cur_y + 210], radius=57, fill=GREEN)
    wf, wsz = fit_single_line_font(draw, "whatsapp: " + info["wa_number"], get_english_bold_font, 58, 38, 720)
    p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf); wx = (W - (w1 + w2)) // 2
    draw_mixed_text(draw, wx, cur_y + 153, p1, wf, wsz, (255, 255, 255), anchor="lm")
    draw_mixed_text(draw, wx + w1, cur_y + 153, p2, wf, wsz, GOLD, anchor="lm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_17(info, output_path):
    W, H = 1080, 1920
    GREEN, BLACK = (6, 78, 21), (17, 24, 39)
    im = Image.new("RGB", (W, H), (251, 249, 234))
    def decor(od, SW, SH, s):
        top_l = quad_bezier((0, 1745 * s), (540 * s, 1865 * s), (SW, 1715 * s))
        od.polygon(top_l + [(SW, SH), (0, SH)], fill=(132, 204, 22, 255))
        top_g = quad_bezier((0, 1765 * s), (540 * s, 1882 * s), (SW, 1735 * s))
        od.polygon(top_g + [(SW, SH), (0, SH)], fill=(6, 78, 21, 255))
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 64, 38, 960)
    draw_mixed_text(draw, W // 2, 215, info["hook_full"], hf, hsz, GREEN, anchor="mm")
    draw.line([(45, 276), (1035, 276)], fill=GREEN, width=4)
    cur_y = _draw_summary(draw, info, 365, BLACK) + 22
    cur_y = _draw_date_fee_box(draw, info, cur_y, (11, 110, 34), (255, 255, 255), (255, 255, 255), radius=34) + 56
    for row in info["rows"]:
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 46, 34, 940, 3)
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm"); cur_y += rsz + 18
        cur_y += 28
    cta_y0 = cur_y + 18
    draw.line([(45, cta_y0 + 26), (225, cta_y0 + 26)], fill=GREEN, width=3)
    draw.line([(855, cta_y0 + 26), (1035, cta_y0 + 26)], fill=GREEN, width=3)
    draw_mixed_text(draw, W // 2, cta_y0 + 26, "আবেদন করতে যোগাযোগ করুন।", get_body_font(44), 44, GREEN, anchor="mm")
    draw.rounded_rectangle([220, cta_y0 + 74, 860, cta_y0 + 172], radius=49, fill=(217, 242, 196))
    wf, wsz = fit_single_line_font(draw, "whatsapp: " + info["wa_number"], get_english_bold_font, 54, 36, 590)
    draw_mixed_text(draw, W // 2, cta_y0 + 123, "whatsapp: " + info["wa_number"], wf, wsz, GREEN, anchor="mm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_18(info, output_path):
    W, H = 1080, 1920
    NAVY, GOLD, RED, BLACK = (0, 42, 92), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (250, 252, 255))
    def decor(od, SW, SH, s):
        _draw_wave_corners(od, SW, SH, s,
            [((460, 180, 60, 195), (250, 204, 21, 255)), ((410, 150, 50, 165), (37, 99, 235, 255)), ((310, 110, 40, 125), (0, 42, 92, 255))],
            [((480, 185, 65, 245), (250, 204, 21, 255)), ((420, 155, 52, 205), (37, 99, 235, 255)), ((320, 115, 42, 155), (0, 42, 92, 255))])
        pts_tr = [(SW, 0), (SW - 330 * s, 0)] + quad_bezier((SW - 330 * s, 0), (SW - 120 * s, 45 * s), (SW, 155 * s))
        od.polygon(pts_tr, fill=(37, 99, 235, 220))
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([48, 155, 1032, 305], radius=75, fill=NAVY)
    _draw_two_tone_fitted(draw, W // 2, 230, info["hook_top"] + " ", info["hook_bottom"], (255, 255, 255), GOLD, get_body_font, 56, 32, 880)
    cur_y = _draw_summary(draw, info, 388, BLACK) + 8
    draw.line([(95, cur_y), (985, cur_y)], fill=(147, 197, 253), width=3)
    cur_y = _draw_date_fee_box(draw, info, cur_y + 24, (254, 247, 214), BLACK, RED, outline_col=RED, radius=32) + 24
    for row in info["rows"]:
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 44, 30, 910, 3)
        lh = rsz + 14; ch = max(148, len(rlines) * lh + 48)
        draw.rounded_rectangle([38, cur_y, 1042, cur_y + ch], radius=32, fill=(216, 236, 254), outline=(147, 197, 253), width=3)
        ty = cur_y + (ch - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines: draw_mixed_text(draw, W // 2, ty, rl, rf, rsz, (10, 32, 68), anchor="mm"); ty += lh
        cur_y += ch + 22
    _draw_pill_cta(draw, info, cur_y + 18, 60, 1020, NAVY, GOLD, (255, 255, 255), GOLD, NAVY, NAVY, radius=105, border_w=4)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

PACK2_RENDERERS = {
    11: _render_design_11, 12: _render_design_12, 13: _render_design_13, 14: _render_design_14,
    15: _render_design_15, 16: _render_design_16, 17: _render_design_17, 18: _render_design_18,
}
