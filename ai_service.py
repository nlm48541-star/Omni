# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image

TRACKER_FILE = "key_tracker.json"

OPENROUTER_MODELS = [
    "google/gemma-4-31b-it:free",                 # 31B Vision (সেরা বাংলা OCR)
    "google/gemma-4-26b-a4b-it:free",             # 26B Vision
    "dots-studio/dots-3-note-preview:free",       # Multimodal Vision (512K)
    "nvidia/nemotron-3.5-super-vl:free",          # 120B Vision
    "openrouter/free",                            # Auto-router fallback
    "nvidia/nemotron-3-ultra-550b-a55b:free"      # 550B Text fallback
]

OPENROUTER_VISION_MODELS = {
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "openrouter/free"
}

OLLAMA_MODELS = [
    "kimi-k2.6",               # 1.04T (Vision)
    "glm-5.2",                 # 753B
    "mistral-large-3:675b",    # 675B (Vision)
    "deepseek-v4.1-flash",     # 552B (Vision)
    "deepseek-v4-pro",
    "qwen3.5:397b",            # 397B
    "minimax-m3",
    "glm-5.3-flash",           # Vision
    "gpt-oss:120b",            # 120B
    "nemotron-3-super",        # 120B
    "gemma4:31b"               # 31B (Vision)
]

OLLAMA_VISION_MODELS = {
    "kimi-k2.6", "mistral-large-3:675b", "deepseek-v4.1-flash",
    "glm-5.3-flash", "gemma4:31b"
}

GROQ_MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"]
CEREBRAS_MODELS = ["zai-glm-4.7", "qwen-3-235b-a22b-instruct-2507", "gpt-oss-120b"]
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]

_DEVA_TO_BN = {
    '\u0901': 'ঁ', '\u0902': 'ং', '\u0903': 'ঃ',
    '\u0905': 'অ', '\u0906': 'আ', '\u0907': 'ই', '\u0908': 'ঈ', '\u0909': 'উ', '\u090A': 'ঊ',
    '\u090B': 'ঋ', '\u090D': 'এ', '\u090E': 'এ', '\u090F': 'এ', '\u0910': 'ঐ',
    '\u0911': 'ও', '\u0912': 'ও', '\u0913': 'ও', '\u0914': 'ঔ',
    '\u0915': 'ক', '\u0916': 'খ', '\u0917': 'গ', '\u0918': 'ঘ', '\u0919': 'ঙ',
    '\u091A': 'চ', '\u091B': 'ছ', '\u091C': 'জ', '\u091D': 'ঝ', '\u091E': 'ঞ',
    '\u091F': 'ট', '\u0920': 'ঠ', '\u0921': 'ড', '\u0922': 'ঢ', '\u0923': 'ণ',
    '\u0924': 'ত', '\u0925': 'থ', '\u0926': 'দ', '\u0927': 'ধ', '\u0928': 'ন', '\u0929': 'ন',
    '\u092A': 'প', '\u092B': 'ফ', '\u092C': 'ব', '\u092D': 'ভ', '\u092E': 'ম',
    '\u092F': 'য', '\u0930': 'র', '\u0931': 'র', '\u0932': 'ল', '\u0933': 'ল', '\u0934': 'ল',
    '\u0935': 'ব', '\u0936': 'শ', '\u0937': 'ষ', '\u0938': 'স', '\u0939': 'হ',
    '\u093E': 'া', '\u093F': 'ি', '\u0940': 'ী', '\u0941': 'ু', '\u0942': 'ূ',
    '\u0943': 'ৃ', '\u0944': 'ৄ', '\u0945': 'ে', '\u0946': 'ে', '\u0947': 'ে', '\u0948': 'ৈ',
    '\u0949': 'ো', '\u094A': 'ো', '\u094B': 'ো', '\u094C': 'ৌ', '\u094D': '্',
    '\u0958': 'ক', '\u0959': 'খ', '\u095A': 'গ', '\u095B': 'জ',
    '\u095C': 'ড়', '\u095D': 'ঢ়', '\u095E': 'ফ', '\u095F': 'য়',
    '\u0964': '।', '\u0965': '।',
    '\u0966': '০', '\u0967': '১', '\u0968': '২', '\u0969': '৩', '\u096A': '৪',
    '\u096B': '৫', '\u096C': '৬', '\u096D': '৭', '\u096E': '৮', '\u096F': '৯',
}


def normalize_bengali_nukta(text):
    if not text:
        return ""
    s = str(text)
    return s.replace('\u09af\u09bc', '\u09df').replace('\u09a1\u09bc', '\u09dc').replace('\u09a2\u09bc', '\u09dd')


