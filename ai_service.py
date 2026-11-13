# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image

TRACKER_FILE = "key_tracker.json"
_LIVE_MODEL_CACHE = {}

OPENROUTER_MODELS = [
    "openrouter/free",
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free"
]

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

CEREBRAS_MODELS = [
    "gpt-oss-120b",
    "qwen-3.8-27b",
    "qwen3-32b",
    "llama3.3-70b",
    "llama3.1-8b"
]

OLLAMA_MODELS = [
    "gemma4:31b",
    "gemma4",
    "deepseek-v4.1-flash",
    "glm-5.3-flash",
    "minimax-m3.1-flash",
    "kimi-k3.1-pro",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "gpt-oss:120b-cloud",
    "deepseek-v3.1:671b-cloud"
]

def parse_multi_keys(env_var_names):
    if isinstance(env_var_names, str):
        env_var_names = [env_var_names]
    for env_name in env_var_names:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            lines = re.split(r'[\r\n,;]+', raw)
            keys = [k.strip() for k in lines if k.strip() and not k.strip().startswith('#')]
            if keys:
                return keys
    return []

def get_saved_key_index(platform, total_keys):
    if total_keys <= 0: return 0
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return int(data.get(f"{platform}_index", 0)) % total_keys
        except Exception: pass
    return 0

def save_key_index(platform, index, total_keys):
    if total_keys <= 0: return
    data = {}
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception: data = {}
    data[f"{platform}_index"] = index % total_keys
    try:
        with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception: pass

def get_ollama_base_url():
    raw = os.environ.get("OLLAMA_API_URL", "").strip()
    if not raw or not raw.startswith("http"):
        return "https://ollama.com"
    base = raw.rstrip("/")
    for suffix in ["/api/chat", "/api", "/v1"]:
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    return base.rstrip("/")

def get_ollama_chat_endpoint():
    return get_ollama_base_url() + "/api/chat"

def encode_image_base64(image_path, max_dim=1024):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception:
        return None

