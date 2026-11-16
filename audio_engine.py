# -*- coding: utf-8 -*-
import os
import re
import time
import shutil
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "300"

_NINADA_INSTANCE = None

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

COMMON_ENG_TO_BN = {
    "whatsapp": "হোয়াটসঅ্যাপ", "ssc": "এসএসসি", "hsc": "এইচএসসি",
    "bsc": "বিএসসি", "msc": "এমএসসি", "bba": "বিবিএ", "mba": "এমবিএ",
    "cgpa": "সিজিপিএ", "gpa": "জিপিএ", "ngo": "এনজিও", "pdf": "পিডিএফ",
    "online": "অনলাইন", "email": "ইমেইল", "circular": "সার্কুলার",
    "job": "জব", "bank": "ব্যাংক", "diploma": "ডিপ্লোমা"
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
    text = str(raw_text)
    for eng, bn in COMMON_ENG_TO_BN.items():
        text = re.sub(rf'\b{eng}\b', bn, text, flags=re.IGNORECASE)
    text = convert_all_numbers_to_bangla_words(text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\*\_\|\#\~\[\]\{\}\<\>\@\$\^\&\+\=\_\\\/\(\)]', ' ', text)
    # Ninada বাংলা মডেলের জন্য স্বাভাবিক দাঁড়ি ও কমা অক্ষুণ্ণ রাখা
    text = re.sub(r'[^\u0980-\u09FF\s,।?!\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _get_ninada_tts():
    global _NINADA_INSTANCE
    if _NINADA_INSTANCE is None:
        from ninada import Ninada
        print("  [🎙️ Ninada TTS] Initializing Ninada v5 (lang='bn', voice='male')...")
        _NINADA_INSTANCE = Ninada(lang="bn")
    return _NINADA_INSTANCE

def _apply_ninada_tempo_and_mastering(raw_wav_path: Path, out_audio_path: Path):
    if not shutil.which("ffmpeg"):
        shutil.copy2(raw_wav_path, out_audio_path)
        return

    af_chain = (
        "atempo=0.92,"
        "highpass=f=80,"
        "equalizer=f=250:t=q:w=1.2:g=2.5,"
        "equalizer=f=4500:t=q:w=1.5:g=-3.5,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=100,"
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )
    cmd = ["ffmpeg", "-y", "-i", str(raw_wav_path), "-af", af_chain]
    if str(out_audio_path).lower().endswith(".mp3"):
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1"])
    else:
        cmd.extend(["-c:a", "pcm_s16le", "-ar", "24000", "-ac", "1"])
    cmd.append(str(out_audio_path))

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode != 0 or not out_audio_path.exists() or out_audio_path.stat().st_size < 1000:
        shutil.copy2(raw_wav_path, out_audio_path)

def synthesize_with_ninada(speech_text, output_audio_path):
    out_path = Path(output_audio_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_wav = out_path.with_suffix(".ninada_raw.wav")

    for attempt in range(3):
        try:
            tts = _get_ninada_tts()
            wav_bytes = None
            try:
                wav_bytes = tts.speak(speech_text, lang="bn", voice="male")
            except Exception:
                wav_bytes = None

            if wav_bytes and len(wav_bytes) > 2000:
                with open(tmp_wav, "wb") as f:
                    f.write(wav_bytes)
            else:
                # বড় স্ক্রিপ্টের ক্ষেত্রে বাক্য ভেঙে সেফটি সিন্থেসিস
                sentences = [s.strip() for s in re.split(r'(?<=[।!?])\s+', speech_text) if len(s.strip()) > 3]
                if not sentences:
                    sentences = [speech_text]

                chunks_pcm = []
                sr = 24000
                pause = np.zeros(int(sr * 0.25), dtype=np.float32)

                for idx, s in enumerate(sentences):
                    b = tts.speak(s, lang="bn", voice="male")
                    if b and len(b) > 1000:
                        c_wav = out_path.with_suffix(f".chunk_{idx}.wav")
                        with open(c_wav, "wb") as cf:
                            cf.write(b)
                        data, c_sr = sf.read(str(c_wav), dtype="float32")
                        sr = c_sr
                        if c_wav.exists():
                            c_wav.unlink()
                        chunks_pcm.append(np.asarray(data, dtype=np.float32).reshape(-1))
                        if idx < len(sentences) - 1:
                            chunks_pcm.append(pause)

                if not chunks_pcm:
                    raise RuntimeError("Ninada returned empty audio chunks")
                merged = np.concatenate(chunks_pcm) if len(chunks_pcm) > 1 else chunks_pcm[0]
                sf.write(str(tmp_wav), merged, sr, subtype="PCM_16")

            _apply_ninada_tempo_and_mastering(tmp_wav, out_path)
            if tmp_wav.exists():
                tmp_wav.unlink()

            if out_path.exists() and out_path.stat().st_size > 1000:
                print(f"  ✅ [Ninada Male SUCCESS] Mastered audio ready ({round(out_path.stat().st_size / 1024, 1)} KB)")
                return True
        except Exception as e:
            print(f"  ⚠️ [Ninada Attempt #{attempt+1}] {e}")
            if tmp_wav.exists():
                try: tmp_wav.unlink()
                except Exception: pass
            time.sleep(1.5)

    print("  ❌ [Ninada Error] Audio synthesis failed after retries.")
    return False

def generate_single_audio_task(text, output_path, key_idx=0):
    speech_text = clean_script_for_speech(text)
    if not speech_text:
        print("  ⚠️ Empty text provided for audio synthesis.")
        return False
    return synthesize_with_ninada(speech_text, output_path)

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
