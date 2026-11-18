# -*- coding: utf-8 -*-
import os
import re
import time
import shutil
import subprocess
from pathlib import Path

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "300"

_NINADA_INSTANCE = None

PHONE_DIGIT_WORDS = {
    '0': "জিরো", '1': "ওয়ান", '2': "টু", '3': "থ্রি", '4': "ফোর",
    '5': "ফাইভ", '6': "সিক্স", '7': "সেভেন", '8': "এইট", '9': "নাইন"
}

BN_ORDINALS = {
    "১ম": "প্রথম", "২য়": "দ্বিতীয়", "২য়": "দ্বিতীয়",
    "৩য়": "তৃতীয়", "৩য়": "তৃতীয়", "৪র্থ": "চতুর্থ",
    "৫ম": "পঞ্চম", "৬ষ্ঠ": "ষষ্ঠ", "৭ম": "সপ্তম",
    "৮ম": "অষ্টম", "৯ম": "নবম", "১০ম": "দশম"
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
    "job": "জব", "bank": "ব্যাংক", "diploma": "ডিপ্লোমা",
    "sms": "এসএমএস", "cv": "সিভি", "nid": "এনআইডি"
}


def int_to_bangla_words(n):
    if n in NUM_WORDS_1_TO_99:
        return NUM_WORDS_1_TO_99[n]
    parts = []
    if n >= 10000000:
        parts.append(int_to_bangla_words(n // 10000000) + " কোটি")
        n %= 10000000
    if n >= 100000:
        parts.append(int_to_bangla_words(n // 100000) + " লক্ষ")
        n %= 100000
    if n >= 1000:
        parts.append(int_to_bangla_words(n // 1000) + " হাজার")
        n %= 1000
    if n >= 100:
        h = n // 100
        n %= 100
        parts.append("একশত" if h == 1 else (int_to_bangla_words(h) + " শত"))
    if n > 0:
        parts.append(NUM_WORDS_1_TO_99.get(n, str(n)))
    return " ".join(parts)


def convert_all_numbers_to_bangla_words(text):
    if not text:
        return ""
    text = str(text)
    bn_to_en = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

    # সংখ্যার ভেতরের কমা সরানো (যেমন: ৮,২৫০ -> ৮২৫০)
    text = re.sub(r'(?<=[0-9০-৯]),(?=[0-9০-৯])', '', text)

    def phone_replacer(match):
        raw_num = match.group(0)
        digits = [d for d in raw_num.translate(bn_to_en) if d.isdigit()]
        if "".join(digits).startswith("8801"):
            digits = digits[2:]
        return " ".join([PHONE_DIGIT_WORDS.get(d, d) for d in digits])

    text = re.sub(r'(?:\+?88)?[\s\-]?(?:01|০১)[\d০-৯]{3,4}[-\s]?[\d০-৯]{5,6}', phone_replacer, text)

    # টাকা, শতাংশ, পরিসর (১৮-৩২), ক্রমবাচক ও দশমিক সংখ্যা রূপান্তর
    text = re.sub(r'([0-9০-৯]+)\s*(?:/=|/-|৳)(?:\s*টাকা)?', r'\1 টাকা', text)
    text = re.sub(r'৳\s*([0-9০-৯]+)(?:\s*টাকা)?', r'\1 টাকা', text)
    text = re.sub(r'([0-9০-৯]+(?:\.[0-9০-৯]+)?)\s*%', r'\1 শতাংশ', text)
    text = re.sub(r'([0-9০-৯]+)\s*[-–—]\s*([0-9০-৯]+)', r'\1 থেকে \2', text)

    ord_pat = "|".join(re.escape(k) for k in BN_ORDINALS)
    text = re.sub(
        rf'(?<![\u0980-\u09FF0-9০-৯])({ord_pat})(?![\u0980-\u09FF0-9০-৯])',
        lambda m: BN_ORDINALS.get(m.group(1), m.group(1)),
        text,
    )

    def dec_replacer(match):
        try:
            left = int_to_bangla_words(int(match.group(1).translate(bn_to_en)))
            right = " ".join(NUM_WORDS_1_TO_99.get(int(ch.translate(bn_to_en)), ch) for ch in match.group(2))
            return f"{left} দশমিক {right}"
        except Exception:
            return match.group(0)

    text = re.sub(r'([0-9০-৯]+)\.([0-9০-৯]+)', dec_replacer, text)

    def num_replacer(match):
        num_str = match.group(0)
        if len(num_str) > 10:
            return " ".join(NUM_WORDS_1_TO_99.get(int(ch.translate(bn_to_en)), ch) for ch in num_str)
        try:
            return int_to_bangla_words(int(num_str.translate(bn_to_en)))
        except Exception:
            return num_str

    text = re.sub(r'[\d০-৯]+', num_replacer, text)
    return text


def clean_script_for_speech(raw_text):
    if not raw_text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL | re.IGNORECASE)
    for eng, bn in COMMON_ENG_TO_BN.items():
        text = re.sub(rf'\b{eng}\b', bn, text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = convert_all_numbers_to_bangla_words(text)
    text = re.sub(r'[\*\_\|\#\~\[\]\{\}\<\>\@\$\^\&\+\=\_\\\/\(\)]', ' ', text)
    # বাংলা TTS মডেলের (IndicF5 ও Ninada) জন্য স্বাভাবিক দাঁড়ি ও কমা অক্ষুণ্ণ রাখা
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


def _finalize_kaggle_audio(raw_wav_path: Path, out_audio_path: Path):
    """Kaggle IndicF5 থেকে পাওয়া WAV-কে broadcast loudness সহ MP3/WAV ফরম্যাটে সেভ করে"""
    out_audio_path.parent.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        shutil.copy2(raw_wav_path, out_audio_path)
        return

    af_chain = "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11"
    is_mp3 = str(out_audio_path).lower().endswith(".mp3")

    cmd = ["ffmpeg", "-y", "-i", str(raw_wav_path), "-af", af_chain]
    if is_mp3:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1"])
    else:
        cmd.extend(["-c:a", "pcm_s16le", "-ar", "24000", "-ac", "1"])
    cmd.append(str(out_audio_path))

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode != 0 or not out_audio_path.exists() or out_audio_path.stat().st_size < 1000:
        if is_mp3:
            fallback_cmd = [
                "ffmpeg", "-y", "-i", str(raw_wav_path),
                "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1",
                str(out_audio_path),
            ]
            subprocess.run(fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            shutil.copy2(raw_wav_path, out_audio_path)


def synthesize_with_ninada(speech_text, output_audio_path):
    """ব্যাকআপ (Priority #2): Ninada Bangla Male TTS"""
    out_path = Path(output_audio_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_wav = out_path.with_suffix(".ninada_raw.wav")

    for attempt in range(3):
        try:
            import numpy as np
            import soundfile as sf

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
                print(f"  ✅ [Ninada Backup SUCCESS] Mastered audio ready ({round(out_path.stat().st_size / 1024, 1)} KB)")
                return True
        except Exception as e:
            print(f"  ⚠️ [Ninada Attempt #{attempt+1}] {e}")
            if tmp_wav.exists():
                try:
                    tmp_wav.unlink()
                except Exception:
                    pass
            time.sleep(1.5)

    print("  ❌ [Ninada Error] Audio synthesis failed after retries.")
    return False


def _is_kaggle_enabled():
    if os.environ.get("DISABLE_KAGGLE_TTS", "").strip().lower() in {"true", "1", "yes", "on"}:
        return False
    try:
        from kaggle_tts import has_kaggle_credentials
        return has_kaggle_credentials()
    except Exception:
        return False


def generate_voiceover_batch_pipeline(batch_items, batch_work_dir="tmp_kaggle_audio", allow_ninada_backup=True):
    """
    ১. প্রাইমারি (Priority #1): Kaggle IndicF5_Bangladeshi (সবগুলো অডিও মাত্র ১টি ব্যাচ রিকোয়েস্টে)
    ২. ব্যাকআপ (Priority #2): Ninada Bangla Male TTS (যদি Kaggle বন্ধ বা ব্যর্থ হয়)
    """
    if not batch_items:
        return {}

    os.makedirs(batch_work_dir, exist_ok=True)
    cleaned_tasks = []
    for idx, item in enumerate(batch_items):
        target_path = str(item["target_path"])
        fname = item.get("filename") or os.path.basename(target_path)
        sp_text = clean_script_for_speech(item["text"])
        if not sp_text:
            continue
        cleaned_tasks.append({
            "filename": fname,
            "text": sp_text,
            "target_path": target_path,
            "idx": idx,
        })

    if not cleaned_tasks:
        return {}

    print("\n" + "=" * 65)
    print("🎙️ [AUDIO ENGINE] Priority #1: Kaggle IndicF5_Bangladeshi | Priority #2 (Backup): Ninada TTS")
    print(f"📦 Total Scripts Queued: {len(cleaned_tasks)}")
    for idx, t in enumerate(cleaned_tasks, 1):
        print(f"  #{idx}: {t['filename']} | {len(t['text'].split())} words | {len(t['text'])} chars")
    print("=" * 65)

    results = {}

    # একই স্ক্রিপ্ট থাকলে Kaggle-এ ডুপ্লিকেট জেনারেট না করে একবারই তৈরি করা
    unique_text_to_key = {}
    kaggle_tasks = []
    task_to_unique_key = {}
    for t in cleaned_tasks:
        sp_text = t["text"]
        if sp_text not in unique_text_to_key:
            u_key = f"kaggle_u{len(unique_text_to_key)}.wav"
            unique_text_to_key[sp_text] = u_key
            kaggle_tasks.append({"filename": u_key, "text": sp_text})
        task_to_unique_key[t["filename"]] = unique_text_to_key[sp_text]

    # ১. প্রাইমারি: Kaggle IndicF5_Bangladeshi
    if _is_kaggle_enabled():
        try:
            from kaggle_tts import generate_voices_batch
            default_voice = os.environ.get("KAGGLE_DEFAULT_VOICE", "male").strip().lower() or "male"
            speech_speed = float(os.environ.get("KAGGLE_SPEECH_SPEED", "0.93") or "0.93")
            nfe_step = int(os.environ.get("KAGGLE_NFE_STEP", "16") or "16")

            generated_map = generate_voices_batch(
                tasks=kaggle_tasks,
                output_dir=batch_work_dir,
                default_voice=default_voice,
                speech_speed=speech_speed,
                nfe_step=nfe_step,
            )

            converted_by_ukey = {}
            for t in cleaned_tasks:
                u_key = task_to_unique_key[t["filename"]]
                src = generated_map.get(u_key)
                dst = Path(t["target_path"]).resolve()
                if u_key in converted_by_ukey and Path(converted_by_ukey[u_key]).exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(converted_by_ukey[u_key], str(dst))
                    results[t["filename"]] = str(dst)
                    print(f"  🎵 Copied '{t['filename']}' -> {dst}")
                elif src and Path(src).exists() and Path(src).stat().st_size > 1000:
                    _finalize_kaggle_audio(Path(src), dst)
                    if dst.exists() and dst.stat().st_size > 1000:
                        converted_by_ukey[u_key] = str(dst)
                        results[t["filename"]] = str(dst)
                        print(f"  🎵 Saved '{t['filename']}' -> {dst}")

            for src in generated_map.values():
                if src and Path(src).exists():
                    try:
                        Path(src).unlink()
                    except Exception:
                        pass

            if len(results) == len(cleaned_tasks):
                return results
        except Exception as e:
            print(f"\n⚠️ [Kaggle TTS Failed] ({e}) — Switching to Priority #2 (Ninada TTS) backup...")
    else:
        print("\nℹ️ [Kaggle TTS Skipped] KAGGLE_API_TOKEN/Credentials unavailable or disabled — Using Priority #2 (Ninada TTS)...")

    # ২. ব্যাকআপ (Priority #2): শুধু যেগুলো Kaggle থেকে আসেনি সেগুলোর জন্য Ninada TTS
    if allow_ninada_backup:
        ninada_cache = {}
        for t in cleaned_tasks:
            if t["filename"] in results:
                continue
            sp_text = t["text"]
            dst = Path(t["target_path"]).resolve()
            if sp_text in ninada_cache and Path(ninada_cache[sp_text]).exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ninada_cache[sp_text], str(dst))
                results[t["filename"]] = str(dst)
                continue
            print(f"  🔄 [Ninada Backup] Synthesizing '{t['filename']}'...")
            if synthesize_with_ninada(sp_text, str(dst)) and dst.exists() and dst.stat().st_size > 1000:
                ninada_cache[sp_text] = str(dst)
                results[t["filename"]] = str(dst)

    return results


def generate_single_audio_task(text, output_path, key_idx=0, skip_kaggle=False):
    speech_text = clean_script_for_speech(text)
    if not speech_text:
        print("  ⚠️ Empty text provided for audio synthesis.")
        return False
    if skip_kaggle:
        return synthesize_with_ninada(speech_text, output_path)

    fname = os.path.basename(output_path)
    work_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), "_tmp_single_audio")
    res = generate_voiceover_batch_pipeline(
        [{"filename": fname, "text": text, "target_path": output_path}],
        batch_work_dir=work_dir,
        allow_ninada_backup=True,
    )
    shutil.rmtree(work_dir, ignore_errors=True)
    return fname in res and os.path.exists(output_path)


def generate_voiceover_audio_pipeline(text, output_audio_path, key_offset=0, memory=None, skip_kaggle=False):
    return generate_single_audio_task(text, output_audio_path, key_idx=key_offset, skip_kaggle=skip_kaggle)


def generate_audios_in_parallel(scripts_list, base_hash, total_needed):
    if not scripts_list or total_needed <= 0:
        return []
    batch_items = []
    for idx in range(total_needed):
        s_text = scripts_list[idx % len(scripts_list)]
        out_file = f"tmp_voice_{base_hash}_{idx+1}.mp3"
        batch_items.append({"filename": out_file, "text": s_text, "target_path": out_file})

    work_dir = f"_tmp_batch_{base_hash}"
    res = generate_voiceover_batch_pipeline(batch_items, batch_work_dir=work_dir, allow_ninada_backup=True)
    shutil.rmtree(work_dir, ignore_errors=True)
    return [it["target_path"] for it in batch_items if it["filename"] in res and os.path.exists(it["target_path"])]
