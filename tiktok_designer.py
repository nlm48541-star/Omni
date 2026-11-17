# -*- coding: utf-8 -*-
import os
import re
import math
import random
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
ELEMENTS_DIR = "Element"
ALL_DESIGN_IDS = list(range(1, 26))

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

def _highlight_numbers_and_dates(text, normal_col, highlight_col):
    months = r'(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|জানুয়ারি|ফেব্রুয়ারি|আগষ্ট)'
    num_tok = r'[০-৯\d]+(?:[,\.\-/][০-৯\d]+)*(?:/-)?'
    unit_tok = rf'(?:\s*(?:{months}|টাকা|/-))?'
    pat = rf'({num_tok}{unit_tok}(?:\s*(?:ও|,|এবং)\s*{num_tok}{unit_tok})*)'
    parts = re.split(pat, str(text))
    spans, has_hl = [], False
    for p in parts:
        if not p: continue
        if re.fullmatch(pat, p):
            spans.append((p, highlight_col)); has_hl = True
        else:
            spans.append((p, normal_col))
    return spans if has_hl else [(str(text), highlight_col)]

def _parse_bracket_highlights(text, normal_col, highlight_col):
    if '[' not in str(text):
        return _highlight_numbers_and_dates(text, normal_col, highlight_col)
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
            l1_words.append(w); idx = i + 1
        else: break

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

