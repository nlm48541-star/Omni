# -*- coding: utf-8 -*-
import os
import re
import json
import base64
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

# =========================================================================
# 🌟 লিমিট শেষ হওয়া কি-ট্র্যাকার ম্যানেজার (JSON File Persistence)
# =========================================================================
def get_exhausted_keys(platform):
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return set(data.get(f"{platform}_exhausted_keys", []))
        except Exception: pass
    return set()

def record_key_exhausted(platform, api_key):
    data = {}
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception: data = {}
    key_list = set(data.get(f"{platform}_exhausted_keys", []))
    key_list.add(api_key)
    data[f"{platform}_exhausted_keys"] = list(key_list)
    try:
        with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception: pass

def clear_exhausted_keys(platform):
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data[f"{platform}_exhausted_keys"] = []
            with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception: pass

# =========================================================================
# 🌟 ১. Gemini 3.8 Flash TTS ইঞ্জিন (স্বাধীন ট্রাই ও ফল্ট-প্রুফ)
# =========================================================================
def synthesize_with_gemini_single(speech_text, output_audio_path, preferred_key_idx=0):
    all_keys = parse_multi_keys(["GEMINI_API_KEYS", "GEMINI_API_KEY"])
    if not all_keys: return False

    exhausted_set = get_exhausted_keys("gemini")
    available_keys = [k for k in all_keys if k not in exhausted_set]

    # সব কি শেষ হয়ে গেলে আবার ১ নম্বর কি থেকে নতুন করে ট্রাই করবে
    if not available_keys:
        print("  🔄 [Gemini] All Gemini keys were exhausted. Resetting cycle to Key #1...")
        clear_exhausted_keys("gemini")
        available_keys = all_keys

    total_avail = len(available_keys)
    start_pos = preferred_key_idx % total_avail

    custom_voice = os.environ.get("GEMINI_VOICE_ID", "").strip()
    primary_voice = custom_voice if custom_voice else "Kore"
    delivery_style = os.environ.get("GEMINI_DELIVERY_STYLE", "Natural, calm, warm and articulate Bengali pronunciation").strip()

    try:
        from google import genai
        from google.genai import types
        http_config = types.HttpOptions(timeout=60_000)
    except Exception:
        http_config = None

    for offset in range(total_avail):
        k_idx = (start_pos + offset) % total_avail
        api_key = available_keys[k_idx]
        masked = mask_key(api_key)

        voices_to_try = [primary_voice]
        if primary_voice != "Kore": voices_to_try.append("Kore")
        if "Puck" not in voices_to_try: voices_to_try.append("Puck")

        for voice_candidate in voices_to_try:
            try:
                if http_config:
                    client = genai.Client(api_key=api_key, http_options=http_config)
                else:
                    client = genai.Client(api_key=api_key)

                interaction = client.interactions.create(
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
                    generation_config={"speech_config": [{"voice": voice_candidate}]}
                )

                if hasattr(interaction, 'output_audio') and hasattr(interaction.output_audio, 'data'):
                    audio_bytes = base64.b64decode(interaction.output_audio.data)
                    if len(audio_bytes) > 2000:
                        os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
                        with open(output_audio_path, "wb") as f:
                            f.write(audio_bytes)
                        print(f"  ✅ [Gemini TTS SUCCESS] Generated using Key ({masked}) with Voice '{voice_candidate}'")
                        return True
            except Exception as e:
                err_msg = str(e).lower()
                if "voice was not found" in err_msg or "404" in err_msg:
                    continue
                else:
                    # লিমিট বা এরর আসলে কি-টিকে ফাইলে সেভ রাখা
                    print(f"  ⚠️ [Gemini Key Notice] Key ({masked}) exhausted/error: {str(e)[:80]}. Saving to tracker...")
                    record_key_exhausted("gemini", api_key)
                    break

    return False