def clean_bengali_text(text):
    """হিন্দি/দেবনাগরী লিক মেরামত করে, ভিনদেশি টফু ক্যারেক্টার বাদ দেয় এবং য়/ড়/ঢ় নর্মালাইজ করে"""
    if text is None:
        return ""
    s = normalize_bengali_nukta(str(text))
    repaired = []
    for ch in s:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:
            if ch in _DEVA_TO_BN:
                repaired.append(_DEVA_TO_BN[ch])
        else:
            repaired.append(ch)
    s = normalize_bengali_nukta("".join(repaired))
    s = re.sub(r'[^\u0980-\u09FF\x20-\x7E\n\r\t।–—‘’“”৳]', '', s)
    return re.sub(r'[ \t]+', ' ', s).strip()


def _sanitize_ai_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_ai_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_ai_json(v) for v in obj]
    if isinstance(obj, str):
        return clean_bengali_text(obj)
    return obj


def parse_multi_keys(env_var_names):
    if isinstance(env_var_names, str):
        env_var_names = [env_var_names]
    for env_name in env_var_names:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            keys = [k.strip() for k in re.split(r'[\r\n,;]+', raw) if k.strip() and not k.strip().startswith('#')]
            if keys:
                return keys
    return []


def get_saved_key_index(platform, total_keys):
    if total_keys <= 0:
        return 0
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                return int(json.load(f).get(f"{platform}_index", 0)) % total_keys
        except Exception:
            pass
    return 0


def save_key_index(platform, index, total_keys):
    if total_keys <= 0:
        return
    data = {}
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[f"{platform}_index"] = index % total_keys
    try:
        with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def get_ollama_chat_endpoint():
    raw = os.environ.get("OLLAMA_API_URL", "").strip()
    if not raw or not raw.startswith("http"):
        raw = "https://ollama.com"
    base = raw.rstrip("/")
    for sfx in ["/api/chat", "/api", "/v1"]:
        if base.endswith(sfx):
            base = base[:-len(sfx)]
    return f"{base.rstrip('/')}/api/chat"


def encode_image_base64(image_path, max_dim=1600):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception:
        return None