def _draw_date_fee_box(draw, info, y0, fill_col, text_col, red_col, outline_col=None, left_stripe_col=None, radius=28, width=4):
    spans = _parse_bracket_highlights(info["combined_df"], text_col, red_col)
    sz, f, lines = 46, get_body_font(46), []
    for sz in range(46, 32, -2):
        f = get_body_font(sz)
        lines = wrap_colored_spans(draw, spans, f, sz, max_width=900)
        if len(lines) <= 3: break
    lh = sz + 16
    box_h = max(180, len(lines) * lh + 60)
    y1 = y0 + box_h
    draw.rounded_rectangle([45, y0, 1035, y1], radius=radius, fill=fill_col, outline=outline_col, width=width if outline_col else 0)
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
# 🎨 DESIGN 1–10 (ORIGINAL DESIGNS — UNCHANGED)
# =========================================================================
def _render_design_1(info, output_path):
    W, H = 1080, 1920
    GREEN, BORDER_G, RED, BLACK = (6, 78, 21), (11, 94, 28), (204, 17, 0), (17, 24, 39)
    im = Image.new("RGB", (W, H), (247, 250, 243))
    def decor(od, SW, SH, s):
        _draw_wave_corners(od, SW, SH, s,
            [((360, 130, 55, 240), (221, 242, 161, 255)), ((280, 100, 48, 185), (151, 215, 0, 255)), ((150, 60, 30, 100), (6, 78, 21, 255))],
            [((420, 145, 62, 260), (221, 242, 161, 255)), ((330, 115, 52, 200), (151, 215, 0, 255)), ((185, 68, 32, 110), (6, 78, 21, 255))])
        top, bot = [], []
        for i in range(61):
            t = i / 60.0; xx = (95 + 890 * t) * s; arch = math.sin(math.pi * t); yt = (348 - 16 * arch) * s
            top.append((xx, yt)); bot.append((xx, yt + 14 * s * (arch ** 0.75)))
        od.polygon(top + list(reversed(bot)), fill=(234, 179, 8, 255))
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([42, 158, 1038, 312], radius=77, fill=GREEN)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 36, 910)
    draw_mixed_text(draw, W // 2, 235, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    cur_y = _draw_summary(draw, info, 405, BLACK)
    box_y0 = cur_y + 26; box_y1 = box_y0 + 230
    draw.rounded_rectangle([45, box_y0, 1035, box_y1], radius=32, fill=(232, 248, 229), outline=BORDER_G, width=4)
    draw.line([(540, box_y0 + 18), (540, box_y1 - 18)], fill=BORDER_G, width=4)
    lbl = get_body_font(44)
    draw_mixed_text(draw, 292, box_y0 + 50, info["date_title"], lbl, 44, BLACK, anchor="mm")
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 44, 30, 440, 2)
    dy = box_y0 + (116 if len(dlines) > 1 else 148)
    for dl in dlines: draw_mixed_text(draw, 292, dy, dl, df, dsz, RED, anchor="mm"); dy += dsz + 12
    draw_mixed_text(draw, 788, box_y0 + 50, info["fee_title"], lbl, 44, BLACK, anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 52, 30, 440, 2)
    fy = box_y0 + (118 if len(flines) > 1 else 148)
    for fl in flines: draw_mixed_text(draw, 788, fy, fl, ff, fsz, RED, anchor="mm"); fy += fsz + 12
    cur_y = box_y1 + 36
    for idx, row in enumerate(info["rows"]):
        bf, bsz = fit_single_line_font(draw, row["badge"], get_body_font, 42, 30, 265)
        pill_w = max(255, min(335, measure_mixed_text(draw, row["badge"], bf, bsz)[0] + 48)); tx = 70 + pill_w + 50
        df, dsz, dlines = fit_multiline_font(draw, row["details"], get_body_font, 44, 32, 1005 - tx, 3)
        lh = dsz + 14; ch = max(195, len(dlines) * lh + 64)
        draw.rounded_rectangle([45, cur_y, 1035, cur_y + ch], radius=28, fill=(253, 242, 208) if idx == 0 else (227, 242, 216))
        ym = cur_y + ch // 2
        draw.rounded_rectangle([70, ym - 44, 70 + pill_w, ym + 44], radius=44, fill=GREEN)
        draw_mixed_text(draw, 70 + pill_w // 2, ym, row["badge"], bf, bsz, (255, 255, 255), anchor="mm")
        draw_mixed_text(draw, 70 + pill_w + 22, ym, "–", get_body_font(44), 44, BLACK, anchor="mm")
        ty = cur_y + (ch - len(dlines) * lh) // 2 + lh // 2
        for dl in dlines: draw_mixed_text(draw, tx, ty, dl, df, dsz, BLACK, anchor="lm"); ty += lh
        cur_y += ch + 32
    _draw_stadium_cta(draw, info, cur_y + 20, GREEN, (250, 204, 21), (255, 255, 255), (253, 224, 71))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_2(info, output_path):
    W, H = 1080, 1920
    NAVY, GOLD, RED, BLACK = (0, 51, 102), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    def decor(od, SW, SH, s):
        od.ellipse([SW - 330 * s, -160 * s, SW + 180 * s, 360 * s], fill=(224, 242, 254, 255))
        od.ellipse([-210 * s, SH - 420 * s, 290 * s, SH + 180 * s], fill=(224, 242, 254, 255))
        _draw_wave_corners(od, SW, SH, s,
            [((340, 135, 60, 220), (250, 204, 21, 255)), ((245, 90, 50, 165), (0, 51, 102, 255))],
            [((430, 150, 80, 270), (250, 204, 21, 255)), ((310, 110, 60, 200), (0, 51, 102, 255))])
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([42, 158, 1038, 312], radius=77, fill=NAVY)
    hf, hsz = fit_single_line_font(draw, info["hook_full"], get_body_font, 56, 36, 910)
    draw_mixed_text(draw, W // 2, 235, info["hook_full"], hf, hsz, (255, 255, 255), anchor="mm")
    draw.rectangle([140, 336, 940, 345], fill=GOLD)
    cur_y = _draw_summary(draw, info, 405, BLACK)
    box_y1 = _draw_date_fee_box(draw, info, cur_y + 26, (254, 240, 184), BLACK, RED, left_stripe_col=GOLD)
    cur_y = box_y1 + 48
    for row in info["rows"]:
        pf, psz = fit_single_line_font(draw, row["badge"], get_body_font, 46, 32, 860)
        pw = min(940, max(380, measure_mixed_text(draw, row["badge"], pf, psz)[0] + 84)); px0 = (W - pw) // 2
        draw.rounded_rectangle([px0, cur_y, px0 + pw, cur_y + 82], radius=41, fill=NAVY)
        draw_mixed_text(draw, W // 2, cur_y + 41, row["badge"], pf, psz, (255, 255, 255), anchor="mm")
        cur_y += 120
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 46, 34, 940, 3)
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm"); cur_y += rsz + 14
        cur_y += 32
    _draw_stadium_cta(draw, info, cur_y + 18, NAVY, GOLD, GOLD, GOLD)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_3(info, output_path):
    W, H = 1080, 1920
    NAVY, GOLD, RED, BLACK = (0, 45, 90), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_diag_stripes(od, SW, SH, s, (0, 45, 90, 255), (250, 204, 21, 255), True))
    _draw_tilted_hero(im, 148, info, NAVY); draw = ImageDraw.Draw(im)
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
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_4(info, output_path):
    W, H = 1080, 1920
    GREEN, GOLD, RED, BLACK = (6, 78, 21), (250, 204, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (249, 250, 245))
    im = _aa_overlay_draw(im, lambda od, SW, SH, s: _draw_wave_corners(od, SW, SH, s,
        [((355, 128, 58, 240), (190, 242, 100, 255)), ((275, 98, 48, 185), (101, 163, 13, 255)), ((165, 58, 30, 110), (6, 78, 21, 255))],
        [((410, 145, 65, 265), (190, 242, 100, 255)), ((305, 110, 50, 200), (101, 163, 13, 255)), ((185, 65, 32, 115), (6, 78, 21, 255))]))
    _draw_tilted_hero(im, 148, info, GREEN); draw = ImageDraw.Draw(im)
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
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_5(info, output_path):
    W, H = 1080, 1920
    GREEN, RED, BLACK = (6, 78, 21), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255)); draw = ImageDraw.Draw(im)
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
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm"); cur_y += rsz + 18
        if idx == 0: draw.line([(180, cur_y + 12), (900, cur_y + 12)], fill=GREEN, width=4); cur_y += 58
    cta_y0 = cur_y + 42
    draw.rounded_rectangle([45, cta_y0, 1035, cta_y0 + 225], radius=44, fill=GREEN)
    draw_mixed_text(draw, W // 2, cta_y0 + 58, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw.line([(85, cta_y0 + 104), (995, cta_y0 + 104)], fill=(255, 255, 255), width=3)
    wf = get_english_bold_font(58); p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf); wx = (W - (w1 + w2)) // 2
    draw_mixed_text(draw, wx, cta_y0 + 162, p1, wf, 58, (255, 255, 255), anchor="lm")
    draw_mixed_text(draw, wx + w1, cta_y0 + 162, p2, wf, 58, (250, 204, 21), anchor="lm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_6(info, output_path):
    W, H = 1080, 1920
    GREEN, RED, BLACK = (6, 78, 21), (185, 28, 28), (17, 24, 39)
    im = Image.new("RGB", (W, H), (252, 251, 232)); draw = ImageDraw.Draw(im)
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
        for rl in rlines: draw_mixed_text(draw, W // 2, cur_y, rl, rf, rsz, BLACK, anchor="mm"); cur_y += rsz + 18
        cur_y += 28
    line_y = cur_y + 24; draw.line([(45, line_y), (1035, line_y)], fill=GREEN, width=4)
    draw.rounded_rectangle([160, line_y + 30, 920, line_y + 124], radius=47, fill=GREEN)
    draw_mixed_text(draw, W // 2, line_y + 77, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw.rounded_rectangle([95, line_y + 136, 985, line_y + 250], radius=46, fill=(255, 255, 255), outline=GREEN, width=4)
    wf = get_english_bold_font(58); p1, p2 = "whatsapp: ", info["wa_number"]
    w1, w2 = get_advance_width(p1, wf), get_advance_width(p2, wf); wx = (W - (w1 + w2)) // 2
    draw_mixed_text(draw, wx, line_y + 193, p1, wf, 58, BLACK, anchor="lm")
    draw_mixed_text(draw, wx + w1, line_y + 193, p2, wf, 58, GREEN, anchor="lm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_7(info, output_path):
    W, H = 1080, 1920
    GREEN, ORANGE, RED, BLACK = (6, 78, 21), (234, 88, 12), (220, 38, 38), (17, 24, 39)
    im = Image.new("RGB", (W, H), (255, 255, 255)); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([42, 152, 1038, 372], radius=42, fill=GREEN)
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 48, 30, 920)
    bf, bsz = fit_single_line_font(draw, info["hook_bottom"], get_body_font, 78, 44, 920)
    draw_mixed_text(draw, W // 2, 218, info["hook_top"], tf, tsz, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, 304, info["hook_bottom"], bf, bsz, (250, 204, 21), anchor="mm")
    cur_y = _draw_summary(draw, info, 430, BLACK)
    box_y0 = cur_y + 24; box_y1 = box_y0 + 195
    draw.rounded_rectangle([42, box_y0, 1038, box_y1], radius=28, fill=(254, 243, 199), outline=ORANGE, width=4)
    draw.line([(335, box_y0 + 18), (335, box_y1 - 18)], fill=ORANGE, width=4)
    draw.line([(710, box_y0 + 18), (710, box_y1 - 18)], fill=ORANGE, width=4)
    ym = (box_y0 + box_y1) // 2
    tf_lbl, tsz_lbl, tlines = fit_multiline_font(draw, info["date_title"], get_body_font, 42, 30, 265, 2)
    ty = ym - ((len(tlines) - 1) * (tsz_lbl + 10)) // 2
    for tl in tlines: draw_mixed_text(draw, 188, ty, tl, tf_lbl, tsz_lbl, BLACK, anchor="mm"); ty += tsz_lbl + 10
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 40, 28, 345, 3)
    dy = ym - ((len(dlines) - 1) * (dsz + 10)) // 2
    for dl in dlines: draw_mixed_text(draw, 522, dy, dl, df, dsz, RED, anchor="mm"); dy += dsz + 10
    fee_spans = [(info["fee_title"] + " ", BLACK), (info["fee_text"], RED)]
    ff, f_sz, flines = get_body_font(40), 40, []
    for f_sz in range(40, 29, -2):
        ff = get_body_font(f_sz); flines = wrap_colored_spans(draw, fee_spans, ff, f_sz, max_width=295)
        if len(flines) <= 3: break
    fy = ym - ((len(flines) - 1) * (f_sz + 10)) // 2
    for fl in flines: draw_colored_spans_line(draw, 874, fy, fl, ff, f_sz); fy += f_sz + 10
    cur_y = box_y1 + 36
    card_styles = [((232, 248, 229), (22, 101, 52)), ((254, 215, 170), ORANGE)]
    for idx, row in enumerate(info["rows"]):
        txt = row["badge"] + " – " + row["details"]
        rf, rsz, rlines = fit_multiline_font(draw, txt, get_body_font, 44, 32, 920, 3)
        lh = rsz + 14; ch = max(185, len(rlines) * lh + 58); fill_c, out_c = card_styles[idx]
        draw.rounded_rectangle([42, cur_y, 1038, cur_y + ch], radius=28, fill=fill_c, outline=out_c, width=4)
        ty = cur_y + (ch - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines: draw_mixed_text(draw, W // 2, ty, rl, rf, rsz, BLACK, anchor="mm"); ty += lh
        cur_y += ch + 30
    fy0 = max(cur_y + 32, 1475)
    draw.rectangle([0, fy0, W, fy0 + 12], fill=(245, 158, 11)); draw.rectangle([0, fy0 + 12, W, H], fill=GREEN)
    draw_mixed_text(draw, W // 2, fy0 + 76, "আবেদন করতে যোগাযোগ করুন।", get_body_font(46), 46, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, fy0 + 152, "whatsapp: " + info["wa_number"], get_english_bold_font(60), 60, (250, 204, 21), anchor="mm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

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
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([125, 152, 955, 372], radius=46, fill=GREEN)
    for dy in [250, 272]: draw.line([(25, dy), (108, dy)], fill=GREEN, width=4); draw.line([(972, dy), (1055, dy)], fill=GREEN, width=4)
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 46, 28, 760)
    bf, bsz = fit_single_line_font(draw, info["hook_bottom"], get_body_font, 76, 42, 760)
    draw_mixed_text(draw, W // 2, 218, info["hook_top"], tf, tsz, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, 304, info["hook_bottom"], bf, bsz, (250, 204, 21), anchor="mm")
    cur_y = _draw_summary(draw, info, 428, BLACK)
    box_y0 = cur_y + 24; box_y1 = box_y0 + 220
    _draw_headered_box(draw, [45, box_y0, 520, box_y1], 68, 24, GREEN, GREEN, MINT_BG)
    df_h, dsz_h = fit_single_line_font(draw, info["date_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 282, box_y0 + 34, info["date_title"], df_h, dsz_h, (255, 255, 255), anchor="mm")
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 40, 28, 425, 2)
    dy = box_y0 + (118 if len(dlines) > 1 else 144)
    for dl in dlines: draw_mixed_text(draw, 282, dy, dl, df, dsz, RED, anchor="mm"); dy += dsz + 10
    _draw_headered_box(draw, [560, box_y0, 1035, box_y1], 68, 24, GREEN, GREEN, MINT_BG)
    ff_h, fsz_h = fit_single_line_font(draw, info["fee_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 798, box_y0 + 34, info["fee_title"], ff_h, fsz_h, (255, 255, 255), anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 48, 28, 425, 2)
    fy = box_y0 + (120 if len(flines) > 1 else 144)
    for fl in flines: draw_mixed_text(draw, 798, fy, fl, ff, fsz, RED, anchor="mm"); fy += fsz + 10
    cur_y = box_y1 + 28
    for row in info["rows"]:
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 42, 30, 910, 3)
        lh = rsz + 14; bh = max(115, len(rlines) * lh + 38); ch = 64 + bh
        _draw_headered_box(draw, [45, cur_y, 1035, cur_y + ch], 64, 24, GREEN, GREEN, MINT_BG)
        bf_h, bsz_h = fit_single_line_font(draw, row["badge"], get_body_font, 40, 28, 900)
        draw_mixed_text(draw, W // 2, cur_y + 32, row["badge"], bf_h, bsz_h, (255, 255, 255), anchor="mm")
        ty = cur_y + 64 + (bh - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines: draw_mixed_text(draw, W // 2, ty, rl, rf, rsz, BLACK, anchor="mm"); ty += lh
        cur_y += ch + 24
    cta_y0 = cur_y + 24
    draw.rounded_rectangle([75, cta_y0, 1005, cta_y0 + 215], radius=107, fill=ORANGE)
    draw_mixed_text(draw, W // 2, cta_y0 + 64, "আবেদন করতে যোগাযোগ করুন।", get_body_font(44), 44, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, cta_y0 + 144, "whatsapp: " + info["wa_number"], get_english_bold_font(58), 58, (253, 224, 71), anchor="mm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

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
    im = _aa_overlay_draw(im, decor); draw = ImageDraw.Draw(im)
    tf, tsz = fit_single_line_font(draw, info["hook_top"], get_body_font, 48, 30, 900)
    bf, bsz = fit_single_line_font(draw, info["hook_bottom"], get_body_font, 80, 44, 900)
    draw_mixed_text(draw, W // 2, 212, info["hook_top"], tf, tsz, (255, 255, 255), anchor="mm")
    draw_mixed_text(draw, W // 2, 300, info["hook_bottom"], bf, bsz, GOLD, anchor="mm")
    cur_y = _draw_summary(draw, info, 432, BLACK)
    box_y0 = cur_y + 24; box_y1 = box_y0 + 220
    _draw_headered_box(draw, [45, box_y0, 520, box_y1], 68, 24, GREEN, GREEN, CREAM)
    df_h, dsz_h = fit_single_line_font(draw, info["date_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 282, box_y0 + 34, info["date_title"], df_h, dsz_h, (255, 255, 255), anchor="mm")
    df, dsz, dlines = fit_multiline_font(draw, info["date_text"], get_body_font, 40, 28, 425, 2)
    dy = box_y0 + (118 if len(dlines) > 1 else 144)
    for dl in dlines: draw_mixed_text(draw, 282, dy, dl, df, dsz, RED, anchor="mm"); dy += dsz + 10
    _draw_headered_box(draw, [560, box_y0, 1035, box_y1], 68, 24, GREEN, GREEN, CREAM)
    ff_h, fsz_h = fit_single_line_font(draw, info["fee_title"], get_body_font, 40, 28, 430)
    draw_mixed_text(draw, 798, box_y0 + 34, info["fee_title"], ff_h, fsz_h, (255, 255, 255), anchor="mm")
    ff, fsz, flines = fit_multiline_font(draw, info["fee_text"], get_body_font, 48, 28, 425, 2)
    fy = box_y0 + (120 if len(flines) > 1 else 144)
    for fl in flines: draw_mixed_text(draw, 798, fy, fl, ff, fsz, RED, anchor="mm"); fy += fsz + 10
    cur_y = box_y1 + 30
    for row in info["rows"]:
        rf, rsz, rlines = fit_multiline_font(draw, row["details"], get_body_font, 42, 30, 575, 3)
        lh = rsz + 14; ch = max(185, len(rlines) * lh + 58)
        draw.rounded_rectangle([45, cur_y, 1035, cur_y + ch], radius=28, fill=(228, 245, 219))
        draw.rounded_rectangle([45, cur_y, 335, cur_y + ch], radius=28, fill=GREEN)
        draw.rectangle([180, cur_y, 335, cur_y + ch], fill=GREEN)
        draw.polygon([(335, cur_y), (388, cur_y + ch // 2), (335, cur_y + ch)], fill=GREEN)
        draw.line([(406, cur_y + 18), (406, cur_y + ch - 18)], fill=GREEN, width=4)
        bf_c, bsz_c, blines = fit_multiline_font(draw, row["badge"], get_body_font, 42, 28, 265, 2)
        blh = bsz_c + 10; by = cur_y + (ch - len(blines) * blh) // 2 + blh // 2
        for bl in blines: draw_mixed_text(draw, 198, by, bl, bf_c, bsz_c, (255, 255, 255), anchor="mm"); by += blh
        ty = cur_y + (ch - len(rlines) * lh) // 2 + lh // 2
        for rl in rlines: draw_mixed_text(draw, 426, ty, rl, rf, rsz, BLACK, anchor="lm"); ty += lh
        cur_y += ch + 28
    cta_y0 = cur_y + 24
    draw.rounded_rectangle([45, cta_y0, 1035, cta_y0 + 225], radius=54, fill=GREEN)
    draw_mixed_text(draw, W // 2, cta_y0 + 56, "আবেদন করতে যোগাযোগ করুন।", get_body_font(44), 44, (255, 255, 255), anchor="mm")
    draw.rounded_rectangle([95, cta_y0 + 102, 985, cta_y0 + 202], radius=50, fill=GOLD)
    draw_mixed_text(draw, W // 2, cta_y0 + 152, "whatsapp: " + info["wa_number"], get_english_bold_font(60), 60, GREEN, anchor="mm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

def _render_design_10(info, output_path):
    W, H = 1080, 1920
    im = Image.new("RGB", (W, H), (253, 247, 215)); draw = ImageDraw.Draw(im)
    GREEN, BLACK, CRIMSON = (20, 90, 40), (17, 24, 39), (153, 27, 27)
    head_font = get_header_font(66)
    h1_lines = wrap_mixed_text(draw, info["hook_top"], head_font, 66, max_width=880); cur_y = 290
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
    body_font = get_body_font(48); cur_y += 28
    for l in wrap_mixed_text(draw, info["main_summary"], body_font, 48, max_width=880):
        draw_mixed_text(draw, W // 2, cur_y, l, body_font, 48, BLACK, anchor="mm"); cur_y += 64
    cur_y += 22; df_txt = _strip_brackets(info["combined_df"])
    for dl in wrap_mixed_text(draw, df_txt, body_font, 46, max_width=880):
        draw_mixed_text(draw, W // 2, cur_y, dl, body_font, 46, BLACK, anchor="mm"); cur_y += 62
    cur_y += 22
    for row in info["rows"]:
        r_txt = row["badge"] + " – " + row["details"]
        for rl in wrap_mixed_text(draw, r_txt, body_font, 46, max_width=880):
            draw_mixed_text(draw, W // 2, cur_y, rl, body_font, 46, CRIMSON, anchor="mm"); cur_y += 60
        cur_y += 10
    wa_y = max(1310, cur_y + 60); wa_num = info["wa_number"]; num_font = get_english_bold_font(66)
    num_w = measure_mixed_text(draw, wa_num, num_font, 66)[0]; wa_img = find_whatsapp_logo()
    if wa_img:
        wa_scaled = wa_img.resize((72, 72), Image.LANCZOS); sx = (W - (72 + 20 + num_w)) // 2
        im.paste(wa_scaled, (sx, wa_y - 36), wa_scaled); draw.text((sx + 92, wa_y), wa_num, font=num_font, fill=BLACK, anchor="lm")
    else:
        draw.ellipse([W // 2 - 250, wa_y - 36, W // 2 - 178, wa_y + 36], fill=(37, 211, 102))
        draw_mixed_text(draw, W // 2 - 214, wa_y, "WA", get_english_bold_font(32), 32, (255, 255, 255), anchor="mm")
        draw.text((W // 2 - 160, wa_y), wa_num, font=num_font, fill=BLACK, anchor="lm")
    cta_font = get_body_font(52)
    draw_mixed_text(draw, W // 2, wa_y + 85, "আবেদন করতে হোয়াটসঅ্যাপে", cta_font, 52, BLACK, anchor="mm")
    draw_mixed_text(draw, W // 2, wa_y + 150, "যোগাযোগ করুন।", cta_font, 52, BLACK, anchor="mm")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

# =========================================================================
# 🧩 SHARED HELPERS FOR NEW DESIGNS 11–25
# =========================================================================
def _split_two_tone(text):
    words = str(text).strip().split()
    return (" ".join(words[:-1]) + " ", words[-1]) if len(words) >= 2 else ("", str(text).strip())

def _draw_two_tone_fitted(draw, cx, cy, p1, p2, c1, c2, font_fn, start_sz, min_sz, max_w):
    spans = ([ (p1, c1) ] if p1 else []) + ([ (p2, c2) ] if p2 else [])
    if not spans: return
    full = (p1 or "") + (p2 or "")
    for sz in range(start_sz, min_sz - 1, -2):
        f = font_fn(sz)
        if measure_mixed_text(draw, full, f, sz)[0] <= max_w:
            draw_colored_spans_line(draw, cx, cy, spans, f, sz); return
    f = font_fn(min_sz); lines = wrap_colored_spans(draw, spans, f, min_sz, max_width=max_w); lh = min_sz + 10
    ty = cy - ((len(lines) - 1) * lh) // 2
    for lt in lines[:2]: draw_colored_spans_line(draw, cx, ty, lt, f, min_sz); ty += lh

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
    s = 2; cw, ch = 960 * s, 325 * s
    ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.rounded_rectangle([135 * s, 16 * s, 825 * s, 146 * s], radius=44 * s, fill=cream_col + (255,), outline=green_col + (255,), width=3 * s)
    tf, tsz = fit_single_line_font(od, info["hook_top"], get_body_font, 44 * s, 28 * s, 630 * s)
    draw_mixed_text(od, cw // 2, 66 * s, info["hook_top"], tf, tsz, green_col, anchor="mm")
    od.rounded_rectangle([42 * s, 108 * s, 918 * s, 274 * s], radius=40 * s, fill=navy_col + (255,))
    p1, p2 = _split_two_tone(info["hook_bottom"])
    _draw_two_tone_fitted(od, cw // 2, 191 * s, p1, p2, (255, 255, 255), (250, 204, 21), get_body_font, 76 * s, 42 * s, 800 * s)
    ts, bs = [], []
    for i in range(41):
        t = i / 40.0; xx = (185 + 590 * t) * s; arch = math.sin(math.pi * t); yt = (288 - 10 * arch) * s
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

def _draw_white_wa_icon(im, cx, cy, size=106):
    s = 2; sz = size * s; ov = Image.new("RGBA", (sz, sz), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); pad = int(sz * 0.1)
    d.ellipse([pad, pad, sz - pad, sz - pad], outline=(255, 255, 255, 255), width=int(sz * 0.085))
    d.polygon([(int(sz * 0.16), int(sz * 0.68)), (int(sz * 0.10), int(sz * 0.90)), (int(sz * 0.34), int(sz * 0.82))], fill=(255, 255, 255, 255))
    d.arc([int(sz * 0.30), int(sz * 0.30), int(sz * 0.70), int(sz * 0.70)], start=35, end=220, fill=(255, 255, 255, 255), width=int(sz * 0.10))
    ov_1x = ov.resize((size, size), Image.LANCZOS); im.paste(ov_1x, (cx - size // 2, cy - size // 2), ov_1x)

# =========================================================================
# 🎨 DESIGN 11–25 (MATCHING THE 15 NEW REFERENCE TEMPLATES)
# =========================================================================
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
        _draw_radiating_rays(od, 102, 978, 258, s, (76, 11, 110, 255), length=58, spread=32)
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

    draw_mixed_text(draw, 760, box_y0 + 108, info["fee_title"], get_body_font(40), 40, BLACK, anchor="mm")
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
        _draw_radiating_rays(od, 92, 988, 265, s, (250, 204, 21, 255), length=64, spread=34)
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
    draw.rounded_rectangle([105, cur_y, 975, cur_y + 205], radius=102, fill=PURPLE)
    _draw_white_wa_icon(im, 205, cur_y + 102, size=104)
    draw = ImageDraw.Draw(im)
    draw.line([(278, cur_y + 32), (278, cur_y + 172)], fill=(255, 255, 255), width=4)
    draw_mixed_text(draw, 312, cur_y + 62, "আবেদন করতে যোগাযোগ করুন।", get_body_font(42), 42, (255, 255, 255), anchor="lm")
    wf, wsz = fit_single_line_font(draw, "whatsapp: " + info["wa_number"], get_english_bold_font, 52, 34, 620)
    p1, p2 = "whatsapp: ", info["wa_number"]; w1 = get_advance_width(p1, wf)
    draw_mixed_text(draw, 312, cur_y + 136, p1, wf, wsz, (255, 255, 255), anchor="lm")
    draw_mixed_text(draw, 312 + w1, cur_y + 136, p2, wf, wsz, GOLD, anchor="lm")
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
        _draw_dot_grid(od, 944, 775, 4, 3, 28, 5, GREEN + (255,), s)
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
            f = get_body_font(sz); lines = wrap_colored_spans(draw, spans, f, sz, max_width=840)
            if len(lines) <= 3: break
        lh = sz + 13; ch = max(148, len(lines) * lh + 46)
        draw.rounded_rectangle([68, cur_y, 1012, cur_y + ch], radius=34, fill=(253, 243, 208))
        draw.rounded_rectangle([94, cur_y + 22, 108, cur_y + ch - 22], radius=7, fill=GREEN)
        ty = cur_y + (ch - len(lines) * lh) // 2 + lh // 2
        for lt in lines: draw_colored_spans_line(draw, 558, ty, lt, f, sz); ty += lh
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
        _draw_diag_stripes(od, SW, SH, s, ORANGE + (255,), NAVY + (255,), True)
        od.ellipse([SW - 160 * s, 210 * s, SW + 120 * s, 490 * s], fill=(254, 243, 199, 170))
        _draw_radiating_rays(od, 92, 988, 265, s, ORANGE + (255,), length=62, spread=34)
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
            [((340, 125, 50, 215), (163, 230, 53, 255)), ((235, 85, 36, 150), GREEN + (255,))],
            [((390, 145, 58, 240), (163, 230, 53, 255)), ((265, 95, 42, 175), GREEN + (255,))])
        od.ellipse([SW - 170 * s, 90 * s, SW + 90 * s, 350 * s], fill=(219, 234, 254, 170))
        _draw_radiating_rays(od, 92, 988, 265, s, GREEN + (255,), length=60, spread=32)
    im = _aa_overlay_draw(im, decor)
    hero_end = _draw_layered_tilted_hero(im, 108, info, (254, 249, 218), GREEN, NAVY)
    draw = ImageDraw.Draw(im)
    cur_y = _draw_summary(draw, info, max(440, hero_end + 36), BLACK) + 18
    cur_y = _draw_df_split(im, 36, cur_y, 1044, 345, info, (236, 253, 245), (22, 101, 52), GREEN, GREEN, BLACK, RED, radius=48, chevron=True, left_two_tone=True, border_w=2) + 18
    cur_y = _draw_split_card(im, 36, cur_y, 1044, 345, info["rows"][0]["badge"], [[(info["rows"][0]["details"], NAVY)]], (224, 242, 254), (29, 78, 216), BLUE, BLUE, radius=48, chevron=True, border_w=2) + 18
    cur_y = _draw_split_card(im, 36, cur_y, 1044, 345, info["rows"][1]["badge"], [[(info["rows"][1]["details"], BLACK)]], (250, 232, 255), (126, 34, 206), PLUM, PLUM, radius=48, chevron=True, border_w=2) + 22
    draw = ImageDraw.Draw(im)
    _draw_tri_bars(draw, 108, 972, cur_y + 110, 86, GREEN, GREEN, gap=24, width=7)
    _draw_pill_cta(draw, info, cur_y, 125, 955, NAVY, GOLD, (255, 255, 255), GOLD, BLACK, BLACK, radius=105, border_w=5)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True); im.save(output_path, "PNG", quality=95)
    return output_path

DESIGN_RENDERERS = {
    1: _render_design_1, 2: _render_design_2, 3: _render_design_3,
    4: _render_design_4, 5: _render_design_5, 6: _render_design_6,
    7: _render_design_7, 8: _render_design_8, 9: _render_design_9,
    10: _render_design_10, 11: _render_design_11, 12: _render_design_12,
    13: _render_design_13, 14: _render_design_14, 15: _render_design_15,
    16: _render_design_16, 17: _render_design_17, 18: _render_design_18,
    19: _render_design_19, 20: _render_design_20, 21: _render_design_21,
    22: _render_design_22, 23: _render_design_23, 24: _render_design_24,
    25: _render_design_25,
}

def render_poster_image(job_data, output_path, design_id=None):
    if design_id is None or design_id not in ALL_DESIGN_IDS:
        design_id = random.choice(ALL_DESIGN_IDS)
    print(f"  [🎨 Poster Design #{design_id}/25] Rendering poster...")
    return DESIGN_RENDERERS[design_id](_extract_poster_content(job_data), output_path)

def prepare_tiktok_slides(job_data, output_prefix="poster", design_id=None):
    out_path = output_prefix + "_1.png"
    render_poster_image(job_data, out_path, design_id=design_id)
    return [out_path]