def parse_json_safely(raw_text):
    if not raw_text: return None
    cleaned = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL | re.IGNORECASE).strip()

    fenced = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL | re.IGNORECASE)
    for block in fenced:
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

    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{', cleaned):
        try:
            obj, _ = decoder.raw_decode(cleaned[match.start():])
            if isinstance(obj, dict) and (obj.get("org_name") or obj.get("poster") or obj.get("scripts")):
                return obj
        except Exception:
            continue
    return None

def remove_years(text):
    if not text: return ""
    text = re.sub(r'\b202[0-9]\b', '', str(text))
    text = re.sub(r'২০২[০-৯]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def sanitize_voiceover_script(script):
    if not script: return ""
    text = str(script)

    bad_patterns = [
        r'সম্পূর্ণ\s*ভিডিও(?:টি)?\s*(?:দেখুন|দেখার\s*জন্য\s*ধন্যবাদ|শেষ\s*পর্যন্ত\s*দেখুন)[^\.\!\n]*[\.\!\n]?',
        r'পুরো\s*ভিডিও(?:টি)?\s*(?:দেখুন|দেখার\s*জন্য\s*ধন্যবাদ)[^\.\!\n]*[\.\!\n]?',
        r'ভিডিওটি\s*শেষ\s*পর্যন্ত\s*দেখার\s*জন্য\s*ধন্যবাদ[^\.\!\n]*[\.\!\n]?',
        r'(?:অফিসিয়াল\s*)?ওয়েবসাইটে?\s*(?:ভিজিট\s*করুন|গিয়ে\s*আবেদন\s*করুন|দেখুন)[^\.\!\n]*[\.\!\n]?',
        r'চ্যানেলটি\s*সাবস্ক্রাইব\s*করুন[^\.\!\n]*[\.\!\n]?',
        r'লাইক\s*(?:ও|এবং)\s*শেয়ার\s*করুন[^\.\!\n]*[\.\!\n]?'
    ]
    for pat in bad_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)

    text = re.sub(r'\s+', ' ', text).strip()
    cta_sentence = "ঘরে বসে যেকোনো চাকরির আবেদন সহজে ও নির্ভুলভাবে সম্পন্ন করতে স্ক্রিনে দেওয়া 01540503092 হোয়াটসঅ্যাপ নাম্বারে মেসেজ দিন।"
    if not any(k in text for k in ["হোয়াটসঅ্যাপ", "হোয়াটসঅ্যাপ", "WhatsApp", "whatsapp"]):
        text = f"{text} {cta_sentence}"
    return text.strip()

def _get_live_openrouter_models():
    if "openrouter" in _LIVE_MODEL_CACHE:
        return _LIVE_MODEL_CACHE["openrouter"]
    models = list(OPENROUTER_MODELS)
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=12)
        if r.status_code == 200:
            for m in r.json().get("data", []):
                mid = m.get("id", "")
                pricing = m.get("pricing", {}) or {}
                if mid.endswith(":free") or (str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0"):
                    if mid and mid not in models and "coder" not in mid.lower():
                        models.append(mid)
    except Exception:
        pass
    _LIVE_MODEL_CACHE["openrouter"] = models[:10]
    return _LIVE_MODEL_CACHE["openrouter"]

def _get_live_groq_models(api_key):
    cache_key = "groq_" + api_key[:8]
    if cache_key in _LIVE_MODEL_CACHE:
        return _LIVE_MODEL_CACHE[cache_key]
    models = list(GROQ_MODELS)
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": "Bearer " + api_key}, timeout=12)
        if r.status_code == 200:
            live_ids = [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
            chat_ids = [m for m in live_ids if not any(b in m.lower() for b in ["whisper", "guard", "orpheus", "tts", "playai", "safeguard"])]
            prioritized = [m for m in GROQ_MODELS if m in chat_ids]
            others = [m for m in chat_ids if m not in prioritized]
            if prioritized or others:
                models = prioritized + others
    except Exception:
        pass
    _LIVE_MODEL_CACHE[cache_key] = models[:8]
    return _LIVE_MODEL_CACHE[cache_key]

def _get_live_ollama_models(api_key):
    if "ollama" in _LIVE_MODEL_CACHE:
        return _LIVE_MODEL_CACHE["ollama"]
    models = list(OLLAMA_MODELS)
    try:
        tags_url = get_ollama_base_url() + "/api/tags"
        r = requests.get(tags_url, headers={"Authorization": "Bearer " + api_key}, timeout=12)
        if r.status_code == 200:
            live = [m.get("name") or m.get("model", "") for m in r.json().get("models", []) if (m.get("name") or m.get("model"))]
            if live:
                prioritized = [m for m in OLLAMA_MODELS if m in live]
                others = [m for m in live if m not in prioritized and "embed" not in m.lower()]
                models = prioritized + others
    except Exception:
        pass
    _LIVE_MODEL_CACHE["ollama"] = models[:10]
    return _LIVE_MODEL_CACHE["ollama"]

def extract_dates_and_posts_from_html_or_text(html_text, plain_text, title=""):
    months = r'(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগষ্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)'
    date_pat = rf'([০-৯\d]{{1,2}}\s*{months})'
    combined = f"{title} {plain_text}"

    st_date, ed_date = "", ""
    st_m = re.search(rf'(?:শুরু|থেকে|প্রকাশ)\s*[:\-\—]?\s*{date_pat}', combined, re.I)
    if st_m: st_date = st_m.group(1).strip()

    ed_m = re.search(rf'(?:শেষ|পর্যন্ত|সময়সীমা)\s*[:\-\—]?\s*{date_pat}', combined, re.I)
    if ed_m: ed_date = ed_m.group(1).strip()

    fee_str = "বিজ্ঞপ্তি অনুযায়ী"
    fee_m = re.search(
        r'(?:আবেদন\s*ফি|পরীক্ষার\s*ফি|(?<!\S)ফি)\s*[:\-\—=]?\s*(?:বাবদ\s*)?([০-৯\d]{2,4}\s*(?:/-|টাকা)(?:\s*(?:ও|,|এবং|/)\s*[০-৯\d]{2,4}\s*(?:/-|টাকা)?)*)',
        combined, re.I
    )
    if fee_m:
        fee_str = fee_m.group(1).strip()
    elif re.search(r'(?:কোনো\s*আবেদন\s*ফি\s*নেই|বিনামূল্যে\s*আবেদন|ফি\s*লাগবে\s*না)', combined, re.I):
        fee_str = "বিনামূল্যে"

    posts = []
    if html_text:
        soup = BeautifulSoup(html_text, 'html.parser')
        for table in soup.find_all('table'):
            for r in table.find_all('tr'):
                cols = [c.get_text().strip() for c in r.find_all(['td', 'th'])]
                if len(cols) >= 3 and not any(h in cols[0] for h in ['পদের নাম', 'ক্রমিক', 'পদ নং', 'নং']):
                    p_name = re.sub(r'[\r\n\t]+', ' ', cols[0])[:45].strip()
                    vac_m = re.search(r'(\d+|[০-৯]+)', cols[1])
                    p_vac = vac_m.group(1) if vac_m else ""
                    p_qual = re.sub(r'[\r\n\t]+', ' ', cols[2])[:35].strip()
                    if len(p_name) > 2:
                        posts.append({"post_name": p_name, "vacancy": p_vac, "qualification": p_qual})
    return st_date, ed_date, fee_str, posts

def _build_rich_fallback_script(org_candidate, article_text, scraped_posts, st_d, ed_d, fee_str):
    parts = [f"সুপ্রিয় চাকরিপ্রার্থী বন্ধুরা, {org_candidate} থেকে নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।"]
    if scraped_posts:
        post_descs = []
        for p in scraped_posts[:5]:
            pn = p.get("post_name", "").strip()
            pv = p.get("vacancy", "").strip()
            pq = p.get("qualification", "").strip()
            if pn:
                desc = f"{pn} পদে {pv} জন" if pv else f"{pn} পদে"
                if pq: desc += f" (যোগ্যতা: {pq})"
                post_descs.append(desc)
        if post_descs:
            parts.append("প্রধান পদসমূহ: " + "। ".join(post_descs) + "।")

    clean_body = re.sub(r'\s+', ' ', str(article_text or "")).strip()
    if clean_body:
        sentences = [s.strip() for s in re.split(r'[।!?]+', clean_body) if len(s.strip()) > 20]
        picked, total_w = [], 0
        for s in sentences:
            if any(bad in s for bad in ["http", "www.", "সাবস্ক্রাইব", "শেয়ার", "ভিজিট"]):
                continue
            wc = len(s.split())
            if total_w + wc > 200:
                break
            picked.append(s)
            total_w += wc
        if picked:
            parts.append("। ".join(picked) + "।")

    if st_d and ed_d:
        parts.append(f"আবেদন শুরু {st_d} থেকে এবং শেষ তারিখ {ed_d}। আবেদন ফি {fee_str}।")
    elif ed_d:
        parts.append(f"আবেদনের শেষ তারিখ {ed_d}। আবেদন ফি {fee_str}।")
    parts.append("ঘরে বসে যেকোনো চাকরির আবেদন সহজে ও নির্ভুলভাবে সম্পন্ন করতে স্ক্রিনে দেওয়া 01540503092 হোয়াটসঅ্যাপ নাম্বারে মেসেজ দিন।")
    return " ".join(parts)

def smart_fallback_data(title, article_text="", raw_html=""):
    clean = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    st_d, ed_d, fee_str, scraped_posts = extract_dates_and_posts_from_html_or_text(raw_html, article_text, title)

    org_candidate = re.sub(r'(\d+|[০-৯]+)\s*পদে', '', clean)
    org_candidate = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = re.sub(r'Job\s*Circular.*$', '', org_candidate, flags=re.IGNORECASE).strip(" -|,")
    if not org_candidate or len(org_candidate) < 3:
        org_candidate = clean.split()[0] if clean else "প্রতিষ্ঠান"

    if st_d and ed_d:
        d_txt = f"{st_d} থেকে {ed_d} পর্যন্ত"
        comb = f"আবেদন শুরু [{st_d}] থেকে [{ed_d}] পর্যন্ত। আবেদন ফি [{fee_str}]।"
    elif ed_d:
        d_txt = f"শেষ তারিখ: {ed_d}"
        comb = f"আবেদন চলছে, শেষ তারিখ [{ed_d}]। আবেদন ফি [{fee_str}]।"
    else:
        d_txt = "চলমান নিয়োগ (বিস্তারিত বিজ্ঞপ্তিতে)"
        comb = f"আবেদন [চলমান রয়েছে]। আবেদন ফি [{fee_str}]।"

    if scraped_posts:
        p1 = scraped_posts[0]
        h1_b = p1.get("qualification") or "পদের বিবরণ"
        h1_t = f"{p1['post_name']} ({p1['vacancy']}টি পদ)" if p1.get("vacancy") else f"{p1['post_name']} পদে নিয়োগ"
        if len(scraped_posts) > 1:
            p2 = scraped_posts[1]
            h2_b = p2.get("qualification") or "অন্যান্য পদ"
            h2_t = f"{p2['post_name']} ({p2['vacancy']}টি পদ)" if p2.get("vacancy") else f"{p2['post_name']} সহ অন্যান্য পদে আবেদন"
        else:
            h2_b = "আবেদনের তথ্য"
            h2_t = f"{org_candidate}-এর বিজ্ঞপ্তির শর্ত অনুযায়ী নির্ধারিত সময়ে আবেদন করুন।"
    else:
        h1_b = "চাকরির বিবরণ"
        h1_t = clean[:85]
        h2_b = "আবেদন তথ্য"
        h2_t = f"{org_candidate}-এর বিজ্ঞপ্তির শর্ত অনুযায়ী যোগ্য প্রার্থীরা আবেদন করতে পারবেন।"

    script = _build_rich_fallback_script(org_candidate, article_text, scraped_posts, st_d, ed_d, fee_str)
    return {
        "org_name": org_candidate,
        "poster": {
            "hero_top": "যোগ্যতানুযায়ী আবেদন",
            "hero_bottom": "নতুন চাকরির সুযোগ!",
            "hero_single_line": f"{org_candidate[:26]} নিয়োগ বিজ্ঞপ্তি!",
            "main_summary": f"{clean} প্রকাশ করা হয়েছে।",
            "date_box_title": "আবেদনের সময়",
            "date_box_text": d_txt,
            "fee_box_title": "আবেদন ফি",
            "fee_box_text": fee_str,
            "combined_date_fee_line": comb,
            "highlight_1_badge": h1_b[:24],
            "highlight_1_text": h1_t,
            "highlight_2_badge": h2_b[:24],
            "highlight_2_text": h2_t
        },
        "start_date": st_d or "চলমান",
        "end_date": ed_d or "বিজ্ঞপ্তিমতে",
        "scripts": [script],
        "voiceover_script": script
    }

def normalize_poster_fields(data):
    if not isinstance(data, dict):
        return data

    org = str(data.get("org_name", "প্রতিষ্ঠান")).strip()
    p = data.get("poster")
    if not isinstance(p, dict):
        p = {}

    hero_top = str(p.get("hero_top") or data.get("hook_top") or "যোগ্যতানুযায়ী আবেদন").strip()
    hero_bot = str(p.get("hero_bottom") or data.get("hook_bottom") or "নতুন চাকরির সুযোগ!").strip()
    hero_single = str(p.get("hero_single_line") or data.get("hook_full") or f"{hero_top} {hero_bot}").strip()
    summary = str(p.get("main_summary") or data.get("poster_main_summary") or f"{org}-এ নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশ।").strip()

    sd = str(data.get("start_date", "")).strip()
    ed = str(data.get("end_date", "")).strip()
    fee = str(data.get("application_fee", "")).strip()

    d_title = str(p.get("date_box_title") or "আবেদনের সময়").strip()
    d_text = str(p.get("date_box_text") or (f"{sd} থেকে {ed} পর্যন্ত" if sd and ed else (ed or "চলমান নিয়োগ"))).strip()
    f_title = str(p.get("fee_box_title") or "আবেদন ফি").strip()
    f_text = str(p.get("fee_box_text") or fee or "বিজ্ঞপ্তিমতে").strip()

    comb = str(p.get("combined_date_fee_line") or "").strip()
    if not comb:
        comb = f"{d_title}: [{d_text}]। {f_title}: [{f_text}]।"

    h1_b = str(p.get("highlight_1_badge") or "পদের বিবরণ").strip()
    h1_t = str(p.get("highlight_1_text") or "").strip()
    h2_b = str(p.get("highlight_2_badge") or "আবেদন তথ্য").strip()
    h2_t = str(p.get("highlight_2_text") or "").strip()

    legacy_rows = data.get("poster_qual_rows", [])
    if not h1_t and isinstance(legacy_rows, list) and len(legacy_rows) > 0:
        h1_b = str(legacy_rows[0].get("badge", h1_b)).strip()
        h1_t = str(legacy_rows[0].get("details", "")).strip()
    if not h2_t and isinstance(legacy_rows, list) and len(legacy_rows) > 1:
        h2_b = str(legacy_rows[1].get("badge", h2_b)).strip()
        h2_t = str(legacy_rows[1].get("details", "")).strip()

    if not h1_t:
        h1_t = f"{org}-এর বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে যোগ্য প্রার্থীরা আবেদন করতে পারবেন।"
    if not h2_t:
        h2_t = f"বিস্তারিত শর্তাবলি অনুযায়ী নির্ধারিত সময়ের মধ্যে আবেদন সম্পন্ন করুন।"

    data["poster"] = {
        "hero_top": hero_top,
        "hero_bottom": hero_bot,
        "hero_single_line": hero_single,
        "main_summary": summary,
        "date_box_title": d_title,
        "date_box_text": d_text,
        "fee_box_title": f_title,
        "fee_box_text": f_text,
        "combined_date_fee_line": comb,
        "highlight_1_badge": h1_b,
        "highlight_1_text": h1_t,
        "highlight_2_badge": h2_b,
        "highlight_2_text": h2_t,
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
            varied = f"{hooks[i % len(hooks)]} {body_remainder}"
            final_list.append(sanitize_voiceover_script(varied))

    data["scripts"] = final_list[:target_count]
    data["voiceover_script"] = final_list[0]
    return data

def generate_job_data_and_script(title, article_text, raw_html, image_paths, scripts_count=2, memory=None):
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Title: {clean_title}\n\nWebpage Article Details:\n{article_text[:6000]}"
    llm_scripts_target = max(1, min(scripts_count, 2))

    prompt = f"""You are an intelligent Bengali Job Circular Editor, Poster Copywriter, and Long-Form Shorts Voiceover Writer.
Read the ENTIRE webpage text AND attached circular images carefully. Do NOT invent fake numbers or copy generic filler phrases. Think naturally about what actually belongs in each poster slot for THIS specific circular!

Article Content:
{full_content}

TASK 1 — VOICEOVER SCRIPTS (TARGET VIDEO DURATION: 1.5 TO 2.5 MINUTES, UNDER 3 MINUTES):
- Write "scripts": Array of {llm_scripts_target} rich, natural spoken Bengali voiceover script(s).
- EACH script MUST be **260 to 320 words long** (for a 100-145 second voiceover).
- Cover ALL real facts found in the article/images clearly:
  1) Exact Company / Ministry / Organization name (কোম্পানি বা মন্ত্রণালয়ের নাম)।
  2) Total number of posts/vacancies (মোট কতগুলো পদ বা শূন্যপদ রয়েছে)।
  3) Exact post names, how many people per post (কোন পদে কতজন লোক নিবে), salary/grade, educational qualification & experience।
  4) Age limit, exact application fee (if mentioned, or state if no fee is needed), application start & end dates (or walk-in interview schedule)।
  5) Closing line: "ঘরে বসে নির্ভুলভাবে আবেদন করতে স্ক্রিনে দেওয়া 01540503092 হোয়াটসঅ্যাপ নাম্বারে মেসেজ দিন।"
- Never say "subscribe", "like/share", or "visit website".

TASK 2 — SMART POSTER SLOT WRITING (NO EMOJIS, PURE NATURAL BENGALI):
Think carefully about THIS circular and write clear, natural Bengali copy for each visual slot of the poster:
- "org_name": Exact organization/company name.
- "poster":
  * "hero_top": Short qualification or job category hook suitable for THIS circular (e.g. "স্নাতক/মাস্টার্স পাশে" or "এসএসসি/এইচএসসি পাশে" or "অভিজ্ঞ ও ফ্রেশারদের জন্য", 2-4 words).
  * "hero_bottom": Short punchy hook (e.g. "সরকারি চাকরি!" or "আকর্ষণীয় ক্যারিয়ার!" or "বড় নিয়োগ সুযোগ!", 2-3 words).
  * "hero_single_line": Combined 1-line top banner headline (max 5-6 words, e.g. "স্নাতক পাশে বড় চাকরির সুযোগ!").
  * "main_summary": 1 clear, natural 2-3 line Bengali summary naming the organization, total vacancies (if any), and circular announcement (12-18 words).
  * "date_box_title": Appropriate title for the date slot (e.g. "আবেদনের সময়", "আবেদন শুরু", or "সাক্ষাৎকারের তারিখ").
  * "date_box_text": Natural, accurate dates from the article (e.g. "৩ নভেম্বর থেকে ২৫ নভেম্বর পর্যন্ত", "শেষ তারিখ: ৩০ নভেম্বর", or "১৮ ও ১৯ নভেম্বর সকাল ১০টা"). If no exact date is given, write naturally like "আবেদন চলমান রয়েছে". NEVER write broken text like "চলমান থেকে শীঘ্রই শেষ হবে".
  * "fee_box_title": Appropriate title (e.g. "আবেদন ফি" if a fee exists, or "আবেদন মাধ্যম" if no fee is mentioned in a private job).
  * "fee_box_text": Exact fee from the article (e.g. "১১২/- ও ৫৬/-") OR if none/free, write "ফি প্রযোজ্য নয়" or "অনলাইন / সরাসরি". NEVER guess random post numbers as fee!
  * "combined_date_fee_line": 1-2 line natural Bengali sentence combining the application time and fee/method, wrapping ONLY the key date/fee words inside [square brackets] so the renderer highlights them in red. Example: "আবেদন শুরু [৩ নভেম্বর] থেকে [২৫ নভেম্বর] পর্যন্ত। আবেদন ফি [১১২/- ও ৫৬/-]।" or "সরাসরি সাক্ষাৎকার [১৮ ও ১৯ নভেম্বর]। আবেদন ফি [সম্পূর্ণ বিনামূল্যে]।"
  * "highlight_1_badge": Short tag for the 1st key block (2-3 words, e.g. "এসএসসি পাশে", "প্রধান পদসমূহ", "শিক্ষাগত যোগ্যতা").
  * "highlight_1_text": Informative, natural 1-2 sentence Bengali highlight about the main posts, vacancy counts, or qualifications (12-20 words).
  * "highlight_2_badge": Short tag for the 2nd key block (2-3 words, e.g. "এইচএসসি পাশে", "সুযোগ-সুবিধা", "অন্যান্য পদ ও শর্ত").
  * "highlight_2_text": Informative, natural 1-2 sentence Bengali highlight about remaining key posts, salary/benefits, age limit, or application method (12-20 words).

Return strictly valid JSON only:
{{
  "org_name": "...",
  "poster": {{
    "hero_top": "...",
    "hero_bottom": "...",
    "hero_single_line": "...",
    "main_summary": "...",
    "date_box_title": "...",
    "date_box_text": "...",
    "fee_box_title": "...",
    "fee_box_text": "...",
    "combined_date_fee_line": "...",
    "highlight_1_badge": "...",
    "highlight_1_text": "...",
    "highlight_2_badge": "...",
    "highlight_2_text": "..."
  }},
  "scripts": ["..."]
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:2] if encode_image_base64(p)]

    # ১. OpenRouter Cloud API
    openrouter_keys = parse_multi_keys(["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"])
    if openrouter_keys:
        total_k = len(openrouter_keys)
        start_idx = get_saved_key_index("openrouter", total_k)
        or_models = _get_live_openrouter_models()
        print(f"\n--- [Priority 1: OpenRouter Cloud API] ({total_k} keys, {len(or_models)} free models) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = openrouter_keys[k_idx]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/omnisync",
                "X-Title": "OmniSync"
            }
            for model in or_models:
                supports_vision = any(v in model.lower() for v in ["openrouter/free", "vision", "vl", "gemma-3", "gemini"])
                for use_imgs, use_json_fmt in [(supports_vision and bool(base64_imgs), True), (False, False)]:
                    msg_content = [{"type": "text", "text": prompt}] if use_imgs else prompt
                    if use_imgs:
                        for b64 in base64_imgs[:2]:
                            msg_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                    payload = {"model": model, "messages": [{"role": "user", "content": msg_content}], "temperature": 0.35, "max_tokens": 4500}
                    if use_json_fmt:
                        payload["response_format"] = {"type": "json_object"}
                    try:
                        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                            if data and (data.get("org_name") or data.get("poster")):
                                save_key_index("openrouter", k_idx, total_k)
                                print(f"  ✅ [OpenRouter SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                            print(f"  ⚠️ [OpenRouter] Model '{model}' invalid JSON output.")
                        else:
                            print(f"  ⚠️ [OpenRouter] Model '{model}' Key #{k_idx+1} HTTP {resp.status_code}: {resp.text[:140]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("openrouter", (k_idx + 1) % total_k, total_k)
                                break
                    except Exception as e:
                        print(f"  ⚠️ [OpenRouter] Model '{model}' error: {e}")

    # ২. Groq Cloud API
    groq_keys = parse_multi_keys(["GROQ_API_KEYS", "GROQ_API_KEY", "GROQ_API"])
    if groq_keys:
        total_k = len(groq_keys)
        start_idx = get_saved_key_index("groq", total_k)
        print(f"\n--- [Priority 2: Groq Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = groq_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            for g_model in _get_live_groq_models(api_key):
                for use_json_fmt in [True, False]:
                    payload = {
                        "model": g_model,
                        "messages": [
                            {"role": "system", "content": "You are an expert Bengali job circular editor and voiceover writer. Output strictly valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.35,
                        "max_tokens": 4500
                    }
                    if use_json_fmt:
                        payload["response_format"] = {"type": "json_object"}
                    try:
                        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=90)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                            if data and (data.get("org_name") or data.get("poster")):
                                save_key_index("groq", k_idx, total_k)
                                print(f"  ✅ [Groq SUCCESS] Model: '{g_model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                            print(f"  ⚠️ [Groq] Model '{g_model}' invalid JSON output.")
                            break
                        else:
                            print(f"  ⚠️ [Groq] Model '{g_model}' Key #{k_idx+1} HTTP {resp.status_code}: {resp.text[:140]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("groq", (k_idx + 1) % total_k, total_k)
                                break
                            if resp.status_code != 400:
                                break
                    except Exception as e:
                        print(f"  ⚠️ [Groq] Model '{g_model}' error: {e}")
                        break

    # ৩. Cerebras Cloud API
    cerebras_keys = parse_multi_keys(["CEREBRAS_API_KEYS", "CEREBRAS_API_KEY"])
    if cerebras_keys:
        total_k = len(cerebras_keys)
        start_idx = get_saved_key_index("cerebras", total_k)
        print(f"\n--- [Priority 3: Cerebras Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = cerebras_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            for c_model in CEREBRAS_MODELS:
                for use_json_fmt in [True, False]:
                    payload = {
                        "model": c_model,
                        "messages": [
                            {"role": "system", "content": "You are an expert Bengali job circular editor and voiceover writer. Output strictly valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.35,
                        "max_tokens": 4500
                    }
                    if use_json_fmt:
                        payload["response_format"] = {"type": "json_object"}
                    try:
                        resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload, timeout=90)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                            if data and (data.get("org_name") or data.get("poster")):
                                save_key_index("cerebras", k_idx, total_k)
                                print(f"  ✅ [Cerebras SUCCESS] Model: '{c_model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                            break
                        else:
                            print(f"  ⚠️ [Cerebras] Model '{c_model}' HTTP {resp.status_code}: {resp.text[:120]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("cerebras", (k_idx + 1) % total_k, total_k)
                                break
                            if resp.status_code != 400:
                                break
                    except Exception as e:
                        print(f"  ⚠️ [Cerebras] Model '{c_model}' error: {e}")
                        break

    # ৪. Ollama Cloud API
    ollama_keys = parse_multi_keys(["OLLAMA_API_KEYS", "OLLAMA_API_KEY", "Ollama_API_Key"])
    if ollama_keys:
        total_k = len(ollama_keys)
        start_idx = get_saved_key_index("ollama", total_k)
        ollama_endpoint = get_ollama_chat_endpoint()
        print(f"\n--- [Priority 4: Ollama Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = ollama_keys[k_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            for model in _get_live_ollama_models(api_key):
                supports_vision = any(v in model.lower() for v in ["gemma4", "vl", "vision"])
                for use_imgs in ([True, False] if (supports_vision and base64_imgs) else [False]):
                    msg_obj = {"role": "user", "content": prompt}
                    if use_imgs:
                        msg_obj["images"] = base64_imgs[:2]
                    payload = {"model": model, "messages": [msg_obj], "stream": False, "options": {"temperature": 0.35}}
                    try:
                        resp = requests.post(ollama_endpoint, headers=headers, json=payload, timeout=120)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                            if data and (data.get("org_name") or data.get("poster")):
                                save_key_index("ollama", k_idx, total_k)
                                print(f"  ✅ [Ollama SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                            print(f"  ⚠️ [Ollama] Model '{model}' invalid JSON output.")
                        else:
                            print(f"  ⚠️ [Ollama] Model '{model}' Key #{k_idx+1} HTTP {resp.status_code}: {resp.text[:140]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("ollama", (k_idx + 1) % total_k, total_k)
                                break
                    except Exception as e:
                        print(f"  ⚠️ [Ollama] Model '{model}' error: {e}")

    print("  ⚠️ [Notice] All AI providers unavailable. Utilizing Enhanced Local Fallback...")
    fallback = smart_fallback_data(title, article_text, raw_html)
    return normalize_scripts_count(fallback, scripts_count)
