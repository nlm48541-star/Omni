# -*- coding: utf-8 -*-
import os, json, re, base64, requests
from datetime import datetime
from PIL import Image

OLLAMA_API_KEY = os.environ.get("Ollama_API_Key", os.environ.get("OLLAMA_API_KEY", "")).strip()
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")
GROQ_API = os.environ.get("GROQ_API", "").strip()

OLLAMA_MODELS = ["kimi-k3", "minimax-m3", "gemma4", "kimi-k2.6"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

DEFAULT_BASE_TAGS = [
    'চাকরির সার্কুলার', 'চাকরির খবর', 'সরকারি চাকরি',
    'job circular', 'govt job circular', 'job application bd'
]

# ১ থেকে ৯৯ পর্যন্ত খাঁটি বাংলা শব্দের ম্যাপিং
BN_NUMS = {
    0: 'শূন্য', 1: 'এক', 2: 'দুই', 3: 'তিন', 4: 'চার', 5: 'পাঁচ', 6: 'ছয়', 7: 'সাত', 8: 'আট', 9: 'নয়', 10: 'দশ',
    11: 'এগারো', 12: 'বারো', 13: 'তেরো', 14: 'চৌদ্দ', 15: 'পনেরো', 16: 'ষোলো', 17: 'সতেরো', 18: 'আঠারো', 19: 'উনিশ', 20: 'বিশ',
    21: 'একুশ', 22: 'বাইশ', 23: 'তেইশ', 24: 'চব্বিশ', 25: 'পঁচিশ', 26: 'ছাব্বিশ', 27: 'সাতাশ', 28: 'আঠাশ', 29: 'উনত্রিশ', 30: 'ত্রিশ',
    31: 'একত্রিশ', 32: 'বত্রিশ', 33: 'তেত্রিশ', 34: 'চৌত্রিশ', 35: 'পঁয়ত্রিশ', 36: 'ছত্রিশ', 37: 'সাঁইত্রিশ', 38: 'আটত্রিশ', 39: 'উনচল্লিশ', 40: 'চল্লিশ',
    41: 'একচল্লিশ', 42: 'বিয়াল্লিশ', 43: 'তেতাল্লিশ', 44: 'চুয়াল্লিশ', 45: 'পঁয়তাল্লিশ', 46: 'ছেচল্লিশ', 47: 'সাতচল্লিশ', 48: 'আটচল্লিশ', 49: 'উনপঞ্চাশ', 50: 'পঞ্চাশ',
    51: 'একান্ন', 52: 'বায়ান্ন', 53: 'তিপ্পান্ন', 54: 'চুয়ান্ন', 55: 'পঞ্চান্ন', 56: 'ছাপ্পান্ন', 57: 'সাতান্ন', 58: 'আটান্ন', 59: 'উনষাট', 60: 'ষাট',
    61: 'একষট্টি', 62: 'বাষট্টি', 63: 'তেষট্টি', 64: 'চৌষট্টি', 65: 'পঁয়ষট্টি', 66: 'ছেষট্টি', 67: 'সাতষট্টি', 68: 'আটষট্টি', 69: 'উনসত্তর', 70: 'সত্তর',
    71: 'একাত্তর', 72: 'বাহাত্তর', 73: 'তিয়াত্তর', 74: 'চৌহাত্তর', 75: 'পঁচাত্তর', 76: 'ছিয়াত্তর', 77: 'সাতাত্তর', 78: 'আটাত্তর', 79: 'উনআশি', 80: 'আশি',
    81: 'একাশি', 82: 'বিরাশি', 83: 'তিরাশি', 84: 'চুরাশি', 85: 'পঁচাশি', 86: 'ছিয়াশি', 87: 'সাতাশি', 88: 'অষ্টআশি', 89: 'ঊননব্বই', 90: 'নব্বই',
    91: 'একানব্বই', 92: 'বানব্বই', 93: 'তিরানব্বই', 94: 'চুরানব্বই', 95: 'পঁচানব্বই', 96: 'ছিয়ানব্বই', 97: 'সাতানব্বই', 98: 'আটানব্বই', 99: 'নিরানব্বই'
}

DIGIT_TO_ENG_BN = {
    '0': 'জিরো', '1': 'ওয়ান', '2': 'টু', '3': 'থ্রি', '4': 'ফোর',
    '5': 'ফাইভ', '6': 'সিক্স', '7': 'সেভেন', '8': 'এইট', '9': 'নাইন',
    '০': 'জিরো', '১': 'ওয়ান', '২': 'টু', '৩': 'থ্রি', '৪': 'ফোর',
    '৫': 'ফাইভ', '৬': 'সিক্স', '৭': 'সেভেন', '৮': 'এইট', '৯': 'নাইন'
}

def en_bn_to_int(s):
    trans = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
    return int(str(s).translate(trans))

def number_to_bangla_words(n):
    if n == 0: return 'শূন্য'
    parts = []
    koti = n // 10000000
    if koti > 0:
        parts.append(number_to_bangla_words(koti) + ' কোটি')
        n %= 10000000
    lakh = n // 100000
    if lakh > 0:
        parts.append(BN_NUMS.get(lakh, str(lakh)) + ' লাখ')
        n %= 100000
    hajar = n // 1000
    if hajar > 0:
        parts.append(BN_NUMS.get(hajar, str(hajar)) + ' হাজার')
        n %= 1000
    shatok = n // 100
    if shatok > 0:
        if shatok == 1: parts.append('একশত')
        else: parts.append(BN_NUMS.get(shatok, str(shatok)) + ' শত')
        n %= 100
    if n > 0:
        parts.append(BN_NUMS.get(n, str(n)))
    return ' '.join(parts)

def convert_all_numbers_in_script(text):
    if not text: return ""
    text = re.sub(r'(\d+),(\d+)', r'\1\2', text)
    text = re.sub(r'([০-৯]+),([০-৯]+)', r'\1\2', text)

    def phone_repl(m):
        raw_phone = m.group(0)
        digits = re.findall(r'[0-9০-৯]', raw_phone)
        return ' '.join(DIGIT_TO_ENG_BN.get(d, d) for d in digits)

    text = re.sub(r'(\+?(?:88|৮৮)?\s*0?1[0-9০-৯]{8,10})', phone_repl, text)

    def num_repl(m):
        num_str = m.group(0)
        try:
            val = en_bn_to_int(num_str)
            return number_to_bangla_words(val)
        except Exception:
            return num_str

    text = re.sub(r'[0-9০-৯]+', num_repl, text)
    return text

def get_current_years():
    cur_year = datetime.now().year
    en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    cur_year_bn = str(cur_year).translate(en_to_bn)
    return str(cur_year), cur_year_bn

def normalize_outdated_years(text):
    if not text: return text
    cur_en, cur_bn = get_current_years()
    text = re.sub(r'\b202[0-5]\b', cur_en, str(text))
    text = re.sub(r'২০২[০-৫]', cur_bn, text)
    return text

def sanitize_youtube_tags(raw_tags, max_total_chars=400):
    clean_tags = []
    current_length = 0
    for tag in raw_tags:
        if not tag or not isinstance(tag, str): continue
        cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\<\>\"\,\n\r]', '', tag)
        cleaned = normalize_outdated_years(re.sub(r'\s+', ' ', cleaned).strip())
        if not cleaned or len(cleaned) < 2: continue
        cleaned = cleaned[:50].strip()
        if cleaned not in clean_tags:
            tag_len = len(cleaned) + (1 if clean_tags else 0)
            if current_length + tag_len <= max_total_chars:
                clean_tags.append(cleaned)
                current_length += tag_len
            else: break
    return clean_tags

def clean_title_for_display(title):
    clean = title.split('|')[0].split('||')[0].strip()
    return re.sub(r'\s+', ' ', re.sub(r'[\r\n\t]+', ' ', clean))

def strip_unwanted_chars(text):
    cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|✪|★|☆', '', str(text))
    return normalize_outdated_years(cleaned.strip())

def extract_vacancy_and_qual(title):
    vac_match = re.search(r'(\d+|[০-৯]+)\s*(টি\s*)?পদে', title)
    vac_str = vac_match.group(0) if vac_match else ""
    qual = ""
    if any(k in title.upper() for k in ["SSC", "এসএসসি"]): qual = "SSC পাশ"
    elif any(k in title.upper() for k in ["HSC", "এইচএসসি"]): qual = "HSC পাশ"
    elif any(k in title for k in ["৮ম", "অষ্টম"]): qual = "৮ম শ্রেণি পাশ"
    elif any(k in title for k in ["স্নাতক", "ডিগ্রী", "অনার্স", "Degree", "Honours"]): qual = "ডিগ্রী/অনার্স পাশ"
    return vac_str, qual

def encode_image_base64(image_path, max_dim=1024):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            if max(img.size) > max_dim: img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception: return None

def parse_json_safely(raw_text):
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception:
        return None

def generate_job_content(title, img_paths):
    cur_en, cur_bn = get_current_years()
    clean_title = clean_title_for_display(title)
    words = clean_title.split()
    org_name = clean_title.split("নিয়োগ")[0].strip() if "নিয়োগ" in clean_title else " ".join(words[:min(3, len(words))])
    vac_str, qual_str = extract_vacancy_and_qual(clean_title)

    prompt = f"""You are a professional Bengali YouTube SEO specialist and scriptwriter.
Context:
- Job Circular Title: "{clean_title}"
- Organization: "{org_name}"
- Current Year Context: {cur_bn} ({cur_en})

CRITICAL SCRIPT RULES:
1. SCRIPT LENGTH: Exactly 4 minutes long (550 to 650 words). Continuous spoken natural Bengali.
2. YEAR RULE: Mention the year AT MOST ONCE during the initial announcement. DO NOT repeatedly mention or force the year across paragraphs.
3. NUMBERS IN WORDS: Every number, vacancy count, salary scale, and date MUST be written in Bengali words (কথায় লেখা). Never use raw digits (0-9).
4. CALL TO ACTION: You MUST clearly tell the audience that if they want to apply for this job from home accurately, they should contact our application service via the WhatsApp number shown on the screen or in the description (01540503092 -> 'জিরো ওয়ান ফাইভ ফোর জিরো ফাইভ জিরো থ্রি জিরো নাইন টু').

Return a strictly valid JSON object:
1. "optimized_title": A UNIQUE, high-CTR YouTube Video Title under 95 characters (Use symbols like 🔥, 🚨, ⚡, 📢, |).
2. "voiceover_script": A comprehensive 4-minute continuous spoken Bengali script (550 to 650 words) with all numbers written in words, year mentioned at most once, and the WhatsApp application service call to action.
3. "video_description": A tailored YouTube Description with circular summary, official contact details, and hashtags:
---
[Circular Summary & Post Highlights here]

আমারা চাকরিপ্রার্থীদের জন্য সরকারি ও বেসরকারি সব ধরনের চাকরির আবেদন প্রক্রিয়াটি সহজ ও নিয়মতান্ত্রিক করতে কাজ করে থাকি।
আমাদের মাধ্যমে যেকোনো চাকরির আবেদন ঘরে বসে সম্পন্ন করতে আজই যোগাযোগ করুন:
💬 হোয়াটসঅ্যাপ (WhatsApp): wa.me/8801540503092
🌐 ফেসবুক পেজ (Facebook Page): https://www.facebook.com/profile.php?id=61583625958904

[3 to 5 targeted Bengali/English hashtags for this circular]
---
4. "specific_tags": A list of 4 to 6 specific SEO tags without emojis or commas.
5. "top_text": 2-3 clean Bengali words for Thumbnail Top Bar (e.g., "সরকারি চাকরি", "পানি উন্নয়ন বোর্ড", "জরুরি নিয়োগ"). DO NOT use any ✪ or star symbols.
6. "row1_text": 2-3 short, impactful words for Thumbnail Hook in RED (e.g., "নিজ জেলায়", "অফিস সহায়ক", "জরুরি নিয়োগ").
7. "row2_text": 2-4 short words for Thumbnail Sub-line in BLACK (e.g., "DC অফিসে চাকরি", "এডমিট কার্ড প্রকাশ", "(SSC পাশ/৬৪ জেলা)").
8. "bot_text": Bottom Bar Bengali text (e.g., "আবেদনের নিয়ম ও বিস্তারিত", "({vac_str if vac_str else 'বিশাল সার্কুলার'}) নিয়োগ").

Return strictly valid JSON:
{{
  "optimized_title": "...",
  "voiceover_script": "...",
  "video_description": "...",
  "specific_tags": ["..."],
  "top_text": "...",
  "row1_text": "...",
  "row2_text": "...",
  "bot_text": "..."
}}"""

    base64_images = [encode_image_base64(p) for p in img_paths[:3] if encode_image_base64(p)]

    # ------------------ [১ম ধাপ: Ollama] ------------------
    if OLLAMA_API_KEY:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OLLAMA_API_KEY}"}
        for model_name in OLLAMA_MODELS:
            print(f"🤖 Attempting Ollama Model '{model_name}' for '{clean_title}'...")
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt, "images": base64_images}],
                "stream": False, "options": {"temperature": 0.5}
            }
            try:
                resp = requests.post(f"{OLLAMA_API_URL}/api/chat", headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    raw_content = resp.json().get("message", {}).get("content", "").strip()
                    data = parse_json_safely(raw_content)
                    if data and data.get("optimized_title") and data.get("voiceover_script"):
                        opt_title = normalize_outdated_years(data.get("optimized_title").strip()[:100])
                        raw_script = normalize_outdated_years(re.sub(r'[\r\n]+', ' ', data.get("voiceover_script").strip()))
                        script = convert_all_numbers_in_script(raw_script)
                        desc = normalize_outdated_years(data.get("video_description", "").strip())
                        raw_tags = data.get("specific_tags", []) + DEFAULT_BASE_TAGS
                        tags = sanitize_youtube_tags(raw_tags)
                        
                        thumb_meta = {
                            "top_text": strip_unwanted_chars(data.get("top_text", "সরকারি চাকরি")),
                            "row1_text": strip_unwanted_chars(data.get("row1_text", "জরুরি নিয়োগ")),
                            "row2_text": strip_unwanted_chars(data.get("row2_text", "(SSC পাশ/৬৪ জেলা)")),
                            "bot_text": strip_unwanted_chars(data.get("bot_text", "আবেদনের নিয়ম ও বিস্তারিত"))
                        }
                        print(f"✨ Successfully Generated via Ollama '{model_name}' (4-min Script)!")
                        return opt_title, script, thumb_meta, desc, tags
            except Exception: pass

    # ------------------ [২য় ধাপ: Groq AI] ------------------
    if GROQ_API:
        headers = {"Authorization": f"Bearer {GROQ_API}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            print(f"🤖 Attempting Groq AI Model '{g_model}'...")
            payload = {
                "model": g_model,
                "messages": [
                    {"role": "system", "content": "You are a professional Bengali YouTube SEO and scriptwriter. Write a 4-minute script (550-650 words) with numbers in words and WhatsApp application call to action. Output strictly valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.5,
                "max_tokens": 2500
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    raw_content = resp.json()['choices'][0]['message']['content']
                    data = parse_json_safely(raw_content)
                    if data and data.get("optimized_title") and data.get("voiceover_script"):
                        opt_title = normalize_outdated_years(data.get("optimized_title").strip()[:100])
                        raw_script = normalize_outdated_years(re.sub(r'[\r\n]+', ' ', data.get("voiceover_script").strip()))
                        script = convert_all_numbers_in_script(raw_script)
                        desc = normalize_outdated_years(data.get("video_description", "").strip())
                        raw_tags = data.get("specific_tags", []) + DEFAULT_BASE_TAGS
                        tags = sanitize_youtube_tags(raw_tags)

                        thumb_meta = {
                            "top_text": strip_unwanted_chars(data.get("top_text", "সরকারি চাকরি")),
                            "row1_text": strip_unwanted_chars(data.get("row1_text", "জরুরি নিয়োগ")),
                            "row2_text": strip_unwanted_chars(data.get("row2_text", "(SSC পাশ/৬৪ জেলা)")),
                            "bot_text": strip_unwanted_chars(data.get("bot_text", "আবেদনের নিয়ম ও বিস্তারিত"))
                        }
                        print(f"✨ Successfully Generated via Groq AI ({g_model}) (4-min Script)!")
                        return opt_title, script, thumb_meta, desc, tags
            except Exception: pass

    return None, None, None, None, None
