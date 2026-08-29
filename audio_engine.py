# -*- coding: utf-8 -*-
import os
import re
import time
import requests

# 🌟 ElevenLabs-এর প্রিমিয়াম ও ন্যাচারাল ভয়েস লিস্ট
PERMITTED_FREE_VOICES = [
    {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George (News Anchor)"},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam (Deep Professional)"},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian (Narrative Anchor)"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel (Authoritative News)"},
    {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam (Crisp Dynamic)"},
    {"id": "iP95p4xoKVk53GoZ742B", "name": "Chris (Casual Professional)"},
    {"id": "pqHfZKP75CvOlQylNhV4", "name": "Bill (Warm Trustworthy)"}
]

# ফোন নাম্বারের জন্য ইংরেজি ডিজিটের বাংলা উচ্চারণ
PHONE_DIGIT_WORDS = {
    '0': "জিরো",
    '1': "ওয়ান",
    '2': "টু",
    '3': "থ্রি",
    '4': "ফোর",
    '5': "ফাইভ",
    '6': "সিক্স",
    '7': "সেভেন",
    '8': "এইট",
    '9': "নাইন"
}

# সাধারণ সংখ্যার জন্য ১ থেকে ৯৯ পর্যন্ত কথায় লেখার ডিকশনারি
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
    if n in NUM_WORDS_1_TO_99:
        return NUM_WORDS_1_TO_99[n]
    parts = []
    if n >= 10000000:
        crore = n // 10000000
        n %= 10000000
        parts.append(int_to_bangla_words(crore) + " কোটি")
    if n >= 100000:
        lakh = n // 100000
        n %= 100000
        parts.append(int_to_bangla_words(lakh) + " লক্ষ")
    if n >= 1000:
        thousand = n // 1000
        n %= 1000
        parts.append(int_to_bangla_words(thousand) + " হাজার")
    if n >= 100:
        hundred = n // 100
        n %= 100
        if hundred == 1: parts.append("একশত")
        else: parts.append(int_to_bangla_words(hundred) + " শত")
    if n > 0:
        parts.append(NUM_WORDS_1_TO_99.get(n, str(n)))
    return " ".join(parts)

def convert_all_numbers_to_bangla_words(text):
    if not text: return ""
    bn_to_en = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

    # ১. প্রথমে ফোন নাম্বার খুঁজে বের করে 'জিরো ওয়ান ফাইভ...' ফরম্যাটে রূপান্তর
    def phone_replacer(match):
        raw_num = match.group(0)
        digits = [d for d in raw_num.translate(bn_to_en) if d.isdigit()]
        # +8801... থাকলে 01... থেকে শুরু করবে
        if "".join(digits).startswith("8801"):
            digits = digits[2:]
        return " ".join([PHONE_DIGIT_WORDS.get(d, d) for d in digits])

    text = re.sub(r'(\+?88)?01[\d০-৯]{9}', phone_replacer, text)

    # ২. এরপর বাকি সব সংখ্যাকে (সাল, পদ সংখ্যা, তারিখ ইত্যাদি) বাংলায় কথায় রূপান্তর
    def num_replacer(match):
        num_str = match.group(0)
        en_num = num_str.translate(bn_to_en)
        try:
            val = int(en_num)
            return int_to_bangla_words(val)
        except Exception:
            return num_str

    text = re.sub(r'[\d০-৯]+', num_replacer, text)
    return text

def mask_key(k):
    if not k or len(k) <= 8: return "****"
    return k[:4] + "..." + k[-4:]

def clean_script_for_speech(raw_text):
    if not raw_text: return ""
    # সংখ্যা ও ফোন নাম্বার কনভার্ট করা হচ্ছে
    text = convert_all_numbers_to_bangla_words(raw_text)
    text = re.sub(r'[\*\_\|\#\~]', '', str(text))
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_all_elevenlabs_keys():
    raw_keys = os.environ.get("ELEVENLABS_API_KEYS", os.environ.get("ELEVENLABS_API_KEY", "")).strip()
    if not raw_keys: return []
    return [k.strip() for k in re.split(r'[\r\n,;]+', raw_keys) if k.strip()]

def get_voice_for_index(voice_index, api_key):
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            custom_voices = [v for v in resp.json().get("voices", []) if v.get("category") == "generated"]
            if custom_voices:
                selected = custom_voices[voice_index % len(custom_voices)]
                return selected.get("voice_id"), f"'{selected.get('name')}' (Custom)"
    except Exception: pass

    v_info = PERMITTED_FREE_VOICES[voice_index % len(PERMITTED_FREE_VOICES)]
    return v_info["id"], f"'{v_info['name']}' (Premade)"

def generate_voiceover_audio_pipeline(text, output_audio_path, voice_index=0):
    print("\n" + "="*65)
    print(f"🎙️ [AUDIO ENGINE] ElevenLabs Voice Synthesis (Voice #{voice_index + 1})")
    print("="*65)

    speech_text = clean_script_for_speech(text)
    words = len(speech_text.split())
    print(f"📊 [Text Analysis] Clean Characters: {len(speech_text)} | Words: {words}")
    print(f"📝 [Script Preview]: \"{speech_text[:140]}...\"\n")

    eleven_keys = get_all_elevenlabs_keys()
    if not eleven_keys:
        print("❌ [ERROR] No ElevenLabs API keys found in secrets!")
        return False

    for idx, api_key in enumerate(eleven_keys, start=1):
        voice_id, voice_name = get_voice_for_index(voice_index, api_key)
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        print(f"  • Attempting Key #{idx}/{len(eleven_keys)}: {mask_key(api_key)}")
        print(f"  • Assigned Voice: {voice_name} [ID: {voice_id}]")

        payload = {
            "text": speech_text,
            "model_id": "eleven_v3",
            "language_code": "bn",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }

        start_t = time.time()
        try:
            resp = requests.post(tts_url, json=payload, headers=headers, timeout=120)
            elapsed = round(time.time() - start_t, 2)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
                with open(output_audio_path, "wb") as f:
                    f.write(resp.content)
                size_mb = round(os.path.getsize(output_audio_path) / (1024*1024), 2)
                print(f"  ✅ [SUCCESS] Voiceover Generated ({size_mb} MB) in {elapsed}s!")
                print(f"  📁 Saved: {output_audio_path}")
                print("="*65 + "\n")
                return True
            else:
                print(f"  ⚠️ Key #{idx} returned HTTP {resp.status_code}: {resp.text[:180]}")
                continue
        except Exception as e:
            print(f"  ⚠️ Key #{idx} error: {e}")
            continue

    print("❌ [FAILED] All ElevenLabs keys exhausted.")
    return False