# =========================================================================
# 🌟 ২. ElevenLabs ইঞ্জিন (২য় অগ্রাধিকার)
# =========================================================================
def synthesize_with_elevenlabs_single(speech_text, output_audio_path, preferred_key_idx=0):
    all_keys = parse_multi_keys(["ELEVENLABS_API_KEYS", "ELEVENLABS_API_KEY"])
    if not all_keys: return False

    exhausted_set = get_exhausted_keys("elevenlabs")
    available_keys = [k for k in all_keys if k not in exhausted_set]

    if not available_keys:
        clear_exhausted_keys("elevenlabs")
        available_keys = all_keys

    total_avail = len(available_keys)
    start_pos = preferred_key_idx % total_avail

    for offset in range(total_avail):
        k_idx = (start_pos + offset) % total_avail
        api_key = available_keys[k_idx]
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
                print(f"  ✅ [ElevenLabs SUCCESS] Generated audio using Key ({mask_key(api_key)})")
                return True
            elif resp.status_code in [401, 402, 429]:
                record_key_exhausted("elevenlabs", api_key)
                continue
        except Exception:
            continue
    return False

# =========================================================================
# 🌟 ৩. Microsoft Edge Neural ব্যাকআপ ইঞ্জিন (৩য় অগ্রাধিকার)
# =========================================================================
def synthesize_with_edge_single(speech_text, output_audio_path):
    print("  🎙️ [Priority 3: Microsoft Edge Neural (bn-BD-PradeepNeural)]")
    try:
        import asyncio, edge_tts
        async def _make():
            c = edge_tts.Communicate(speech_text, "bn-BD-PradeepNeural", rate="+0%", pitch="+0Hz")
            await c.save(output_audio_path)
        asyncio.run(_make())
        if os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000:
            print("  ✅ [Edge TTS SUCCESS] Generated audio using Microsoft Edge!")
            return True
    except Exception as e:
        print(f"  ⚠️ Edge TTS notice: {e}")
    return False

# =========================================================================
# 🌟 ৪. লোকাল ব্যাকগ্রাউন্ড মিউজিক ফলব্যাক
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
# 🌟 একক অডিও জেনারেটর পাইপলাইন
# =========================================================================
def generate_single_audio_task(text, output_path, key_idx=0):
    speech_text = clean_script_for_speech(text)

    # ১. Gemini TTS
    if synthesize_with_gemini_single(speech_text, output_path, preferred_key_idx=key_idx):
        return True

    # ২. ElevenLabs
    if synthesize_with_elevenlabs_single(speech_text, output_path, preferred_key_idx=key_idx):
        return True

    # ৩. Edge TTS
    if synthesize_with_edge_single(speech_text, output_path):
        return True

    # ৪. মিউজিক ফলব্যাক
    fallback_music = get_fallback_music_file()
    if fallback_music and os.path.exists(fallback_music):
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        shutil.copyfile(fallback_music, output_path)
        print(f"  ⚠️ [Music Fallback] Used '{fallback_music}'")
        return True

    return False

# =========================================================================
# 🌟 সম্পূর্ণ প্যারালাল অডিও জেনারেশন ইঞ্জিন (সবগুলো অডিও একসাথে জেনারেট হবে)
# =========================================================================
def generate_audios_in_parallel(scripts_list, base_hash, total_needed):
    """
    প্রয়োজনীয় অডিওগুলো ক্রমানুসারে আলাদা আলাদা কি নিয়ে একসাথে প্যারালালভাবে জেনারেট করবে।
    """
    print("\n" + "="*65)
    print(f"🎙️ [PARALLEL AUDIO ENGINE] Synthesizing {total_needed} Audios Simultaneously...")
    print("="*65)

    audio_paths = [f"tmp_voice_{base_hash}_{i+1}.mp3" for i in range(total_needed)]
    tasks = []

    # প্যারালাল থ্রেড এক্সিকিউটর (একসাথে সর্বোচ্চ ৮টি অডিও জেনারেট হবে)
    workers = min(total_needed, 8)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for idx in range(total_needed):
            s_text = scripts_list[idx % len(scripts_list)]
            out_file = audio_paths[idx]
            # প্রতিটি অডিও টাস্ক তার নিজ ইনডেক্স অনুযায়ী আলাদা কি প্রিফার করবে
            tasks.append(executor.submit(generate_single_audio_task, s_text, out_file, idx))

        results = [t.result() for t in tasks]

    successful_audios = [p for p, ok in zip(audio_paths, results) if ok and os.path.exists(p)]
    print(f"✅ [Parallel Audio Complete] {len(successful_audios)} of {total_needed} audios successfully synthesized!\n")
    return successful_audios

def generate_voiceover_audio_pipeline(text, output_audio_path, key_offset=0, memory=None):
    return generate_single_audio_task(text, output_audio_path, key_idx=key_offset)
