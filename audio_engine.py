# -*- coding: utf-8 -*-
import os
import re
import time
import base64
import random
import shutil
import requests
import concurrent.futures

TRACKER_FILE = "key_tracker.json"

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

def convert_all_numbers_to_bangla_words(text):
    if not text: return ""
    bn_to_en = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

    def phone_replacer(match):
        raw_num = match.group(0)
        digits = [d for d in raw_num.translate(bn_to_en) if d.isdigit()]
        if "".join(digits).startswith("8801"): digits = digits[2:]
        return " ".join([PHONE_DIGIT_WORDS.get(d, d) for d in digits])

    text = re.sub(r'(\+?88)?01[\d০-৯]{9}', phone_replacer, text)

    def num_replacer(match):
        num_str = match.group(0)
        try: return int_to_bangla_words(int(num_str.translate(bn_to_en)))
        except Exception: return num_str

    text = re.sub(r'[\d০-৯]+', num_replacer, text)
    return text

def mask_key(k):
    if not k or len(k) <= 8: return "****"
    return k[:4] + "..." + k[-4:]

def clean_script_for_speech(raw_text):
    if not raw_text: return ""
    text = convert_all_numbers_to_bangla_words(raw_text)
    text = re.sub(r'[\*\_\|\#\~]', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_multi_keys(env_var_names):
    if isinstance(env_var_names, str): env_var_names = [env_var_names]
    for env_name in env_var_names:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            lines = re.split(r'[\r\n,;]+', raw)
            keys = [k.strip() for k in lines if k.strip() and not k.strip().startswith('#')]
            if keys: return keys
    return []

def get_saved_key_index(platform, total_keys):
    if total_keys <= 0: return 0
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return int(data.get(f"{platform}_index", 0)) % total_keys
        except Exception: pass
    return 0

def save_key_index(platform, index, total_keys):
    if total_keys <= 0: return
    data = {}
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception: data = {}
    data[f"{platform}_index"] = index % total_keys
    try:
        with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception: pass

# =========================================================================
# 🌟 ১. Gemini 3.8 Flash TTS ইঞ্জিন (৬০ সেকেন্ড সেফটি গার্ড সহ)
# =========================================================================
def _call_gemini_api_direct(api_key, speech_text, voice_candidate, delivery_style):
    from google import genai
    client = genai.Client(api_key=api_key)
    return client.interactions.create(
        model="gemini-3.8-flash-tts",
        input=[{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": speech_text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": delivery_style
                }]
            }]
        }],
        response_format={"type": "audio"},
        generation_config={
            "speech_config": [{"voice": voice_candidate}]
        }
    )

def synthesize_with_gemini(speech_text, output_audio_path):
    gemini_keys = parse_multi_keys(["GEMINI_API_KEYS", "GEMINI_API_KEY"])
    if not gemini_keys:
        return False

    total_k = len(gemini_keys)
    start_idx = get_saved_key_index("gemini", total_k)
    print(f"\n--- [Priority 1: Gemini 3.8 Flash TTS] ({total_k} keys detected) ---")

    custom_voice = os.environ.get("GEMINI_VOICE_ID", "").strip()
    primary_voice = custom_voice if custom_voice else "Kore"
    delivery_style = os.environ.get("GEMINI_DELIVERY_STYLE", "Natural, calm, warm and articulate Bengali pronunciation").strip()

    try:
        import google.genai
    except ImportError:
        print("  ⚠️ 'google-genai' library not installed.")
        return False

    for offset in range(total_k):
        k_idx = (start_idx + offset) % total_k
        api_key = gemini_keys[k_idx]
        masked = mask_key(api_key)
        print(f"  🚀 Attempting Gemini Key #{k_idx+1}/{total_k} ({masked})")

        voices_to_try = [primary_voice]
        if primary_voice != "Kore": voices_to_try.append("Kore")
        if "Puck" not in voices_to_try: voices_to_try.append("Puck")

        for voice_candidate in voices_to_try:
            start_t = time.time()
            try:
                # 🌟 কোনো অবস্থাতেই যাতে ৬ ঘণ্টা আটকে না থাকে (সর্বোচ্চ ৬০ সেকেন্ড)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_call_gemini_api_direct, api_key, speech_text, voice_candidate, delivery_style)
                    interaction = future.result(timeout=60)

                if hasattr(interaction, 'output_audio') and hasattr(interaction.output_audio, 'data'):
                    audio_bytes = base64.b64decode(interaction.output_audio.data)
                    if len(audio_bytes) > 2000:
                        os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
                        with open(output_audio_path, "wb") as f:
                            f.write(audio_bytes)
                        save_key_index("gemini", k_idx, total_k)
                        elapsed = round(time.time() - start_t, 2)
                        print(f"  ✅ [SUCCESS] Generated via Gemini 3.8 Flash TTS! (Voice: '{voice_candidate}' in {elapsed}s)")
                        return True
            except concurrent.futures.TimeoutError:
                print(f"  ⚠️ Gemini Key #{k_idx+1} socket stalled (>60s). Skipping to next key/engine immediately...")
                save_key_index("gemini", (k_idx + 1) % total_k, total_k)
                break
            except Exception as e:
                err_msg = str(e)
                if "voice was not found" in err_msg or "404" in err_msg:
                    continue
                elif "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                    print(f"  ⚠️ Gemini Key #{k_idx+1} quota/rate limit. Switching key...")
                    save_key_index("gemini", (k_idx + 1) % total_k, total_k)
                    break
                else:
                    print(f"  ⚠️ Gemini Key #{k_idx+1} error: {e}")
                    break

    return False

