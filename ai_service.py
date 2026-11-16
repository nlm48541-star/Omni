# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image

TRACKER_FILE = "key_tracker.json"

# শুধু সচল ফ্রি মডেলসমূহ (৪০৪ পেইড হওয়া মডেল বাদ দেওয়া হয়েছে)
OPENROUTER_MODELS = [
    "nvidia/nemotron-3.5-super-vl:free",           # 120B Vision
    "google/gemma-4-31b-it:free",                 # 31B Vision
    "google/gemma-4-26b-a4b-it:free",             # 26B Vision
    "nvidia/nemotron-3-ultra-550b-a55b:free",     # 550B Text
    "openrouter/free"                             # Auto-router fallback
]

OPENROUTER_VISION_MODELS = {
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
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
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]

def parse_multi_keys(env_var_names):
    if isinstance(env_var_names, str):
        env_var_names = [env_var_names]
    for env_name in env_var_names:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            keys = [k.strip() for k in re.split(r'[\r\n,;]+', raw) if k.strip() and not k.strip().startswith('#')]
            if keys: return keys
    return []

def get_saved_key_index(platform, total_keys):
    if total_keys <= 0: return 0
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                return int(json.load(f).get(f"{platform}_index", 0)) % total_keys
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

def get_ollama_chat_endpoint():
    raw = os.environ.get("OLLAMA_API_URL", "").strip()
    if not raw or not raw.startswith("http"):
        raw = "https://ollama.com"
    base = raw.rstrip("/")
    for sfx in ["/api/chat", "/api", "/v1"]:
        if base.endswith(sfx):
            base = base[:-len(sfx)]
    return f"{base.rstrip('/')}/api/chat"

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
    for block in re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL | re.IGNORECASE):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict): return obj
        except Exception: pass
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict): return obj
    except Exception: pass
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{', cleaned):
        try:
            obj, _ = dec.raw_decode(cleaned[m.start():])
            if isinstance(obj, dict) and (obj.get("org_name") or obj.get("poster") or obj.get("motion") or obj.get("scripts")):
                return obj
        except Exception: continue
    return None

def remove_years(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', re.sub(r'২০২[০-৯]|\b202[0-9]\b', '', str(text))).strip()

def sanitize_voiceover_script(script):
    if not script: return ""
    text = str(script)
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
    if len(str(s0).split()) < 110:
        return False
    return True

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
    fee_m = re.search(r'(?:আবেদন\s*ফি|পরীক্ষার\s*ফি|(?<!\S)ফি)\s*[:\-\—=]?\s*(?:বাবদ\s*)?([০-৯\d]{2,4}\s*(?:/-|টাকা)(?:\s*(?:ও|,|এবং|/)\s*[০-৯\d]{2,4}\s*(?:/-|টাকা)?)*)', combined, re.I)
    if fee_m: fee_str = fee_m.group(1).strip()
    elif re.search(r'(?:কোনো\s*আবেদন\s*ফি\s*নেই|বিনামূল্যে\s*আবেদন|ফি\s*লাগবে\s*না)', combined, re.I):
        fee_str = "বিনামূল্যে"

    posts = []
    if html_text:
        for table in BeautifulSoup(html_text, 'html.parser').find_all('table'):
            for r in table.find_all('tr'):
                cols = [c.get_text().strip() for c in r.find_all(['td', 'th'])]
                if len(cols) >= 3 and not any(h in cols[0] for h in ['পদের নাম', 'ক্রমিক', 'পদ নং', 'নং', 'বিষয়', 'বিভাগ']):
                    pn = re.sub(r'[\r\n\t]+', ' ', cols[0])[:45].strip()
                    vm = re.search(r'(\d+|[০-৯]+)', cols[1])
                    pv = vm.group(1) if vm else ""
                    pq = re.sub(r'[\r\n\t]+', ' ', cols[2])[:35].strip()
                    if len(pn) > 2:
                        posts.append({"post_name": pn, "vacancy": pv, "qualification": pq, "salary_grade": ""})
    return st_date, ed_date, fee_str, posts

def _build_rich_fallback_script(org_candidate, article_text, scraped_posts, st_d, ed_d, fee_str):
    parts = [f"সুপ্রিয় চাকরিপ্রার্থী বন্ধুরা, {org_candidate} থেকে নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।"]
    if scraped_posts:
        descs = [f"{p['post_name']} পদে {p.get('vacancy') or 'যোগ্য'} জন" for p in scraped_posts[:6] if p.get("post_name")]
        if descs: parts.append("প্রধান পদসমূহ: " + "। ".join(descs) + "।")
    clean_body = re.sub(r'\s+', ' ', str(article_text or "")).strip()
    if clean_body:
        picked, total_w = [], 0
        for s in [s.strip() for s in re.split(r'[।!?]+', clean_body) if len(s.strip()) > 20]:
            if any(b in s for b in ["http", "www.", "সাবস্ক্রাইব", "শেয়ার", "ভিজিট"]): continue
            if total_w + len(s.split()) > 200: break
            picked.append(s); total_w += len(s.split())
        if picked: parts.append("। ".join(picked) + "।")
    if st_d and ed_d: parts.append(f"আবেদন শুরু {st_d} থেকে এবং শেষ তারিখ {ed_d}। আবেদন ফি {fee_str}।")
    elif ed_d: parts.append(f"আবেদনের শেষ তারিখ {ed_d}। আবেদন ফি {fee_str}।")
    parts.append("আমাদের মাধ্যমে নির্ভুলভাবে আবেদন সম্পন্ন করতে স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে যোগাযোগ করুন।")
    return " ".join(parts)

def smart_fallback_data(title, article_text="", raw_html=""):
    clean = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    st_d, ed_d, fee_str, scraped_posts = extract_dates_and_posts_from_html_or_text(raw_html, article_text, title)
    org_cand = re.sub(r'(\d+|[০-৯]+)\s*পদে|(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$|Job\s*Circular.*$', '', clean, flags=re.I).strip(" -|,")
    if not org_cand or len(org_cand) < 3: org_cand = clean.split()[0] if clean else "প্রতিষ্ঠান"

    vac_m = re.search(r'(\d+|[০-৯]+)\s*পদে', clean)
    vac_num = 0
    if vac_m:
        try: vac_num = int(vac_m.group(1).translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")))
        except Exception: pass

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
            "age_limit": "১৮–৩০/৩২ বছর", "salary_range": "বিজ্ঞপ্তি অনুযায়ী",
            "application_fee": fee_str, "apply_method": "অনলাইন / নির্দেশিত",
            "start_date": st_d or "চলমান", "end_date": ed_d or "বিজ্ঞপ্তিমতে"
        },
        "start_date": st_d or "চলমান", "end_date": ed_d or "বিজ্ঞপ্তিমতে",
        "scripts": [script], "voiceover_script": script
    }

def normalize_poster_fields(data):
    if not isinstance(data, dict): return data
    org = str(data.get("org_name", "প্রতিষ্ঠান")).strip()
    p = data.get("poster") if isinstance(data.get("poster"), dict) else {}
    m = data.get("motion") if isinstance(data.get("motion"), dict) else {}

    hero_top = str(p.get("hero_top") or "যোগ্যতানুযায়ী আবেদন").strip()
    hero_bot = str(p.get("hero_bottom") or "নতুন চাকরির সুযোগ!").strip()
    d_title = str(p.get("date_box_title") or "আবেদনের সময়").strip()
    d_text = str(p.get("date_box_text") or m.get("end_date") or "চলমান নিয়োগ").strip()
    f_title = str(p.get("fee_box_title") or "আবেদন ফি").strip()
    f_text = str(p.get("fee_box_text") or m.get("application_fee") or "বিজ্ঞপ্তিমতে").strip()

    data["poster"] = {
        "hero_top": hero_top, "hero_bottom": hero_bot,
        "hero_single_line": str(p.get("hero_single_line") or f"{hero_top} {hero_bot}").strip(),
        "main_summary": str(p.get("main_summary") or f"{org}-এ নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশ।").strip(),
        "date_box_title": d_title, "date_box_text": d_text,
        "fee_box_title": f_title, "fee_box_text": f_text,
        "combined_date_fee_line": str(p.get("combined_date_fee_line") or f"{d_title}: [{d_text}]। {f_title}: [{f_text}]।").strip(),
        "highlight_1_badge": str(p.get("highlight_1_badge") or "পদের বিবরণ").strip(),
        "highlight_1_text": str(p.get("highlight_1_text") or f"{org}-এর বিভিন্ন পদে যোগ্য প্রার্থীরা আবেদন করতে পারবেন।").strip(),
        "highlight_2_badge": str(p.get("highlight_2_badge") or "আবেদন তথ্য").strip(),
        "highlight_2_text": str(p.get("highlight_2_text") or "নির্ধারিত সময়ের মধ্যে নিয়ম অনুযায়ী আবেদন সম্পন্ন করুন।").strip(),
    }

    bad_post_labels = {"সর্বোচ্চ বেতন", "বয়সসীমা", "বেতন", "আবেদন ফি", "যোগ্যতা"}
    raw_pm = m.get("posts") if isinstance(m.get("posts"), list) else []
    clean_pm = [it for it in raw_pm if isinstance(it, dict) and str(it.get("post_name", "")).strip() not in bad_post_labels]

    sal_rng = str(m.get("salary_range") or "বিজ্ঞপ্তি অনুযায়ী").strip()
    if sal_rng == "নির্দিষ্ট নয়": sal_rng = "বিজ্ঞপ্তি অনুযায়ী"
    app_fee = str(m.get("application_fee") or f_text).strip()
    if app_fee == "নির্দিষ্ট নয়": app_fee = "বিজ্ঞপ্তি অনুযায়ী"

    data["motion"] = {
        "org_name": str(m.get("org_name") or org).strip(),
        "category_badge": str(m.get("category_badge") or "নিয়োগ বিজ্ঞপ্তি").strip(),
        "hook_subtitle": str(m.get("hook_subtitle") or hero_top).strip(),
        "total_vacancy_num": m.get("total_vacancy_num", 0),
        "total_vacancy_display": str(m.get("total_vacancy_display") or "").strip(),
        "highlights": m.get("highlights") if isinstance(m.get("highlights"), list) else [hero_bot],
        "posts": clean_pm[:20],
        "age_limit": str(m.get("age_limit") or "১৮–৩০/৩২ বছর").strip(),
        "salary_range": sal_rng,
        "application_fee": app_fee,
        "apply_method": str(m.get("apply_method") or "অনলাইন").strip(),
        "start_date": str(m.get("start_date") or data.get("start_date") or "চলমান").strip(),
        "end_date": str(m.get("end_date") or data.get("end_date") or "শীঘ্রই").strip(),
    }
    return data

def normalize_scripts_count(data, target_count):
    data = normalize_poster_fields(data)
    scripts = data.get("scripts", [])
    single = data.get("voiceover_script", "")
    if single and not scripts: scripts = [single]

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
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Title: {clean_title}\n\nWebpage Article Details:\n{article_text[:11000]}"
    llm_scripts_target = max(1, min(scripts_count, 2))

    prompt = f"""You are an expert Bengali Job Circular Analyst, Motion Graphics Copywriter, and Voiceover Writer.
Read BOTH the webpage text AND the attached job circular image(s) carefully! Most post details, fees, and dates are inside the tables or circular images.

Article Content:
{full_content}

TASK 1 — VOICEOVER SCRIPTS (TARGET DURATION: 1.5 TO 2.5 MINUTES):
- Write "scripts": Array of {llm_scripts_target} detailed, fluent spoken Bengali script(s), EACH **250 to 310 words long**.
- Cover ALL real facts from text & images: Organization name, total vacancies, post names with exact vacancy counts, salary scale, educational qualification, age limit, application fee, start & end dates.
- CRITICAL SPEECH RULES FOR TTS:
  1) Write EVERYTHING in **100% pure Bengali Unicode words** (e.g. "এমওডিসি", "আইএসপিআর", "টিএ ডিএ", "অনলাইন আবেদন পোর্টাল").
  2) NEVER write ANY website URLs, domain names (like teletalk.com.bd, gov.bd, http), or English words inside "scripts"!
  3) NEVER write phone numbers inside "scripts". End EVERY script strictly with:
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

TASK 3 — MOTION GRAPHICS SLOTS ("motion", MINIMAL & CONCISE):
- "motion":
  * "org_name": Short official org name.
  * "category_badge": e.g. "নিয়োগ বিজ্ঞপ্তি" (2-3 words).
  * "hook_subtitle": Concise qualification tag (3-5 words, e.g. "অষ্টম/এসএসসি/এইচএসসি পাশ").
  * "total_vacancy_num": Integer total vacancy count (e.g. 169, or 0 if unspecified).
  * "total_vacancy_display": e.g. "১৬৯টি" (or "বিভিন্ন পদ").
  * "highlights": Array with 1 concise 3-4 word tag (e.g. ["স্থায়ী সরকারি চাকরি"]).
  * "posts": Array of REAL job post names from the text/images (up to 20): [{{"post_name": "...", "vacancy": "৮৫টি", "qualification": "এসএসসি পাশ", "salary_grade": "২০তম গ্রেড"}}]. NEVER put "বয়সসীমা" or "সর্বোচ্চ বেতন" as a post_name!
  * "age_limit": Concise (e.g. "১৮–৩২ বছর").
  * "salary_range": Concise (e.g. "৮,২৫০ – ২৪,৬৮০/-" or "বিজ্ঞপ্তি অনুযায়ী", NEVER "নির্দিষ্ট নয়").
  * "application_fee": Concise (e.g. "১১২/- ও ৫৬/-" or "বিনামূল্যে" or "বিজ্ঞপ্তি অনুযায়ী").
  * "apply_method": Concise (e.g. "অনলাইন (টেলিটক)" or "সরাসরি / ডাকযোগে").
  * "start_date": Exact start date (e.g. "১০ নভেম্বর ২০২৬" or "চলমান").
  * "end_date": Exact end date (e.g. "১০ ডিসেম্বর ২০২৬").

Return strictly valid JSON only:
{{
  "org_name": "...",
  "poster": {{ ... }},
  "motion": {{ ... }},
  "scripts": ["..."]
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:2] if encode_image_base64(p)]

    # ১. OpenRouter (ভিশন মডেল আগে, যখন ছবি থাকে)
    openrouter_keys = parse_multi_keys(["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"])
    if openrouter_keys:
        total_k, start_idx = len(openrouter_keys), get_saved_key_index("openrouter", len(openrouter_keys))
        print(f"\n--- [Priority 1: OpenRouter Cloud API] ({total_k} keys, VisionFirst={bool(base64_imgs)}) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = openrouter_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/omnisync", "X-Title": "OmniSync"}
            for model in OPENROUTER_MODELS:
                is_vis = model in OPENROUTER_VISION_MODELS and bool(base64_imgs)
                for use_imgs in ([True, False] if is_vis else [False]):
                    mc = [{"type": "text", "text": prompt}] if use_imgs else prompt
                    if use_imgs:
                        for b64 in base64_imgs[:2]: mc.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                    try:
                        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json={"model": model, "messages": [{"role": "user", "content": mc}], "temperature": 0.35, "max_tokens": 5500}, timeout=90)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                            if _is_quality_ai_result(data):
                                save_key_index("openrouter", k_idx, total_k)
                                print(f"  ✅ [OpenRouter SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                        else:
                            print(f"  ⚠️ [OpenRouter] '{model}' HTTP {resp.status_code}: {resp.text[:120]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("openrouter", (k_idx + 1) % total_k, total_k); break
                    except Exception as e: print(f"  ⚠️ [OpenRouter] '{model}' error: {e}")

    # ২. Ollama Cloud (URL বাগ ফিক্সড)
    ollama_keys = parse_multi_keys(["OLLAMA_API_KEYS", "OLLAMA_API_KEY", "Ollama_API_Key"])
    if ollama_keys:
        total_k, start_idx = len(ollama_keys), get_saved_key_index("ollama", len(ollama_keys))
        ep = get_ollama_chat_endpoint()
        print(f"\n--- [Priority 2: Ollama Cloud API] ({total_k} keys, Endpoint={ep}) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = ollama_keys[k_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            for model in OLLAMA_MODELS:
                is_vis = model in OLLAMA_VISION_MODELS and bool(base64_imgs)
                for use_imgs in ([True, False] if is_vis else [False]):
                    mo = {"role": "user", "content": prompt}
                    if use_imgs: mo["images"] = base64_imgs[:2]
                    try:
                        resp = requests.post(ep, headers=headers, json={"model": model, "messages": [mo], "stream": False, "options": {"temperature": 0.35}}, timeout=120)
                        if resp.status_code == 200:
                            data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                            if _is_quality_ai_result(data):
                                save_key_index("ollama", k_idx, total_k)
                                print(f"  ✅ [Ollama SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                                return normalize_scripts_count(data, scripts_count)
                        else:
                            print(f"  ⚠️ [Ollama] '{model}' HTTP {resp.status_code}: {resp.text[:120]}")
                            if resp.status_code in [401, 402, 429]:
                                save_key_index("ollama", (k_idx + 1) % total_k, total_k); break
                    except Exception as e: print(f"  ⚠️ [Ollama] '{model}' error: {e}")

    # ৩. Groq Cloud
    groq_keys = parse_multi_keys(["GROQ_API_KEYS", "GROQ_API_KEY", "GROQ_API"])
    if groq_keys:
        total_k, start_idx = len(groq_keys), get_saved_key_index("groq", len(groq_keys))
        print(f"\n--- [Priority 3: Groq Cloud API] ({total_k} keys) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = groq_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            for g_model in GROQ_MODELS:
                for use_jf in [True, False]:
                    pl = {"model": g_model, "messages": [{"role": "system", "content": "Output strictly valid JSON only."}, {"role": "user", "content": prompt}], "temperature": 0.35, "max_tokens": 5500}
                    if use_jf: pl["response_format"] = {"type": "json_object"}
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
                                save_key_index("groq", (k_idx + 1) % total_k, total_k); break
                            if resp.status_code != 400: break
                    except Exception as e:
                        print(f"  ⚠️ [Groq] '{g_model}' error: {e}"); break

    # ৪. Google Gemini
    gemini_keys = parse_multi_keys(["GEMINI_API_KEYS", "GEMINI_API_KEY"])
    if gemini_keys:
        total_k, start_idx = len(gemini_keys), get_saved_key_index("gemini", len(gemini_keys))
        print(f"\n--- [Priority 4 (Final Cloud): Google Gemini] ({total_k} keys) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = gemini_keys[k_idx]
            for g_model in GEMINI_MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={api_key}"
                parts = [{"text": prompt}]
                for b64 in base64_imgs[:2]: parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})
                try:
                    resp = requests.post(url, json={"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.35, "responseMimeType": "application/json"}}, timeout=60)
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
                            save_key_index("gemini", (k_idx + 1) % total_k, total_k); break
                except Exception as e: print(f"  ⚠️ [Gemini] '{g_model}' error: {e}")

    print("  ⚠️ [Notice] Utilizing Local Fallback...")
    return normalize_scripts_count(smart_fallback_data(title, article_text, raw_html), scripts_count)
