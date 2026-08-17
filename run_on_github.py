import os
import re
import json
import base64
import random
import asyncio
import requests
import feedparser
import yt_dlp
import shutil
import subprocess
import math
from time import mktime
from urllib.parse import urljoin
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from PIL import Image

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

CONFIG_FILE = "automation_config.json"
MEMORY_FILE = "bot_memory.json"
COOKIES_FILE = "cookies.txt"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f: return json.load(f)
    return default_val

def save_json(filepath, data):
    with open(filepath, 'w') as f: json.dump(data, f, indent=4)

def strip_html(text):
    if not text: return ""
    return re.sub(re.compile('<.*?>'), '', text)

def clean_text(text, keep_hashtags=False):
    if not text: return ""
    text = re.sub(r'@\w+', '', text)
    if not keep_hashtags: text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n+', '\n\n', text).strip()

def clean_telegram_id(tg_id_str):
    if not tg_id_str: return ""
    clean_id = tg_id_str.split('/')[-1].replace('@', '').strip()
    return clean_id

def get_credential(config, key, env_var):
    val = os.environ.get(env_var, "").strip()
    if not val:
        val = config.get("credentials", {}).get(key, "").strip()
    return val

# --- MULTI-AUDIO RANDOM SELECTOR ---
def get_all_audio_files():
    audio_files = []
    music_dir = "Music"
    if os.path.exists(music_dir) and os.path.isdir(music_dir):
        for f in os.listdir(music_dir):
            if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                audio_files.append(os.path.join(music_dir, f))
    for f in os.listdir('.'):
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
            audio_files.append(f)
    return list(set(audio_files))

def get_random_audio_file():
    all_audios = get_all_audio_files()
    if all_audios:
        chosen = random.choice(all_audios)
        print(f"  [+] Selected random background audio: '{chosen}'")
        return chosen
    return None

# --- REELS GENERATION HELPERS ---
def sanitize_filename(name):
    if not name: return "reels_video"
    cleaned = re.sub(r'[\/:*?"<>|\x00-\x1f]', '', name)
    return cleaned.strip()[:100]

