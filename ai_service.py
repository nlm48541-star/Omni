# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image
from config_manager import detect_offline_application_rules

TRACKER_FILE = "key_tracker.json"

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")

# 🌟 Ollama Cloud মডেল লিস্ট (Gemma মডেল সর্বোচ্চ প্রায়োরিটিতে)
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

# 🌟 OpenRouter মডেল লিস্ট
OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-small-24b-instruct-2501"
]

# 🌟 Groq Cloud মডেল লিস্ট
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

# 🌟 Cerebras Cloud মডেল লিস্ট
CEREBRAS_MODELS = [
    "llama3.3-70b",
    "llama3.1-8b"
]

# =========================================================================
# 🌟 কি পার্সিং ও ট্র্যাকার হেল্পার (এন্টার/নিউলাইন সাপোর্ট ও ইনডেক্স সেভ)
# =========================================================================
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

def mask_key(k):
    if not k or len(k) <= 8: return "****"
    return k[:4] + "..." + k[-4:]

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
    cta_sentence = "ঘরে বসে যেকোনো চাকরির আবেদন সহজে ও নির্ভুলভাবে সম্পন্ন করতে আমাদের ইনবক্স করুন অথবা প্রোফাইল বায়ো দেখুন।"
    if not any(k in text for k in ["ইনবক্স", "বায়ো", "বায়ো", "মেসেজ"]):
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
        org_candidate = clean.split()[0] if clean else "সরকারি নিয়োগ বিজ্ঞপ্তি"

    if not scraped_posts:
        vac_match = re.search(r'(\d+|[০-৯]+)\s*(?:টি\s*)?পদে', clean)
        vac_str = (vac_match.group(1)) if vac_match else "০১"
        scraped_posts = [{"post_name": "বিজ্ঞপ্তিতে উল্লেখিত পদ", "vacancy": vac_str, "qualification": "বিজ্ঞপ্তি অনুযায়ী"}]

    fallback_script = f"নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। {clean} এর জন্য আগ্রহী প্রার্থীরা প্রয়োজনীয় যোগ্যতা নিয়ে আবেদন সম্পন্ন করতে পারেন। ঘরে বসে যেকোনো চাকরির আবেদন সহজে ও নির্ভুলভাবে সম্পন্ন করতে আমাদের ইনবক্স করুন অথবা প্রোফাইল বায়ো দেখুন।"

    is_offline, off_reason = detect_offline_application_rules(article_text, raw_html, title)

    return {
        "org_name": org_candidate,
        "is_online_application": not is_offline,
        "application_method": "postal" if is_offline else "online",
        "offline_reason": off_reason if is_offline else "",
        "headline": "নিয়োগ বিজ্ঞপ্তি",
        "start_date": st_d,
        "end_date": ed_d,
        "posts": scraped_posts,
        "voiceover_script": fallback_script,
        "optimized_title": clean[:90],
        "video_description": f"{clean}\n\nআবেদন করতে যোগাযোগ করুন Whatsapp: +8801540503092"
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

# =========================================================================
# 🌟 মাস্টার এআই কো-অর্ডিনেটর (Ollama -> OpenRouter -> Groq -> Cerebras)
# =========================================================================
def generate_job_data_and_script(title, article_text, raw_html, image_paths, memory=None):
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Title: {clean_title}\n\nWebpage Article Details:\n{article_text[:3000]}"

    prompt = f"""You are a professional Bengali Job Circular Content Engine and Voiceover Writer.
Analyze this circular and circular images:

Content:
{full_content}

CRITICAL RULES:
1. APPLICATION METHOD ANALYSIS:
   - "is_online_application": true/false (true ONLY if candidates can apply online via website/portal/form/teletalk/email).
   - "application_method": "online" | "postal" | "courier" | "in_person"
   - "offline_reason": reason in Bengali if false.

2. MULTI-SCRIPT GENERATION:
   - Provide "scripts": Array of 8 UNIQUE spoken Bengali voiceover scripts (each 100-130 words).
   - Each script must have a DIFFERENT hook and sentence structure.
   - All 8 scripts MUST strictly end with this CTA: "আবেদনটি নির্ভুলভাবে সম্পন্ন করতে আমাদের ইনবক্স করুন অথবা প্রোফাইল বায়ো দেখুন।"
   - NO years (2026/২০২৬), NO phone digits, NO website mentions, NO like/subscribe mentions.

3. DATA EXTRACTION:
   - "org_name": Official institution name.
   - "start_date": e.g. "০১ অক্টোবর".
   - "end_date": e.g. "৩০ অক্টোবর".
   - "posts": List of post objects: {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}.

Return strictly valid JSON:
{{
  "org_name": "...",
  "is_online_application": true,
  "application_method": "online",
  "offline_reason": "",
  "start_date": "...",
  "end_date": "...",
  "posts": [
    {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}
  ],
  "scripts": [
    "স্ক্রিপ্ট ১...",
    "স্ক্রিপ্ট ২...",
    "স্ক্রিপ্ট ৩...",
    "স্ক্রিপ্ট ৪...",
    "স্ক্রিপ্ট ৫...",
    "স্ক্রিপ্ট ৬...",
    "স্ক্রিপ্ট ৭...",
    "স্ক্রিপ্ট ৮..."
  ],
  "optimized_title": "...",
  "video_description": "..."
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ---------------------------------------------------------------------
    # 🌟 প্ল্যাটফর্ম ১: Ollama Cloud (১ম অগ্রাধিকার - Gemma মডেল অগ্রাধিকার)
    # ---------------------------------------------------------------------
    ollama_keys = parse_multi_keys(["OLLAMA_API_KEYS", "OLLAMA_API_KEY", "Ollama_API_Key"])
    if ollama_keys:
        total_k = len(ollama_keys)
        start_idx = get_saved_key_index("ollama", total_k)
        ollama_endpoint = get_ollama_chat_endpoint()

        print(f"\n--- [Priority 1: Ollama Cloud API] ({total_k} keys detected) ---")
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
                    resp = requests.post(ollama_endpoint, headers=headers, json=payload, timeout=90)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and data.get("org_name") and data.get("posts"):
                            save_key_index("ollama", k_idx, total_k)
                            print(f"  ✅ [Ollama SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        print(f"  ⚠️ Ollama Key #{k_idx+1} limit/auth notice (HTTP {resp.status_code}). Switching key...")
                        save_key_index("ollama", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ---------------------------------------------------------------------
    # 🌟 প্ল্যাটফর্ম ২: OpenRouter Cloud API (২য় অগ্রাধিকার)
    # ---------------------------------------------------------------------
    openrouter_keys = parse_multi_keys(["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"])
    if openrouter_keys:
        total_k = len(openrouter_keys)
        start_idx = get_saved_key_index("openrouter", total_k)
        print(f"\n--- [Priority 2: OpenRouter Cloud API] ({total_k} keys detected) ---")

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
                # OpenRouter ইমেজ সাপোর্ট হ্যান্ডলিং
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
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name") and data.get("posts"):
                            save_key_index("openrouter", k_idx, total_k)
                            print(f"  ✅ [OpenRouter SUCCESS] Model: '{model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        print(f"  ⚠️ OpenRouter Key #{k_idx+1} limit (HTTP {resp.status_code}). Switching key...")
                        save_key_index("openrouter", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ---------------------------------------------------------------------
    # 🌟 প্ল্যাটফর্ম ৩: Groq Cloud API (৩য় অগ্রাধিকার)
    # ---------------------------------------------------------------------
    groq_keys = parse_multi_keys(["GROQ_API_KEYS", "GROQ_API_KEY", "GROQ_API"])
    if groq_keys:
        total_k = len(groq_keys)
        start_idx = get_saved_key_index("groq", total_k)
        print(f"\n--- [Priority 3: Groq Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = groq_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            for g_model in GROQ_MODELS:
                payload = {
                    "model": g_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional Bengali job circular analyst. Return strictly valid JSON containing 8 distinct voiceover scripts ending with inbox/bio CTA."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": 3000
                }
                try:
                    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=80)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name") and data.get("posts"):
                            save_key_index("groq", k_idx, total_k)
                            print(f"  ✅ [Groq SUCCESS] Model: '{g_model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        print(f"  ⚠️ Groq Key #{k_idx+1} limit (HTTP {resp.status_code}). Switching key...")
                        save_key_index("groq", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # ---------------------------------------------------------------------
    # 🌟 প্ল্যাটফর্ম ৪: Cerebras Cloud API (৪র্থ অগ্রাধিকার)
    # ---------------------------------------------------------------------
    cerebras_keys = parse_multi_keys(["CEREBRAS_API_KEYS", "CEREBRAS_API_KEY"])
    if cerebras_keys:
        total_k = len(cerebras_keys)
        start_idx = get_saved_key_index("cerebras", total_k)
        print(f"\n--- [Priority 4: Cerebras Cloud API] ({total_k} keys detected) ---")

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = cerebras_keys[k_idx]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            for c_model in CEREBRAS_MODELS:
                payload = {
                    "model": c_model,
                    "messages": [
                        {"role": "system", "content": "You are a Bengali job circular analyst. Return strictly valid JSON with 8 voiceover scripts ending with inbox/bio CTA."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": 3000
                }
                try:
                    resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload, timeout=80)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("org_name") and data.get("posts"):
                            save_key_index("cerebras", k_idx, total_k)
                            print(f"  ✅ [Cerebras SUCCESS] Model: '{c_model}' (Key #{k_idx+1})")
                            return normalize_eight_scripts(data)
                    elif resp.status_code in [401, 402, 429]:
                        print(f"  ⚠️ Cerebras Key #{k_idx+1} limit (HTTP {resp.status_code}). Switching key...")
                        save_key_index("cerebras", (k_idx + 1) % total_k, total_k)
                        break
                except Exception: pass

    # চূড়ান্ত স্মার্ট ফলব্যাক
    print("  ⚠️ [Notice] All Cloud AI Platforms exhausted/unavailable. Utilizing Smart Local Fallback...")
    fallback = smart_fallback_data(title, article_text, raw_html)
    return normalize_eight_scripts(fallback)
