import os
import re
import json
import random
import asyncio
import requests
import feedparser
import yt_dlp
import shutil
import subprocess
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
        cmd = [
            "ffprobe", "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            audio_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  [!] Error reading audio duration with ffprobe: {e}")
        return 30.0

def create_reels_video(image_paths, audio_path, output_path, fps=24):
    print(f"  [~] Generating Reel Video: '{output_path}'")
    if not image_paths: return False

    # Filter out images >= 16:9
    valid_images = []
    for img_path in image_paths:
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                if h == 0: continue
                ratio = w / h
                if ratio < (16 / 9):
                    valid_images.append(img_path)
                else:
                    print(f"  [-] Skipping {img_path}: Aspect ratio ({ratio:.2f}) is >= 16/9.")
        except Exception as e:
            print(f"  [!] Error examining image {img_path}: {e}")

    if not valid_images:
        print("  [!] No valid images under 16:9 ratio found. Skipping video compilation.")
        return False

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

    frame_count = 0
    
    for idx, img_path in enumerate(valid_images):
        try:
            img = Image.open(img_path).convert('RGB')
            w, h = img.size
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
                    frame.save(os.path.join(temp_dir, f"frame_{frame_count:05d}.jpg"), "JPEG", quality=85)
                    frame_count += 1
            else:
                new_w = 720
                new_h = int(720 / ratio)
                resized = img.resize((new_w, new_h), resampling)
                y_offset = (1280 - new_h) // 2
                
                bg_frame = Image.new("RGB", (720, 1280), (0, 0, 0))
                bg_frame.paste(resized, (0, y_offset))
                
                for f in range(num_f):
                    bg_frame.save(os.path.join(temp_dir, f"frame_{frame_count:05d}.jpg"), "JPEG", quality=85)
                    frame_count += 1
        except Exception as e:
            print(f"  [!] Error building frame for image {img_path}: {e}")

    if frame_count == 0:
        shutil.rmtree(temp_dir)
        return False

    if os.path.exists(output_path): os.remove(output_path)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(temp_dir, "frame_%05d.jpg"),
        "-i", audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]

    try:
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except subprocess.CalledProcessError as e:
        print(f"  [!] ffmpeg failed. stderr: {e.stderr.decode() if e.stderr else ''}")
        success = False

    shutil.rmtree(temp_dir, ignore_errors=True)
    return success