# =========================================================================
# 🌟 ২. ElevenLabs ইঞ্জিন (২য় অগ্রাধিকার)
# =========================================================================
def synthesize_with_elevenlabs(speech_text, output_audio_path):
    eleven_keys = parse_multi_keys(["ELEVENLABS_API_KEYS", "ELEVENLABS_API_KEY"])
    if not eleven_keys:
        return False

    total_k = len(eleven_keys)
    start_idx = get_saved_key_index("elevenlabs", total_k)
    print(f"\n--- [Priority 2: ElevenLabs TTS] ({total_k} keys detected) ---")

    for offset in range(total_k):
        k_idx = (start_idx + offset) % total_k
        api_key = eleven_keys[k_idx]
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb").strip() or "JBFqnCBsd6RMkjVDRZzb"
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        payload = {
            "text": speech_text,
            "model_id": "eleven_v3",
            "language_code": "bn",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}

        try:
            resp = requests.post(tts_url, json=payload, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 1000:
                os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
                with open(output_audio_path, "wb") as f:
                    f.write(resp.content)
                save_key_index("elevenlabs", k_idx, total_k)
                print(f"  ✅ [SUCCESS] Generated via ElevenLabs Key #{k_idx+1}!")
                return True
            elif resp.status_code in [401, 402, 429]:
                print(f"  ⚠️ ElevenLabs Key #{k_idx+1} quota/limit (HTTP {resp.status_code}). Switching key...")
                save_key_index("elevenlabs", (k_idx + 1) % total_k, total_k)
                continue
        except Exception:
            continue
    return False

# =========================================================================
# 🌟 ৩. Microsoft Edge Neural ব্যাকআপ ইঞ্জিন
# =========================================================================
def synthesize_with_edge_fallback(speech_text, output_audio_path):
    print("\n--- [Emergency Backup: Microsoft Edge Neural (bn-BD-PradeepNeural)] ---")
    try:
        import asyncio, edge_tts
        start_t = time.time()
        async def _make():
            c = edge_tts.Communicate(speech_text, "bn-BD-PradeepNeural", rate="+0%", pitch="+0Hz")
            await c.save(output_audio_path)
        asyncio.run(_make())
        if os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000:
            elapsed = round(time.time() - start_t, 2)
            print(f"  ✅ [SUCCESS] Generated via Microsoft Edge Neural in {elapsed}s!")
            return True
    except Exception as e:
        print(f"  ⚠️ Edge fallback notice: {e}")
    return False

# =========================================================================
# 🌟 ৪. লোকাল ব্যাকগ্রাউন্ড মিউজিক (চূড়ান্ত ফলব্যাক)
# =========================================================================
def get_fallback_music_file():
    candidates = []
    for m_dir in ["Music", "music", "MUSIC"]:
        if os.path.exists(m_dir) and os.path.isdir(m_dir):
            for f in os.listdir(m_dir):
                if f.lower().endswith(('.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac')):
                    candidates.append(os.path.join(m_dir, f))
    if candidates: return random.choice(list(set(candidates)))
    return None

# =========================================================================
# 🌟 মাস্টার অডিও পাইপলাইন (Orchestrator)
# =========================================================================
def generate_voiceover_audio_pipeline(text, output_audio_path, memory=None):
    speech_text = clean_script_for_speech(text)
    clean_chars = len(speech_text)
    words = len(speech_text.split())

    print("\n" + "="*65)
    print("🎙️ [AUDIO ENGINE] Multi-Tier Voice Synthesis Active")
    print(f"📊 [Text Stats] Chars: {clean_chars} | Words: {words}")
    print(f"📝 [Preview]: \"{speech_text[:120]}...\"")
    print("="*65)

    if synthesize_with_gemini(speech_text, output_audio_path):
        return True

    if synthesize_with_elevenlabs(speech_text, output_audio_path):
        return True

    if synthesize_with_edge_fallback(speech_text, output_audio_path):
        return True

    fallback_music = get_fallback_music_file()
    if fallback_music and os.path.exists(fallback_music):
        os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
        shutil.copyfile(fallback_music, output_audio_path)
        print(f"  ⚠️ [Music Fallback] Used '{fallback_music}'")
        return True

    print("\n❌ [CRITICAL] All audio engines failed.")
    return False
