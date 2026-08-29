# -*- coding: utf-8 -*-
import os
import re
import time
import requests

FREE_PERMITTED_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George (News Anchor)

def mask_key(k):
    if not k or len(k) <= 8: return "****"
    return k[:4] + "..." + k[-4:]

def clean_script_for_speech(raw_text):
    if not raw_text: return ""
    text = re.sub(r'[\*\_\|\#\~]', '', str(raw_text))
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_all_elevenlabs_keys():
    raw_keys = os.environ.get("ELEVENLABS_API_KEYS", os.environ.get("ELEVENLABS_API_KEY", "")).strip()
    if not raw_keys: return []
    return [k.strip() for k in re.split(r'[\r\n,;]+', raw_keys) if k.strip()]

def get_best_free_voice(api_key):
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            voices = resp.json().get("voices", [])
            for v in voices:
                if v.get("category") == "generated":
                    return v.get("voice_id"), f"'{v.get('name')}' (Custom)"
            for v in voices:
                if v.get("category") == "premade" and "george" in v.get("name", "").lower():
                    return v.get("voice_id"), f"'{v.get('name')}' (Official)"
            for v in voices:
                if v.get("category") == "premade" and "adam" in v.get("name", "").lower():
                    return v.get("voice_id"), f"'{v.get('name')}' (Official)"
            for v in voices:
                if v.get("category") == "premade":
                    return v.get("voice_id"), f"'{v.get('name')}' (Premade)"
    except Exception:
        pass
    return FREE_PERMITTED_VOICE_ID, "'George' (Default)"

def generate_voiceover_audio_pipeline(text, output_audio_path):
    print("\n" + "="*60)
    print("🎙️ [AUDIO ENGINE] ElevenLabs Eleven v3 Bengali Voiceover Synthesis")
    print("="*60)

    speech_text = clean_script_for_speech(text)
    words = len(speech_text.split())
    print(f"📊 [Text Analysis] Total Characters: {len(speech_text)} | Words: {words}")
    print(f"📝 [Script Preview]: \"{speech_text[:120]}...\"\n")

    eleven_keys = get_all_elevenlabs_keys()
    if not eleven_keys:
        print("❌ [ERROR] No ElevenLabs API keys found in secrets!")
        return False

    for idx, api_key in enumerate(eleven_keys, start=1):
        voice_id, voice_name = get_best_free_voice(api_key)
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        print(f"  • Attempting Key #{idx}/{len(eleven_keys)}: {mask_key(api_key)}")
        print(f"  • Selected Voice: {voice_name} [ID: {voice_id}]")

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
                print(f"  ✅ [SUCCESS] Generated Voiceover ({size_mb} MB) in {elapsed}s!")
                print(f"  📁 Saved Path: {output_audio_path}")
                print("="*60 + "\n")
                return True
            else:
                print(f"  ⚠️ Key #{idx} returned HTTP {resp.status_code}: {resp.text[:180]}")
                continue
        except Exception as e:
            print(f"  ⚠️ Key #{idx} network error: {e}")
            continue

    print("❌ [FAILED] All ElevenLabs keys exhausted.")
    return False
