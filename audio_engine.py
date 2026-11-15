# -*- coding: utf-8 -*-
import os
import re
import time
import asyncio
import edge_tts
import concurrent.futures

# Microsoft Edge-এর সেরা ৪টি বাংলা নিউরাল ভয়েস (একটি ফেইল করলে স্বয়ংক্রিয়ভাবে পরেরটি নিবে)
EDGE_VOICES = [
    "bn-BD-PradeepNeural",    # বাংলাদেশ পুরুষ (মূল ভয়েস)
    "bn-BD-NabanitaNeural",   # বাংলাদেশ নারী
    "bn-IN-BashkarNeural",    # বাংলা পুরুষ
    "bn-IN-TanishaaNeural"    # বাংলা নারী
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

def clean_script_for_speech(raw_text):
    if not raw_text: return ""
    text = convert_all_numbers_to_bangla_words(raw_text)
    # সমস্ত ব্র্যাকেট ও অপ্রয়োজনীয় চিহ্ন মুছে ফেলা যাতে Edge-TTS কোনো ত্রুটি ছাড়া পড়তে পারে
    text = re.sub(r'[\*\_\|\#\~\[\]\{\}\<\>\@\$\^\&\+\=\_\\\/]', ' ', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _run_edge_tts_coroutine(speech_text, voice_name, output_audio_path):
    async def _make():
        communicate = edge_tts.Communicate(speech_text, voice_name, rate="+0%", pitch="+0Hz")
        await communicate.save(output_audio_path)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_make())
    finally:
        loop.close()

def synthesize_with_edge_tts(speech_text, output_audio_path):
    """
    Microsoft Edge Neural TTS:
    ৪টি বাংলা ভয়েস দিয়ে একের পর এক চেষ্টা করবে যাতে ১০০% ক্ষেত্রে সফলভাবে অডিও ফাইল তৈরি হয়।
    """
    os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)

    for voice in EDGE_VOICES:
        for attempt in range(2):
            try:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                fut = executor.submit(_run_edge_tts_coroutine, speech_text, voice, output_audio_path)
                fut.result(timeout=60)
                executor.shutdown(wait=False)

                if os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000:
                    print(f"  ✅ [Edge TTS SUCCESS] Generated using voice '{voice}' ({round(os.path.getsize(output_audio_path)/1024, 1)} KB)")
                    return True
            except Exception as e:
                try: executor.shutdown(wait=False)
                except Exception: pass
                time.sleep(1)

    print("  ❌ [Edge TTS Error] All voices failed to respond.")
    return False

def generate_single_audio_task(text, output_path, key_idx=0):
    speech_text = clean_script_for_speech(text)
    if not speech_text:
        print("  ⚠️ Empty text provided for audio synthesis.")
        return False
    return synthesize_with_edge_tts(speech_text, output_path)

def generate_voiceover_audio_pipeline(text, output_audio_path, key_offset=0, memory=None):
    return generate_single_audio_task(text, output_audio_path, key_idx=key_offset)

def generate_audios_in_parallel(scripts_list, base_hash, total_needed):
    audio_paths = []
    for idx in range(total_needed):
        s_text = scripts_list[idx % len(scripts_list)]
        out_file = f"tmp_voice_{base_hash}_{idx+1}.mp3"
        if generate_single_audio_task(s_text, out_file, idx):
            audio_paths.append(out_file)
    return audio_paths