def parse_json_safely(raw_text):
    if not raw_text:
        return None
    cleaned = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL | re.IGNORECASE).strip()
    for block in re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL | re.IGNORECASE):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{', cleaned):
        try:
            obj, _ = dec.raw_decode(cleaned[m.start():])
            if isinstance(obj, dict) and (obj.get("org_name") or obj.get("poster") or obj.get("motion") or obj.get("scripts")):
                return obj
        except Exception:
            continue
    return None


def remove_years(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', re.sub(r'২০২[০-৯]|\b202[0-9]\b', '', str(text))).strip()


def sanitize_voiceover_script(script):
    if not script:
        return ""
    text = clean_bengali_text(script)
    bad_patterns = [
        r'সম্পূর্ণ\s*ভিডিও(?:টি)?\s*(?:দেখুন|দেখার\s*জন্য\s*ধন্যবাদ|শেষ\s*পর্যন্ত\s*দেখুন)[^\.\!\n।]*[\.\!\n।]?',
        r'পুরো\s*ভিডিও(?:টি)?\s*(?:দেখুন|দেখার\s*জন্য\s*ধন্যবাদ)[^\.\!\n।]*[\.\!\n।]?',
        r'ভিডিওটি\s*শেষ\s*পর্যন্ত\s*দেখার\s*জন্য\s*ধন্যবাদ[^\.\!\n।]*[\.\!\n।]?',
        r'(?:অফিসিয়াল\s*)?ওয়েবসাইটে?\s*(?:ভিজিট\s*করুন|গিয়ে\s*আবেদন\s*করুন|দেখুন)[^\.\!\n।]*[\.\!\n।]?',
        r'চ্যানেলটি\s*সাবস্ক্রাইব\s*করুন[^\.\!\n।]*[\.\!\n।]?',
        r'লাইক\s*(?:ও|এবং)\s*শেয়ার\s*করুন[^\.\!\n।]*[\.\!\n।]?',
        r'[^।!?\n]*(?:হোয়াটসঅ্যাপ|হোয়াটসঅ্যাপ|whatsapp)[^।!?\n]*[।!?]?'
    ]
    for pat in bad_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+|www\.\S+|wa\.me/\S+', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+(?:/\S*)?\b', ' ', text)
    text = re.sub(r'(?:\+?88)?(?:01|০১)[-\s]?[\d০-৯]{3,4}[-\s]?[\d০-৯]{5,6}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    cta_sentence = "আমাদের মাধ্যমে নির্ভুলভাবে আবেদন সম্পন্ন করতে স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে যোগাযোগ করুন।"
    return f"{text} {cta_sentence}".strip()


def _is_quality_ai_result(data):
    if not isinstance(data, dict) or not (data.get("org_name") or data.get("poster") or data.get("motion")):
        return False
    scripts = data.get("scripts", [])
    s0 = scripts[0] if (isinstance(scripts, list) and scripts) else data.get("voiceover_script", "")
    return len(str(s0).split()) >= 110


def extract_dates_and_posts_from_html_or_text(html_text, plain_text, title=""):
    months = r'(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|জানুয়ারি|ফেব্রুয়ারি|আগষ্ট)'
    date_pat = rf'([০-৯\d]{{1,2}}\s*{months})'
    combined = normalize_bengali_nukta(f"{title} {plain_text}")
    st_date, ed_date = "", ""
    st_m = re.search(rf'(?:শুরু|থেকে|প্রকাশ)\s*[:\-\—]?\s*{date_pat}', combined, re.I)
    if st_m:
        st_date = st_m.group(1).strip()
    ed_m = re.search(rf'(?:শেষ|পর্যন্ত|সময়সীমা)\s*[:\-\—]?\s*{date_pat}', combined, re.I)
    if ed_m:
        ed_date = ed_m.group(1).strip()

    fee_str = "বিজ্ঞপ্তি অনুযায়ী"
    fee_m = re.search(r'(?:আবেদন\s*ফি|পরীক্ষার\s*ফি|(?<!\S)ফি)\s*[:\-\—=]?\s*(?:বাবদ\s*)?([০-৯\d]{2,4}\s*(?:/-|টাকা)(?:\s*(?:ও|,|এবং|/)\s*[০-৯\d]{2,4}\s*(?:/-|টাকা)?)*)', combined, re.I)
    if fee_m:
        fee_str = fee_m.group(1).strip()
    elif re.search(r'(?:কোনো\s*আবেদন\s*ফি\s*নেই|বিনামূল্যে\s*আবেদন|ফি\s*লাগবে\s*না|ফি\s*প্রযোজ্য\s*নয়)', combined, re.I):
        fee_str = "বিনামূল্যে"

    posts = []
    if html_text:
        for table in BeautifulSoup(html_text, 'html.parser').find_all('table'):
            for r in table.find_all('tr'):
                cols = [clean_bengali_text(c.get_text()) for c in r.find_all(['td', 'th'])]
                if len(cols) >= 3 and not any(h in cols[0] for h in ['পদের নাম', 'ক্রমিক', 'পদ নং', 'নং', 'বিষয়', 'বিভাগ']):
                    pn = re.sub(r'[\r\n\t]+', ' ', cols[0])[:85].strip()
                    vm = re.search(r'(\d+|[০-৯]+)', cols[1])
                    pv = vm.group(1) if vm else ""
                    pq = re.sub(r'[\r\n\t]+', ' ', cols[2])[:60].strip()
                    if len(pn) > 2:
                        posts.append({"post_name": pn, "vacancy": pv, "qualification": pq, "salary_grade": ""})
    return st_date, ed_date, fee_str, posts


def _build_rich_fallback_script(org_candidate, article_text, scraped_posts, st_d, ed_d, fee_str):
    parts = [f"সুপ্রিয় চাকরিপ্রার্থী বন্ধুরা, {org_candidate} থেকে নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।"]
    if scraped_posts:
        descs = [f"{p['post_name']} পদে {p.get('vacancy') or 'যোগ্য'} জন" for p in scraped_posts[:6] if p.get("post_name")]
        if descs:
            parts.append("প্রধান পদসমূহ: " + "। ".join(descs) + "।")
    clean_body = clean_bengali_text(article_text or "")
    if clean_body:
        picked, total_w = [], 0
        for s in [s.strip() for s in re.split(r'[।!?]+', clean_body) if len(s.strip()) > 20]:
            if any(b in s for b in ["http", "www.", "সাবস্ক্রাইব", "শেয়ার", "ভিজিট"]):
                continue
            if total_w + len(s.split()) > 200:
                break
            picked.append(s)
            total_w += len(s.split())
        if picked:
            parts.append("। ".join(picked) + "।")
    if st_d and ed_d:
        parts.append(f"আবেদন শুরু {st_d} থেকে এবং শেষ তারিখ {ed_d}। আবেদন ফি {fee_str}।")
    elif ed_d:
        parts.append(f"আবেদনের শেষ তারিখ {ed_d}। আবেদন ফি {fee_str}।")
    parts.append("আমাদের মাধ্যমে নির্ভুলভাবে আবেদন সম্পন্ন করতে স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে যোগাযোগ করুন।")
    return " ".join(parts)


def smart_fallback_data(title, article_text="", raw_html=""):
    clean = clean_bengali_text(remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip()))
    st_d, ed_d, fee_str, scraped_posts = extract_dates_and_posts_from_html_or_text(raw_html, article_text, title)
    org_cand = re.sub(r'(\d+|[০-৯]+)\s*পদে|(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$|Job\s*Circular.*$', '', clean, flags=re.I).strip(" -|,")
    if not org_cand or len(org_cand) < 3:
        org_cand = clean.split()[0] if clean else "প্রতিষ্ঠান"

    vac_m = re.search(r'(\d+|[০-৯]+)\s*পদে', clean)
    vac_num = 0
    if vac_m:
        try:
            vac_num = int(vac_m.group(1).translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")))
        except Exception:
            pass

    d_txt = f"{st_d} থেকে {ed_d} পর্যন্ত" if (st_d and ed_d) else (f"শেষ তারিখ: {ed_d}" if ed_d else "চলমান নিয়োগ")
    comb = f"আবেদন শুরু [{st_d}] থেকে [{ed_d}] পর্যন্ত। আবেদন ফি [{fee_str}]।" if (st_d and ed_d) else f"আবেদন [চলমান]। আবেদন ফি [{fee_str}]।"
    script = _build_rich_fallback_script(org_cand, article_text, scraped_posts, st_d, ed_d, fee_str)

    return {
        "org_name": org_cand,
        "poster": {
            "hero_top": "যোগ্যতানুযায়ী আবেদন", "hero_bottom": "নতুন চাকরির সুযোগ!",
            "hero_single_line": f"{org_cand[:26]} নিয়োগ বিজ্ঞপ্তি!", "main_summary": f"{clean} প্রকাশ করা হয়েছে।",
            "date_box_title": "আবেদনের সময়", "date_box_text": d_txt,
            "fee_box_title": "আবেদন ফি", "fee_box_text": fee_str, "combined_date_fee_line": comb,
            "highlight_1_badge": "পদের বিবরণ", "highlight_1_text": clean[:85],
            "highlight_2_badge": "আবেদন তথ্য", "highlight_2_text": f"{org_cand}-এর শর্তাবলি অনুযায়ী নির্ধারিত সময়ে আবেদন করুন।"
        },
        "motion": {
            "org_name": org_cand, "category_badge": "নিয়োগ বিজ্ঞপ্তি", "hook_subtitle": "যোগ্যতানুযায়ী আবেদন",
            "total_vacancy_num": vac_num, "total_vacancy_display": f"{vac_m.group(1)}টি" if vac_m else "বিভিন্ন পদ",
            "highlights": ["আকর্ষণীয় ক্যারিয়ার সুযোগ"], "posts": scraped_posts[:20],
            "age_limit": "১৮–৩২ বছর", "salary_range": "বিজ্ঞপ্তি অনুযায়ী",
            "application_fee": fee_str, "apply_method": "অনলাইন / নির্দেশিত",
            "start_date": st_d or "চলমান", "end_date": ed_d or "বিজ্ঞপ্তিমতে"
        },
        "start_date": st_d or "চলমান", "end_date": ed_d or "বিজ্ঞপ্তিমতে",
        "scripts": [script], "voiceover_script": script
    }


def normalize_poster_fields(data):
    if not isinstance(data, dict):
        return data
    data = _sanitize_ai_json(data)
    org = clean_bengali_text(data.get("org_name", "প্রতিষ্ঠান")) or "প্রতিষ্ঠান"
    p = data.get("poster") if isinstance(data.get("poster"), dict) else {}
    m = data.get("motion") if isinstance(data.get("motion"), dict) else {}

    hero_top = clean_bengali_text(p.get("hero_top") or "যোগ্যতানুযায়ী আবেদন")
    hero_bot = clean_bengali_text(p.get("hero_bottom") or "নতুন চাকরির সুযোগ!")
    d_title = clean_bengali_text(p.get("date_box_title") or "আবেদনের সময়")
    d_text = clean_bengali_text(p.get("date_box_text") or m.get("end_date") or "চলমান নিয়োগ")
    f_title = clean_bengali_text(p.get("fee_box_title") or "আবেদন ফি")
    f_text = clean_bengali_text(p.get("fee_box_text") or m.get("application_fee") or "বিজ্ঞপ্তিমতে")

    data["poster"] = {
        "hero_top": hero_top, "hero_bottom": hero_bot,
        "hero_single_line": clean_bengali_text(p.get("hero_single_line") or f"{hero_top} {hero_bot}"),
        "main_summary": clean_bengali_text(p.get("main_summary") or f"{org}-এ নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশ।"),
        "date_box_title": d_title, "date_box_text": d_text,
        "fee_box_title": f_title, "fee_box_text": f_text,
        "combined_date_fee_line": clean_bengali_text(p.get("combined_date_fee_line") or f"{d_title}: [{d_text}]। {f_title}: [{f_text}]।"),
        "highlight_1_badge": clean_bengali_text(p.get("highlight_1_badge") or "পদের বিবরণ"),
        "highlight_1_text": clean_bengali_text(p.get("highlight_1_text") or f"{org}-এর বিভিন্ন পদে যোগ্য প্রার্থীরা আবেদন করতে পারবেন।"),
        "highlight_2_badge": clean_bengali_text(p.get("highlight_2_badge") or "আবেদন তথ্য"),
        "highlight_2_text": clean_bengali_text(p.get("highlight_2_text") or "নির্ধারিত সময়ের মধ্যে নিয়ম অনুযায়ী আবেদন সম্পন্ন করুন।"),
    }

    bad_post_labels = {"সর্বোচ্চ বেতন", "বয়সসীমা", "বেতন", "আবেদন ফি", "যোগ্যতা"}
    bad_vals = {"নির্দিষ্ট নয়", "উল্লেখ নেই", "জানা যায়নি", "অনির্দিষ্ট", "নেই", "n/a", "none", "null", "unspecified"}
    raw_pm = m.get("posts") if isinstance(m.get("posts"), list) else []
    clean_pm = []
    for it in raw_pm:
        if not isinstance(it, dict):
            continue
        pn = clean_bengali_text(it.get("post_name", ""))
        if not pn or pn in bad_post_labels:
            continue
        vac = clean_bengali_text(it.get("vacancy", ""))
        if not vac or vac.lower() in bad_vals:
            vac = "নিয়োগ"
        qual = clean_bengali_text(it.get("qualification", ""))
        if qual.lower() in bad_vals:
            qual = ""
        grade = clean_bengali_text(it.get("salary_grade", ""))
        if grade.lower() in bad_vals:
            grade = ""
        clean_pm.append({"post_name": pn[:88], "vacancy": vac, "qualification": qual, "salary_grade": grade})

    sal_rng = clean_bengali_text(m.get("salary_range") or "বিজ্ঞপ্তি অনুযায়ী")
    if sal_rng.lower() in bad_vals:
        sal_rng = "বিজ্ঞপ্তি অনুযায়ী"
    app_fee = clean_bengali_text(m.get("application_fee") or f_text)
    if app_fee.lower() in bad_vals:
        app_fee = "বিজ্ঞপ্তি অনুযায়ী"
    age_lim = clean_bengali_text(m.get("age_limit") or "১৮–৩২ বছর")
    if age_lim.lower() in bad_vals:
        age_lim = "বিজ্ঞপ্তি অনুযায়ী"

    data["motion"] = {
        "org_name": clean_bengali_text(m.get("org_name") or org),
        "category_badge": clean_bengali_text(m.get("category_badge") or "নিয়োগ বিজ্ঞপ্তি"),
        "hook_subtitle": clean_bengali_text(m.get("hook_subtitle") or hero_top),
        "total_vacancy_num": m.get("total_vacancy_num", 0),
        "total_vacancy_display": clean_bengali_text(m.get("total_vacancy_display") or ""),
        "highlights": [clean_bengali_text(h) for h in m.get("highlights", []) if clean_bengali_text(h)] if isinstance(m.get("highlights"), list) else [hero_bot],
        "posts": clean_pm[:20],
        "age_limit": age_lim,
        "salary_range": sal_rng,
        "application_fee": app_fee,
        "apply_method": clean_bengali_text(m.get("apply_method") or "অনলাইন"),
        "start_date": clean_bengali_text(m.get("start_date") or data.get("start_date") or "চলমান"),
        "end_date": clean_bengali_text(m.get("end_date") or data.get("end_date") or "শীঘ্রই"),
    }
    return data


def normalize_scripts_count(data, target_count):
    data = normalize_poster_fields(data)
    scripts = data.get("scripts", [])
    single = data.get("voiceover_script", "")
    if single and not scripts:
        scripts = [single]

    hooks = [
        "চাকরিপ্রার্থীদের জন্য সুখবর! নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।",
        "দারুণ সুযোগ! স্বনামধন্য প্রতিষ্ঠানে নতুন চাকরির বিজ্ঞপ্তি প্রকাশ।",
        "আবেদন শুরু হয়ে গেছে! চাকরির এই সুবর্ণ সুযোগ হাতছাড়া করবেন না।",
        "নতুন প্রকাশিত এই নিয়োগ সার্কুলারের সম্পূর্ণ বিস্তারিত জেনে নিন।",
        "যোগ্যতা অনুযায়ী এখনই আবেদন করুন, আকর্ষণীয় ক্যারিয়ার গড়ার দারুণ সুযোগ।",
        "বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে লোকবল নিয়োগ দেওয়া হচ্ছে।",
        "আপনার স্বপ্নের চাকরির সন্ধান পেতে এখনই সম্পূর্ণ তথ্য জেনে নিন।",
        "নতুন প্রকাশিত এই চাকরির সার্কুলারে নির্ভুলভাবে দ্রুত আবেদন সম্পন্ন করতে পারেন।"
    ]

    base_text = scripts[0] if scripts else "নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।"
    split_parts = re.split(r'(?<=[।!?])\s+', base_text.strip(), maxsplit=1)
    body_remainder = split_parts[1] if len(split_parts) > 1 and len(split_parts[1]) > 80 else base_text

    final_list = []
    for i in range(target_count):
        if i < len(scripts) and len(scripts[i].strip()) > 60:
            final_list.append(sanitize_voiceover_script(scripts[i]))
        else:
            final_list.append(sanitize_voiceover_script(f"{hooks[i % len(hooks)]} {body_remainder}"))

    data["scripts"] = final_list[:target_count]
    data["voiceover_script"] = final_list[0]
    return data


def generate_job_data_and_script(title, article_text, raw_html, image_paths, scripts_count=8, memory=None):
    clean_title = clean_bengali_text(remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip()))
    full_content = f"Title: {clean_title}\n\nStructured Webpage Content:\n{clean_bengali_text(article_text[:12000])}"
    llm_scripts_target = max(1, min(scripts_count, 2))

    prompt = f"""You are an expert Bengali Job Circular Analyst, Motion Graphics Copywriter, and Voiceover Writer.
Read BOTH the structured webpage text/tables AND ALL attached official job circular image(s) carefully!
Many job websites put summary/dates in the HTML text while the exact post-by-post table (পদ সংখ্যা, যোগ্যতা, বেতন গ্রেড) is inside the circular image(s).
YOU decide what belongs in each JSON field based strictly on verified facts from the text & images!

{full_content}

TASK 1 — VOICEOVER SCRIPTS (TARGET DURATION: 1.5 TO 2.5 MINUTES):
- Write "scripts": Array of {llm_scripts_target} detailed, fluent spoken Bengali script(s), EACH **250 to 310 words long**.
- Cover ALL real facts from text & circular images: Organization name, total vacancies, ALL real posts with exact vacancy counts, educational qualifications, salary grade/scale, age limit, exact application fee, and exact application start & end dates.
- CRITICAL SPEECH & SCRIPT RULES:
  1) Write ONLY 100% pure standard Bengali Unicode script (বাংলা বর্ণমালা) + Bengali/English digits. NEVER mix Hindi/Devanagari or Chinese characters!
  2) Write ALL numbers, dates, fees, and ages using clear digits (e.g. "১৮–৫৫ বছর", "২১ নভেম্বর ২০২৬", "৮ম পাশ", "১১২ টাকা", "৩.৫০"). Our TTS engine converts digits accurately — NEVER spell numbers into broken words like "পঞ্চান্নোবেন" or "এককুশ"!
  3) Write English acronyms phonetically in Bengali (e.g. "আইডিআরএ", "আইইউবি", "এসএসসি", "এইচএসসি", "টিওআর", "ই-মেইল", "বিডিজবস").
  4) NEVER include website URLs, domain names (e.g. teletalk.com.bd, gov.bd), or phone numbers inside "scripts". End EVERY script strictly with:
     "আমাদের মাধ্যমে নির্ভুলভাবে আবেদন সম্পন্ন করতে স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে যোগাযোগ করুন।"

TASK 2 — POSTER SLOTS ("poster"):
- "org_name": Exact organization name.
- "poster":
  * "hero_top": Short qualification hook (2-4 words).
  * "hero_bottom": Short punchy hook (2-3 words).
  * "hero_single_line": 1-line headline (max 6 words).
  * "main_summary": 1 crisp Bengali summary sentence (12-18 words).
  * "date_box_title": e.g. "আবেদনের সময়" or "সাক্ষাৎকারের তারিখ".
  * "date_box_text": Exact date phrase (e.g. "১০ নভেম্বর থেকে ১০ ডিসেম্বর পর্যন্ত").
  * "fee_box_title": "আবেদন ফি" (or "আবেদন মাধ্যম" if free).
  * "fee_box_text": Exact fee or "বিনামূল্যে" / "বিজ্ঞপ্তি অনুযায়ী".
  * "combined_date_fee_line": 1-2 line natural sentence wrapping key date/fee words in [brackets].
  * "highlight_1_badge" & "highlight_1_text": 1st highlight block.
  * "highlight_2_badge" & "highlight_2_text": 2nd highlight block.

TASK 3 — MOTION GRAPHICS SLOTS ("motion", ACCURATE & CONSISTENT WITH SCRIPTS):
- "motion":
  * "org_name": Short official org name.
  * "category_badge": e.g. "সরকারি নিয়োগ" or "নিয়োগ বিজ্ঞপ্তি" (2-3 words).
  * "hook_subtitle": Concise qualification tag (3-5 words, e.g. "৮ম/এসএসসি/স্নাতক পাশ").
  * "total_vacancy_num": Integer total vacancy count (e.g. 16, or 0 if unspecified/অসংখ্য).
  * "total_vacancy_display": e.g. "১৬টি" or "বিভিন্ন পদ".
  * "highlights": Array with 1 concise 3-4 word tag (e.g. ["স্থায়ী সরকারি চাকরি"]).
  * "posts": Array of REAL job posts extracted from tables/circular images (up to 20): [{{"post_name": "...", "vacancy": "৮৫টি or নিয়োগ", "qualification": "এসএসসি পাশ", "salary_grade": "২০তম গ্রেড"}}]. NEVER put "নির্দিষ্ট নয়", "উল্লেখ নেই", "বয়সসীমা" or "সর্বোচ্চ বেতন"! If count unspecified, use "নিয়োগ".
  * "age_limit": Concise (e.g. "১৮–৩২ বছর").
  * "salary_range": Concise (e.g. "৮,২৫০ – ২৪,৬৮০/-" or "বিজ্ঞপ্তি অনুযায়ী").
  * "application_fee": Exact fee (e.g. "১১২/- ও ৫৬/-" or "বিনামূল্যে" or "বিজ্ঞপ্তি অনুযায়ী").
  * "apply_method": Concise (e.g. "অনলাইন (টেলিটক)" or "ডাকযোগে / সরাসরি").
  * "start_date": Exact application start date matching the script (e.g. "১ ডিসেম্বর ২০২৬" or "চলমান").
  * "end_date": Exact application deadline matching the script (e.g. "২০ ডিসেম্বর ২০২৬").

Return strictly valid JSON only:
{{
  "org_name": "...",
  "poster": {{ ... }},
  "motion": {{ ... }},
  "scripts": ["..."]
}}"""

    base64_imgs = [b for b in (encode_image_base64(p) for p in image_paths[:4]) if b]

    def _try_openrouter(vision_only):
        openrouter_keys = parse_multi_keys(["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"])
        if not openrouter_keys:
            return None
        total_k, start_idx = len(openrouter_keys), get_saved_key_index("openrouter", len(openrouter_keys))
        models = [m for m in OPENROUTER_MODELS if (m in OPENROUTER_VISION_MODELS) == vision_only]
        if not models:
            return None
        print(f"\n--- [OpenRouter Cloud API | Vision={vision_only}] ({total_k} keys, {len(base64_imgs)} imgs) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = openrouter_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/omnisync", "X-Title": "OmniSync"}
            for model in models:
                use_imgs = vision_only and bool(base64_imgs)
                mc = [{"type": "text", "text": prompt}] if use_imgs else prompt
                if use_imgs:
                    for b64 in base64_imgs[:4]:
                        mc.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                try:
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json={"model": model, "messages": [{"role": "user", "content": mc}], "temperature": 0.3, "max_tokens": 5500}, timeout=75)
                    if resp.status_code == 200:
                        msg_obj = resp.json().get('choices', [{}])[0].get('message', {})
                        raw_out = msg_obj.get('content') or msg_obj.get('reasoning') or ""
                        data = parse_json_safely(raw_out)
                        if _is_quality_ai_result(data):
                            save_key_index("openrouter", k_idx, total_k)
                            print(f"  ✅ [OpenRouter SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                        print(f"  ⚠️ [OpenRouter] '{model}' returned incomplete JSON/short script, trying next...")
                    else:
                        print(f"  ⚠️ [OpenRouter] '{model}' HTTP {resp.status_code}: {resp.text[:120]}")
                        if resp.status_code in [401, 402]:
                            save_key_index("openrouter", (k_idx + 1) % total_k, total_k)
                            break
                        if resp.status_code == 429:
                            continue  # পরের free মডেলগুলো চেষ্টা করবে
                except Exception as e:
                    print(f"  ⚠️ [OpenRouter] '{model}' error: {e}")
            save_key_index("openrouter", (k_idx + 1) % total_k, total_k)
        return None

    def _try_ollama(vision_only):
        ollama_keys = parse_multi_keys(["OLLAMA_API_KEYS", "OLLAMA_API_KEY", "Ollama_API_Key"])
        if not ollama_keys:
            return None
        total_k, start_idx = len(ollama_keys), get_saved_key_index("ollama", len(ollama_keys))
        ep = get_ollama_chat_endpoint()
        models = [m for m in OLLAMA_MODELS if (m in OLLAMA_VISION_MODELS) == vision_only]
        if not models:
            return None
        print(f"\n--- [Ollama Cloud API | Vision={vision_only}] ({total_k} keys) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = ollama_keys[k_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            for model in models:
                mo = {"role": "user", "content": prompt}
                if vision_only and base64_imgs:
                    mo["images"] = base64_imgs[:3]
                try:
                    resp = requests.post(ep, headers=headers, json={"model": model, "messages": [mo], "stream": False, "options": {"temperature": 0.3}}, timeout=100)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if _is_quality_ai_result(data):
                            save_key_index("ollama", k_idx, total_k)
                            print(f"  ✅ [Ollama SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                    else:
                        print(f"  ⚠️ [Ollama] '{model}' HTTP {resp.status_code}: {resp.text[:120]}")
                        if resp.status_code in [401, 402, 429]:
                            save_key_index("ollama", (k_idx + 1) % total_k, total_k)
                            break
                except Exception as e:
                    print(f"  ⚠️ [Ollama] '{model}' error: {e}")
        return None

    def _try_gemini():
        gemini_keys = parse_multi_keys(["GEMINI_API_KEYS", "GEMINI_API_KEY"])
        if not gemini_keys:
            return None
        total_k, start_idx = len(gemini_keys), get_saved_key_index("gemini", len(gemini_keys))
        print(f"\n--- [Google Gemini Vision/Text] ({total_k} keys) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = gemini_keys[k_idx]
            for g_model in GEMINI_MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={api_key}"
                parts = [{"text": prompt}]
                for b64 in base64_imgs[:4]:
                    parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})
                try:
                    resp = requests.post(url, json={"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"}}, timeout=60)
                    if resp.status_code == 200:
                        cands = resp.json().get("candidates", [])
                        if cands:
                            data = parse_json_safely(cands[0].get("content", {}).get("parts", [{}])[0].get("text", ""))
                            if _is_quality_ai_result(data):
                                save_key_index("gemini", k_idx, total_k)
                                print(f"  ✅ [Gemini SUCCESS] Model: '{g_model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                    else:
                        print(f"  ⚠️ [Gemini] '{g_model}' HTTP {resp.status_code}: {resp.text[:120]}")
                        if resp.status_code in [400, 401, 403, 429]:
                            save_key_index("gemini", (k_idx + 1) % total_k, total_k)
                            break
                except Exception as e:
                    print(f"  ⚠️ [Gemini] '{g_model}' error: {e}")
        return None

    if base64_imgs:
        for fn in [lambda: _try_openrouter(True), lambda: _try_ollama(True), _try_gemini]:
            res = fn()
            if res:
                return res

    for fn in [lambda: _try_openrouter(False), lambda: _try_ollama(False)]:
        res = fn()
        if res:
            return res

    groq_keys = parse_multi_keys(["GROQ_API_KEYS", "GROQ_API_KEY", "GROQ_API"])
    if groq_keys:
        total_k, start_idx = len(groq_keys), get_saved_key_index("groq", len(groq_keys))
        print(f"\n--- [Groq Cloud API] ({total_k} keys) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = groq_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            for g_model in GROQ_MODELS:
                for use_jf in [True, False]:
                    pl = {"model": g_model, "messages": [{"role": "system", "content": "Output strictly valid JSON in pure Bengali script only."}, {"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 5500}
                    if use_jf:
                        pl["response_format"] = {"type": "json_object"}
                    try:
                        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=pl, timeout=90)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                            if _is_quality_ai_result(data):
                                save_key_index("groq", k_idx, total_k)
                                print(f"  ✅ [Groq SUCCESS] Model: '{g_model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                            break
                        else:
                            print(f"  ⚠️ [Groq] '{g_model}' HTTP {resp.status_code}: {resp.text[:120]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("groq", (k_idx + 1) % total_k, total_k)
                                break
                            if resp.status_code != 400:
                                break
                    except Exception as e:
                        print(f"  ⚠️ [Groq] '{g_model}' error: {e}")
                        break

    cerebras_keys = parse_multi_keys(["CEREBRAS_API_KEYS", "CEREBRAS_API_KEY"])
    if cerebras_keys:
        total_k, start_idx = len(cerebras_keys), get_saved_key_index("cerebras", len(cerebras_keys))
        print(f"\n--- [Cerebras Cloud API] ({total_k} keys) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            headers = {"Authorization": f"Bearer {cerebras_keys[k_idx]}", "Content-Type": "application/json"}
            for c_model in CEREBRAS_MODELS:
                try:
                    resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json={"model": c_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 5500}, timeout=60)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if _is_quality_ai_result(data):
                            save_key_index("cerebras", k_idx, total_k)
                            print(f"  ✅ [Cerebras SUCCESS] Model: '{c_model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("cerebras", (k_idx + 1) % total_k, total_k)
                        break
                except Exception as e:
                    print(f"  ⚠️ [Cerebras] '{c_model}' error: {e}")

    if not base64_imgs:
        res = _try_gemini()
        if res:
            return res

    print("  ⚠️ [Notice] Utilizing Local Fallback...")
    return normalize_scripts_count(smart_fallback_data(title, article_text, raw_html), scripts_count)
