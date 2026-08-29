# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from PIL import Image
from datetime import datetime

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", os.environ.get("Ollama_API_Key", "")).strip()
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")
GROQ_API = os.environ.get("GROQ_API", "").strip()

OLLAMA_MODELS = ["kimi-k3", "minimax-m3", "gemma4", "kimi-k2.6"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

def get_current_years():
    cur_year = datetime.now().year
    en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    cur_year_bn = str(cur_year).translate(en_to_bn)
    return str(cur_year), cur_year_bn

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

def generate_job_data_and_script(title, image_paths):
    cur_en, cur_bn = get_current_years()
    clean_title = re.sub(r'\s+', ' ', str(title)).strip()

    prompt = f"""You are a professional Bengali Job Circular Analyst, UI Data Extractor, and Voiceover Scriptwriter.
Context:
- Circular Title: "{clean_title}"
- Current Year Context: {cur_bn} ({cur_en})

Extract data from the circular images or title to construct a complete UI dataset and 1-minute voiceover script.

Return strictly valid JSON with these EXACT keys:
1. "org_name": Organization name in Bengali (e.g., "মৎস্য ও প্রাণিসম্পদ তথ্য দপ্তর", "বাংলাদেশ রেলওয়ে", "পল্লী বিদ্যুৎ সমিতি").
2. "headline": Main headline (e.g., "নিয়োগ বিজ্ঞপ্তি").
3. "circular_date": Date of circular publish (e.g., "২৭ জুলাই ২০২৬" or current date).
4. "total_vacancies": Total posts count with suffix (e.g., "১৯ টি", "১২ টি").
5. "posts": Array of job post objects (up to 8 posts). Each item MUST have:
     - "post_name": Name of post (e.g. "সহকারী চিত্রশিল্পী", "অফিস সহায়ক")
     - "grade": Grade info (e.g. "গ্রেড-১৩", "গ্রেড-২০")
     - "vacancy": Vacancy number in Bengali digits (e.g. "১", "২", "১০")
6. "start_date": Application start date (e.g. "০৩-০৭-২০২৬").
7. "start_time": Start time (e.g. "সকাল ১০:০০").
8. "end_date": Application deadline (e.g. "৩০-০৮-২০২৬").
9. "end_time": Deadline time (e.g. "বিকাল ৫:০০").
10. "cta_text": "Whatsapp: +8801540503092".
11. "voiceover_script": A comprehensive, natural spoken Bengali voiceover script (around 140 to 180 words, exactly ~1 minute speaking duration) describing the job circular, positions, qualifications, deadlines, and a call-to-action to contact WhatsApp +8801540503092. (No emojis, no brackets, continuous spoken Bengali only).
12. "optimized_title": Social media / YouTube video title under 90 characters.
13. "video_description": Video description with job details, WhatsApp link wa.me/8801540503092 and relevant hashtags.

Output format (JSON):
{{
  "org_name": "...",
  "headline": "নিয়োগ বিজ্ঞপ্তি",
  "circular_date": "...",
  "total_vacancies": "... টি",
  "posts": [
    {{"post_name": "...", "grade": "গ্রেড-...", "vacancy": "..."}}
  ],
  "start_date": "...",
  "start_time": "সকাল ১০:০০",
  "end_date": "...",
  "end_time": "বিকাল ৫:০০",
  "cta_text": "Whatsapp: +8801540503092",
  "voiceover_script": "...",
  "optimized_title": "...",
  "video_description": "..."
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ১. Ollama Cloud
    if OLLAMA_API_KEY:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OLLAMA_API_KEY}"}
        for model in OLLAMA_MODELS:
            print(f"  [AI] Attempting Ollama model '{model}'...")
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt, "images": base64_imgs}],
                "stream": False,
                "options": {"temperature": 0.3}
            }
            try:
                resp = requests.post(f"{OLLAMA_API_URL}/api/chat", headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    content = resp.json().get("message", {}).get("content", "")
                    data = parse_json_safely(content)
                    if data and data.get("voiceover_script"):
                        print(f"  [+] Successfully extracted via Ollama ({model})!")
                        return data
            except Exception as e:
                print(f"  [!] Ollama ({model}) notice: {e}")

    # ২. Groq AI Fallback
    if GROQ_API:
        headers = {"Authorization": f"Bearer {GROQ_API}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            print(f"  [AI] Attempting Groq AI model '{g_model}'...")
            payload = {
                "model": g_model,
                "messages": [
                    {"role": "system", "content": "You are a professional Bengali job circular analyzer. Output strictly valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
                "max_tokens": 2200
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    data = parse_json_safely(content)
                    if data and data.get("voiceover_script"):
                        print(f"  [+] Successfully extracted via Groq ({g_model})!")
                        return data
            except Exception as e:
                print(f"  [!] Groq ({g_model}) notice: {e}")

    # ৩. ডিফল্ট ফলব্যাক
    return {
        "org_name": clean_title[:45],
        "headline": "নিয়োগ বিজ্ঞপ্তি",
        "circular_date": f"{cur_bn} সার্কুলার",
        "total_vacancies": "একাধিক পদ",
        "posts": [
            {"post_name": "নিয়োগ সংক্রান্ত পদসমূহ", "grade": "বিজ্ঞপ্তি অনুযায়ী", "vacancy": "১"}
        ],
        "start_date": "চলমান",
        "start_time": "সকাল ১০:০০",
        "end_date": "শীঘ্রই শেষ হবে",
        "end_time": "বিকাল ৫:০০",
        "cta_text": "Whatsapp: +8801540503092",
        "voiceover_script": f"নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। {clean_title} এর জন্য আগ্রহী প্রার্থীরা দ্রুত আবেদন করতে পারেন। ঘরে বসে নির্ভুলভাবে অনলাইনে আবেদন সম্পন্ন করতে আজই যোগাযোগ করুন হোয়াটসঅ্যাপে।",
        "optimized_title": clean_title[:90],
        "video_description": f"{clean_title}\n\nআবেদন করতে যোগাযোগ করুন Whatsapp: +8801540503092"
    }
