# -*- coding: utf-8 -*-
import os
import re
import math
import random
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
ELEMENTS_DIR = "Element"
ALL_DESIGN_IDS = list(range(1, 11))

def find_whatsapp_logo():
    for d in [ELEMENTS_DIR, "Elements", "element", "elements", ".", "Images", "images"]:
        if os.path.exists(d) and os.path.isdir(d):
            for f in os.listdir(d):
                fl = f.lower()
                if any(h in fl for h in ["whatsapp", "wa_logo", "whatsapp_logo", "whatsapp_icon", "wa"]) and fl.endswith(('.png', '.webp', '.jpg', '.jpeg')):
                    try:
                        im = Image.open(os.path.join(d, f)).convert("RGBA")
                        bbox = im.getbbox()
                        return im.crop(bbox) if bbox else im
                    except Exception:
                        pass
    return None

def find_font_file(font_hints, fallback_name="kalpurush.ttf"):
    if isinstance(font_hints, str):
        font_hints = [font_hints]
    all_fonts = []
    for d in [FONTS_DIR, ".", "fonts"]:
        if os.path.exists(d) and os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith(('.ttf', '.otf')):
                    all_fonts.append(os.path.join(d, f))

    if os.path.exists("/usr/share/fonts"):
        for root, _, files in os.walk("/usr/share/fonts"):
            for f in files:
                if f.lower().endswith(('.ttf', '.otf')) and any(k in f.lower() for k in ['bengali', 'bangla', 'kalpurush', 'solaiman', 'lohit', 'noto']):
                    all_fonts.append(os.path.join(root, f))

    for hint in font_hints:
        ch = hint.lower().replace(" ", "").replace("-", "").replace("_", "")
        for fpath in all_fonts:
            fn = os.path.basename(fpath).lower().replace(" ", "").replace("-", "").replace("_", "")
            if ch in fn:
                return fpath
    return all_fonts[0] if all_fonts else fallback_name

def get_header_font(size):
    path = find_font_file(["Shokuntola UNICODE", "Shokuntola", "shokuntola", "Li Ador Noirrit Bold", "kalpurush", "NotoSansBengali-Bold"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_body_font(size):
    path = find_font_file(["Li Ador Noirrit Bold", "Li Ador Noirrit", "kalpurush", "NotoSansBengali-Bold", "NotoSansBengali-Regular"])
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def get_english_bold_font(font_size):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, font_size)
            except Exception: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception: return ImageFont.load_default()

def remove_emojis(text):
    if not text: return ""
    pat = re.compile("[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\u2b00-\u2bff\u2300-\u23ff\u200d\ufe0f]", flags=re.UNICODE)
    return re.sub(r'[⎚💻👥📱📞🏢]+', '', pat.sub('', str(text)))

def split_text_by_script(text):
    clean = remove_emojis(text)
    tokens = re.split(r'([A-Za-z0-9]+(?:[A-Za-z0-9\:\-\+\/\.\_\@]*[A-Za-z0-9])?)', str(clean))
    return [(t, bool(re.match(r'^[A-Za-z0-9]+(?:[A-Za-z0-9\:\-\+\/\.\_\@]*[A-Za-z0-9])?$', t))) for t in tokens if t]

def get_advance_width(text, font):
    if not text: return 0.0
    try: return float(font.getlength(text))
    except Exception:
        try:
            b = font.getbbox(text)
            return float(b[2] - b[0])
        except Exception:
            return float(len(text) * 14)

def measure_mixed_text(draw, text, bn_font, font_size):
    eng_font = get_english_bold_font(font_size)
    total_w, max_h = 0.0, font_size
    for seg, is_eng in split_text_by_script(text):
        f = eng_font if is_eng else bn_font
        total_w += get_advance_width(seg, f)
        try:
            asc, desc = f.getmetrics()
            max_h = max(max_h, asc + desc)
        except Exception: pass
    return int(round(total_w)), int(round(max_h))

def draw_mixed_text(draw, x, y, text, bn_font, font_size, fill_color, anchor="lm"):
    eng_font = get_english_bold_font(font_size)
    total_w, _ = measure_mixed_text(draw, text, bn_font, font_size)
    cur_x = (x - total_w / 2.0) if anchor in ["mm", "center"] else ((x - total_w) if anchor in ["rm", "right"] else float(x))

    try:
        bn_asc, bn_desc = bn_font.getmetrics()
        eng_asc, _ = eng_font.getmetrics()
        baseline_y = y + int((bn_asc - bn_desc) * 0.40)
        has_m = True
    except Exception:
        has_m = False

    for seg, is_eng in split_text_by_script(text):
        f = eng_font if is_eng else bn_font
        w = get_advance_width(seg, f)
        if has_m:
            draw.text((cur_x, baseline_y - (eng_asc if is_eng else bn_asc)), seg, font=f, fill=fill_color, anchor="la")
        else:
            draw.text((cur_x, y), seg, font=f, fill=fill_color, anchor="lm")
        cur_x += w

def wrap_mixed_text(draw, text, bn_font, font_size, max_width=880):
    if not text: return []
    words = str(remove_emojis(text)).strip().split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        if measure_mixed_text(draw, test, bn_font, font_size)[0] <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(' '.join(cur))
            cur = [w]
    if cur: lines.append(' '.join(cur))
    return lines

def wrap_colored_spans(draw, spans, bn_font, font_size, max_width=880):
    tokens = [(p, col) for txt, col in spans for p in re.findall(r'\S+\s*|\s+', str(txt)) if p]
    lines, cur = [], []
    for tok, col in tokens:
        test = "".join(t for t, _ in cur) + tok
        if measure_mixed_text(draw, test.rstrip(), bn_font, font_size)[0] <= max_width or not cur:
            cur.append((tok, col))
        else:
            cur[-1] = (cur[-1][0].rstrip(), cur[-1][1])
            lines.append(cur)
            cur = [(tok.lstrip(), col)] if tok.strip() else []
    if cur:
        cur[-1] = (cur[-1][0].rstrip(), cur[-1][1])
        lines.append(cur)
    return lines

def draw_colored_spans_line(draw, center_x, y, line_tokens, bn_font, font_size):
    merged = []
    for txt, col in line_tokens:
        if not txt: continue
        if merged and merged[-1][1] == col:
            merged[-1] = (merged[-1][0] + txt, col)
        else:
            merged.append((txt, col))

    full_str = "".join(t for t, _ in merged)
    cur_x = center_x - measure_mixed_text(draw, full_str, bn_font, font_size)[0] / 2.0
    for txt, col in merged:
        w, _ = measure_mixed_text(draw, txt, bn_font, font_size)
        draw_mixed_text(draw, cur_x, y, txt, bn_font, font_size, col, anchor="lm")
        cur_x += w

def fit_single_line_font(draw, text, font_fn, start_size, min_size, max_width):
    for sz in range(start_size, min_size - 1, -2):
        f = font_fn(sz)
        if measure_mixed_text(draw, text, f, sz)[0] <= max_width:
            return f, sz
    return font_fn(min_size), min_size

def fit_multiline_font(draw, text, font_fn, start_size, min_size, max_width, max_lines):
    for sz in range(start_size, min_size - 1, -2):
        f = font_fn(sz)
        lines = wrap_mixed_text(draw, text, f, sz, max_width=max_width)
        if len(lines) <= max_lines:
            return f, sz, lines
    f = font_fn(min_size)
    return f, min_size, wrap_mixed_text(draw, text, f, min_size, max_width=max_width)

def clean_org_name(org_name):
    if not org_name: return "নিয়োগ বিজ্ঞপ্তি"
    clean = re.sub(r'[\r\n\t]+', ' ', str(org_name)).strip()
    clean = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Job\s*Circular.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'সার্কুলার.*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'202[0-9]|২০২[০-৯]', '', clean).strip(" -|,")
    return clean if len(clean) > 2 else org_name

def quad_bezier(p0, p1, p2, steps=48):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        pts.append((
            u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        ))
    return pts

def _aa_overlay_draw(base_im, draw_fn):
    W, H = base_im.size
    s = 2
    ov = Image.new("RGBA", (W * s, H * s), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(ov), W * s, H * s, s)
    ov_small = ov.resize((W, H), Image.LANCZOS)
    out = base_im.convert("RGBA")
    out.alpha_composite(ov_small)
    return out.convert("RGB")

def _draw_headered_box(draw, box, header_h, radius, border_col, header_col, body_col, border_w=4):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=body_col)
    draw.rounded_rectangle([x0, y0, x1, y0 + header_h], radius=radius, fill=header_col)
    draw.rectangle([x0, y0 + radius, x1, y0 + header_h], fill=header_col)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=border_col, width=border_w)

