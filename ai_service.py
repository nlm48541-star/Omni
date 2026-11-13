# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image

TRACKER_FILE = "key_tracker.json"

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")

OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-small-24b-instruct-2501"
]

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

CEREBRAS_MODELS = [
    "llama3.3-70b",
    "llama3.1-8b"
]

OLLAMA_MODELS = [
    "gemma4:31b",
    "gemma4",
    "gemma2:27b",
    "gemma2",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "nemotron-3-nano:30b",
    "kimi-k3",
    "minimax-m3"
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

def get_ollama_chat_endpoint():
    raw = os.environ.get("OLLAMA_API_URL", "").strip()
    if not raw or not raw.startswith("http"):
        base = "https://ollama.com"
    else:
        base = raw.rstrip("/")

    if base.endswith("/api/chat"):
        return base
    elif base.endswith("/api"):
        return f"{base}/chat"
    else:
        return f"{base}/api/chat"

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
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match: return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception:
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
    cta_sentence = "ঘরে বসে যেকোনো চাকরির আবেদন সহজে ও নির্ভুলভাবে সম্পন্ন করতে স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে মেসেজ দিন।"
    if not any(k in text for k in ["হোয়াটসঅ্যাপ", "হোয়াটসঅ্যাপ", "WhatsApp", "whatsapp"]):
        text = f"{text} {cta_sentence}"

    return text.strip()

def extract_dates_and_posts_from_html_or_text(html_text, plain_text, title=""):
    months = r'(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগষ্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)'
    date_pat = rf'([০-৯\d]{{1,2}}\s*{months})'

    combined = f"{title} {plain_text}"
    st_date, ed_date = "চলমান", "শীঘ্রই শেষ হবে"

    st_m = re.search(rf'(?:শুরু|থেকে|প্রকাশ)\s*[:\-\—]?\s*{date_pat}', combined, re.I)
    if st_m: st_date = st_m.group(1).strip()

    ed_m = re.search(rf'(?:শেষ|পর্যন্ত|সময়সীমা)\s*[:\-\—]?\s*{date_pat}', combined, re.I)
    if ed_m: ed_date = ed_m.group(1).strip()

    fee_str = "বিজ্ঞপ্তিমতে"
    fee_m = re.search(r'(?:আবেদন\s*ফি|পরীক্ষার\s*ফি|ফি)[^০-৯\d\n]{0,20}((?:[০-৯\d]{2,4}\s*(?:/-|টাকা)?(?:\s*(?:ও|,|এবং)\s*[০-৯\d]{2,4}\s*(?:/-|টাকা)?)*))', combined, re.I)
    if fee_m:
        extracted = fee_m.group(1).strip()
        if extracted:
            fee_str = extracted if ("/-" in extracted or "টাকা" in extracted) else f"{extracted}/-"
    elif re.search(r'বিনামূল্যে|ফি\s*লাগবে\s*না|কোনো\s*ফি\s*নেই', combined, re.I):
        fee_str = "বিনামূল্যে"

    posts = []
    if html_text:
        soup = BeautifulSoup(html_text, 'html.parser')
        for table in soup.find_all('table'):
            for r in table.find_all('tr'):
                cols = [c.get_text().strip() for c in r.find_all(['td', 'th'])]
                if len(cols) >= 3 and not any(h in cols[0] for h in ['পদের নাম', 'ক্রমিক', 'পদ নং', 'নং']):
                    p_name = re.sub(r'[\r\n\t]+', ' ', cols[0])[:40].strip()
                    vac_m = re.search(r'(\d+|[০-৯]+)', cols[1])
                    p_vac = vac_m.group(1) if vac_m else "০১"
                    p_qual = re.sub(r'[\r\n\t]+', ' ', cols[2])[:35].strip()

                    if len(p_name) > 2:
                        posts.append({"post_name": p_name, "vacancy": p_vac, "qualification": p_qual})

    return st_date, ed_date, fee_str, posts

def smart_fallback_data(title, article_text="", raw_html=""):
    clean = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    st_d, ed_d, fee_str, scraped_posts = extract_dates_and_posts_from_html_or_text(raw_html, article_text, title)

    org_candidate = clean
    org_candidate = re.sub(r'(\d+|[০-৯]+)\s*পদে', '', org_candidate)
    org_candidate = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = re.sub(r'Job\s*Circular.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = org_candidate.strip(" -|,")
    if not org_candidate or len(org_candidate) < 3:
        org_candidate = clean.split()[0] if clean else "সরকারি প্রতিষ্ঠান"

    vac_m = re.search(r'(\d+|[০-৯]+)\s*পদে', clean)
    vac_str = vac_m.group(1) if vac_m else "বিভিন্ন"

    p1 = scraped_posts[0] if scraped_posts else {"post_name": "বিজ্ঞপ্তিতে উল্লেখিত পদ", "vacancy": vac_str, "qualification": "এসএসসি/স্নাতক"}
    p2 = scraped_posts[1] if len(scraped_posts) > 1 else {"post_name": "অন্যান্য পদসমূহ", "vacancy": "বিভিন্ন", "qualification": "বিজ্ঞপ্তি অনুযায়ী"}

    qual_rows = [
        {
            "badge": p1.get("qualification", "যোগ্যতানুযায়ী")[:22] or "যোগ্যতানুযায়ী",
            "lead": p1.get("post_name", "বিভিন্ন পদ")[:24],
            "details": f"{p1.get('post_name', 'বিভিন্ন পদ')} - {p1.get('vacancy', '০১')}টি পদে আবেদন করতে পারবেন।"
        },
        {
            "badge": p2.get("qualification", "অন্যান্য যোগ্যতা")[:22] or "অন্যান্য যোগ্যতা",
            "lead": p2.get("post_name", "অন্যান্য পদ")[:24],
            "details": f"{p2.get('post_name', 'অন্যান্য পদ')} - {p2.get('vacancy', '০১')}টি সহ বিজ্ঞপ্তির অন্যান্য পদে আবেদন করা যাবে।"
        }
    ]

    return {
        "org_name": org_candidate,
        "hook_top": "যোগ্যতানুযায়ী আবেদন",
        "hook_bottom": "বড় চাকরির সুযোগ!",
        "hook_full": "নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশ!",
        "poster_main_summary": f"{org_candidate} এ – {vac_str} পদে বিশাল নিয়োগ সার্কুলার প্রকাশ।",
        "application_fee": fee_str,
        "poster_qual_rows": qual_rows,
        "poster_headline_1": f"{org_candidate} বিশাল নিয়োগ",
        "poster_headline_2": "সুযোগ!",
        "poster_p1_lines": [f"প্রয়োজনীয় শিক্ষাগত যোগ্যতায় {org_candidate} এ", f"{vac_str} পদে আবেদনের দুর্দান্ত সুযোগ।"],
        "poster_fee_line": f"আবেদন ফি {fee_str}।",
        "poster_p3_lines": ["বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে", "আগ্রহী প্রার্থীরা আবেদন করতে পারবেন।"],
        "start_date": st_d,
        "end_date": ed_d,
        "posts": scraped_posts or [p1],
        "voiceover_script": f"নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। {clean} এর জন্য আগ্রহী প্রার্থীরা আবেদন করতে পারেন। ঘরে বসে নির্ভুলভাবে আবেদন করতে স্ক্রিনে দেওয়া নাম্বারে হোয়াটসঅ্যাপ করুন।",
        "scripts": [],
        "optimized_title": clean[:90]
    }

def normalize_poster_fields(data):
    if not isinstance(data, dict):
        return data

    org = str(data.get("org_name", "সরকারি প্রতিষ্ঠান")).strip()
    hook_top = str(data.get("hook_top", "")).strip()
    hook_bottom = str(data.get("hook_bottom", "")).strip()
    hook_full = str(data.get("hook_full", "")).strip()

    if not hook_top:
        hook_top = "এসএসসি/এইচএসসি/স্নাতক পাশে"
    if not hook_bottom:
        h2 = str(data.get("poster_headline_2", "")).strip()
        hook_bottom = h2 if h2 and h2 != "সুযোগ!" else "বড় চাকরির সুযোগ!"
    if not hook_full:
        hook_full = f"{hook_top} {hook_bottom}".strip()

    data["hook_top"] = hook_top
    data["hook_bottom"] = hook_bottom
    data["hook_full"] = hook_full

    if not data.get("poster_main_summary"):
        h1 = str(data.get("poster_headline_1", "")).strip()
        p1 = data.get("poster_p1_lines", [])
        if h1 and p1:
            data["poster_main_summary"] = f"{h1} – {' '.join(p1[:1])}".strip()
        else:
            data["poster_main_summary"] = f"{org} এ বিশাল নিয়োগ সার্কুলার প্রকাশ।"

    fee = str(data.get("application_fee", "")).strip()
    if not fee:
        fee_line = str(data.get("poster_fee_line", "")).strip()
        cleaned_fee = re.sub(r'^আবেদন\s*ফি\s*[:\-]?\s*', '', fee_line).strip(" .।")
        fee = cleaned_fee if cleaned_fee else "বিজ্ঞপ্তিমতে"
    data["application_fee"] = fee

    if not data.get("poster_fee_line"):
        data["poster_fee_line"] = f"আবেদন ফি {fee}।"

    qual_rows = data.get("poster_qual_rows", [])
    if not isinstance(qual_rows, list) or len(qual_rows) == 0:
        posts = data.get("posts", [])
        derived = []
        for p in posts[:2]:
            q_label = str(p.get("qualification", "যোগ্যতানুযায়ী")).strip()
            if len(q_label) > 22:
                q_label = q_label.split(',')[0].split('/')[0][:22].strip()
            if "পাশে" not in q_label and any(k in q_label for k in ["এসএসসি", "এইচএসসি", "স্নাতক", "ডিপ্লোমা", "অষ্টম"]):
                q_label = f"{q_label} পাশে"
            pname = str(p.get("post_name", "বিভিন্ন পদ")).strip()
            pvac = str(p.get("vacancy", "০১")).strip()
            derived.append({
                "badge": q_label or "যোগ্যতানুযায়ী",
                "lead": pname[:24],
                "details": f"{pname} - {pvac}টি পদে আবেদন করতে পারবেন।"
            })
        if len(derived) == 0:
            p3 = data.get("poster_p3_lines", ["বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে আবেদন করা যাবে।"])
            derived = [
                {"badge": "যোগ্যতানুযায়ী", "lead": "বিভিন্ন পদ", "details": " ".join(p3)},
                {"badge": "আবেদন তথ্য", "lead": "বিস্তারিত", "details": "যোগ্যতা ও অভিজ্ঞতা অনুযায়ী সকল প্রার্থী আবেদন করতে পারবেন।"}
            ]
        elif len(derived) == 1:
            derived.append({
                "badge": "অন্যান্য তথ্য",
                "lead": "শর্তাবলি",
                "details": "বিজ্ঞপ্তির শর্তাবলি অনুযায়ী নির্ধারিত সময়ের মধ্যে আবেদন সম্পন্ন করুন।"
            })
        qual_rows = derived
    elif len(qual_rows) == 1:
        qual_rows.append({
            "badge": "অন্যান্য তথ্য",
            "lead": "আবেদন প্রক্রিয়া",
            "details": "বিজ্ঞপ্তিতে উল্লেখিত শর্তাবলি অনুযায়ী নির্ধারিত সময়ের মধ্যে আবেদন সম্পন্ন করুন।"
        })

    normalized_rows = []
    for r in qual_rows[:2]:
        if isinstance(r, dict):
            badge = str(r.get("badge", "যোগ্যতানুযায়ী")).strip()
            details = str(r.get("details", "")).strip()
            lead = str(r.get("lead", "")).strip()
            if not lead and details:
                lead = re.split(r'[\-\–\—:,]', details)[0].strip()[:24]
            normalized_rows.append({"badge": badge, "lead": lead, "details": details})
    data["poster_qual_rows"] = normalized_rows

    if not data.get("poster_headline_1"):
        data["poster_headline_1"] = f"{org} বিশাল নিয়োগ"
    if not data.get("poster_headline_2"):
        data["poster_headline_2"] = hook_bottom

    return data

def normalize_scripts_count(data, target_count):
    data = normalize_poster_fields(data)
    scripts = data.get("scripts", [])
    single = data.get("voiceover_script", "")
    if single and not scripts:
        scripts = [single]

    hooks = [
        "চাকরিপ্রার্থীদের জন্য সুখবর! নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।",
        "দারুণ সুযোগ! সরকারি ও স্বনামধন্য প্রতিষ্ঠানে নতুন চাকরির বিজ্ঞপ্তি।",
        "আবেদন শুরু হয়ে গেছে! ঘরে বসে চাকরির সুযোগ হাতছাড়া করবেন না।",
        "বেকারত্ব দূর করতে আজই আবেদন করুন নতুন প্রকাশিত এই সার্কুলারে।",
        "যোগ্যতা অনুযায়ী এখনই আবেদন করুন, আকর্ষণীয় ক্যারিয়ার গড়ার দারুণ সুযোগ।",
        "বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে বিপুল সংখ্যক লোকবল নেওয়া হচ্ছে।",
        "আপনার স্বপ্নের চাকরির সন্ধান পেতে এখনই বিস্তারিত জেনে নিন।",
        "নতুন প্রকাশিত এই চাকরির সার্কুলারে দ্রুত আবেদন সম্পন্ন করতে পারেন।"
    ]
    base_text = scripts[0] if scripts else "নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। আগ্রহী প্রার্থীরা প্রয়োজনীয় যোগ্যতা নিয়ে দ্রুত আবেদন সম্পন্ন করতে পারেন।"
    clean_base = re.sub(r'^(?:.*?)(?=এর জন্য|এ বিভিন্ন|পদে|বিজ্ঞপ্তি)', '', base_text).strip()

    final_list = []
    for i in range(target_count):
        if i < len(scripts) and len(scripts[i].strip()) > 20:
            final_list.append(sanitize_voiceover_script(scripts[i]))
        else:
            hook = hooks[i % len(hooks)]
            varied = f"{hook} {clean_base}"
            final_list.append(sanitize_voiceover_script(varied))

    data["scripts"] = final_list[:target_count]
    data["voiceover_script"] = final_list[0]
    return data

def generate_job_data_and_script(title, article_text, raw_html, image_paths, scripts_count=8, memory=None):
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Title: {clean_title}\n\nWebpage Article Details:\n{article_text[:3000]}"

    prompt = f"""You are a professional Bengali Job Circular Visual Poster Designer and Voiceover Writer.
Analyze this circular details carefully:

Content:
{full_content}

CRITICAL RULES FOR POSTER & SCRIPTS (STRICT NO EMOJIS):
1. HERO HOOKS & MAIN SUMMARY (Concise, impactful Bengali, zero emojis):
   - "org_name": Official organization name in Bengali.
   - "hook_top": Education qualification hook (2-4 words, e.g. "এসএসসি/এইচএসসি পাশে" or "স্নাতক পাশে" or "অষ্টম/এসএসসি পাশে").
   - "hook_bottom": Short punchy hook (2-3 words, e.g. "সরকারি চাকরি!" or "সুবর্ণ সুযোগ চাকরি!" or "বড় চাকরির সুযোগ!").
   - "hook_full": Combined 1-line hero title (max 6 words, e.g. "এসএসসি/এইচএসসি পাশে সরকারি চাকরি!").
   - "poster_main_summary": Single crisp sentence (12-18 words) with organization name, total vacancy count, and announcement (e.g. "বাংলাদেশের মহা-হিসাব নিরীক্ষক ও নিয়ন্ত্রক এর কার্যালয়ে (সিএজি) – ৩৪৭ পদে বিশাল নিয়োগ সার্কুলার প্রকাশ।").

2. EXACT DATES & APPLICATION FEE:
   - "start_date": Exact opening date (e.g. "৩ নভেম্বর" or "চলমান").
   - "end_date": Exact deadline date (e.g. "২৫ নভেম্বর").
   - "application_fee": Exact concise fee only (e.g. "১১২/- ও ৫৬/-" or "২২৩/-" or "বিনামূল্যে" or "বিজ্ঞপ্তিমতে").

3. QUALIFICATION-WISE POSTS ROWS (EXACTLY 2 ROWS):
   - "poster_qual_rows": Array of exactly 2 objects grouping the key circular posts by education qualification:
     [
       {{"badge": "এসএসসি পাশে", "lead": "অফিস সহায়ক", "details": "অফিস সহায়ক - ২০৯টি, (২৩তম গ্রেড)"}},
       {{"badge": "এইচএসসি পাশে", "lead": "জুনিয়র অডিটর", "details": "জুনিয়র অডিটর - ৭০টি, কম্পিউটার মুদ্রাক্ষরিক - ৬২টি পদে (১৩তম গ্রেড) আবেদন করতে পারবেন।"}}
     ]
   - Keep each "badge" very short (2-3 words max), "lead" 1-3 words (main post name), "details" concise (10-18 words max).

4. LEGACY POSTER FIELDS (keep populated too):
   - "poster_headline_1": Short headline (e.g. "সিএজিতে বিশাল নিয়োগ")
   - "poster_headline_2": Short hook (e.g. "বড় সুযোগ!")
   - "poster_p1_lines": Array of 1-2 short punchy lines about qualification & vacancies.
   - "poster_fee_line": Short fee sentence (e.g. "আবেদন ফি ১১২/- ও ৫৬/-।")
   - "poster_p3_lines": Array of 1-2 short lines highlighting key posts (DO NOT repeat deadline dates here).
   - "posts": Array of {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}.

5. SCRIPTS:
   - Provide "scripts": Array of exactly {scripts_count} UNIQUE spoken Bengali voiceover scripts (100-120 words each).
   - Strict Outro CTA: "আবেদনটি নির্ভুলভাবে সম্পন্ন করতে স্ক্রিনে দেওয়া নাম্বারে হোয়াটসঅ্যাপে মেসেজ দিন।"

Return strictly valid JSON:
{{
  "org_name": "...",
  "hook_top": "...",
  "hook_bottom": "...",
  "hook_full": "...",
  "poster_main_summary": "...",
  "start_date": "...",
  "end_date": "...",
  "application_fee": "...",
  "poster_qual_rows": [
    {{"badge": "...", "lead": "...", "details": "..."}},
    {{"badge": "...", "lead": "...", "details": "..."}}
  ],
  "poster_headline_1": "...",
  "poster_headline_2": "বড় সুযোগ!",
  "poster_p1_lines": ["..."],
  "poster_fee_line": "আবেদন ফি বিজ্ঞপ্তিমতে।",
  "poster_p3_lines": ["..."],
  "posts": [{{"post_name": "...", "vacancy": "০১", "qualification": "..."}}],
  "scripts": ["..."]
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ১. OpenRouter Cloud API (১ম অগ্রাধিকার)
    openrouter_keys = parse_multi_keys(["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"])
    if openrouter_keys:
        total_k = len(openrouter_keys)
        start_idx = get_saved_key_index("openrouter", total_k)
        print(f"\n--- [Priority 1: OpenRouter Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = openrouter_keys[k_idx]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/omnisync",
                "X-Title": "OmniSync"
            }

            for model in OPENROUTER_MODELS:
                msg_content = [{"type": "text", "text": prompt}]
                for b64 in base64_imgs[:2]:
                    msg_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": msg_content}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3
                }
                try:
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name"):
                            save_key_index("openrouter", k_idx, total_k)
                            print(f"  ✅ [OpenRouter SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("openrouter", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ২. Groq Cloud API (২য় অগ্রাধিকার)
    groq_keys = parse_multi_keys(["GROQ_API_KEYS", "GROQ_API_KEY", "GROQ_API"])
    if groq_keys:
        total_k = len(groq_keys)
        start_idx = get_saved_key_index("groq", total_k)
        print(f"\n--- [Priority 2: Groq Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = groq_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            for g_model in GROQ_MODELS:
                payload = {
                    "model": g_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional Bengali job circular poster and voiceover writer. Return strictly valid JSON with no emojis."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": 3000
                }
                try:
                    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name"):
                            save_key_index("groq", k_idx, total_k)
                            print(f"  ✅ [Groq SUCCESS] Model: '{g_model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("groq", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ৩. Cerebras Cloud API (৩য় অগ্রাধিকার)
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
                payload = {
                    "model": c_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional Bengali job circular poster and voiceover writer. Return strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": 3000
                }
                try:
                    resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name"):
                            save_key_index("cerebras", k_idx, total_k)
                            print(f"  ✅ [Cerebras SUCCESS] Model: '{c_model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("cerebras", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ৪. Ollama Cloud API (সর্বশেষ অগ্রাধিকার)
    ollama_keys = parse_multi_keys(["OLLAMA_API_KEYS", "OLLAMA_API_KEY", "Ollama_API_Key"])
    if ollama_keys:
        total_k = len(ollama_keys)
        start_idx = get_saved_key_index("ollama", total_k)
        ollama_endpoint = get_ollama_chat_endpoint()

        print(f"\n--- [Priority 4 (Last): Ollama Cloud API] ({total_k} keys detected) ---")
        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = ollama_keys[k_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

            for model in OLLAMA_MODELS:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": base64_imgs}],
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
                try:
                    resp = requests.post(ollama_endpoint, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and data.get("org_name"):
                            save_key_index("ollama", k_idx, total_k)
                            print(f"  ✅ [Ollama SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_scripts_count(data, scripts_count)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("ollama", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    print("  ⚠️ [Notice] Utilizing Local Smart Poster Fallback...")
    fallback = smart_fallback_data(title, article_text, raw_html)
    return normalize_scripts_count(fallback, scripts_count)
