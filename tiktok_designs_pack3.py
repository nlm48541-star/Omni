# -*- coding: utf-8 -*-
import os
from PIL import Image, ImageDraw

from tiktok_designer import (
    get_body_font, get_english_bold_font, get_advance_width,
    draw_mixed_text, draw_colored_spans_line, wrap_colored_spans,
    fit_single_line_font, fit_multiline_font, quad_bezier, _aa_overlay_draw,
    _draw_wave_corners, _draw_diag_stripes, _draw_summary, _draw_date_fee_box
)
from tiktok_designs_pack2 import (
    _draw_two_tone_fitted, _draw_dot_grid, _draw_radiating_rays, _draw_tri_bars,
    _draw_tilted_box_hero, _draw_layered_tilted_hero, _draw_two_tier_hero,
    _draw_split_card, _draw_df_split, _draw_pill_cta, _draw_white_wa_icon
)

def _render_design_19(info, output_path):
    W, H = 1080, 1920
    PURPLE, GOLD, INK = (88, 12, 130), (250, 204, 21), (34, 14, 52)
    im = Image.new("RGB", (W, H), (251, 249, 255))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_diag_stripes(od, SW, SH, s, (88, 12, 130, 255), (216, 180, 254, 255), True))
    draw = ImageDraw.Draw(im)
    hero_bot = _draw_two_tier_hero(draw, info, PURPLE, PURPLE, y_top=172)
    cur_y = _draw_summary(draw, info, hero_bot + 64, INK) + 12
    draw.line([(75, cur_y), (1005, cur_y)], fill=(107, 33, 168), width=3); cur_y += 26
    cur_y = _draw_df_split(im, 40, cur_y, 1040, 340, info, (243, 232, 255), None, PURPLE, PURPLE, INK, (107, 15, 140), radius=84, border_w=0) + 20
    cur_y = _draw_split_card(im, 40, cur_y, 1040, 340, info["rows"][0]["badge"], [[(info["rows"][0]["details"], INK)]], (243, 232, 255), None, PURPLE, PURPLE, radius=84, border_w=0) + 20
    cur_y = _draw_split_card(im, 40, cur_y, 1040, 340, info["rows"][1]["badge"], [[(info["rows"][1]["details"], INK)]], (243, 232, 255), None, PURPLE, PURPLE, radius=84, border_w=0) + 28
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([95, cur_y, 985, cur_y + 205], radius=102, fill=PURPLE)
    _draw_white_wa_icon(im, 195, cur_y + 102, size=102)
    draw = ImageDraw.Draw(im)
    draw.line([(265, cur_y + 32), (265, cur_y + 172)], fill=(255, 255, 255), width=4)
    cf, csz = fit_single_line_font(draw, "আবেদন করতে যোগাযোগ করুন।", get_body_font, 40, 28, 620)
    draw_mixed_text(draw, 295, cur_y + 62, "আবেদন করতে যোগাযোগ করুন।", cf, csz, (255, 255, 255), anchor="lm")
    wf, wsz = fit_single_line_font(draw, "whatsapp: " + info["wa_number"], get_english_bold_font, 52, 34, 620)
    p1, p2 = "whatsapp: ", info["wa_number"]; w1 = get_advance_width(p1, wf)
    draw_mixed_text(draw, 295, cur_y + 136, p1, wf, wsz, (255, 255, 255), anchor="lm")
    draw_mixed_text(draw, 295 + w1, cur_y + 136, p2, wf, wsz, GOLD, anchor="lm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_20(info, output_path):
    W, H = 1080, 1920
    GREEN, CRIMSON, GOLD, RED, BLACK = (6, 78, 21), (153, 12, 12), (250, 204, 21), (204, 17, 0), (17, 24, 39)
    im = Image.new("RGB", (W, H), (244, 250, 236))
    def decor(od, SW, SH, s):
        od.polygon([(SW, 0), (SW - 420 * s, 0)] + quad_bezier((SW - 420 * s, 0), (SW - 180 * s, 95 * s), (SW, 220 * s)), fill=(163, 218, 88, 255))
        od.polygon([(SW, 0), (SW - 310 * s, 0)] + quad_bezier((SW - 310 * s, 0), (SW - 110 * s, 60 * s), (SW, 150 * s)), fill=GREEN + (255,))
        top_l = quad_bezier((0, 1690 * s), (480 * s, 1825 * s), (SW, 1705 * s))
        od.polygon(top_l + [(SW, SH), (0, SH)], fill=(132, 204, 22, 255))
        top_g = quad_bezier((0, 1735 * s), (520 * s, 1855 * s), (SW, 1740 * s))
        od.polygon(top_g + [(SW, SH), (0, SH)], fill=GREEN + (255,))
        _draw_dot_grid(od, 36, 36, 4, 3, 28, 5, GREEN + (255,), s)
        _draw_dot_grid(od, 998, 785, 4, 3, 20, 4, GREEN + (255,), s)
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([46, 155, 1034, 305], radius=75, fill=GREEN)
    _draw_two_tone_fitted(draw, W // 2, 230, info["hook_top"] + " ", info["hook_bottom"], (255, 255, 255), GOLD, get_body_font, 56, 32, 880)
    draw.line([(115, 332), (965, 332)], fill=GREEN, width=3)
    cur_y = _draw_summary(draw, info, 400, BLACK) + 18
    cur_y = _draw_date_fee_box(draw, info, cur_y, (220, 245, 206), GREEN, RED, outline_col=GREEN, radius=38) + 24
    for row in info["rows"]:
        spans = [(row["badge"] + " – ", GREEN), (row["details"], BLACK)]
        sz, f, lines = 44, get_body_font(44), []
        for sz in range(44, 30, -2):
            f = get_body_font(sz); lines = wrap_colored_spans(draw, spans, f, sz, max_width=815)
            if len(lines) <= 3: break
        lh = sz + 13; ch = max(148, len(lines) * lh + 46)
        draw.rounded_rectangle([60, cur_y, 988, cur_y + ch], radius=34, fill=(253, 243, 208))
        draw.rounded_rectangle([86, cur_y + 22, 100, cur_y + ch - 22], radius=7, fill=GREEN)
        ty = cur_y + (ch - len(lines) * lh) // 2 + lh // 2
        for lt in lines: draw_colored_spans_line(draw, 542, ty, lt, f, sz); ty += lh
        cur_y += ch + 22
    cta_y0 = cur_y + 18
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_radiating_rays(od, 138, 942, cta_y0 + 110, s, GREEN + (255,), length=62, spread=32))
    draw = ImageDraw.Draw(im)
    _draw_pill_cta(draw, info, cta_y0, 150, 930, CRIMSON, None, (255, 255, 255), GOLD, GREEN, GREEN, radius=108, border_w=0)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_21(info, output_path):
    W, H = 1080, 1920
    NAVY, ORANGE, GOLD, BLACK = (0, 40, 85), (245, 158, 11), (245, 166, 15), (17, 24, 39)
    im = Image.new("RGB", (W, H), (250, 252, 255))
    def decor(od, SW, SH, s):
        _draw_diag_stripes(od, SW, SH, s, (245, 158, 11, 255), (0, 40, 85, 255), True)
        od.ellipse([SW - 250 * s, -50 * s, SW + 90 * s, 290 * s], fill=(224, 242, 254, 175))
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    hero_bot = _draw_two_tier_hero(draw, info, NAVY, NAVY, y_top=172)
    draw.rounded_rectangle([115, hero_bot + 16, 965, hero_bot + 26], radius=5, fill=ORANGE)
    cur_y = _draw_summary(draw, info, hero_bot + 82, BLACK) + 18
    cur_y = _draw_df_split(im, 36, cur_y, 1044, 340, info, (226, 242, 254), (147, 197, 253), NAVY, NAVY, BLACK, (234, 88, 12), radius=84, border_w=2) + 20
    cur_y = _draw_split_card(im, 36, cur_y, 1044, 340, info["rows"][0]["badge"], [[(info["rows"][0]["details"], NAVY)]], (226, 242, 254), (147, 197, 253), NAVY, NAVY, radius=84, border_w=2) + 20
    cur_y = _draw_split_card(im, 36, cur_y, 1044, 340, info["rows"][1]["badge"], [[(info["rows"][1]["details"], BLACK)]], (226, 242, 254), (147, 197, 253), NAVY, NAVY, radius=84, border_w=2) + 24
    draw = ImageDraw.Draw(im)
    _draw_pill_cta(draw, info, cur_y, 120, 960, NAVY, None, (255, 255, 255), GOLD, BLACK, BLACK, radius=108, border_w=0)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_22(info, output_path):
    W, H = 1080, 1920
    NAVY, GOLD, AMBER, RED = (0, 45, 95), (250, 204, 21), (245, 158, 11), (220, 38, 38)
    im = Image.new("RGB", (W, H), (249, 252, 255))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_wave_corners(od, SW, SH, s,
        [((390, 145, 65, 235), (219, 234, 254, 210)), ((340, 120, 54, 185), GOLD + (255,)), ((260, 92, 42, 130), NAVY + (255,))],
        [((470, 175, 75, 275), (219, 234, 254, 210)), ((410, 148, 62, 220), GOLD + (255,)), ((320, 112, 46, 160), NAVY + (255,))]))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([48, 152, 1032, 302], radius=75, fill=NAVY)
    _draw_two_tone_fitted(draw, W // 2, 227, info["hook_top"] + " ", info["hook_bottom"], (255, 255, 255), GOLD, get_body_font, 56, 32, 880)
    draw.line([(135, 342), (945, 342)], fill=NAVY, width=3)
    draw.polygon([(540, 326), (556, 342), (540, 358), (524, 342)], fill=NAVY)
    cur_y = _draw_summary(draw, info, 412, (10, 32, 68)) + 20
    cur_y = _draw_date_fee_box(draw, info, cur_y, (224, 242, 254), NAVY, RED, outline_col=NAVY, radius=48) + 52
    for idx, row in enumerate(info["rows"]):
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 46, 34, 940, 3)
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, NAVY, anchor="mm"); cur_y += rsz + 16
        if idx == 0: draw.line([(115, cur_y + 10), (965, cur_y + 10)], fill=AMBER, width=3); cur_y += 50
    _draw_pill_cta(draw, info, cur_y + 24, 128, 952, (254, 240, 158), NAVY, NAVY, NAVY, (255, 255, 255), GOLD, radius=72, border_w=4)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_23(info, output_path):
    W, H = 1080, 1920
    GREEN, BLACK = (4, 88, 18), (17, 24, 39)
    im = Image.new("RGB", (W, H), (250, 251, 249)); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([38, 165, 1042, 315], radius=52, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 34, 910)
    draw_mixed_text(draw, W // 2, 240, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.line([(38, 346), (1042, 346)], fill=GREEN, width=3)
    cur_y = _draw_summary(draw, info, 415, BLACK) + 20
    cur_y = _draw_date_fee_box(draw, info, cur_y, (216, 242, 198), GREEN, GREEN, radius=32) + 56
    for row in info["rows"]:
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 46, 34, 940, 3)
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm"); cur_y += rsz + 18
        cur_y += 28
    draw.line([(42, cur_y + 4), (1038, cur_y + 4)], fill=(74, 148, 74), width=3)
    _draw_pill_cta(draw, info, cur_y + 32, 42, 1038, GREEN, None, (255, 255, 255), (255, 255, 255), BLACK, GREEN, radius=100, border_w=0)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_24(info, output_path):
    W, H = 1080, 1920
    NAVY, ORANGE, GREEN, GOLD, RED, BLACK = (0, 42, 92), (234, 88, 12), (6, 78, 21), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (253, 251, 246))
    def decor(od, SW, SH, s):
        od.polygon([(0, 0), (175 * s, 0), (0, 175 * s)], fill=ORANGE + (255,))
        od.polygon([(175 * s, 0), (205 * s, 0), (0, 205 * s), (0, 175 * s)], fill=(255, 255, 255, 255))
        od.polygon([(205 * s, 0), (250 * s, 0), (0, 250 * s), (0, 205 * s)], fill=NAVY + (255,))
        od.polygon([(SW, SH), (SW - 250 * s, SH), (SW, SH - 250 * s)], fill=ORANGE + (255,))
        od.polygon([(SW - 250 * s, SH), (SW - 285 * s, SH), (SW, SH - 285 * s), (SW, SH - 250 * s)], fill=(255, 255, 255, 255))
        od.polygon([(SW - 285 * s, SH), (SW - 335 * s, SH), (SW, SH - 335 * s), (SW, SH - 285 * s)], fill=NAVY + (255,))
        od.ellipse([SW - 160 * s, 210 * s, SW + 120 * s, 490 * s], fill=(254, 243, 199, 170))
        _draw_radiating_rays(od, 88, 992, 306, s, ORANGE + (255,), length=52, spread=32)
    im = _aa_overlay_draw(im, decor)
    hero_end = _draw_tilted_box_hero(im, 134, info, NAVY, shadow_col=ORANGE)
    draw = ImageDraw.Draw(im)
    div_y = max(416, hero_end + 8); draw.line([(115, div_y), (965, div_y)], fill=ORANGE, width=4)
    draw.polygon([(540, div_y - 16), (556, div_y), (540, div_y + 16), (524, div_y)], fill=ORANGE)
    cur_y = _draw_summary(draw, info, div_y + 52, BLACK) + 18
    cur_y = _draw_df_split(im, 38, cur_y, 1042, 345, info, (224, 242, 254), (2, 132, 199), NAVY, NAVY, BLACK, RED, radius=56, left_two_tone=True, border_w=2) + 20
    cur_y = _draw_split_card(im, 38, cur_y, 1042, 345, info["rows"][0]["badge"], [[(info["rows"][0]["details"], NAVY)]], (255, 247, 237), ORANGE, ORANGE, ORANGE, radius=56, border_w=2) + 20
    cur_y = _draw_split_card(im, 38, cur_y, 1042, 345, info["rows"][1]["badge"], [[(info["rows"][1]["details"], BLACK)]], (236, 253, 245), (22, 101, 52), GREEN, GREEN, radius=56, border_w=2) + 24
    draw = ImageDraw.Draw(im)
    _draw_pill_cta(draw, info, cur_y, 110, 970, NAVY, GOLD, (255, 255, 255), GOLD, BLACK, BLACK, radius=105, border_w=5)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_25(info, output_path):
    W, H = 1080, 1920
    NAVY, GREEN, BLUE, PLUM, GOLD, RED, BLACK = (0, 42, 92), (6, 78, 21), (0, 82, 168), (102, 12, 92), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (244, 249, 255))
    def decor(od, SW, SH, s):
        _draw_wave_corners(od, SW, SH, s,
            [((320, 115, 45, 195), (163, 230, 53, 255)), ((215, 78, 32, 135), GREEN + (255,))],
            [((340, 125, 48, 200), (163, 230, 53, 255)), ((235, 85, 36, 145), GREEN + (255,))])
        od.ellipse([SW - 170 * s, 90 * s, SW + 90 * s, 350 * s], fill=(219, 234, 254, 170))
        _draw_radiating_rays(od, 82, 998, 316, s, GREEN + (255,), length=48, spread=28)
    im = _aa_overlay_draw(im, decor)
    hero_end = _draw_layered_tilted_hero(im, 108, info, (254, 249, 218), GREEN, NAVY)
    draw = ImageDraw.Draw(im)
    cur_y = _draw_summary(draw, info, max(440, hero_end + 36), BLACK) + 18
    cur_y = _draw_df_split(im, 36, cur_y, 1044, 345, info, (236, 253, 245), (22, 101, 52), GREEN, GREEN, BLACK, RED, radius=48, chevron=True, left_two_tone=True, border_w=2) + 18
    cur_y = _draw_split_card(im, 36, cur_y, 1044, 345, info["rows"][0]["badge"], [[(info["rows"][0]["details"], NAVY)]], (224, 242, 254), (29, 78, 216), BLUE, BLUE, radius=48, chevron=True, border_w=2) + 18
    cur_y = _draw_split_card(im, 36, cur_y, 1044, 345, info["rows"][1]["badge"], [[(info["rows"][1]["details"], BLACK)]], (250, 232, 255), (126, 34, 206), PLUM, PLUM, radius=48, chevron=True, border_w=2) + 22
    draw = ImageDraw.Draw(im)
    _draw_tri_bars(draw, 112, 968, cur_y + 110, 66, GREEN, GREEN, gap=24, width=7)
    _draw_pill_cta(draw, info, cur_y, 125, 955, NAVY, GOLD, (255, 255, 255), GOLD, BLACK, BLACK, radius=105, border_w=5)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

PACK3_RENDERERS = {
    19: _render_design_19, 20: _render_design_20, 21: _render_design_21,
    22: _render_design_22, 23: _render_design_23, 24: _render_design_24,
    25: _render_design_25,
}
