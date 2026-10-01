# -*- coding: utf-8 -*-
import os
import re
import json
import html
from datetime import datetime

CONFIG_FILE = "automation_config.json"
MEMORY_FILE = "bot_memory.json"
SKIPPED_OFFLINE_FILE = "skipped_offline_jobs.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default_val
    return default_val

def save_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"  [!] Failed to save JSON to {filepath}: {e}")

def get_credential(config, key, env_var):
    val = os.environ.get(env_var, "").strip()
    if not val and isinstance(config, dict):
        val = config.get("credentials", {}).get(key, "").strip()
    return val

def strip_html(text):
    if not text: return ""
    text = re.sub(r'<br\s*/?>', '\n', str(text), flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', str(text), flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text

def clean_text(text, keep_hashtags=False):
    if not text: return ""
    text = strip_html(text)
    text = re.sub(r'\[\.\.\.\]|\.\.\.', '', text)
    text = re.sub(r'বিস্তারিত\s*পড়ুন.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'@\w+', '', text)
    if not keep_hashtags:
        text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n+', '\n\n', text).strip()

def clean_telegram_id(tg_id_str):
    if not tg_id_str: return ""
    return tg_id_str.split('/')[-1].replace('@', '').strip()

def clean_feed_url(url):
    if not url: return ""
    if "morss.it" in url:
        matches = re.findall(r'https?://[^\s\'"]+', url)
        if len(matches) > 1:
            return matches[-1]
        cleaned = re.sub(r'https?://morss\.it/([^/]+/)*', '', url)
        if not cleaned.startswith('http'):
            cleaned = 'https://' + cleaned.lstrip('/')
        return cleaned
    return url

def sanitize_filename(name):
    if not name: return "video_output"
    cleaned = re.sub(r'[\/:*?"<>|\x00-\x1f]', '', str(name))
    return cleaned.strip()[:90]

# =========================================================================
# 🌟 অফলাইন সার্কুলার মেমোরি ম্যানেজার (skipped_offline_jobs.json)
# =========================================================================
def load_skipped_offline_urls():
    """পূর্বে স্কিপ করা সমস্ত অফলাইন সার্কুলার লিংক সংগ্রহ করে"""
    data = load_json(SKIPPED_OFFLINE_FILE, [])
    if isinstance(data, list):
        return {item.get("url") for item in data if isinstance(item, dict) and item.get("url")}
    return set()

def record_skipped_offline_job(url, title, reason):
    """অফলাইন সার্কুলারটিকে skipped_offline_jobs.json ফাইলে রেকর্ড করে রাখে"""
    data = load_json(SKIPPED_OFFLINE_FILE, [])
    if not isinstance(data, list):
        data = []
    
    # ডুপ্লিকেট এন্ট্রি এড়ানো
    for item in data:
        if isinstance(item, dict) and item.get("url") == url:
            return

    new_record = {
        "url": url,
        "title": title,
        "reason": reason,
        "skipped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    data.append(new_record)
    save_json(SKIPPED_OFFLINE_FILE, data[-500:])  # সর্বশেষ ৫০০টি রেকর্ড সংরক্ষিত থাকবে

# =========================================================================
# 🌟 ডাকযোগ / কুরিয়ার / সরাসরি আবেদন যাচাই রুলস
# =========================================================================
def detect_offline_application_rules(text, html_content="", title=""):
    combined = f"{title} {text} {html_content}".lower()

    # অনলাইনে আবেদনের নিশ্চিত চিহ্নসমূহ
    online_indicators = [
        r'teletalk\.com\.bd',
        r'online\s*application',
        r'apply\s*online',
        r'অনলাইনে\s*(?:আবেদন|ফরম|ফর্ম|দরখাস্ত|রেজিস্ট্রেশন)',
        r'অনলাইনের\s*মাধ্যমে\s*আবেদন',
        r'ওয়েবসাইটে\s*(?:গিয়ে\s*)?আবেদন',
        r'ওয়েবসাইটে\s*(?:গিয়ে\s*)?আবেদন',
        r'লিংকে\s*প্রবেশ\s*করে\s*আবেদন',
        r'ই\-?মেইলে\s*(?:আবেদন|পাঠাতে|প্রেরণ)',
        r'email\s*application',
        r'portal\.',
        r'erecruitment',
        r'apply\.bdjobs\.com',
        r'bdjobs\.com'
    ]

    # অফলাইন / ডাকযোগ / কুরিয়ার / সরাসরি আবেদনের নিশ্চিত চিহ্নসমূহ
    offline_indicators = [
        r'ডাকযোগে\s*(?:আবেদন|পাঠাতে|প্রেরণ|পৌঁছাতে|জমা|পৌঁছানো)',
        r'কুরি(?:য়ার|য়ার)\s*(?:সার্ভিস|সার্ভিসের\s*মাধ্যমে|এর\s*মাধ্যমে)?\s*(?:পাঠাতে|প্রেরণ|পৌঁছাতে)',
        r'সরাসরি\s*(?:বা\s*ডাকযোগে|অফিসে\s*জমা|পৌঁছাতে|কার্যালয়ে\s*পৌঁছাতে)',
        r'হাতে\s*হাতে\s*(?:জমা|পৌঁছাতে)',
        r'খামের\s*উপর\s*(?:পদের\s*নাম|বিজ্ঞপ্তি\s*নং)',
        r'খামের\s*ওপর\s*(?:পদের\s*নাম|বিজ্ঞপ্তি\s*নং)',
        r'রেজিস্ট্রি\s*ডাকযোগে',
        r'জিইপি\s*(?:এর\s*মাধ্যমে|ডাকযোগে)',
        r'স্বহস্তে\s*লিখিত\s*আবেদন',
        r'ডাকযোগে\s*বা\s*সরাসরি',
        r'অফিস\s*চলাকালীন\s*সময়ে\s*জমা',
        r'নিম্নস্বাক্ষরকারীর\s*কার্যালয়ে\s*পৌঁছাতে\s*হবে',
        r'বরাবর\s*ডাকযোগে\s*পাঠাতে\s*হবে',
        r'ডাকযোগে\s*আবেদনপত্র\s*পাঠাতে\s*হবে',
        r'আবেদনপত্র\s*সরাসরি\s*বা\s*ডাকযোগে'
    ]

    has_online = any(re.search(p, combined, re.I) for p in online_indicators)
    has_offline = any(re.search(p, combined, re.I) for p in offline_indicators)

    # অফলাইন নির্দেশ আছে কিন্তু কোনো অনলাইন লিংক নেই
    if has_offline and not has_online:
        return True, "আবেদনের মাধ্যম ডাকযোগে/কুরিয়ারে/সরাসরি অফিসে জমা (অনলাইন পোর্টাল নেই)"
    return False, "অনলাইন আবেদন বা সাধারণ বিজ্ঞপ্তি"

def check_if_offline_application(article_text, raw_html="", job_data=None, title=""):
    """
    এআই ভিশন এবং রুলস ইঞ্জিন উভয় স্তরে স্ক্যান করে নিশ্চিত হয় এটি অফলাইন আবেদন কিনা।
    """
    if job_data is None:
        job_data = {}

    ai_online = job_data.get("is_online_application")
    ai_method = str(job_data.get("application_method", "")).lower().strip()
    ai_reason = job_data.get("offline_reason", "")

    # এআই ছবি ও লেখা দেখে নিশ্চিত করেছে
    if ai_online is False or ai_method in ["postal", "courier", "in_person", "offline", "offline_other"]:
        return True, ai_reason or f"AI সনাক্ত করেছে আবেদনের পদ্ধতি অফলাইন ({ai_method})"

    # রেজেক্স দিয়ে টেক্সট ও এইচটিএমএল যাচাই
    is_offline, reason = detect_offline_application_rules(article_text, raw_html, title)
    if is_offline:
        return True, reason

    return False, "অনলাইন আবেদন"
