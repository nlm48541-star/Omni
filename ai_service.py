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

    return st_date, ed_date, posts

def smart_fallback_data(title, article_text="", raw_html=""):
    clean = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    st_d, ed_d, scraped_posts = extract_dates_and_posts_from_html_or_text(raw_html, article_text, title)
    
    org_candidate = clean
    org_candidate = re.sub(r'(\d+|[০-৯]+)\s*পদে', '', org_candidate)
    org_candidate = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = re.sub(r'Job\s*Circular.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = org_candidate.strip(" -|,")
    if not org_candidate or len(org_candidate) < 3:
        org_candidate = clean.split()[0] if clean else "সরকারি প্রতিষ্ঠান"

    vac_m = re.search(r'(\d+|[০-৯]+)\s*পদে', clean)
    vac_str = vac_m.group(1) if vac_m else "বিভিন্ন"

    return {
        "org_name": org_candidate,
        "poster_headline_1": f"{org_candidate}র বিশাল নিয়োগ",
        "poster_headline_2": "সুযোগ!",
        "poster_p1_lines": [f"প্রয়োজনীয় শিক্ষাগত যোগ্যতায় {org_candidate}রে", f"{vac_str} পদে আবেদনের দুর্দান্ত সুযোগ।"],
        "poster_fee_line": "আবেদন ফি বিজ্ঞপ্তিমতে।",
        "poster_p3_lines": ["👥 বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে", "আগ্রহী প্রার্থীরা আবেদন করতে পারবেন।"],
        "start_date": st_d,
        "end_date": ed_d,
        "posts": scraped_posts or [{"post_name": "বিজ্ঞপ্তিতে উল্লেখিত পদ", "vacancy": "০১", "qualification": "বিজ্ঞপ্তি অনুযায়ী"}],
        "voiceover_script": f"নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। {clean} এর জন্য আগ্রহী প্রার্থীরা আবেদন করতে পারেন। ঘরে বসে নির্ভুলভাবে আবেদন করতে স্ক্রিনে দেওয়া নাম্বারে হোয়াটসঅ্যাপ করুন।",
        "scripts": [],
        "optimized_title": clean[:90]
    }

def normalize_eight_scripts(data):
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

    final_8 = []
    for i in range(8):
        if i < len(scripts) and len(scripts[i].strip()) > 20:
            final_8.append(sanitize_voiceover_script(scripts[i]))
        else:
            varied = f"{hooks[i]} {clean_base}"
            final_8.append(sanitize_voiceover_script(varied))

    data["scripts"] = final_8[:8]
    data["voiceover_script"] = final_8[0]
    return data

def generate_job_data_and_script(title, article_text, raw_html, image_paths, memory=None):
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Title: {clean_title}\n\nWebpage Article Details:\n{article_text[:3000]}"

    prompt = f"""You are a professional Bengali Job Circular Visual Poster Designer and Voiceover Writer.
Analyze this circular details:

Content:
{full_content}

CRITICAL RULES FOR POSTER & SCRIPTS:
1. POSTER LAYOUT EXTRACTION (VERY CONCISE & EXACT):
   - "poster_headline_1": Short first line in Bengali (e.g. "প্রাণিসম্পদ অধিদপ্তরের বিশাল নিয়োগ")
   - "poster_headline_2": Short punchy hook (e.g. "সুযোগ!" or "বড় সুযোগ!")
   - "poster_p1_lines": Array of 1-2 short punchy Bengali lines about qualification & vacancies.
   - "poster_fee_line": e.g. "রাত ১২:০০ টা পর্যন্ত। আবেদন ফি বিজ্ঞপ্তিমতে।"
   - "poster_p3_lines": Array of 1-2 short lines highlighting key posts & vacancy counts.

2. SCRIPTS:
   - Provide "scripts": Array of 8 UNIQUE spoken Bengali voiceover scripts (100-120 words each).
   - Strict Outro CTA: "আবেদনটি নির্ভুলভাবে সম্পন্ন করতে স্ক্রিনে দেওয়া নাম্বারে হোয়াটসঅ্যাপে মেসেজ দিন।"

3. DATA:
   - "org_name": Official organization name.
   - "start_date": e.g. "০১ অক্টোবর".
   - "end_date": e.g. "০৬ অক্টোবর".
   - "posts": Array of {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}.

Return strictly valid JSON:
{{
  "org_name": "...",
  "poster_headline_1": "...",
  "poster_headline_2": "সুযোগ!",
  "poster_p1_lines": ["..."],
  "poster_fee_line": "...",
  "poster_p3_lines": ["..."],
  "start_date": "...",
  "end_date": "...",
  "posts": [{{"post_name": "...", "vacancy": "০১", "qualification": "..."}}],
  "scripts": ["..."]
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ১. OpenRouter Cloud API (১ম অগ্রাধিকার - নো টাইমআউট)
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
                    # 🌟 নো টাইমআউট
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name"):
                            save_key_index("openrouter", k_idx, total_k)
                            print(f"  ✅ [OpenRouter SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("openrouter", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ২. Groq Cloud API (২য় অগ্রাধিকার - নো টাইমআউট)
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
                        {"role": "system", "content": "You are a professional Bengali job circular visual poster and voiceover writer. Return strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": 3000
                }
                try:
                    # 🌟 নো টাইমআউট
                    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name"):
                            save_key_index("groq", k_idx, total_k)
                            print(f"  ✅ [Groq SUCCESS] Model: '{g_model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("groq", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ৩. Cerebras Cloud API (৩য় অগ্রাধিকার - নো টাইমআউট)
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
                        {"role": "system", "content": "You are a professional Bengali job circular visual poster and voiceover writer. Return strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": 3000
                }
                try:
                    # 🌟 নো টাইমআউট
                    resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name"):
                            save_key_index("cerebras", k_idx, total_k)
                            print(f"  ✅ [Cerebras SUCCESS] Model: '{c_model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("cerebras", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ৪. Ollama Cloud API (সর্বশেষ অগ্রাধিকার - নো টাইমআউট)
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
                    # 🌟 নো টাইমআউট
                    resp = requests.post(ollama_endpoint, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and data.get("org_name"):
                            save_key_index("ollama", k_idx, total_k)
                            print(f"  ✅ [Ollama SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        save_key_index("ollama", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    print("  ⚠️ [Notice] Utilizing Local Smart Poster Fallback...")
    fallback = smart_fallback_data(title, article_text, raw_html)
    return normalize_eight_scripts(fallback)
