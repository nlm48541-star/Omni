# -*- coding: utf-8 -*-
import os
import re
import time
import requests

# 🌟 ElevenLabs-এর প্রিমিয়াম ও ন্যাচারাল ফ্রি-পারমিটেড ভয়েস লিস্ট
PERMITTED_FREE_VOICES = [
    {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George (News Anchor)"},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam (Deep Professional)"},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian (Narrative Anchor)"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel (Authoritative News)"},
    {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam (Crisp Dynamic)"},
    {"id": "iP95p4xoKVk53GoZ742B", "name": "Chris (Casual Professional)"},
    {"id": "pqHfZKP75CvOlQylNhV4", "name": "Bill (Warm Trustworthy)"}
]

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

def get_voice_for_index(voice_index, api_key):
    """
    প্রতিটি পেজের জন্য ভিন্ন ভিন্ন ভয়েস নির্ধারণ করে (George ➔ Adam ➔ Brian ➔ Daniel...)
    """
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            custom_voices = [v for v in resp.json().get("voices", []) if v.get("category") == "generated"]
            if custom_voices:
                selected = custom_voices[voice_index % len(custom_voices)]
                return selected.get("voice_id"), f"'{selected.get('name')}' (Custom Generated)"
    except Exception: pass

    # প্রি-মেড পারমিটেড ভয়েস লিস্ট থেকে রোটেট করবে
    v_info = PERMITTED_FREE_VOICES[voice_index % len(PERMITTED_FREE_VOICES)]
    return v_info["id"], f"'{v_info['name']}' (Official Premade)"

def generate_voiceover_audio_pipeline(text, output_audio_path, voice_index=0):
    print("\n" + "="*65)
    print(f"🎙️ [AUDIO ENGINE] Generating Voiceover (Page/Voice #{voice_index + 1})")
    print("="*65)

    speech_text = clean_script_for_speech(text)
    words = len(speech_text.split())
    print(f"📊 [Text Analysis] Total Characters: {len(speech_text)} | Words: {words}")
    print(f"📝 [Script Preview]: \"{speech_text[:120]}...\"\n")

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
                print(f"  ✅ [SUCCESS] Voiceover Generated with {voice_name} ({size_mb} MB) in {elapsed}s!")
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
