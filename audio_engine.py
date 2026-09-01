# -*- coding: utf-8 -*-
import os
import re
import time
import requests

PERMITTED_FREE_VOICES = [
    {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George"},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam"},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel"},
    {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam"}
]

PHONE_DIGIT_WORDS = {
    '0': "জিরো", '1': "ওয়ান", '2': "টু", '3': "থ্রি", '4': "ফোর",
    '5': "ফাইভ", '6': "সিক্স", '7': "সেভেন", '8': "এইট", '9': "নাইন"
}

NUM_WORDS_1_TO_99 = {
    0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিন", 4: "চার", 5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়",
    10: "দশ", 11: "এগারো", 12: "বারো", 13: "তেরো", 14: "চৌদ্দ", 15: "পনেরো", 16: "ষোলো", 17: "সতেরো", 18: "আঠারো", 19: "উনিশ",
    20: "বিশ", 21: "একুশ", 22: "বাইশ", 23: "তেইশ", 24: "চব্বিশ", 25: "পঁচিশ", 26: "ছাব্বিশ", 27: "সাতাশ", 28: "আঠাশ", 29: "উনত্রিশ",
    30: "ত্রিশ", 31: "একত্রিশ", 32: "বত্রিশ", 33: "তেত্রিশ", 34: "চৌত্রিশ", 35: "পঁয়ত্রিশ", 36: "ছত্রিশ", 37: "সাঁইত্রিশ", 38: "আটত্রিশ", 39: "উনচল্লিশ",
    40: "চল্লিশ", 41: "একচল্লিশ", 42: "বিয়াল্লিশ", 43: "তেতাল্লিশ", 44: "চুয়াল্লিশ", 45: "পঁয়তাল্লিশ", 46: "ছেচল্লিশ", 47: "সাতচল্লিশ", 48: "আটচল্লিশ", 49: "উনপঞ্চাশ",
    50: "পঞ্চাশ", 51: "একান্ন", 52: "বায়ান্ন", 53: "তিপ্পান্ন", 54: "চুয়ান্ন", 55: "পঞ্চান্ন", 56: "ছাপ্পান্ন", 57: "সাতান্ন", 58: "আটান্ন", 59: "উনষাট",
    60: "ষাট", 61: "একষট্টি", 62: "বাষট্টি", 63: "তেষট্টি", 64: "চৌষট্টি", 65: "পঁয়ষট্টি", 66: "ছেষট্টি", 67: "সাতষট্টি", 68: "আটষট্টি", 69: "উনসত্তর",
    70: "সত্তর", 71: "একাত্তর", 72: "বাহাত্তর", 73: "তিয়াত্তর", 74: "চৌহাত্তর", 75: "পঁচাত্তর", 76: "ছিয়াত্তর", 77: "সাতাত্তর", 78: "আটাত্তর", 79: "উনাশি",
    80: "আশি", 81: "একাশি", 82: "বিরাশি", 83: "তিরাশি", 84: "চুরাশি", 85: "পঁচাশি", 86: "ছিয়াশি", 87: "সাতাশি", 88: "অষ্টআশি", 89: "ঊননব্বই",
    90: "নব্বই", 91: "একানব্বই", 92: "বানব্বই", 93: "তিরানব্বই", 94: "চুরানব্বই", 95: "পঁচানব্বই", 96: "ছিয়ানব্বই", 97: "সাতানব্বই", 98: "আটানব্বই", 99: "নিরানব্বই"
}

def int_to_bangla_words(n):
    if n in NUM_WORDS_1_TO_99: return NUM_WORDS_1_TO_99[n]
    parts = []
    if n >= 10000000: parts.append(int_to_bangla_words(n // 10000000) + " কোটি"); n %= 10000000
    if n >= 100000: parts.append(int_to_bangla_words(n // 100000) + " লক্ষ"); n %= 100000
    if n >= 1000: parts.append(int_to_bangla_words(n // 1000) + " হাজার"); n %= 1000
    if n >= 100:
        h = n // 100; n %= 100
        parts.append("একশত" if h == 1 else (int_to_bangla_words(h) + " শত"))
    if n > 0: parts.append(NUM_WORDS_1_TO_99.get(n, str(n)))
    return " ".join(parts)

def clean_script_for_speech(raw_text):
    if not raw_text: return ""
    bn_to_en = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

    def phone_replacer(match):
        digits = [d for d in match.group(0).translate(bn_to_en) if d.isdigit()]
        if "".join(digits).startswith("8801"): digits = digits[2:]
        return " ".join([PHONE_DIGIT_WORDS.get(d, d) for d in digits])

    text = re.sub(r'(\+?88)?01[\d০-৯]{9}', phone_replacer, raw_text)

    def num_replacer(match):
        try: return int_to_bangla_words(int(match.group(0).translate(bn_to_en)))
        except Exception: return match.group(0)

    text = re.sub(r'[\d০-৯]+', num_replacer, text)
    text = re.sub(r'[\*\_\|\#\~\[\]\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def get_all_elevenlabs_keys():
    raw = os.environ.get("ELEVENLABS_API_KEYS", os.environ.get("ELEVENLABS_API_KEY", "")).strip()
    return [k.strip() for k in re.split(r'[\r\n,;]+', raw) if k.strip()]

def generate_voiceover_audio_pipeline(text, output_audio_path, memory=None):
    speech_text = clean_script_for_speech(text)
    eleven_keys = get_all_elevenlabs_keys()
    if not eleven_keys: return False

    total_k = len(eleven_keys)
    start_idx = (memory.get("elevenlabs_key_index", 0) if isinstance(memory, dict) else 0) % total_k

    for offset in range(total_k):
        k_idx = (start_idx + offset) % total_k
        api_key = eleven_keys[k_idx]
        voice_id = PERMITTED_FREE_VOICES[k_idx % len(PERMITTED_FREE_VOICES)]["id"]

        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": speech_text,
            "model_id": "eleven_v3",
            "language_code": "bn",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}

        try:
            resp = requests.post(tts_url, json=payload, headers=headers, timeout=120)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
                with open(output_audio_path, "wb") as f: f.write(resp.content)
                if isinstance(memory, dict): memory["elevenlabs_key_index"] = k_idx
                return True
        except Exception: pass

    return False
