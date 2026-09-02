# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from PIL import Image

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")
GROQ_API = os.environ.get("GROQ_API", "").strip()

OLLAMA_MODELS = ["kimi-k3", "minimax-m3", "gemma4", "kimi-k2.6"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

def get_all_ollama_keys():
    raw_keys = os.environ.get("OLLAMA_API_KEYS", os.environ.get("OLLAMA_API_KEY", os.environ.get("Ollama_API_Key", ""))).strip()
    if not raw_keys: return []
    return [k.strip() for k in re.split(r'[\r\n,;]+', raw_keys) if k.strip()]

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

def extract_dates_from_text(text):
    """টেক্সট থেকে বাংলা মাসের নামসহ সঠিক শুরুর ও শেষ তারিখ বের করে"""
    months = r'(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগষ্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)'
    date_pat = rf'([০-৯\d]{{1,2}}\s*{months})'
    
    st_date, ed_date = "চলমান", "শীঘ্রই শেষ হবে"
    st_m = re.search(rf'(?:শুরু|থেকে|প্রকাশ)\s*[:\-\—]?\s*{date_pat}', text, re.I)
    if st_m: st_date = st_m.group(1).strip()
    
    ed_m = re.search(rf'(?:শেষ|পর্যন্ত|সময়সীমা)\s*[:\-\—]?\s*{date_pat}', text, re.I)
    if ed_m: ed_date = ed_m.group(1).strip()
    
    return st_date, ed_date

def smart_fallback_data(title, article_text=""):
    clean = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    st_d, ed_d = extract_dates_from_text(f"{title} {article_text}")
    
    vac_match = re.search(r'(\d+|[০-৯]+)\s*(?:টি\s*)?পদে', clean)
    vac_str = (vac_match.group(1)) if vac_match else "০১"
    
    org_candidate = clean
    org_candidate = re.sub(r'(\d+|[০-৯]+)\s*পদে', '', org_candidate)
    org_candidate = re.sub(r'(?:নতুন\s*)?নিয়োগ\s*বিজ্ঞপ্তি.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = re.sub(r'Job\s*Circular.*$', '', org_candidate, flags=re.IGNORECASE)
    org_candidate = org_candidate.strip(" -|,")
    if not org_candidate or len(org_candidate) < 3:
        org_candidate = clean.split()[0] if clean else "সরকারি নিয়োগ বিজ্ঞপ্তি"

    return {
        "org_name": org_candidate,
        "headline": "নিয়োগ বিজ্ঞপ্তি",
        "start_date": st_d,
        "end_date": ed_d,
        "posts": [
            {"post_name": "বিজ্ঞপ্তিতে উল্লেখিত পদ", "vacancy": vac_str, "qualification": "বিজ্ঞপ্তি অনুযায়ী"}
        ],
        "voiceover_script": f"নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। {clean} এর জন্য আগ্রহী প্রার্থীরা প্রয়োজনীয় যোগ্যতা নিয়ে আবেদন সম্পন্ন করতে পারেন। ঘরে বসে সহজে নির্ভুলভাবে আবেদন করতে আজই যোগাযোগ করুন স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে।",
        "optimized_title": clean[:90],
        "video_description": f"{clean}\n\nআবেদন করতে যোগাযোগ করুন Whatsapp: +8801540503092"
    }

def generate_job_data_and_script(title, article_text, image_paths, memory=None):
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Job Title: {clean_title}\n\nArticle Details:\n{article_text[:2500]}"

    prompt = f"""You are a professional Bengali Job Circular Analyst.
Analyze the following circular details and images, and extract the EXACT fields for our 8-row table template:

Content:
{full_content}

CRITICAL RULES:
1. "org_name": Extract ONLY the official company/ministry/institution name (e.g. "পাবনা বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "কর্ণফুলী ফার্টিলাইজার কোম্পানি লিমিটেড"). Do NOT include words like "নিয়োগ বিজ্ঞপ্তি" or "2026".
2. "start_date": Extract exact start date with Bengali month, WITHOUT YEAR (e.g. "২৭ জুলাই" or "০১ আগস্ট").
3. "end_date": Extract exact deadline date with Bengali month, WITHOUT YEAR (e.g. "২১ আগস্ট" or "৩০ সেপ্টেম্বর").
4. "posts": Extract up to 16 actual post items from the text. Each object MUST contain:
   - "post_name": Actual position name (e.g. "সহকারী চিত্রশিল্পী", "কম্পিউটার অপারেটর", "অফিস সহায়ক")
   - "vacancy": Vacancy count in Bengali digits (e.g. "০১", "০২", "১০")
   - "qualification": Educational requirement (e.g. "স্নাতক/সম্মান", "এইচএসসি পাশ", "অষ্টম শ্রেণি পাশ")
5. "voiceover_script": ~1 minute spoken Bengali script without mentioning phone numbers or years.

Return strictly valid JSON only:
{{
  "org_name": "...",
  "start_date": "...",
  "end_date": "...",
  "posts": [
    {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}
  ],
  "voiceover_script": "...",
  "optimized_title": "...",
  "video_description": "..."
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ১. Ollama Cloud
    ollama_keys = get_all_ollama_keys()
    if ollama_keys:
        total_k = len(ollama_keys)
        start_idx = (memory.get("ollama_key_index", 0) if isinstance(memory, dict) else 0) % total_k

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = ollama_keys[k_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

            for model in OLLAMA_MODELS:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": base64_imgs}],
                    "stream": False,
                    "options": {"temperature": 0.2}
                }
                try:
                    resp = requests.post(f"{OLLAMA_API_URL}/api/chat", headers=headers, json=payload, timeout=45)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and data.get("org_name") and data.get("posts") and len(data.get("posts")) > 0:
                            if isinstance(memory, dict): memory["ollama_key_index"] = k_idx
                            return data
                except Exception: pass

    # ২. Groq AI ব্যাকআপ
    if GROQ_API:
        headers = {"Authorization": f"Bearer {GROQ_API}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            payload = {
                "model": g_model,
                "messages": [
                    {"role": "system", "content": "You are a professional Bengali job circular analyzer. Extract exact post names, counts, qualifications, and dates from text."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "max_tokens": 2500
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                    if data and data.get("org_name") and data.get("posts") and len(data.get("posts")) > 0:
                        return data
            except Exception: pass

    return smart_fallback_data(title, article_text)