def get_audio_duration(audio_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  [!] Error reading audio duration with ffprobe: {e}")
        return 30.0

def find_front_overlay_file():
    if os.path.exists("Front.png"):
        return "Front.png"
    for filename in os.listdir("."):
        if filename.lower() in ["front.png", "front.jpg", "front.jpeg", "front.webp"]:
            return filename
    return None

def create_reels_video(image_paths, audio_path, output_path, fps=24):
    print(f"  [~] Generating Reel Video: '{output_path}'")
    if not image_paths: return False

    valid_images = [p for p in image_paths if os.path.exists(p)]
    if not valid_images: return False

    audio_duration = get_audio_duration(audio_path)
    total_frames = int(audio_duration * fps)
    num_images = len(valid_images)
    frames_per_image = total_frames // num_images
    remainder = total_frames % num_images

    temp_dir = f"_tmp_reels_frames_{random.randint(100000, 999999)}"
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try: resampling = Image.Resampling.LANCZOS
    except AttributeError: resampling = Image.ANTIALIAS

    # Load floating Front.png overlay dynamically
    front_overlay = None
    overlay_filename = find_front_overlay_file()
    if overlay_filename:
        try:
            overlay_raw = Image.open(overlay_filename).convert("RGBA")
            ow, oh = overlay_raw.size
            target_w = 160  # Optimal watermark width for 720p vertical video
            if ow > target_w:
                target_h = max(1, int(oh * (target_w / ow)))
                front_overlay = overlay_raw.resize((target_w, target_h), resampling)
            else:
                front_overlay = overlay_raw
            print(f"  [+] Floating Front overlay loaded successfully from '{overlay_filename}'!")
        except Exception as e:
            print(f"  [!] Failed to load Front overlay image: {e}")
            front_overlay = None

    frame_count = 0
    
    for idx, img_path in enumerate(valid_images):
        try:
            img = Image.open(img_path).convert('RGB')
            w, h = img.size
            if h == 0: continue
            ratio = w / h
            num_f = frames_per_image + (1 if idx < remainder else 0)

            if ratio < (9 / 16):
                new_w = 720
                new_h = int(720 / ratio)
                resized = img.resize((new_w, new_h), resampling)
                max_y = new_h - 1280
                for f in range(num_f):
                    p = f / (num_f - 1) if num_f > 1 else 0.0
                    y = int(p * max_y)
                    crop_box = (0, y, 720, y + 1280)
                    frame = resized.crop(crop_box)

                    # Float Front.png across corners smoothly
                    if front_overlay:
                        ow, oh = front_overlay.size
                        max_x = max(0, 720 - ow)
                        max_y_f = max(0, 1280 - oh)
                        progress = frame_count / max(1, total_frames)
                        ox = int(((math.sin(progress * math.pi * 6) + 1) / 2) * max_x)
                        oy = int(((math.cos(progress * math.pi * 4) + 1) / 2) * max_y_f)
                        
                        frame_rgba = frame.convert("RGBA")
                        frame_rgba.paste(front_overlay, (ox, oy), front_overlay)
                        frame = frame_rgba.convert("RGB")

                    frame.save(os.path.join(temp_dir, f"frame_{frame_count:05d}.jpg"), "JPEG", quality=85)
                    frame_count += 1
            else:
                new_w = 720
                new_h = int(720 / ratio)
                resized = img.resize((new_w, new_h), resampling)
                y_offset = (1280 - new_h) // 2
                
                for f in range(num_f):
                    bg_frame = Image.new("RGB", (720, 1280), (0, 0, 0))
                    bg_frame.paste(resized, (0, y_offset))

                    # Float Front.png across corners smoothly
                    if front_overlay:
                        ow, oh = front_overlay.size
                        max_x = max(0, 720 - ow)
                        max_y_f = max(0, 1280 - oh)
                        progress = frame_count / max(1, total_frames)
                        ox = int(((math.sin(progress * math.pi * 6) + 1) / 2) * max_x)
                        oy = int(((math.cos(progress * math.pi * 4) + 1) / 2) * max_y_f)
                        
                        bg_rgba = bg_frame.convert("RGBA")
                        bg_rgba.paste(front_overlay, (ox, oy), front_overlay)
                        bg_frame = bg_rgba.convert("RGB")

                    bg_frame.save(os.path.join(temp_dir, f"frame_{frame_count:05d}.jpg"), "JPEG", quality=85)
                    frame_count += 1
        except Exception: pass

    if frame_count == 0:
        shutil.rmtree(temp_dir)
        return False

    if os.path.exists(output_path): os.remove(output_path)

    ffmpeg_cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(temp_dir, "frame_%05d.jpg"), "-i", audio_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", output_path]

    try:
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except subprocess.CalledProcessError: success = False

    shutil.rmtree(temp_dir, ignore_errors=True)
    return success

# --- FACEBOOK REELS & VIDEO UPLOADER ---
def post_reel_to_facebook(page_id, page_token, video_path, title, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        payload = {'upload_phase': 'start', 'access_token': page_token}
        res = requests.post(url, data=payload, timeout=25)
        if res.status_code != 200: return False
        
        data = res.json()
        video_id, upload_url = data.get("video_id"), data.get("upload_url")
        if not video_id or not upload_url: return False
            
        file_size = os.path.getsize(video_path)
        headers = {"Authorization": f"OAuth {page_token}", "offset": "0", "file_size": str(file_size), "Content-Type": "application/octet-stream"}
        with open(video_path, "rb") as f:
            up_res = requests.post(upload_url, headers=headers, data=f, timeout=180)
            
        if up_res.status_code != 200: return False
            
        finish_payload = {"video_id": video_id, "upload_phase": "finish", "video_state": "PUBLISHED", "description": caption, "title": title, "access_token": page_token}
        pub_res = requests.post(url, data=finish_payload, timeout=40)
        if pub_res.status_code == 200:
            print(f"  [+] FB Reel published successfully to page {page_id}!")
            return True
        else: return False
    except Exception: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
        files = {'file': open(video_path, 'rb')}
        data = {'description': caption, 'access_token': page_token}
        res = requests.post(url, data=data, files=files, timeout=120)
        return res.status_code == 200
    except Exception: return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try: 
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': open(photo_path, 'rb')}, timeout=60)
        return res.status_code == 200
    except Exception: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': open(path, 'rb')}, timeout=45)
            if r.status_code == 200: att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token}, timeout=30)
        if res.status_code == 200:
            print(f"  [+] FB Multi-Photo Album published to page {page_id}!")
            return True
        return False
    except Exception: return False