# --- FACEBOOK REELS & VIDEO UPLOADER ---
def post_reel_to_facebook(page_id, page_token, video_path, title, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        payload = {'upload_phase': 'start', 'access_token': page_token}
        res = requests.post(url, data=payload, timeout=25)
        if res.status_code != 200:
            print(f"  [!] FB Reel Step 1 Failed ({res.status_code}) for page {page_id}: {res.text}")
            return False
        
        data = res.json()
        video_id, upload_url = data.get("video_id"), data.get("upload_url")
        if not video_id or not upload_url: return False
            
        file_size = os.path.getsize(video_path)
        headers = {
            "Authorization": f"OAuth {page_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        with open(video_path, "rb") as f:
            up_res = requests.post(upload_url, headers=headers, data=f, timeout=180)
            
        if up_res.status_code != 200:
            print(f"  [!] FB Reel Step 2 Upload Failed ({up_res.status_code}): {up_res.text}")
            return False
            
        finish_payload = {
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": caption,
            "title": title,
            "access_token": page_token
        }
        pub_res = requests.post(url, data=finish_payload, timeout=40)
        if pub_res.status_code == 200:
            print(f"  [+] FB Reel published successfully to page {page_id}!")
            return True
        else:
            print(f"  [!] FB Reel Step 3 Publish Failed ({pub_res.status_code}): {pub_res.text}")
            return False
    except Exception as e:
        print(f"  [!] Exception during FB Reels upload to page {page_id}: {e}")
        return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
        files = {'file': open(video_path, 'rb')}
        data = {'description': caption, 'access_token': page_token}
        res = requests.post(url, data=data, files=files, timeout=120)
        if res.status_code == 200:
            print(f"  [+] FB Standard Video Feed uploaded successfully to page {page_id}!")
            return True
        else:
            print(f"  [!] FB Standard Video Feed failed ({res.status_code}) for page {page_id}: {res.text}")
            return False
    except Exception as e:
        print(f"  [!] Exception posting FB video feed: {e}")
        return False

# --- YOUTUBE SHORTS UPLOADER ---
def get_youtube_access_token(client_id, client_secret, refresh_token):
    if not client_id or not client_secret or not refresh_token: return None
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
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
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(os.path.getsize(video_path)),
            "X-Upload-Content-Type": "video/mp4"
        }
        
        metadata = {
            "snippet": {"title": title[:80] + " #shorts", "description": description + "\n\n#shorts #reels", "categoryId": "22"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
        
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
    except Exception as e:
        print(f"  [!] Exception during YouTube Shorts upload: {e}")
        return False

# --- TIKTOK REELS UPLOADER (MAKIISTHENES DIRECT API ENGINE WITH REGEX PARSER) ---
def upload_video_to_tiktok(video_path, description):
    import sys, json
    tiktok_cookies_data = os.environ.get("TIKTOK_COOKIES", "")
    if not tiktok_cookies_data:
        print("  [!] TIKTOK_COOKIES environment secret not found. Skipping TikTok upload.")
        return False

    engine_dir = "tiktok_engine"
    if not os.path.exists(engine_dir):
        print("  [!] tiktok_engine directory not found. Make sure workflow cloned makiisthenes/TiktokAutoUploader.")
        return False

    print(f"  [~] Starting TikTok Direct API upload for: '{description[:40]}...'")
    
    cookies_dir = os.path.join(engine_dir, "CookiesDir")
    os.makedirs(cookies_dir, exist_ok=True)
    username = "omni_user"
    cookie_file = os.path.join(cookies_dir, f"{username}.json")

    try:
        tiktok_cookies_str = tiktok_cookies_data.strip()
        cookies_json = []

        # Parse Netscape cookie format
        for line in tiktok_cookies_str.splitlines():
            line = line.strip()
            if line.startswith("#HttpOnly_"): line = line[len("#HttpOnly_"):]
            if not line or line.startswith("#"): continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain, flag, path, secure, expiration, name, value = parts[:7]
                cookies_json.append({
                    "domain": domain,
                    "expirationDate": float(expiration) if expiration.replace('.', '', 1).isdigit() else 1800000000,
                    "hostOnly": not domain.startswith("."),
                    "httpOnly": False,
                    "name": name,
                    "path": path,
                    "sameSite": "unspecified",
                    "secure": secure.upper() == "TRUE",
                    "session": False,
                    "storeId": "0",
                    "value": value
                })

        sessionid_val = None
        session_match = re.search(r'sessionid(?:_ss)?[\t\s"=\:]+([a-f0-9]{32})', tiktok_cookies_str, re.IGNORECASE)
        if session_match:
            sessionid_val = session_match.group(1)

        if not sessionid_val:
            for c in cookies_json:
                if isinstance(c, dict) and c.get("name") in ["sessionid", "sessionid_ss"]:
                    sessionid_val = c.get("value")
                    break

        if sessionid_val:
            cookies_json.append({
                "domain": ".tiktok.com",
                "name": "sessionid",
                "value": sessionid_val,
                "path": "/",
                "secure": True
            })

        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies_json, f, indent=2)

        abs_video_path = os.path.abspath(video_path)
        cmd = [sys.executable, "cli.py", "upload", "-u", username, "-v", abs_video_path, "-t", description[:150]]
        
        print("  [~] Executing TikTok Direct API Upload Request...")
        res = subprocess.run(cmd, cwd=engine_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        
        if res.returncode == 0 or "uploaded" in res.stdout.lower() or "success" in res.stdout.lower():
            print("  [+] TikTok Direct API video upload successful!")
            return True
        else:
            print(f"  [!] TikTok upload output: {res.stdout.strip()}")
            if res.stderr: print(f"  [!] TikTok Stderr: {res.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  [!] Exception during TikTok Direct API upload: {e}")
        return False
    finally:
        if os.path.exists(cookie_file): os.remove(cookie_file)

# --- WHATSAPP (RENDER BAILEYS BRIDGE) ENGINE ---
def warmup_render_server(render_url):
    if not render_url: return
    try:
        url = f"{render_url.rstrip('/')}/qr"
        print("  [~] Warming up Render WhatsApp Server...")
        requests.get(url, timeout=15)
    except Exception: pass

def post_to_whatsapp_channel(render_url, channel_id, text, image_url=None):
    if not render_url: return False
    try:
        url = f"{render_url.rstrip('/')}/send"
        clean_id = channel_id.split('/')[-1].replace('@newsletter', '').strip()
        payload = {
            "channel_id": clean_id, 
            "text": text,
            "image_url": image_url if image_url else ""
        }
        res = requests.post(url, json=payload, timeout=90)
        if res.status_code == 200 and res.json().get("status") == "success":
            print(f"  [+] Posted successfully (Media: {bool(image_url)}) to WhatsApp Channel '{clean_id}' via Render!")
            return True
        else:
            print(f"  [!] Render WA Error ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"  [!] WhatsApp Render posting exception: {e}")
        return False

# --- FACEBOOK ACCESS ENGINE ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}&limit=100"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if str(p.get('id')) == str(page_id):
                    return p.get('access_token')
    except Exception as e:
        print(f"  [!] Exception fetching page token for {page_id}: {e}")
    return master_user_token

def post_text_to_facebook(page_id, page_token, text):
    try: 
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': text, 'access_token': page_token}, timeout=25)
        if res.status_code == 200: return True
        else:
            print(f"  [!] FB text post error on page {page_id}: {res.text}")
            return False
    except Exception as e:
        print(f"  [!] FB text post exception on page {page_id}: {e}")
        return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try: 
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': open(photo_path, 'rb')}, timeout=60)
        if res.status_code == 200: return True
        else:
            print(f"  [!] FB photo post error on page {page_id}: {res.text}")
            return False
    except Exception as e:
        print(f"  [!] FB photo post exception on page {page_id}: {e}")
        return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': open(path, 'rb')}, timeout=45)
            if r.status_code == 200: att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token}, timeout=30)
        if res.status_code == 200: return True
        else:
            print(f"  [!] FB multi-photo post error on page {page_id}: {res.text}")
            return False
    except Exception as e:
        print(f"  [!] FB multi-photo post exception on page {page_id}: {e}")
        return False

# --- CORE PIPELINE CONTROLLER ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    if not rules: return memory

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else ("WhatsApp" if "WhatsApp" in p_str else "Website")))
    
    tg_session = get_credential(config, "tg_session", "TG_SESSION")
    tg_api_id = get_credential(config, "tg_api_id", "TG_API_ID")
    tg_api_hash = get_credential(config, "tg_api_hash", "TG_API_HASH")
    fb_user_token = get_credential(config, "fb_token", "FB_TOKEN") or get_credential(config, "fb_user_token", "FB_USER_TOKEN")
    render_wa_url = get_credential(config, "render_wa_url", "RENDER_WA_URL") or "https://wa-channel-bridge.onrender.com"

    if any(clean_platform(r['destination']) == "WhatsApp" for r in rules):
        warmup_render_server(render_wa_url)

    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        if tg_session and tg_api_id and tg_api_hash:
            try:
                print("  [~] Authenticating Telegram Telethon Client...")
                tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
                await tg_client.start()
                print("  [+] Telegram Client Authenticated Successfully!")
            except Exception as e:
                print(f"  [!!!] Telegram Session Failed to Authenticate: {e}")
                tg_client = None

    current_time = datetime.now(timezone.utc)
    global_yt_tt_processed = set()

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        source_platform, dest_platform = clean_platform(rule['source']), clean_platform(rule['destination'])
        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        
        min_words = rule.get("min_words", 60)
        lookback_threshold = current_time - timedelta(hours=rule.get("lookback_hours", 24.0))
        keep_hashtags = rule.get("keep_hashtags", False)

        print(f"\n⚡ Processing Sync: {source_platform} ({len(source_ids)} sources) ➔ {dest_platform} ({len(dest_ids)} outputs)")

        for source_id in source_ids:
            try:
                # --- WEBSITE SOURCE (RSS FEED) AUTOMATION ---
                if source_platform == "Website":
                    is_prothom_alo = "prothomalo.com" in source_id
                    
                    if is_prothom_alo:
                        try:
                            resp = requests.get("https://www.prothomalo.com/feed/", headers=HEADERS, timeout=15)
                            feed = feedparser.parse(resp.content if resp.status_code == 200 else "https://www.prothomalo.com/feed/")
                        except Exception:
                            feed = feedparser.parse("https://www.prothomalo.com/feed/")
                            
                        match = re.search(r'prothomalo\.com(/[a-zA-Z0-9_\-/]+)', source_id)
                        clean_path = match.group(1) if match else ""
                        if clean_path:
                            feed.entries = [entry for entry in feed.entries if clean_path in entry.get('link', '')]
                    else:
                        feed = feedparser.parse(source_id)

                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    for entry in reversed(feed.entries[:15]):
                        entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc) if ('published_parsed' in entry and entry.published_parsed) else current_time
                        entry_link = entry.get('link', '').strip()
                        if not entry_link and 'links' in entry and entry.links: entry_link = entry.links[0].get('href', '').strip()
                        if not entry_link: entry_link = entry.get('id', entry.get('guid', '')).strip()

                        if not entry_link or not entry_link.startswith(('http://', 'https://')): continue
                        if entry_time < lookback_threshold or entry_link in processed_links: continue

                        # ALWAYS mark entry as processed in this run to prevent infinite re-uploading loops!
                        new_processed_links.append(entry_link)

                        # --- SKIP ARTICLE IF ALL 4 KEYWORDS MATCH IN TITLE ---
                        target_keywords = ["চলমান", "সকল", "চাকরির", "নিয়োগ"]
                        if all(kw in entry.title for kw in target_keywords):
                            print(f"  [-] Skipping article completely '{entry.title}': Title matched filter keywords.")
                            continue

                        raw_description = entry.summary if 'summary' in entry else (entry.description if 'description' in entry else "")
                        cleaned_description = strip_html(raw_description)

                        if rule['txt'] and len(clean_text(entry.title + " " + cleaned_description, keep_hashtags=keep_hashtags).split()) < min_words: continue

                        img_urls = []
                        if 'enclosures' in entry and entry.enclosures: img_urls.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('type', '').startswith('image/') or enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))])
                        if 'media_content' in entry and entry.media_content: img_urls.extend([mc.get('url') for mc in entry.media_content if mc.get('url') and mc.get('url') not in img_urls])
                        if 'media_thumbnail' in entry and entry.media_thumbnail: img_urls.extend([mt.get('url') for mt in entry.media_thumbnail if mt.get('url') and mt.get('url') not in mt_urls])
                        img_urls.extend([url for url in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_description, re.IGNORECASE) if url not in img_urls])

                        try:
                            web_res = requests.get(entry_link, headers=HEADERS, timeout=10)
                            if web_res.status_code == 200:
                                if is_prothom_alo and BeautifulSoup:
                                    soup = BeautifulSoup(web_res.text, 'html.parser')
                                    story_blocks = soup.select('div.story-element.story-element-text, div.video-description, p.story-element-text, article p')
                                    if story_blocks:
                                        paragraphs = [b.get_text().strip() for b in story_blocks if b.get_text().strip()]
                                        if paragraphs: cleaned_description = "\n\n".join(paragraphs)
                                
                                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)
                                scraped_imgs = [og_match.group(1)] if og_match else []
                                scraped_imgs.extend([url for re_match in [re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)] for url in re_match if url not in scraped_imgs and not any(l in url.lower() for l in ['logo', 'icon', 'avatar', 'gravatar', 'banner', 'loader', 'theme', 'spinner'])])
                                img_urls.extend([i for i in scraped_imgs if i not in img_urls])
                        except Exception as e:
                            print(f"  [!] Failed full-text extraction: {e}")

                        cleaned_img_urls = []
                        seen_base_urls = set()
                        for url in img_urls[:9]:
                            if not url.startswith(('http://', 'https://')): url = urljoin(entry_link, url)
                            base_url = url.split('?')[0].split('#')[0]
                            if base_url not in seen_base_urls:
                                seen_base_urls.add(base_url)
                                cleaned_img_urls.append(url)

                        contact_suffix = "\n\nআবেদন করতে যোগাযোগ করুন whatsapp 01540503092"
                        title_only_flag = rule.get('title_only', False)
                        
                        if title_only_flag:
                            final_post_text = clean_text(f"{entry.title}", keep_hashtags=keep_hashtags) + contact_suffix
                        else:
                            if cleaned_description:
                                final_post_text = clean_text(f"{entry.title}\n\n{cleaned_description}", keep_hashtags=keep_hashtags) + contact_suffix
                            else:
                                final_post_text = clean_text(f"{entry.title}\n\n🔗 {entry_link}", keep_hashtags=keep_hashtags) + contact_suffix

                        # DOWNLOAD & FILTER IMAGES (SKIP BANNER IMAGES RATIO >= 16/9)
                        photo_paths = []
                        if cleaned_img_urls and rule.get('img', True):
                            for idx, url in enumerate(cleaned_img_urls):
                                try:
                                    ir = requests.get(url, headers=HEADERS, timeout=10)
                                    if ir.status_code == 200:
                                        p = f"tmp_rss_{hash(entry_link)}_{idx}.jpg"
                                        with open(p, 'wb') as f: f.write(ir.content)
                                        
                                        try:
                                            with Image.open(p) as img:
                                                w, h = img.size
                                                if h > 0 and (w / h) < (16 / 9):
                                                    photo_paths.append(p)
                                                else:
                                                    print(f"  [-] Skipping photo {p}: Aspect ratio ({w/h:.2f}) is >= 16/9.")
                                                    if os.path.exists(p): os.remove(p)
                                        except Exception as img_err:
                                            print(f"  [!] Invalid image file {p}: {img_err}")
                                            if os.path.exists(p): os.remove(p)
                                except Exception: pass

                        posted_success = False
                        
                        # 1. SEND TEXT / IMAGES TO TELEGRAM, FACEBOOK & WHATSAPP
                        if rule['txt']:
                            for did in dest_ids:
                                if dest_platform == "Telegram" and tg_client:
                                    clean_tg_target = clean_telegram_id(did)
                                    try:
                                        print(f"  [~] Sending Photo/Text Post to Telegram Channel: @{clean_tg_target}...")
                                        if photo_paths: 
                                            await tg_client.send_file(clean_tg_target, photo_paths, caption=final_post_text)
                                        else: 
                                            await tg_client.send_message(clean_tg_target, final_post_text)
                                        posted_success = True
                                        print(f"  [+] Telegram Channel post successful!")
                                    except Exception as tg_err:
                                        print(f"  [!] Failed sending to Telegram (@{clean_tg_target}): {tg_err}")
                                        
                                elif dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token:
                                        print(f"  [~] Sending Photo/Text Post to FB Page: {did}...")
                                        if len(photo_paths) > 1: 
                                            posted_success = post_multi_photo_to_facebook(did, token, photo_paths, final_post_text)
                                        elif len(photo_paths) == 1: 
                                            posted_success = post_photo_to_facebook(did, token, photo_paths[0], final_post_text)
                                        else: 
                                            posted_success = post_text_to_facebook(did, token, final_post_text)

                                elif dest_platform == "WhatsApp":
                                    first_img_url = cleaned_img_urls[0] if (cleaned_img_urls and photo_paths) else None
                                    print(f"  [~] Sending Photo/Text Post to WhatsApp Channel: {did} via Render...")
                                    if post_to_whatsapp_channel(render_wa_url, did, final_post_text, image_url=first_img_url):
                                        posted_success = True

                        # 2. GENERATE & SEND UNIQUE REELS VIDEO FOR FACEBOOK PAGES
                        if photo_paths:
                            if dest_platform == "Facebook":
                                for did in dest_ids:
                                    token = get_page_access_token(fb_user_token, did)
                                    if token:
                                        audio_file = get_random_audio_file()
                                        if audio_file:
                                            video_title = sanitize_filename(f"{entry.title}_{did}_{random.randint(100, 999)}")
                                            os.makedirs("reels_output", exist_ok=True)
                                            page_video_file = f"reels_output/{video_title}.mp4"
                                            
                                            video_created = create_reels_video(photo_paths, audio_file, page_video_file)
                                            if video_created and os.path.exists(page_video_file):
                                                print(f"  [~] Uploading UNIQUE Reel to FB Page: {did} (Music: {os.path.basename(audio_file)})...")
                                                reel_ok = post_reel_to_facebook(did, token, page_video_file, entry.title, final_post_text)
                                                
                                                if not reel_ok:
                                                    print(f"  [~] Falling back to Standard Video Feed for FB Page: {did}...")
                                                    post_video_to_facebook(did, token, page_video_file, final_post_text)

                                                if os.path.exists(page_video_file):
                                                    os.remove(page_video_file)

                            # 3. YOUTUBE SHORTS & TIKTOK UPLOAD (RUNS EXACTLY ONCE PER ARTICLE)
                            if entry_link not in global_yt_tt_processed:
                                global_yt_tt_processed.add(entry_link)
                                
                                # YouTube Shorts
                                audio_file_yt = get_random_audio_file()
                                if audio_file_yt:
                                    video_title_yt = sanitize_filename(f"{entry.title}_yt_{random.randint(100, 999)}")
                                    os.makedirs("reels_output", exist_ok=True)
                                    yt_video_file = f"reels_output/{video_title_yt}.mp4"
                                    
                                    if create_reels_video(photo_paths, audio_file_yt, yt_video_file) and os.path.exists(yt_video_file):
                                        yt_id = os.environ.get("YT_CLIENT_ID", "")
                                        yt_secret = os.environ.get("YT_CLIENT_SECRET", "")
                                        yt_refresh = os.environ.get("YT_REFRESH_TOKEN", "")
                                        if yt_id and yt_secret and yt_refresh:
                                            print(f"  [~] Uploading UNIQUE Reel to YouTube Shorts (Music: {os.path.basename(audio_file_yt)})...")
                                            upload_video_to_youtube(yt_id, yt_secret, yt_refresh, yt_video_file, entry.title, final_post_text)

                                        if os.path.exists(yt_video_file):
                                            os.remove(yt_video_file)

                                # TikTok
                                audio_file_tt = get_random_audio_file()
                                if audio_file_tt:
                                    video_title_tt = sanitize_filename(f"{entry.title}_tt_{random.randint(100, 999)}")
                                    os.makedirs("reels_output", exist_ok=True)
                                    tt_video_file = f"reels_output/{video_title_tt}.mp4"
                                    
                                    if create_reels_video(photo_paths, audio_file_tt, tt_video_file) and os.path.exists(tt_video_file):
                                        tiktok_cookies = os.environ.get("TIKTOK_COOKIES", "")
                                        if tiktok_cookies:
                                            print(f"  [~] Uploading UNIQUE Reel to TikTok (Music: {os.path.basename(audio_file_tt)})...")
                                            upload_video_to_tiktok(tt_video_file, final_post_text)

                                        if os.path.exists(tt_video_file):
                                            os.remove(tt_video_file)

                        for path in photo_paths:
                            if os.path.exists(path): os.remove(path)

                    memory[rule_key] = new_processed_links[-50:]

            except Exception as e:
                print(f"  [!] FATAL EXCEPTION in Core Loop for {source_id}: {e}")

    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    u = await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {}))
    save_json(MEMORY_FILE, u)
    print("\n✅ Operation Completely Finalized Successfully!")

if __name__ == "__main__": asyncio.run(main())