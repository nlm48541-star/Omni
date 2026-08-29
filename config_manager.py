# -*- coding: utf-8 -*-
import os
import re
import json

CONFIG_FILE = "automation_config.json"
MEMORY_FILE = "bot_memory.json"

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

def clean_text(text, keep_hashtags=False):
    if not text:
        return ""
    text = re.sub(r'@\w+', '', str(text))
    if not keep_hashtags:
        text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n+', '\n\n', text).strip()

def clean_telegram_id(tg_id_str):
    if not tg_id_str:
        return ""
    return tg_id_str.split('/')[-1].replace('@', '').strip()

def clean_feed_url(url):
    if not url:
        return ""
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
    if not name:
        return "video_output"
    cleaned = re.sub(r'[\/:*?"<>|\x00-\x1f]', '', str(name))
    return cleaned.strip()[:90]
