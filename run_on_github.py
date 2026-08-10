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

def sanitize_filename(name):
    if not name: return "reels_video"
    cleaned = re.sub(r'[\/:*?"<>|\x00-\x1f]', '', name)
    return cleaned.strip()[:100]

def get_audio_duration(audio_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception: return 30.0

def create_reels_video(image_paths, audio_path, output_path, fps=24):
    print(f"  [~] Generating Reel Video: '{output_path}'")
    if not image_paths: return False

    audio_duration = get_audio_duration(audio_path)
    total_frames = int(audio_duration * fps)
    num_images = len(image_paths)
    frames_per_image = total_frames // num_images
    remainder = total_frames % num_images

    temp_dir = f"_tmp_reels_frames_{random.randint(100000, 999999)}"
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try: resampling = Image.Resampling.LANCZOS
    except AttributeError: resampling = Image.ANTIALIAS

    frame_count = 0
    for idx, img_path in enumerate(image_paths):
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
                    frame = resized.crop((0, y, 720, y + 1280))
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
        except Exception as e: print(f"  [!] Error building frame for image {img_path}: {e}")

    if frame_count == 0:
        shutil.rmtree(temp_dir)
        return False

    if os.path.exists(output_path): os.remove(output_path)
    ffmpeg_cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(temp_dir, "frame_%05d.jpg"), "-i", audio_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", output_path]
    try:
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except subprocess.CalledProcessError as e:
        success = False
    shutil.rmtree(temp_dir, ignore_errors=True)
    return success


def post_reel_to_facebook(page_id, page_token, video_path, title, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        res = requests.post(url, data={'upload_phase': 'start', 'access_token': page_token}, timeout=25)
        if res.status_code != 200: return False
        
        data = res.json()
        if not data.get("video_id") or not data.get("upload_url"): return False
            
        with open(video_path, "rb") as f:
            up_res = requests.post(data.get("upload_url"), headers={"Authorization": f"OAuth {page_token}", "offset": "0", "file_size": str(os.path.getsize(video_path)), "Content-Type": "application/octet-stream"}, data=f, timeout=180)
            
        if up_res.status_code != 200: return False
        pub_res = requests.post(url, data={"video_id": data.get("video_id"), "upload_phase": "finish", "video_state": "PUBLISHED", "description": caption, "title": title, "access_token": page_token}, timeout=40)
        if pub_res.status_code == 200:
            print(f"  [+] FB Reel published successfully to page {page_id}!")
            return True
        return False
    except Exception: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/videos", data={'description': caption, 'access_token': page_token}, files={'file': open(video_path, 'rb')}, timeout=120)
        if res.status_code == 200: return True
        return False
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


def upload_video_to_youtube(client_id, client_secret, refresh_token, video_path, title, description):
    try:
        token_res = requests.post("https://oauth2.googleapis.com/token", data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=20)
        if token_res.status_code != 200: return False
        access_token = token_res.json().get("access_token")
        if not access_token: return False

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(os.path.getsize(video_path)), "X-Upload-Content-Type": "video/mp4"}
        metadata = {"snippet": {"title": title[:80] + " #shorts", "description": description + "\n\n#shorts #reels", "categoryId": "22"}, "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
        res = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", headers=headers, json=metadata, timeout=30)
        if res.status_code != 200: return False
            
        with open(video_path, "rb") as f:
            up_res = requests.put(res.headers.get("Location"), headers={"Content-Length": str(os.path.getsize(video_path)), "Content-Type": "video/mp4"}, data=f, timeout=300)
        if up_res.status_code in [200, 201]:
            print(f"  [+] YouTube Short uploaded successfully!")
            return True
        return False
    except Exception: return False


def upload_video_to_tiktok(video_path, description):
    import sys, json
    tiktok_cookies_data = os.environ.get("TIKTOK_COOKIES", "")
    if not tiktok_cookies_data: return False

    engine_dir = "tiktok_engine"
    if not os.path.exists(engine_dir): return False

    print(f"  [~] Starting TikTok Direct API upload...")
    cookies_dir = os.path.join(engine_dir, "CookiesDir")
    os.makedirs(cookies_dir, exist_ok=True)
    username = "omni_user"
    cookie_file = os.path.join(cookies_dir, f"{username}.json")

    try:
        tiktok_cookies_str = tiktok_cookies_data.strip()
        cookies_list = []
        
        # Exact Parser for valid Session Injector bypassing Regex strictures safely natively easily!
        if tiktok_cookies_str.startswith("[") or tiktok_cookies_str.startswith("{"):
            try:
                parsed = json.loads(tiktok_cookies_str)
                cookies_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception: pass
        else:
            for line in tiktok_cookies_str.splitlines():
                line = line.strip()
                if line.startswith("#HttpOnly_"): line = line[10:]
                if not line or line.startswith("#"): continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies_list.append({
                        "domain": parts[0],
                        "expirationDate": float(parts[4]) if parts[4].replace('.', '', 1).isdigit() else 1800000000,
                        "hostOnly": not parts[0].startswith("."),
                        "httpOnly": False,
                        "name": parts[5],
                        "path": parts[2],
                        "secure": parts[3].upper() == "TRUE",
                        "session": False,
                        "value": parts[6]
                    })
        
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies_list, f, indent=2)

        abs_video_path = os.path.abspath(video_path)
        cmd = [sys.executable, "cli.py", "upload", "-u", username, "-v", abs_video_path, "-t", description[:150]]
        
        print("  [~] Executing TikTok Server Action Protocol...")
        res = subprocess.run(cmd, cwd=engine_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        
        if res.returncode == 0 or "uploaded" in res.stdout.lower() or "success" in res.stdout.lower():
            print("  [+] TikTok Direct API video upload successful!")
            return True
        else:
            print(f"  [!] TikTok server output failure: {res.stdout.strip()}")
            if res.stderr: print(f"  [!] Exception: {res.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  [!] TT Execution Fault -> {e}")
        return False
    finally:
        if os.path.exists(cookie_file): os.remove(cookie_file)


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
            for p in image_paths[:3]: 
                if os.path.exists(p):
                    with open(p, 'rb') as f: encoded_images.append(base64.b64encode(f.read()).decode('utf-8'))
        
        payload = {"channel_id": clean_id, "text": text, "images": encoded_images}
        res = requests.post(f"{render_url.rstrip('/')}/send", json=payload, timeout=90)
        if res.status_code == 200 and res.json().get("status") == "success":
            print(f"  [+] WA Album/Text Post successfully broadcast on '{clean_id}' via Render!")
            return True
        return False
    except Exception: return False


def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        r = requests.get(f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}&limit=100", timeout=20)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if str(p.get('id')) == str(page_id): return p.get('access_token')
    except Exception: pass
    return master_user_token

# --- PIPELINE START ---
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

                        raw_paths, video_paths = [], []
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
                                                    if (img.size[0] / img.size[1]) < (16 / 9): video_paths.append(p)
                                        except Exception:
                                            if os.path.exists(p): os.remove(p)
                                except Exception: pass

                        # 1. SEND PHOTOS
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
                                        else: post_text_to_facebook(did, token, final_post_text)
                                elif dest_platform == "WhatsApp":
                                    post_to_whatsapp_channel(render_wa_url, did, final_post_text, raw_paths)

                        # 2. SEND VIDEOS
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
                                        if os.environ.get("TIKTOK_COOKIES", ""): upload_video_to_tiktok(tt_f, final_post_text)
                                        if os.path.exists(tt_f): os.remove(tt_f)

                        for path in raw_photo_paths:
                            if os.path.exists(path): os.remove(path)
                    memory[rule_key] = new_processed_links[-50:]
            except Exception: pass
    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    save_json(MEMORY_FILE, await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {})))
    print("\n✅ Task Exectued.")

if __name__ == "__main__": asyncio.run(main())