# --- YOUTUBE SHORTS UPLOADER ---
def get_youtube_access_token(client_id, client_secret, refresh_token):
    if not client_id or not client_secret or not refresh_token: return None
    url = "https://oauth2.googleapis.com/token"
    payload = {"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}
    try:
        res = requests.post(url, data=payload, timeout=20)
        if res.status_code == 200: return res.json().get("access_token")
    except Exception: pass
    return None

def upload_video_to_youtube(client_id, client_secret, refresh_token, video_path, title, description):
    access_token = get_youtube_access_token(client_id, client_secret, refresh_token)
    if not access_token: return False

    try:
        init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(os.path.getsize(video_path)), "X-Upload-Content-Type": "video/mp4"}
        metadata = {"snippet": {"title": title[:80] + " #shorts", "description": description + "\n\n#shorts #reels", "categoryId": "22"}, "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
        
        res = requests.post(init_url, headers=headers, json=metadata, timeout=30)
        if res.status_code != 200: return False
            
        upload_url = res.headers.get("Location")
        if not upload_url: return False
            
        with open(video_path, "rb") as f:
            up_res = requests.put(upload_url, headers={"Content-Length": str(os.path.getsize(video_path)), "Content-Type": "video/mp4"}, data=f, timeout=300)
            
        if up_res.status_code in [200, 201]:
            print(f"  [+] YouTube Short uploaded successfully!")
            return True
        return False
    except Exception: return False

# --- TIKTOK BUFFER GRAPHQL UPLOADER ---
def upload_video_to_tiktok(video_path, description, config=None):
    if config is None: config = {}
    buffer_profile_id = get_credential(config, "buffer_profile_id", "BUFFER_PROFILE_ID")
    buffer_access_token = get_credential(config, "buffer_access_token", "BUFFER_ACCESS_TOKEN")
    
    if not buffer_profile_id or not buffer_access_token:
        print("  [!] Buffer Credentials missing (BUFFER_PROFILE_ID / BUFFER_ACCESS_TOKEN). Skipping TikTok upload.")
        return False

    print("  [~] Uploading TikTok video via Buffer GraphQL API...")
    
    video_url = None
    filename = os.path.basename(video_path)

    # Tier 1: transfer.sh (Super fast & reliable on GitHub Actions runner)
    try:
        with open(video_path, 'rb') as f:
            up_res = requests.put(f"https://transfer.sh/{filename}", data=f, headers=HEADERS, timeout=45)
            if up_res.status_code == 200 and up_res.text.strip().startswith("http"):
                video_url = up_res.text.strip()
                print(f"  [+] Video uploaded to transfer.sh: {video_url}")
    except Exception as e:
        print(f"  [!] transfer.sh error: {e}")

    # Tier 2: tmpfiles.org
    if not video_url:
        try:
            with open(video_path, 'rb') as f:
                up_res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, headers=HEADERS, timeout=45)
                if up_res.status_code == 200:
                    raw_url = up_res.json().get("data", {}).get("url", "")
                    if raw_url:
                        video_url = raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                        print(f"  [+] Video uploaded to tmpfiles.org: {video_url}")
        except Exception as e:
            print(f"  [!] tmpfiles.org error: {e}")

    # Tier 3: Catbox.moe
    if not video_url:
        try:
            with open(video_path, 'rb') as f:
                up_res = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": f}, headers=HEADERS, timeout=45)
                if up_res.status_code == 200 and up_res.text.strip().startswith("http"):
                    video_url = up_res.text.strip()
                    print(f"  [+] Video uploaded to Catbox: {video_url}")
        except Exception as e:
            print(f"  [!] Catbox error: {e}")

    # Tier 4: Litterbox
    if not video_url:
        try:
            with open(video_path, 'rb') as f:
                up_res = requests.post("https://litterbox.catbox.moe/resources/internals/api.php", data={"reqtype": "fileupload", "time": "24h"}, files={"fileToUpload": f}, headers=HEADERS, timeout=45)
                if up_res.status_code == 200 and up_res.text.startswith("http"):
                    video_url = up_res.text.strip()
                    print(f"  [+] Video uploaded to Litterbox: {video_url}")
        except Exception as e:
            print(f"  [!] Litterbox error: {e}")

    # Tier 5: 0x0.st
    if not video_url:
        try:
            with open(video_path, 'rb') as f:
                up_res = requests.post("https://0x0.st", files={"file": f}, headers=HEADERS, timeout=45)
                if up_res.status_code == 200 and up_res.text.strip().startswith("http"):
                    video_url = up_res.text.strip()
                    print(f"  [+] Video uploaded to 0x0.st: {video_url}")
        except Exception as e:
            print(f"  [!] 0x0.st error: {e}")

    if not video_url:
        print("  [!] Failed to upload video to public host for Buffer.")
        return False

    graphql_url = "https://api.buffer.com"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {buffer_access_token}"
    }

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    for mode in ["shareNow", "addToQueue"]:
        payload = {
            "query": mutation,
            "variables": {
                "input": {
                    "channelId": buffer_profile_id,
                    "text": description[:150],
                    "schedulingType": "automatic",
                    "mode": mode,
                    "assets": [
                        {
                            "video": {
                                "url": video_url
                            }
                        }
                    ]
                }
            }
        }

        try:
            res = requests.post(graphql_url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                res_data = res.json()
                data = res_data.get("data", {}).get("createPost", {})
                if "post" in data and data["post"]:
                    print(f"  [+] TikTok video published successfully via Buffer GraphQL API ({mode})!")
                    return True
                elif "message" in data and data["message"]:
                    print(f"  [!] Buffer GraphQL Mutation Warning ({mode}): {data['message']}")
                elif "errors" in res_data:
                    print(f"  [!] Buffer GraphQL API Errors: {res_data['errors']}")
            else:
                print(f"  [!] Buffer GraphQL API HTTP Error ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"  [!] Exception during Buffer GraphQL request: {e}")

    return False

# --- WHATSAPP RENDER BACKEND MEDIA COMPILER / CHUNKER BASE64 MAKER BRIDGE SYSTEM---
def warmup_render_server(render_url):
    if not render_url: return
    try: requests.get(f"{render_url.rstrip('/')}/qr", timeout=15)
    except Exception: pass

def post_to_whatsapp_channel(render_url, channel_id, text, image_paths):
    if not render_url: return False
    try:
        clean_id = channel_id.split('/')[-1].replace('@newsletter', '').strip()
        encoded_images = []
        if image_paths and len(image_paths) > 0:
            for p in image_paths[:5]:
                if os.path.exists(p):
                    with open(p, 'rb') as f: encoded_images.append(base64.b64encode(f.read()).decode('utf-8'))
        
        payload = {"channel_id": clean_id, "text": text, "images": encoded_images}
        res = requests.post(f"{render_url.rstrip('/')}/send", json=payload, timeout=90)
        if res.status_code == 200 and res.json().get("status") == "success":
            print(f"  [+] Posted successfully (Media Array Sent: {len(encoded_images)}) to WhatsApp Channel '{clean_id}' via Render!")
            return True
        return False
    except Exception: return False

# --- FACEBOOK PAGE ACCESS HANDLER ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}&limit=100"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if str(p.get('id')) == str(page_id): return p.get('access_token')
    except Exception: pass
    return master_user_token

# --- MAIN CONTROLLER ALGORITHMIC PIPELINE STRUCTURE ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    if not rules: return memory

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else ("WhatsApp" if "WhatsApp" in p_str else "Website")))
    tg_session, tg_api_id, tg_api_hash = get_credential(config, "tg_session", "TG_SESSION"), get_credential(config, "tg_api_id", "TG_API_ID"), get_credential(config, "tg_api_hash", "TG_API_HASH")
    fb_user_token = get_credential(config, "fb_token", "FB_TOKEN") or get_credential(config, "fb_user_token", "FB_USER_TOKEN")
    render_wa_url = get_credential(config, "render_wa_url", "RENDER_WA_URL") or "https://wa-channel-bridge.onrender.com"

    if any(clean_platform(r['destination']) == "WhatsApp" for r in rules): warmup_render_server(render_wa_url)
    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        if tg_session and tg_api_id and tg_api_hash:
            try:
                tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
                await tg_client.start()
                print("  [+] Telegram Client Authenticated!")
            except Exception: tg_client = None

    current_time = datetime.now(timezone.utc)
    global_yt_tt_processed = set()

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        source_platform, dest_platform = clean_platform(rule['source']), clean_platform(rule['destination'])
        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        min_words = rule.get("min_words", 60)
        lookback_threshold = current_time - timedelta(hours=rule.get("lookback_hours", 24.0))

        for source_id in source_ids:
            try:
                if source_platform == "Website":
                    try:
                        resp = requests.get("https://www.prothomalo.com/feed/" if "prothomalo.com" in source_id else source_id, headers=HEADERS, timeout=15)
                        feed = feedparser.parse(resp.content if resp.status_code == 200 else source_id)
                    except Exception: feed = feedparser.parse(source_id)

                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    for entry in reversed(feed.entries[:15]):
                        entry_link = entry.get('link', '').strip()
                        if not entry_link and 'links' in entry and entry.links: entry_link = entry.links[0].get('href', '').strip()
                        if not entry_link: entry_link = entry.get('id', entry.get('guid', '')).strip()

                        if not entry_link or not entry_link.startswith(('http://', 'https://')) or entry_link in processed_links: continue
                        new_processed_links.append(entry_link)
                        
                        target_keywords = ["চলমান", "সকল", "চাকরির", "নিয়োগ"]
                        if all(kw in entry.title for kw in target_keywords): continue

                        raw_desc = strip_html(entry.summary if 'summary' in entry else entry.description if 'description' in entry else "")
                        if rule['txt'] and len(clean_text(entry.title + " " + raw_desc).split()) < min_words: continue

                        img_urls = []
                        if 'enclosures' in entry and entry.enclosures: img_urls.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
                        if 'media_content' in entry and entry.media_content: img_urls.extend([mc.get('url') for mc in entry.media_content])
                        img_urls.extend([url for url in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_desc, re.IGNORECASE)])

                        try:
                            web_res = requests.get(entry_link, headers=HEADERS, timeout=10)
                            if web_res.status_code == 200:
                                scraped_imgs = [u for r in [re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)] for u in r if not any(l in u.lower() for l in ['logo', 'icon', 'avatar'])]
                                img_urls.extend([i for i in scraped_imgs if i not in img_urls])
                        except Exception: pass

                        cleaned_img_urls = []
                        seen_bases = set()
                        for u in img_urls[:6]:
                            u = urljoin(entry_link, u) if not u.startswith('http') else u
                            b_url = u.split('?')[0]
                            if b_url not in seen_bases:
                                seen_bases.add(b_url)
                                cleaned_img_urls.append(u)

                        contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন whatsapp 01540503092"
                        final_post_text = f"{clean_text(entry.title)}{contact_sfx}" if rule.get('title_only', False) else f"{clean_text(entry.title)}\n\n{raw_desc[:250]}...{contact_sfx}"

                        raw_paths = []
                        if cleaned_img_urls and rule.get('img', True):
                            for idx, u in enumerate(cleaned_img_urls):
                                try:
                                    ir = requests.get(u, headers=HEADERS, timeout=10)
                                    if ir.status_code == 200:
                                        p = f"tmp_rss_{hash(entry_link)}_{idx}.jpg"
                                        with open(p, 'wb') as f: f.write(ir.content)
                                        try:
                                            with Image.open(p) as img:
                                                if img.size[1] > 0:
                                                    raw_paths.append(p)
                                        except Exception:
                                            if os.path.exists(p): os.remove(p)
                                except Exception: pass

                        # --- VIDEO IMAGES SELECTION LOGIC ---
                        # 1. Single image: Use unconditionally
                        # 2. Multiple images: Check ONLY 1st image. If 1st image is 16:9 banner (w/h >= 16/9), skip 1st image and keep all remaining images!
                        video_paths = []
                        if raw_paths:
                            if len(raw_paths) == 1:
                                video_paths = list(raw_paths)
                            else:
                                skip_first = False
                                try:
                                    with Image.open(raw_paths[0]) as first_img:
                                        w, h = first_img.size
                                        if h > 0 and (w / h) >= (16 / 9):
                                            skip_first = True
                                except Exception:
                                    pass

                                if skip_first and len(raw_paths) > 1:
                                    video_paths = list(raw_paths[1:])
                                else:
                                    video_paths = list(raw_paths)

                        if rule['txt']:
                            for did in dest_ids:
                                if dest_platform == "Telegram" and tg_client:
                                    clean_tg = clean_telegram_id(did)
                                    try:
                                        if raw_paths: await tg_client.send_file(clean_tg, raw_paths, caption=final_post_text)
                                        else: await tg_client.send_message(clean_tg, final_post_text)
                                    except Exception: pass
                                elif dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token:
                                        if len(raw_paths) > 1: post_multi_photo_to_facebook(did, token, raw_paths, final_post_text)
                                        elif len(raw_paths) == 1: post_photo_to_facebook(did, token, raw_paths[0], final_post_text)
                                elif dest_platform == "WhatsApp":
                                    post_to_whatsapp_channel(render_wa_url, did, final_post_text, raw_paths)

                        if video_paths:
                            if dest_platform == "Facebook":
                                for did in dest_ids:
                                    token = get_page_access_token(fb_user_token, did)
                                    audio = get_random_audio_file()
                                    if token and audio:
                                        pvf = f"reels_output/{sanitize_filename(entry.title)}_{did}.mp4"
                                        os.makedirs("reels_output", exist_ok=True)
                                        if create_reels_video(video_paths, audio, pvf):
                                            if not post_reel_to_facebook(did, token, pvf, entry.title, final_post_text): post_video_to_facebook(did, token, pvf, final_post_text)
                                        if os.path.exists(pvf): os.remove(pvf)
                            if entry_link not in global_yt_tt_processed:
                                global_yt_tt_processed.add(entry_link)
                                audio_yt, audio_tt = get_random_audio_file(), get_random_audio_file()
                                if audio_yt:
                                    yt_f = f"reels_output/{sanitize_filename(entry.title)}_yt_{random.randint(10, 99)}.mp4"
                                    if create_reels_video(video_paths, audio_yt, yt_f):
                                        yt_i, yt_s, yt_r = os.environ.get("YT_CLIENT_ID",""), os.environ.get("YT_CLIENT_SECRET",""), os.environ.get("YT_REFRESH_TOKEN","")
                                        if yt_i and yt_s and yt_r: upload_video_to_youtube(yt_i, yt_s, yt_r, yt_f, entry.title, final_post_text)
                                        if os.path.exists(yt_f): os.remove(yt_f)
                                if audio_tt:
                                    tt_f = f"reels_output/{sanitize_filename(entry.title)}_tt_{random.randint(10, 99)}.mp4"
                                    if create_reels_video(video_paths, audio_tt, tt_f):
                                        if os.environ.get("BUFFER_ACCESS_TOKEN", "") or os.environ.get("BUFFER_PROFILE_ID", "") or config.get("credentials", {}).get("buffer_access_token"):
                                            upload_video_to_tiktok(tt_f, final_post_text, config)
                                        if os.path.exists(tt_f): os.remove(tt_f)

                        for path in raw_paths:
                            if os.path.exists(path): os.remove(path)
                    memory[rule_key] = new_processed_links[-50:]
            except Exception: pass
    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    save_json(MEMORY_FILE, await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {})))
    print("\n✅ Task Executed.")

if __name__ == "__main__": asyncio.run(main())