def _strip_brackets(txt):
    return str(txt).replace("[", "").replace("]", "").strip()

def _parse_bracket_highlights(text, normal_col, highlight_col):
    parts = re.split(r'(\[[^\]]+\])', str(text))
    spans = []
    for p in parts:
        if not p: continue
        if p.startswith('[') and p.endswith(']') and len(p) > 2:
            spans.append((p[1:-1], highlight_col))
        else:
            spans.append((p, normal_col))
    return spans or [(str(text), normal_col)]

def _extract_poster_content(job_data):
    org = clean_org_name(job_data.get("org_name", "প্রতিষ্ঠান"))
    p = job_data.get("poster") if isinstance(job_data.get("poster"), dict) else {}

    hook_top = _strip_brackets(remove_emojis(p.get("hero_top") or job_data.get("hook_top") or "যোগ্যতানুযায়ী আবেদন"))
    hook_bottom = _strip_brackets(remove_emojis(p.get("hero_bottom") or job_data.get("hook_bottom") or "নতুন চাকরির সুযোগ!"))
    hook_full = _strip_brackets(remove_emojis(p.get("hero_single_line") or job_data.get("hook_full") or (hook_top + " " + hook_bottom)))
    main_summary = _strip_brackets(remove_emojis(p.get("main_summary") or job_data.get("poster_main_summary") or (org + "-এ নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশ।")))

    date_title = _strip_brackets(remove_emojis(p.get("date_box_title") or "আবেদনের সময়"))
    date_text = _strip_brackets(remove_emojis(p.get("date_box_text") or "চলমান নিয়োগ"))
    fee_title = _strip_brackets(remove_emojis(p.get("fee_box_title") or "আবেদন ফি"))
    fee_text = _strip_brackets(remove_emojis(p.get("fee_box_text") or job_data.get("application_fee") or "বিজ্ঞপ্তিমতে"))
    combined_df = remove_emojis(p.get("combined_date_fee_line") or f"{date_title}: [{date_text}]। {fee_title}: [{fee_text}]।").strip()

    rows = [
        {
            "badge": _strip_brackets(remove_emojis(p.get("highlight_1_badge") or "পদের বিবরণ")),
            "details": _strip_brackets(remove_emojis(p.get("highlight_1_text") or (org + "-এর বিভিন্ন পদে যোগ্য প্রার্থীরা আবেদন করতে পারবেন।")))
        },
        {
            "badge": _strip_brackets(remove_emojis(p.get("highlight_2_badge") or "আবেদন তথ্য")),
            "details": _strip_brackets(remove_emojis(p.get("highlight_2_text") or "বিস্তারিত শর্তাবলি অনুযায়ী নির্ধারিত সময়ের মধ্যে আবেদন সম্পন্ন করুন।"))
        }
    ]
    wa_number = os.environ.get("WHATSAPP_NUMBER", "01540503092").strip() or "01540503092"
    return {
        "org": org, "hook_top": hook_top, "hook_bottom": hook_bottom, "hook_full": hook_full,
        "main_summary": main_summary, "date_title": date_title, "date_text": date_text,
        "fee_title": fee_title, "fee_text": fee_text, "combined_df": combined_df,
        "rows": rows, "wa_number": wa_number
    }

