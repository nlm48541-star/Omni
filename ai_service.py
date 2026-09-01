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

def find_demo_image():
    """রিপোজিটরিতে সেভ থাকা demo.png / demo.jpg খুঁজে বের করে"""
    for d in [".", "Backgrounds"]:
        for name in ["demo.png", "demo.jpg", "Demo.png", "Demo.jpg", "input_file_1.png"]:
            p = os.path.join(d, name)
            if os.path.exists(p): return p
    return None

def smart_fallback_data(title):
    clean = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
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
        "start_date": "চলমান",
        "end_date": "শীঘ্রই শেষ হবে",
        "posts": [
            {"post_name": "বিজ্ঞপ্তিতে উল্লেখিত পদসমূহ", "vacancy": vac_str, "qualification": "বিজ্ঞপ্তি অনুযায়ী"}
        ],
        "voiceover_script": f"নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। {clean} এর জন্য আগ্রহী প্রার্থীরা প্রয়োজনীয় যোগ্যতা নিয়ে আবেদন সম্পন্ন করতে পারেন। ঘরে বসে সহজে নির্ভুলভাবে আবেদন করতে আজই যোগাযোগ করুন স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে।",
        "optimized_title": clean[:90],
        "video_description": f"{clean}\n\nআবেদন করতে যোগাযোগ করুন Whatsapp: +8801540503092"
    }

def generate_job_data_and_script(title, image_paths, memory=None):
    clean_title = remove_years(re.sub(r'\s+', ' ', str(title)).strip())

    prompt = f"""You are a professional Bengali Job Circular Analyst.
Context Title: "{clean_title}"

Look at the attached job circular image and extract the exact fields for our 8-row template:
1. "org_name": Official organization name in Bengali (e.g. "মৎস্য ও প্রাণিসম্পদ তথ্য দপ্তর").
2. "start_date": Application start date without year (e.g. "২৭ জুলাই").
3. "end_date": Application deadline without year (e.g. "২১ আগস্ট").
4. "posts": Array of actual job positions (up to 16 positions). Each post object MUST have:
   - "post_name": Exact name of the post (e.g. "সহকারী চিত্রশিল্পী", "গাড়ী চালক", "অফিস সহায়ক")
   - "vacancy": Vacancy number in Bengali digits (e.g. "০১", "০২", "১০")
   - "qualification": Short educational requirement (e.g. "স্নাতক/সম্মান", "অষ্টম শ্রেণি পাশ", "এইচএসসি পাশ")
5. "voiceover_script": ~1 minute continuous spoken Bengali script (No phone digits spoken, no years mentioned).

Return strictly valid JSON:
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

    # ডেমো ইমেজ থাকলে রেফারেন্স হিসেবে এআই-কে পাঠানো
    demo_p = find_demo_image()
    if demo_p:
        demo_b64 = encode_image_base64(demo_p)
        if demo_b64: base64_imgs.append(demo_b64)

    # ১. Ollama Cloud মেমরি-ভিত্তিক লুপ
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
                        if data and data.get("org_name") and data.get("posts"):
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
                    {"role": "system", "content": "You are a professional Bengali job circular analyzer. Output valid JSON matching the 3-column template format."},
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
                    if data and data.get("org_name") and data.get("posts"): return data
            except Exception: pass

    return smart_fallback_data(title)
