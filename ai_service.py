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

def mask_key(k):
    if not k or len(k) <= 8: return "****"
    return k[:4] + "..." + k[-4:]

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
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception:
        return None

def remove_years(text):
    """সাল উল্লেখ থাকলে মুছে ফেলে"""
    if not text: return ""
    text = re.sub(r'\b202[0-9]\b', '', str(text))
    text = re.sub(r'২০২[০-৯]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_job_data_and_script(title, image_paths):
    clean_title = remove_years(re.sub(r'\s+', ' ', str(title)).strip())

    prompt = f"""You are a professional Bengali Job Circular Analyst, UI Data Extractor, and Voiceover Scriptwriter.
Context:
- Circular Title: "{clean_title}"

STRICT GUIDELINES:
1. "voiceover_script": 
   - Write a continuous spoken Bengali voiceover script of around 140 to 180 words (~1 minute duration).
   - Write all counts/vacancies/dates strictly in Bengali words (e.g., "১৫০" ➔ "একশত পঞ্চাশ", "১২" ➔ "বারো", "৩ জুলাই" ➔ "তিন জুলাই").
   - DO NOT speak the phone number digits. Instead, say: "আমাদের মাধ্যমে নির্ভুলভাবে আবেদন করতে স্ক্রিনে বা ডেসক্রিপশনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে আজই যোগাযোগ করুন।"
   - DO NOT mention any year (e.g. 2026 or ২০২৬) anywhere in the script.

2. "optimized_title":
   - Write an engaging title under 90 characters. DO NOT include any year.

Return strictly valid JSON:
{{
  "org_name": "Official organization name in Bengali",
  "headline": "নিয়োগ বিজ্ঞপ্তি",
  "circular_date": "Date of publish (no year)",
  "total_vacancies": "... টি",
  "posts": [
    {{"post_name": "...", "grade": "গ্রেড-...", "vacancy": "..."}}
  ],
  "start_date": "আবেদন শুরুর তারিখ",
  "start_time": "সকাল ১০:০০",
  "end_date": "আবেদনের শেষ তারিখ",
  "end_time": "বিকাল ৫:০০",
  "cta_text": "Whatsapp: +8801540503092",
  "voiceover_script": "...",
  "optimized_title": "...",
  "video_description": "..."
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ১. Ollama Cloud
    ollama_keys = get_all_ollama_keys()
    if ollama_keys:
        for k_idx, api_key in enumerate(ollama_keys, start=1):
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            for model in OLLAMA_MODELS:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": base64_imgs}],
                    "stream": False,
                    "options": {"temperature": 0.4}
                }
                try:
                    resp = requests.post(f"{OLLAMA_API_URL}/api/chat", headers=headers, json=payload, timeout=45)
                    if resp.status_code == 200:
                        content = resp.json().get("message", {}).get("content", "")
                        data = parse_json_safely(content)
                        if data and data.get("voiceover_script"):
                            data["optimized_title"] = remove_years(data.get("optimized_title", clean_title))
                            return data
                except Exception: pass

    # ২. Groq AI
    if GROQ_API:
        headers = {"Authorization": f"Bearer {GROQ_API}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            payload = {
                "model": g_model,
                "messages": [
                    {"role": "system", "content": "You are a professional Bengali job analyzer. Do not mention any years. Do not recite phone digits."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
                "max_tokens": 2200
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    data = parse_json_safely(content)
                    if data and data.get("voiceover_script"):
                        data["optimized_title"] = remove_years(data.get("optimized_title", clean_title))
                        return data
            except Exception: pass

    # ৩. ডিফল্ট ফলব্যাক
    return {
        "org_name": clean_title[:45],
        "headline": "নিয়োগ বিজ্ঞপ্তি",
        "circular_date": "নতুন সার্কুলার",
        "total_vacancies": "একাধিক পদ",
        "posts": [{"post_name": "নিয়োগ সংক্রান্ত পদসমূহ", "grade": "বিজ্ঞপ্তি অনুযায়ী", "vacancy": "১"}],
        "start_date": "চলমান",
        "start_time": "সকাল ১০:০০",
        "end_date": "শীঘ্রই শেষ হবে",
        "end_time": "বিকাল ৫:০০",
        "cta_text": "Whatsapp: +8801540503092",
        "voiceover_script": f"নতুন সরকারি ও বেসরকারি চাকরির খবর। {clean_title} প্রকাশিত হয়েছে। আগ্রহী প্রার্থীরা প্রয়োজনীয় শিক্ষাগত যোগ্যতা নিয়ে দ্রুত আবেদন সম্পন্ন করতে পারেন। ঘরে বসে সহজে নির্ভুলভাবে আবেদন করতে আজই যোগাযোগ করুন স্ক্রিনে ও ডেসক্রিপশনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে।",
        "optimized_title": clean_title[:90],
        "video_description": f"{clean_title}\n\nআবেদন করতে যোগাযোগ করুন Whatsapp: +8801540503092"
    }
