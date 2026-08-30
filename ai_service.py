# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import requests
from PIL import Image
from datetime import datetime

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")
GROQ_API = os.environ.get("GROQ_API", "").strip()

OLLAMA_MODELS = ["kimi-k3", "minimax-m3", "gemma4", "kimi-k2.6"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

def mask_key(k):
    if not k or len(k) <= 8: return "****"
    return k[:4] + "..." + k[-4:]

def get_all_ollama_keys():
    """একাধিক Ollama API Key লোড করে (কমা, সেমিকোলন বা নতুন লাইন দিয়ে আলাদা করা)"""
    raw_keys = os.environ.get("OLLAMA_API_KEYS", os.environ.get("OLLAMA_API_KEY", os.environ.get("Ollama_API_Key", ""))).strip()
    if not raw_keys: return []
    return [k.strip() for k in re.split(r'[\r\n,;]+', raw_keys) if k.strip()]

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

CRITICAL RULES FOR "voiceover_script":
1. Write a continuous, spoken Bengali voiceover script of around 140 to 180 words (exactly ~1 minute duration).
2. ALL NUMBERS in the script MUST be written in words (কথায় লেখা):
   - Years/Dates: "২০২৬" ➔ "দুই হাজার ছাব্বিশ", "০৩ জুলাই" ➔ "তিন জুলাই", "৩০ আগস্ট" ➔ "ত্রিশ আগস্ট"
   - Vacancies/Counts: "১৫০" ➔ "একশত পঞ্চাশ", "১২" ➔ "বারো", "১০" ➔ "দশ"
   - Phone Number: Pronounce in English phonetic words in Bengali: "জিরো ওয়ান ফাইভ ফোর জিরো ফাইভ জিরো থ্রি জিরো নাইন টু"
3. Do NOT use emojis or brackets in the script.

Return strictly valid JSON:
{{
  "org_name": "Official organization name in Bengali",
  "headline": "নিয়োগ বিজ্ঞপ্তি",
  "circular_date": "Date of publish",
  "total_vacancies": "... টি",
  "posts": [
    {{"post_name": "...", "grade": "গ্রেড-...", "vacancy": "..."}}
  ],
  "start_date": "...",
  "start_time": "সকাল ১০:০০",
  "end_date": "...",
  "end_time": "বিকাল ৫:০০",
  "cta_text": "Whatsapp: +8801540503092",
  "voiceover_script": "Comprehensive ~1-minute spoken Bengali script with numbers in words...",
  "optimized_title": "Social title under 90 chars",
  "video_description": "Description with contact link and hashtags..."
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]

    # ১. Ollama Cloud মাল্টিপল এপিআই কী লুপ
    ollama_keys = get_all_ollama_keys()
    if ollama_keys:
        print(f"🔑 [Ollama API Pool] Loaded {len(ollama_keys)} Ollama Cloud key(s).")
        for k_idx, api_key in enumerate(ollama_keys, start=1):
            masked_k = mask_key(api_key)
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            print(f"\n--- [Attempting Ollama Key #{k_idx}/{len(ollama_keys)}: {masked_k}] ---")

            key_failed = False
            for model in OLLAMA_MODELS:
                print(f"  [AI] Attempting Ollama model '{model}' with Key #{k_idx}...")
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
                            print(f"  ✅ [SUCCESS] Generated via Ollama '{model}' using Key #{k_idx}!")
                            return data
                    elif resp.status_code in [401, 402, 429]:
                        print(f"  ⚠️ Ollama Key #{k_idx} failed with HTTP {resp.status_code} (Quota/Auth error). Switching to next key...")
                        key_failed = True
                        break
                    else:
                        print(f"  ⚠️ Ollama ({model}) returned HTTP {resp.status_code}: {resp.text[:120]}")
                except Exception as e:
                    print(f"  ⚠️ Ollama ({model}) notice with Key #{k_idx}: {e}")

            if key_failed:
                continue

    # ২. Groq AI ব্যাকআপ
    if GROQ_API:
        print("\n🤖 [AI Fallback] Attempting Groq AI...")
        headers = {"Authorization": f"Bearer {GROQ_API}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            print(f"  [AI] Attempting Groq AI model '{g_model}'...")
            payload = {
                "model": g_model,
                "messages": [
                    {"role": "system", "content": "You are a professional Bengali job circular analyzer. Write all numbers in Bengali words."},
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
                        print(f"  ✅ [SUCCESS] Generated via Groq ({g_model})!")
                        return data
            except Exception as e:
                print(f"  [!] Groq ({g_model}) notice: {e}")

    # ৩. ডিফল্ট হার্ড ফলব্যাক
    return {
        "org_name": clean_title[:45],
        "headline": "নিয়োগ বিজ্ঞপ্তি",
        "circular_date": f"{cur_bn} সার্কুলার",
        "total_vacancies": "একাধিক পদ",
        "posts": [{"post_name": "নিয়োগ সংক্রান্ত পদসমূহ", "grade": "বিজ্ঞপ্তি অনুযায়ী", "vacancy": "১"}],
        "start_date": "চলমান",
        "start_time": "সকাল ১০:০০",
        "end_date": "শীঘ্রই শেষ হবে",
        "end_time": "বিকাল ৫:০০",
        "cta_text": "Whatsapp: +8801540503092",
        "voiceover_script": f"নতুন সরকারি ও বেসরকারি চাকরির খবর। {clean_title} প্রকাশিত হয়েছে। আগ্রহী প্রার্থীরা প্রয়োজনীয় শিক্ষাগত যোগ্যতা নিয়ে দ্রুত আবেদন সম্পন্ন করতে পারেন। ঘরে বসে সহজে নির্ভুলভাবে আবেদন করতে আজই যোগাযোগ করুন হোয়াটসঅ্যাপে জিরো ওয়ান ফাইভ ফোর জিরো ফাইভ জিরো থ্রি জিরো নাইন টু নাম্বারে।",
        "optimized_title": clean_title[:90],
        "video_description": f"{clean_title}\n\nআবেদন করতে যোগাযোগ করুন Whatsapp: +8801540503092"
    }