def _draw_tilted_hero(im, y_top, info, bg_col, top_col=(255, 255, 255), bot_col=(253, 224, 71), angle=2.4):
    pw, ph = 940, 225
    pill_im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill_im)
    pd.rounded_rectangle([8, 8, pw - 8, ph - 8], radius=46, fill=bg_col + (255,))
    tf, tsz = fit_single_line_font(pd, info["hook_top"], get_body_font, 48, 32, pw - 80)
    bf, bsz = fit_single_line_font(pd, info["hook_bottom"], get_body_font, 82, 46, pw - 80)
    draw_mixed_text(pd, pw // 2, 70, info["hook_top"], tf, tsz, top_col, anchor="mm")
    draw_mixed_text(pd, pw // 2, 152, info["hook_bottom"], bf, bsz, bot_col, anchor="mm")
    rot = pill_im.rotate(angle, resample=Image.BICUBIC, expand=True)
    im.paste(rot, ((im.width - rot.width) // 2, y_top), rot)

def _draw_inline_pill_row(draw, row, cur_y, pill_col, text_col=(17, 24, 39)):
    W = 1080
    bf, bsz = fit_single_line_font(draw, row["badge"], get_body_font, 42, 28, 340)
    bw, _ = measure_mixed_text(draw, row["badge"], bf, bsz)
    pill_w, pill_h = bw + 48, 74
    df, dsz = get_body_font(46), 46
    dash = " – "
    dash_w = measure_mixed_text(draw, dash, df, dsz)[0]
    avail1 = 960 - pill_w - dash_w

    words = row["details"].split()
    l1_words, idx = [], 0
    for i, w in enumerate(words):
        if measure_mixed_text(draw, " ".join(l1_words + [w]), df, dsz)[0] <= avail1:
            l1_words.append(w)
            idx = i + 1
        else:
            break

    if l1_words:
        l1_txt = dash + " ".join(l1_words)
        l1_w = measure_mixed_text(draw, l1_txt, df, dsz)[0]
        sx = (W - (pill_w + l1_w)) // 2
        draw.rounded_rectangle([sx, cur_y, sx + pill_w, cur_y + pill_h], radius=37, fill=pill_col)
        draw_mixed_text(draw, sx + pill_w // 2, cur_y + pill_h // 2, row["badge"], bf, bsz, (255, 255, 255), anchor="mm")
        draw_mixed_text(draw, sx + pill_w, cur_y + pill_h // 2, l1_txt, df, dsz, text_col, anchor="lm")
        rem = " ".join(words[idx:]).strip()
        ny = cur_y + pill_h + 38
    else:
        sx = (W - pill_w) // 2
        draw.rounded_rectangle([sx, cur_y, sx + pill_w, cur_y + pill_h], radius=37, fill=pill_col)
        draw_mixed_text(draw, W // 2, cur_y + pill_h // 2, row["badge"], bf, bsz, (255, 255, 255), anchor="mm")
        rem = row["details"]
        ny = cur_y + pill_h + 40

    if rem:
        rf, rsz, rlines = fit_multiline_font(draw, rem, get_body_font, 46, 34, 950, 3)
        for rl in rlines:
            draw_mixed_text(draw, W // 2, ny, rl, rf, rsz, text_col, anchor="mm")
            ny += rsz + 14
    return ny

def _draw_wave_corners(od, SW, SH, s, tl_layers, br_layers):
    for (tx, cx, cy, ly), col in tl_layers:
        pts = [(0, 0), (tx * s, 0)] + quad_bezier((tx * s, 0), (cx * s, cy * s), (0, ly * s))
        od.polygon(pts, fill=col)
    for (bx, cx, cy, ry), col in br_layers:
        pts = [(SW, SH), (SW - bx * s, SH)] + quad_bezier((SW - bx * s, SH), (SW - cx * s, SH - cy * s), (SW, SH - ry * s))
        od.polygon(pts, fill=col)

def _draw_diag_stripes(od, SW, SH, s, col1, col2, mirror_top_left=True):
    if mirror_top_left:
        od.polygon([(0, 0), (300 * s, 0), (0, 300 * s)], fill=col1)
        od.polygon([(300 * s, 0), (345 * s, 0), (0, 345 * s), (0, 300 * s)], fill=(255, 255, 255, 255))
        od.polygon([(345 * s, 0), (400 * s, 0), (0, 400 * s), (0, 345 * s)], fill=col2)
    od.polygon([(SW, SH), (SW - 340 * s, SH), (SW, SH - 340 * s)], fill=col1)
    od.polygon([(SW - 340 * s, SH), (SW - 385 * s, SH), (SW, SH - 385 * s), (SW, SH - 340 * s)], fill=(255, 255, 255, 255))
    od.polygon([(SW - 385 * s, SH), (SW - 440 * s, SH), (SW, SH - 440 * s), (SW, SH - 385 * s)], fill=col2)

def _draw_summary(draw, info, start_y, col=(17, 24, 39)):
    sf, ssz, slines = fit_multiline_font(draw, info["main_summary"], get_body_font, 56, 40, 950, 3)
    y = start_y
    for l in slines:
        draw_mixed_text(draw, 540, y, l, sf, ssz, col, anchor="mm")
        y += ssz + 18
    return y

def _draw_date_fee_box(draw, info, y0, fill_col, text_col, red_col, outline_col=None, left_stripe_col=None):
    spans = _parse_bracket_highlights(info["combined_df"], text_col, red_col)
    sz, f, lines = 46, get_body_font(46), []
    for sz in range(46, 32, -2):
        f = get_body_font(sz)
        lines = wrap_colored_spans(draw, spans, f, sz, max_width=900)
        if len(lines) <= 3:
            break
    lh = sz + 16
    box_h = max(180, len(lines) * lh + 60)
    y1 = y0 + box_h
    draw.rounded_rectangle([45, y0, 1035, y1], radius=28, fill=fill_col, outline=outline_col, width=4 if outline_col else 0)
    if left_stripe_col:
        draw.rounded_rectangle([45, y0, 68, y1], radius=12, fill=left_stripe_col)
        draw.rectangle([57, y0, 68, y1], fill=left_stripe_col)
    cy = y0 + (box_h - len(lines) * lh) // 2 + lh // 2
    for lt in lines:
        draw_colored_spans_line(draw, 550 if left_stripe_col else 540, cy, lt, f, sz)
        cy += lh
    return y1

def _draw_stadium_cta(draw, info, y0, bg_col, border_col, prefix_col, num_col):
    y1 = y0 + 225
    draw.rounded_rectangle([95, y0, 985, y1], radius=112, fill=bg_col, outline=border_col, width=7)
    draw_mixed_text(draw, 540, y0 + 58, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw.line([(175, y0 + 104), (905, y0 + 104)], fill=(255, 255, 255), width=3)
    wf = get_english_bold_font(58)
    p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf)
    wx = (1080 - (w1 + w2)) // 2
    draw_mixed_text(draw, wx, y0 + 162, p1, wf, 58, prefix_col, anchor="lm")
    draw_mixed_text(draw, wx + w1, y0 + 162, p2, wf, 58, num_col, anchor="lm")

# =========================================================================
# 🎨 DESIGN 1: Soft Mint + Green/Lime Waves + Swoosh + 2-Col Box + Colored Cards
# =========================================================================
def _render_design_1(info, output_path):
    W, H = 1080, 1920
    GREEN, BORDER_G, RED, BLACK = (6, 78, 21), (11, 94, 28), (204, 17, 0), (17, 24, 39)
    im = Image.new("RGB", (W, H), (247, 250, 243))

    def decor(od, SW, SH, s):
        _draw_wave_corners(
            od, SW, SH, s,
            [((360, 130, 55, 240), (221, 242, 161, 255)), ((280, 100, 48, 185), (151, 215, 0, 255)), ((150, 60, 30, 100), (6, 78, 21, 255))],
            [((420, 145, 62, 260), (221, 242, 161, 255)), ((330, 115, 52, 200), (151, 215, 0, 255)), ((185, 68, 32, 110), (6, 78, 21, 255))]
        )
        top, bot = [], []
        for i in range(61):
            t = i / 60.0
            xx = (95 + 890 * t) * s
            arch = math.sin(math.pi * t)
            yt = (348 - 16 * arch) * s
            top.append((xx, yt))
            bot.append((xx, yt + 14 * s * (arch ** 0.75)))
        od.polygon(top + list(reversed(bot)), fill=(234, 179, 8, 255))

    im = _aa_overlay_draw(im, decor)
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([42, 158, 1038, 312], radius=77, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 36, 910)
    draw_mixed_text(draw, W // 2, 235, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")

    cur_y = _draw_summary(draw, info, 405, BLACK)
    box_y0 = cur_y + 26
    box_y1 = box_y0 + 230
    draw.rounded_rectangle([45, box_y0, 1035, box_y1], radius=32, fill=(232, 248, 229), outline=BORDER_G, width=4)
    draw.line([(540, box_y0 + 18), (540, box_y1 - 18)], fill=BORDER_G, width=4)

    lbl = get_body_font(44)
    draw_mixed_text(draw, 292, box_y0 + 50, info["date_title"], lbl, 44, BLACK, anchor="mm")
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 44, 30, 440, 2)
    dy = box_y0 + (116 if len(dlines) > 1 else 148)
    for dl in dlines:
        draw_mixed_text(draw, 292, dy, dl, df, dsz, RED, anchor="mm")
        dy += dsz + 12

    draw_mixed_text(draw, 788, box_y0 + 50, info["fee_title"], lbl, 44, BLACK, anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 52, 30, 440, 2)
    fy = box_y0 + (118 if len(flines) > 1 else 148)
    for fl in flines:
        draw_mixed_text(draw, 788, fy, fl, ff, fsz, RED, anchor="mm")
        fy += fsz + 12

    cur_y = box_y1 + 36
    for idx, row in enumerate(info["rows"]):
        bf, bsz = fit_single_line_font(draw, row["badge"], get_body_font, 42, 30, 265)
        pill_w = max(255, min(335, measure_mixed_text(draw, row["badge"], bf, bsz)[0] + 48))
        tx = 70 + pill_w + 50
        df, dsz, dlines = fit_multiline_font(draw, row["details"], get_body_font, 44, 32, 1005 - tx, 3)
        lh = dsz + 14
        ch = max(195, len(dlines) * lh + 64)
        draw.rounded_rectangle([45, cur_y, 1035, cur_y + ch], radius=28, fill=(253, 242, 208) if idx == 0 else (227, 242, 216))
        ym = cur_y + ch // 2
        draw.rounded_rectangle([70, ym - 44, 70 + pill_w, ym + 44], radius=44, fill=GREEN)
        draw_mixed_text(draw, 70 + pill_w // 2, ym, row["badge"], bf, bsz, (255, 255, 255), anchor="mm")
        draw_mixed_text(draw, 70 + pill_w + 22, ym, "–", get_body_font(44), 44, BLACK, anchor="mm")
        ty = cur_y + (ch - len(dlines) * lh) // 2 + lh // 2
        for dl in dlines:
            draw_mixed_text(draw, tx, ty, dl, df, dsz, BLACK, anchor="lm")
            ty += lh
        cur_y += ch + 32

    _draw_stadium_cta(draw, info, cur_y + 20, GREEN, (250, 204, 21), (255, 255, 255), (253, 224, 71))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 2: Navy & Gold Theme + Left Gold Accent + Centered Pill Sections
# =========================================================================
def _render_design_2(info, output_path):
    W, H = 1080, 1920
    NAVY, GOLD, RED, BLACK = (0, 51, 102), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))

    def decor(od, SW, SH, s):
        od.ellipse([SW - 330 * s, -160 * s, SW + 180 * s, 360 * s], fill=(224, 242, 254, 255))
        od.ellipse([-210 * s, SH - 420 * s, 290 * s, SH + 180 * s], fill=(224, 242, 254, 255))
        _draw_wave_corners(
            od, SW, SH, s,
            [((340, 135, 60, 220), (250, 204, 21, 255)), ((245, 90, 50, 165), (0, 51, 102, 255))],
            [((430, 150, 80, 270), (250, 204, 21, 255)), ((310, 110, 60, 200), (0, 51, 102, 255))]
        )

    im = _aa_overlay_draw(im, decor)
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([42, 158, 1038, 312], radius=77, fill=NAVY)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 36, 910)
    draw_mixed_text(draw, W // 2, 235, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.rectangle([140, 336, 940, 345], fill=GOLD)

    cur_y = _draw_summary(draw, info, 405, BLACK)
    box_y1 = _draw_date_fee_box(draw, info, cur_y + 26, (254, 240, 184), BLACK, RED, left_stripe_col=GOLD)

    cur_y = box_y1 + 48
    for row in info["rows"]:
        pf, psz = fit_single_line_font(draw, row["badge"], get_body_font, 46, 32, 860)
        pw = min(940, max(380, measure_mixed_text(draw, row["badge"], pf, psz)[0] + 84))
        px0 = (W - pw) // 2
        draw.rounded_rectangle([px0, cur_y, px0 + pw, cur_y + 82], radius=41, fill=NAVY)
        draw_mixed_text(draw, W // 2, cur_y + 41, row["badge"], pf, psz, (255, 255, 255), anchor="mm")
        cur_y += 120
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 46, 34, 940, 3)
        for rl in rlines:
            draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm")
            cur_y += rsz + 14
        cur_y += 32

    _draw_stadium_cta(draw, info, cur_y + 18, NAVY, GOLD, GOLD, GOLD)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 3: Diagonal Navy/Yellow Stripes + Tilted Badge + Inline Pills
# =========================================================================
def _render_design_3(info, output_path):
    W, H = 1080, 1920
    NAVY, GOLD, RED, BLACK = (0, 45, 90), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_diag_stripes(od, SW, SH, s, (0, 45, 90, 255), (250, 204, 21, 255), True))
    _draw_tilted_hero(im, 148, info, NAVY)
    draw = ImageDraw.Draw(im)

    cur_y = _draw_summary(draw, info, 440, BLACK)
    draw.line([(65, cur_y + 14), (1015, cur_y + 14)], fill=NAVY, width=3)
    box_y1 = _draw_date_fee_box(draw, info, cur_y + 40, (254, 240, 138), BLACK, RED)

    cur_y = _draw_inline_pill_row(draw, info["rows"][0], box_y1 + 42, NAVY, BLACK)
    draw.line([(65, cur_y + 12), (1015, cur_y + 12)], fill=(156, 163, 175), width=2)
    cur_y = _draw_inline_pill_row(draw, info["rows"][1], cur_y + 38, NAVY, BLACK)

    cta_y0 = cur_y + 34
    draw.rounded_rectangle([42, cta_y0, 1038, cta_y0 + 225], radius=48, fill=NAVY)
    draw_mixed_text(draw, W // 2, cta_y0 + 56, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw.rounded_rectangle([185, cta_y0 + 104, 895, cta_y0 + 198], radius=47, fill=GOLD)
    draw_mixed_text(draw, W // 2, cta_y0 + 151, "whatsapp: " + info["wa_number"], get_english_bold_font(54), 54, BLACK, anchor="mm")
    for dy in [139, 162]:
        draw.line([(72, cta_y0 + dy), (165, cta_y0 + dy)], fill=GOLD, width=4)
        draw.line([(915, cta_y0 + dy), (1008, cta_y0 + dy)], fill=GOLD, width=4)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 4: Green/Lime Waves + Tilted Green Badge + Mint Box + Yellow CTA Pill
# =========================================================================
def _render_design_4(info, output_path):
    W, H = 1080, 1920
    GREEN, GOLD, RED, BLACK = (6, 78, 21), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (249, 250, 245))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_wave_corners(
        od, SW, SH, s,
        [((355, 128, 58, 240), (190, 242, 100, 255)), ((275, 98, 48, 185), (101, 163, 13, 255)), ((165, 58, 30, 110), (6, 78, 21, 255))],
        [((410, 145, 65, 265), (190, 242, 100, 255)), ((305, 110, 50, 200), (101, 163, 13, 255)), ((185, 65, 32, 115), (6, 78, 21, 255))]
    ))
    _draw_tilted_hero(im, 148, info, GREEN)
    draw = ImageDraw.Draw(im)

    cur_y = _draw_summary(draw, info, 440, BLACK)
    draw.line([(65, cur_y + 14), (1015, cur_y + 14)], fill=(22, 101, 52), width=3)
    box_y1 = _draw_date_fee_box(draw, info, cur_y + 40, (220, 252, 231), GREEN, RED, outline_col=(22, 101, 52))

    cur_y = _draw_inline_pill_row(draw, info["rows"][0], box_y1 + 42, GREEN, BLACK)
    draw.line([(65, cur_y + 12), (1015, cur_y + 12)], fill=(134, 239, 172), width=2)
    cur_y = _draw_inline_pill_row(draw, info["rows"][1], cur_y + 38, GREEN, BLACK)

    cta_y0 = cur_y + 34
    draw.rounded_rectangle([55, cta_y0, 1025, cta_y0 + 225], radius=54, fill=GREEN)
    draw_mixed_text(draw, W // 2, cta_y0 + 56, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw.rounded_rectangle([115, cta_y0 + 104, 965, cta_y0 + 198], radius=47, fill=GOLD)
    draw_mixed_text(draw, W // 2, cta_y0 + 151, "whatsapp: " + info["wa_number"], get_english_bold_font(58), 58, BLACK, anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 5: Minimal White + Pill Cap Divider + Mint Box + Clean Highlight Rows
# =========================================================================
def _render_design_5(info, output_path):
    W, H = 1080, 1920
    GREEN, RED, BLACK = (6, 78, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([40, 158, 1040, 310], radius=44, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 36, 920)
    draw_mixed_text(draw, W // 2, 234, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.line([(45, 352), (1035, 352)], fill=GREEN, width=4)
    draw.rounded_rectangle([465, 340, 615, 364], radius=12, fill=GREEN)

    cur_y = _draw_summary(draw, info, 422, BLACK)
    box_y1 = _draw_date_fee_box(draw, info, cur_y + 28, (217, 242, 208), GREEN, RED)

    cur_y = box_y1 + 60
    for idx, row in enumerate(info["rows"]):
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 48, 36, 940, 3)
        for rl in rlines:
            draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm")
            cur_y += rsz + 18
        if idx == 0:
            draw.line([(180, cur_y + 12), (900, cur_y + 12)], fill=GREEN, width=4)
            cur_y += 58

    cta_y0 = cur_y + 42
    draw.rounded_rectangle([45, cta_y0, 1035, cta_y0 + 225], radius=44, fill=GREEN)
    draw_mixed_text(draw, W // 2, cta_y0 + 58, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw.line([(85, cta_y0 + 104), (995, cta_y0 + 104)], fill=(255, 255, 255), width=3)
    wf = get_english_bold_font(58)
    p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf)
    wx = (W - (w1 + w2)) // 2
    draw_mixed_text(draw, wx, cta_y0 + 162, p1, wf, 58, (255, 255, 255), anchor="lm")
    draw_mixed_text(draw, wx + w1, cta_y0 + 162, p2, wf, 58, (250, 204, 21), anchor="lm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 6: Pale Cream + Blush Pink Box (All Red) + Two-Piece Outline CTA
# =========================================================================
def _render_design_6(info, output_path):
    W, H = 1080, 1920
    GREEN, RED, BLACK = (6, 78, 21), (185, 28, 28), (17, 24, 39)
    im = Image.new("RGB", (W, H), (252, 251, 232))
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([40, 158, 1040, 310], radius=44, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 36, 920)
    draw_mixed_text(draw, W // 2, 234, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.line([(45, 348), (1035, 348)], fill=GREEN, width=4)

    cur_y = _draw_summary(draw, info, 415, BLACK)
    box_y1 = _draw_date_fee_box(draw, info, cur_y + 28, (250, 220, 217), RED, RED)

    cur_y = box_y1 + 60
    for row in info["rows"]:
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 48, 36, 940, 3)
        for rl in rlines:
            draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm")
            cur_y += rsz + 18
        cur_y += 28

    line_y = cur_y + 24
    draw.line([(45, line_y), (1035, line_y)], fill=GREEN, width=4)
    draw.rounded_rectangle([160, line_y + 30, 920, line_y + 124], radius=47, fill=GREEN)
    draw_mixed_text(draw, W // 2, line_y + 77, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")

    draw.rounded_rectangle([95, line_y + 136, 985, line_y + 250], radius=46, fill=(255, 255, 255), outline=GREEN, width=4)
    wf = get_english_bold_font(58)
    p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf)
    wx = (W - (w1 + w2)) // 2
    draw_mixed_text(draw, wx, line_y + 193, p1, wf, 58, BLACK, anchor="lm")
    draw_mixed_text(draw, wx + w1, line_y + 193, p2, wf, 58, GREEN, anchor="lm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 7: 3-Col Orange Bordered Box + Green/Peach Cards + Full-Bleed Footer
# =========================================================================
def _render_design_7(info, output_path):
    W, H = 1080, 1920
    GREEN, ORANGE, RED, BLACK = (6, 78, 21), (234, 88, 12), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([42, 152, 1038, 372], radius=42, fill=GREEN)
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 48, 30, 920)
    bf, bsz = fit_single_line_font(draw, info["hook_bottom"], get_body_font, 78, 44, 920)
    draw_mixed_text(draw, W // 2, 218, info["hook_top"], tf, tsz, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, 304, info["hook_bottom"], bf, bsz, (250, 204, 21), anchor="mm")

    cur_y = _draw_summary(draw, info, 430, BLACK)
    box_y0 = cur_y + 24
    box_y1 = box_y0 + 195
    draw.rounded_rectangle([42, box_y0, 1038, box_y1], radius=28, fill=(254, 243, 199), outline=ORANGE, width=4)
    draw.line([(335, box_y0 + 18), (335, box_y1 - 18)], fill=ORANGE, width=4)
    draw.line([(710, box_y0 + 18), (710, box_y1 - 18)], fill=ORANGE, width=4)

    ym = (box_y0 + box_y1) // 2
    tf_lbl, tsz_lbl, tlines = fit_multiline_font(draw, info["date_title"], get_body_font, 42, 30, 265, 2)
    ty = ym - ((len(tlines) - 1) * (tsz_lbl + 10)) // 2
    for tl in tlines:
        draw_mixed_text(draw, 188, ty, tl, tf_lbl, tsz_lbl, BLACK, anchor="mm")
        ty += tsz_lbl + 10

    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 40, 28, 345, 3)
    dy = ym - ((len(dlines) - 1) * (dsz + 10)) // 2
    for dl in dlines:
        draw_mixed_text(draw, 522, dy, dl, df, dsz, RED, anchor="mm")
        dy += dsz + 10

    fee_spans = [(info["fee_title"] + " ", BLACK), (info["fee_text"], RED)]
    ff, f_sz, flines = get_body_font(40), 40, []
    for f_sz in range(40, 29, -2):
        ff = get_body_font(f_sz)
        flines = wrap_colored_spans(draw, fee_spans, ff, f_sz, max_width=295)
        if len(flines) <= 3:
            break
    fy = ym - ((len(flines) - 1) * (f_sz + 10)) // 2
    for fl in flines:
        draw_colored_spans_line(draw, 874, fy, fl, ff, f_sz)
        fy += f_sz + 10

    cur_y = box_y1 + 36
    card_styles = [((232, 248, 229), (22, 101, 52)), ((254, 215, 170), ORANGE)]
    for idx, row in enumerate(info["rows"]):
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 44, 32, 920, 3)
        lh = rsz + 14
        ch = max(185, len(rlines) * lh + 58)
        fill_c, out_c = card_styles[idx]
        draw.rounded_rectangle([42, cur_y, 1038, cur_y + ch], radius=28, fill=fill_c, outline=out_c, width=4)
        ty = cur_y + (ch - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines:
            draw_mixed_text(draw, W // 2, ty, rl, rf, rsz, BLACK, anchor="mm")
            ty += lh
        cur_y += ch + 30

    fy0 = max(cur_y + 32, 1475)
    draw.rectangle([0, fy0, W, fy0 + 12], fill=(245, 158, 11))
    draw.rectangle([0, fy0 + 12, W, H], fill=GREEN)
    draw_mixed_text(draw, W // 2, fy0 + 76, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, fy0 + 152, "whatsapp: " + info["wa_number"], get_english_bold_font(60), 60, (250, 204, 21), anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 8: Winged Hero Box + Headered Mint Boxes + Orange CTA + Bottom Stripes
# =========================================================================
def _render_design_8(info, output_path):
    W, H = 1080, 1920
    GREEN, MINT_BG, ORANGE, RED, BLACK = (6, 78, 21), (240, 253, 244), (234, 88, 12), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))

    def decor(od, SW, SH, s):
        od.polygon([(0, SH), (0, SH - 180 * s), (150 * s, SH)], fill=(6, 78, 21, 255))
        od.polygon([(150 * s, SH), (185 * s, SH), (0, SH - 215 * s), (0, SH - 180 * s)], fill=(255, 255, 255, 255))
        od.polygon([(185 * s, SH), (225 * s, SH), (0, SH - 255 * s), (0, SH - 215 * s)], fill=(6, 78, 21, 255))
        od.polygon([(SW, SH), (SW, SH - 180 * s), (SW - 150 * s, SH)], fill=(6, 78, 21, 255))
        od.polygon([(SW - 150 * s, SH), (SW - 185 * s, SH), (SW, SH - 215 * s), (SW, SH - 180 * s)], fill=(255, 255, 255, 255))
        od.polygon([(SW - 185 * s, SH), (SW - 225 * s, SH), (SW, SH - 255 * s), (SW, SH - 215 * s)], fill=(6, 78, 21, 255))

    im = _aa_overlay_draw(im, decor)
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([125, 152, 955, 372], radius=46, fill=GREEN)
    for dy in [250, 272]:
        draw.line([(25, dy), (108, dy)], fill=GREEN, width=4)
        draw.line([(972, dy), (1055, dy)], fill=GREEN, width=4)
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 46, 28, 760)
    bf, bsz = fit_single_line_font(draw, info["hook_bottom"], get_body_font, 76, 42, 760)
    draw_mixed_text(draw, W // 2, 218, info["hook_top"], tf, tsz, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, 304, info["hook_bottom"], bf, bsz, (250, 204, 21), anchor="mm")

    cur_y = _draw_summary(draw, info, 428, BLACK)
    box_y0 = cur_y + 24
    box_y1 = box_y0 + 220

    _draw_headered_box(draw, [45, box_y0, 520, box_y1], 68, 24, GREEN, GREEN, MINT_BG)
    df_h, dsz_h = fit_single_line_font(draw, info["date_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 282, box_y0 + 34, info["date_title"], df_h, dsz_h, (255, 255, 255), anchor="mm")
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 40, 28, 425, 2)
    dy = box_y0 + (118 if len(dlines) > 1 else 144)
    for dl in dlines:
        draw_mixed_text(draw, 282, dy, dl, df, dsz, RED, anchor="mm")
        dy += dsz + 10

    _draw_headered_box(draw, [560, box_y0, 1035, box_y1], 68, 24, GREEN, GREEN, MINT_BG)
    ff_h, fsz_h = fit_single_line_font(draw, info["fee_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 798, box_y0 + 34, info["fee_title"], ff_h, fsz_h, (255, 255, 255), anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 48, 28, 425, 2)
    fy = box_y0 + (120 if len(flines) > 1 else 144)
    for fl in flines:
        draw_mixed_text(draw, 798, fy, fl, ff, fsz, RED, anchor="mm")
        fy += fsz + 10

    cur_y = box_y1 + 28
    for row in info["rows"]:
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 42, 30, 910, 3)
        lh = rsz + 14
        bh = max(115, len(rlines) * lh + 38)
        ch = 64 + bh
        _draw_headered_box(draw, [45, cur_y, 1035, cur_y + ch], 64, 24, GREEN, GREEN, MINT_BG)
        bf_h, bsz_h = fit_single_line_font(draw, row["badge"], get_body_font, 40, 28, 900)
        draw_mixed_text(draw, W // 2, cur_y + 32, row["badge"], bf_h, bsz_h, (255, 255, 255), anchor="mm")
        ty = cur_y + 64 + (bh - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines:
            draw_mixed_text(draw, W // 2, ty, rl, rf, rsz, BLACK, anchor="mm")
            ty += lh
        cur_y += ch + 24

    cta_y0 = cur_y + 24
    draw.rounded_rectangle([75, cta_y0, 1005, cta_y0 + 215], radius=107, fill=ORANGE)
    draw_mixed_text(draw, W // 2, cta_y0 + 64, "আবেদন করতে যোগাযোগ করুন।", get_body_font(44), 44, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, cta_y0 + 144, "whatsapp: " + info["wa_number"], get_english_bold_font(58), 58, (253, 224, 71), anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 9: Arched Banner + Gold Rim + Cream Info Boxes + Chevron Arrow Tabs
# =========================================================================
def _render_design_9(info, output_path):
    W, H = 1080, 1920
    GREEN, GOLD, CREAM, RED, BLACK = (6, 78, 21), (250, 204, 21), (254, 252, 232), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))

    def decor(od, SW, SH, s):
        _draw_diag_stripes(od, SW, SH, s, (250, 204, 21, 255), (6, 78, 21, 255), True)
        top_c = quad_bezier((35 * s, 175 * s), (540 * s, 120 * s), (1045 * s, 175 * s))
        bot_gold = quad_bezier((1045 * s, 376 * s), (540 * s, 402 * s), (35 * s, 376 * s))
        bot_green = quad_bezier((1045 * s, 364 * s), (540 * s, 388 * s), (35 * s, 364 * s))
        od.polygon(top_c + [(1045 * s, 376 * s)] + bot_gold + [(35 * s, 175 * s)], fill=(250, 204, 21, 255))
        od.polygon(top_c + [(1045 * s, 364 * s)] + bot_green + [(35 * s, 175 * s)], fill=(6, 78, 21, 255))

    im = _aa_overlay_draw(im, decor)
    draw = ImageDraw.Draw(im)

    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 48, 30, 900)
    bf, bsz = fit_single_line_font(draw, info["hook_bottom"], get_body_font, 80, 44, 900)
    draw_mixed_text(draw, W // 2, 212, info["hook_top"], tf, tsz, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, 300, info["hook_bottom"], bf, bsz, GOLD, anchor="mm")

    cur_y = _draw_summary(draw, info, 432, BLACK)
    box_y0 = cur_y + 24
    box_y1 = box_y0 + 220

    _draw_headered_box(draw, [45, box_y0, 520, box_y1], 68, 24, GREEN, GREEN, CREAM)
    df_h, dsz_h = fit_single_line_font(draw, info["date_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 282, box_y0 + 34, info["date_title"], df_h, dsz_h, (255, 255, 255), anchor="mm")
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 40, 28, 425, 2)
    dy = box_y0 + (118 if len(dlines) > 1 else 144)
    for dl in dlines:
        draw_mixed_text(draw, 282, dy, dl, df, dsz, RED, anchor="mm")
        dy += dsz + 10

    _draw_headered_box(draw, [560, box_y0, 1035, box_y1], 68, 24, GREEN, GREEN, CREAM)
    ff_h, fsz_h = fit_single_line_font(draw, info["fee_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 798, box_y0 + 34, info["fee_title"], ff_h, fsz_h, (255, 255, 255), anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 48, 28, 425, 2)
    fy = box_y0 + (120 if len(flines) > 1 else 144)
    for fl in flines:
        draw_mixed_text(draw, 798, fy, fl, ff, fsz, RED, anchor="mm")
        fy += fsz + 10

    cur_y = box_y1 + 30
    for row in info["rows"]:
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 42, 30, 575, 3)
        lh = rsz + 14
        ch = max(185, len(rlines) * lh + 58)
        draw.rounded_rectangle([45, cur_y, 1035, cur_y + ch], radius=28, fill=(228, 245, 219))
        draw.rounded_rectangle([45, cur_y, 335, cur_y + ch], radius=28, fill=GREEN)
        draw.rectangle([180, cur_y, 335, cur_y + ch], fill=GREEN)
        draw.polygon([(335, cur_y), (388, cur_y + ch // 2), (335, cur_y + ch)], fill=GREEN)
        draw.line([(406, cur_y + 18), (406, cur_y + ch - 18)], fill=GREEN, width=4)

        bf_c, bsz_c, blines = fit_multiline_font(draw, row["badge"], get_body_font, 42, 28, 265, 2)
        blh = bsz_c + 10
        by = cur_y + (ch - len(blines) * blh) // 2 + blh // 2
        for bl in blines:
            draw_mixed_text(draw, 198, by, bl, bf_c, bsz_c, (255, 255, 255), anchor="mm")
            by += blh

        ty = cur_y + (ch - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines:
            draw_mixed_text(draw, 426, ty, rl, rf, rsz, BLACK, anchor="lm")
            ty += lh
        cur_y += ch + 28

    cta_y0 = cur_y + 24
    draw.rounded_rectangle([45, cta_y0, 1035, cta_y0 + 225], radius=54, fill=GREEN)
    draw_mixed_text(draw, W // 2, cta_y0 + 56, "আবেদন করতে যোগাযোগ করুন।", get_body_font(44), 44, (255, 255, 255), anchor="mm")
    draw.rounded_rectangle([95, cta_y0 + 102, 985, cta_y0 + 202], radius=50, fill=GOLD)
    draw_mixed_text(draw, W // 2, cta_y0 + 152, "whatsapp: " + info["wa_number"], get_english_bold_font(60), 60, GREEN, anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🎨 DESIGN 10: Original Classic Cream Poster Design (Smart AI Content)
# =========================================================================
def _render_design_10(info, output_path):
    W, H = 1080, 1920
    im = Image.new("RGB", (W, H), (253, 247, 215))
    draw = ImageDraw.Draw(im)
    GREEN, BLACK, CRIMSON = (20, 90, 40), (17, 24, 39), (153, 27, 27)

    head_font = get_header_font(66)
    h1_lines = wrap_mixed_text(draw, info["hook_top"], head_font, 66, max_width=880)
    cur_y = 290
    for idx, line in enumerate(h1_lines):
        draw_mixed_text(draw, W // 2, cur_y, line, head_font, 66, GREEN, anchor="mm")
        if idx == len(h1_lines) - 1:
            w1 = measure_mixed_text(draw, line, head_font, 66)[0]
            draw.line([(max(100, (W - w1) // 2 - 15), cur_y + 44), (min(W - 100, (W + w1) // 2 + 15), cur_y + 44)], fill=GREEN, width=4)
        cur_y += 80

    cur_y += 10
    for line in wrap_mixed_text(draw, info["hook_bottom"], head_font, 64, max_width=880):
        draw_mixed_text(draw, W // 2, cur_y, line, head_font, 64, GREEN, anchor="mm")
        w2 = measure_mixed_text(draw, line, head_font, 64)[0]
        draw.line([(max(120, (W - w2) // 2 - 10), cur_y + 44), (min(W - 120, (W + w2) // 2 + 10), cur_y + 44)], fill=GREEN, width=4)
        cur_y += 76

    body_font = get_body_font(48)
    cur_y += 28
    for l in wrap_mixed_text(draw, info["main_summary"], body_font, 48, max_width=880):
        draw_mixed_text(draw, W // 2, cur_y, l, body_font, 48, BLACK, anchor="mm")
        cur_y += 64

    cur_y += 22
    df_txt = _strip_brackets(info["combined_df"])
    for dl in wrap_mixed_text(draw, df_txt, body_font, 46, max_width=880):
        draw_mixed_text(draw, W // 2, cur_y, dl, body_font, 46, BLACK, anchor="mm")
        cur_y += 62

    cur_y += 22
    for row in info["rows"]:
        r_txt = row["badge"] + " – " + row["details"]
        for rl in wrap_mixed_text(draw, r_txt, body_font, 46, max_width=880):
            draw_mixed_text(draw, W // 2, cur_y, rl, body_font, 46, CRIMSON, anchor="mm")
            cur_y += 60
        cur_y += 10

    wa_y = max(1310, cur_y + 60)
    wa_num = info["wa_number"]
    num_font = get_english_bold_font(66)
    num_w = measure_mixed_text(draw, wa_num, num_font, 66)[0]
    wa_img = find_whatsapp_logo()
    if wa_img:
        wa_scaled = wa_img.resize((72, 72), Image.LANCZOS)
        sx = (W - (72 + 20 + num_w)) // 2
        im.paste(wa_scaled, (sx, wa_y - 36), wa_scaled)
        draw.text((sx + 92, wa_y), wa_num, font=num_font, fill=BLACK, anchor="lm")
    else:
        draw.ellipse([W // 2 - 250, wa_y - 36, W // 2 - 178, wa_y + 36], fill=(37, 211, 102))
        draw_mixed_text(draw, W // 2 - 214, wa_y, "WA", get_english_bold_font(32), 32, (255, 255, 255), anchor="mm")
        draw.text((W // 2 - 160, wa_y), wa_num, font=num_font, fill=BLACK, anchor="lm")

    cta_font = get_body_font(52)
    draw_mixed_text(draw, W // 2, wa_y + 85, "আবেদন করতে হোয়াটসঅ্যাপে", cta_font, 52, BLACK, anchor="mm")
    draw_mixed_text(draw, W // 2, wa_y + 150, "যোগাযোগ করুন।", cta_font, 52, BLACK, anchor="mm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    im.save(output_path, "PNG", quality=95)
    return output_path

DESIGN_RENDERERS = {
    1: _render_design_1, 2: _render_design_2, 3: _render_design_3,
    4: _render_design_4, 5: _render_design_5, 6: _render_design_6,
    7: _render_design_7, 8: _render_design_8, 9: _render_design_9,
    10: _render_design_10,
}

def render_poster_image(job_data, output_path, design_id=None):
    if design_id is None or design_id not in ALL_DESIGN_IDS:
        design_id = random.choice(ALL_DESIGN_IDS)
    print(f"  [🎨 Poster Design #{design_id}/10] Rendering poster...")
    return DESIGN_RENDERERS[design_id](_extract_poster_content(job_data), output_path)

def prepare_tiktok_slides(job_data, output_prefix="poster", design_id=None):
    out_path = output_prefix + "_1.png"
    render_poster_image(job_data, out_path, design_id=design_id)
    return [out_path]
