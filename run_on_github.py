import os
import re
import json
import asyncio
import requests
import feedparser
from time import mktime
from urllib.parse import urljoin
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

CONFIG_FILE = "automation_config.json"
MEMORY_FILE = "bot_memory.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default_val

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def strip_html(text):
    if not text:
        return ""
    clean_re = re.compile('<.*?>')
    return re.sub(clean_re, '', text)

def clean_text(text, keep_hashtags=False):
    if not text:
        return ""
    text = re.sub(r'@\w+', '', text)
    if not keep_hashtags:
        text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

# --- YOUTUBE 100% WORKING DOWNLOADER (THIRDPARTY INVIDIOUS API) ---
def download_youtube_video(video_url, output_path):
    """
    Downloads YouTube videos avoiding Cloud IP blocking by fetching
    the real video source link using reliable Cobalt/Invidious proxy APIs.
    """
    # Using public robust Cobalt API for YouTube Extraction
    api_url = "https://co.wuk.sh/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": video_url,
        "vQuality": "720", 
        "isAudioOnly": False,
        "vCodec": "h264" # Ensuring best MP4 compatability
    }
    
    try:
        # Step 1: Request proxy direct URL
        req = requests.post(api_url, headers=headers, json=payload, timeout=15)
        if req.status_code != 200:
            print(f"  [!] YouTube Bypass API error: HTTP {req.status_code}")
            return False
            
        data = req.json()
        direct_video_url = data.get("url")
        
        if not direct_video_url:
            print(f"  [!] Failed to extract valid direct video URL from proxy.")
            return False
            
        # Step 2: Download the file to local path
        print("  [~] Saving video file from fast-proxy...")
        vid_req = requests.get(direct_video_url, stream=True, timeout=20)
        
        if vid_req.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in vid_req.iter_content(chunk_size=1024*1024): 
                    if chunk: 
                        f.write(chunk)
            print("  [+] Video successfully downloaded!")
            return True
        else:
            print(f"  [!] Failed downloading proxy URL. HTTP {vid_req.status_code}")
            return False
            
    except Exception as e:
        print(f"  [!] Proxy YT extraction Exception: {e}")
        return False

# --- FACEBOOK ENGINE ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token:
        print("  [!] Error: Master User Access Token is empty!")
        return None
    url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}"
    try:
        r = requests.get(url)
        response_data = r.json()
        if r.status_code == 200:
            pages = response_data.get('data', [])
            for page in pages:
                if page['id'] == page_id:
                    return page['access_token']
            print(f"  [!] Error: Page ID {page_id} not found in your Master Token accounts list.")
        else:
            print(f"  [!] Facebook Token Fetch Error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"  [!] Facebook Token Request Exception: {e}")
    return None

def post_text_to_facebook(page_id, page_token, text):
    url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
    payload = {'message': text, 'access_token': page_token}
    try:
        r = requests.post(url, data=payload)
        return r.status_code == 200
    except Exception as e:
        print(f"  [!] Facebook Request Exception (Text): {e}")
        return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
    payload = {'caption': caption, 'access_token': page_token}
    try:
        files = {'source': open(photo_path, 'rb')}
        r = requests.post(url, data=payload, files=files)
        return r.status_code == 200
    except Exception as e:
        print(f"  [!] Facebook Request Exception (Photo): {e}")
        return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        attached_media = []
        for idx, path in enumerate(photo_paths):
            url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
            payload = {'published': 'false', 'access_token': page_token}
            files = {'source': open(path, 'rb')}
            r = requests.post(url, data=payload, files=files)
            if r.status_code == 200:
                attached_media.append({"media_fbid": r.json().get('id')})
            else:
                print(f"  [!] Error uploading photo {idx+1}: {r.text}")

        if not attached_media:
            return False

        feed_url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
        feed_payload = {
            'message': caption,
            'attached_media': json.dumps(attached_media),
            'access_token': page_token
        }
        r_feed = requests.post(feed_url, data=feed_payload)
        return r_feed.status_code == 200
    except Exception as e:
        print(f"  [!] Facebook Multi-Photo Exception: {e}")
        return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
    payload = {'description': caption, 'access_token': page_token}
    try:
        files = {'file': open(video_path, 'rb')}
        r = requests.post(url, data=payload, files=files)
        if r.status_code == 200:
            return True
        else:
            print(f"  [!] Facebook API Error (Video): {r.text}")
            return False
    except Exception as e:
        print(f"  [!] Facebook Video Exception: {e}")
        return False

def post_to_wordpress(wp_url, username, app_password, title, content):
    url = f"{wp_url}/wp-json/wp/v2/posts"
    headers = {'Content-Type': 'application/json'}
    payload = {'title': title, 'content': content, 'status': 'publish'}
    r = requests.post(url, json=payload, headers=headers, auth=(username, app_password))
    return r.status_code == 201

# --- MAIN CONTROLLER ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    
    if not rules:
        print("[!] No active routes configured. Exiting.")
        return memory

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else "Website"))

    tg_session = credentials.get('tg_session', '')
    tg_api_id = credentials.get('tg_api_id', '')
    tg_api_hash = credentials.get('tg_api_hash', '')
    wp_username = credentials.get('wp_username', '')
    wp_app_password = credentials.get('wp_app_password', '')
    fb_user_token = credentials.get('fb_user_token', credentials.get('fb_token', ''))

    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        if tg_session and tg_api_id and tg_api_hash:
            try:
                tg_client = TelegramClient(StringSession(tg_session), int(tg_api_id), tg_api_hash)
                await tg_client.start()
            except Exception as e:
                print(f"[!] Error initializing Telegram Client: {e}")
                tg_client = None

    current_time = datetime.now(timezone.utc)

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        source_platform = clean_platform(rule['source'])
        dest_platform = clean_platform(rule['destination'])

        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        
        min_words = rule.get("min_words", 60)
        lookback_hours = rule.get("lookback_hours", 1.0)
        lookback_threshold = current_time - timedelta(hours=lookback_hours)
        keep_hashtags = rule.get("keep_hashtags", False)

        print(f"\n⚡ Sync Target: {source_platform} ➔ {dest_platform}")

        for source_id in source_ids:
            try:
                if source_platform == "Telegram" and tg_client:
                    last_id = memory.get(rule_key, 0)
                    if isinstance(last_id, list): 
                        last_id = 0
                        
                    messages = await tg_client.get_messages(source_id, limit=30)
                    for msg in reversed(messages):
                        if msg.date < lookback_threshold or msg.id <= last_id:
                            continue

                        cleaned_text = clean_text(msg.text, keep_hashtags=keep_hashtags) if msg.text else ""
                        if rule['txt'] and len(cleaned_text.split()) < min_words: continue

                        if rule['txt'] and cleaned_text:
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token: post_text_to_facebook(dest_id, token, cleaned_text)

                        if rule.get('img', True) and msg.photo:
                            photo_path = await msg.download_media()
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token: post_photo_to_facebook(dest_id, token, photo_path, cleaned_text)
                            if os.path.exists(photo_path): os.remove(photo_path)

                        if rule['vid'] and msg.video:
                            video_path = await msg.download_media()
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token: post_video_to_facebook(dest_id, token, video_path, cleaned_text)
                            if os.path.exists(video_path): os.remove(video_path)
                        
                        last_id = max(last_id, msg.id)
                    memory[rule_key] = last_id

                elif source_platform == "Website":
                    feed = feedparser.parse(source_id)
                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    for entry in reversed(feed.entries[:15]):
                        if 'published_parsed' in entry and entry.published_parsed:
                            entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                        else:
                            entry_time = current_time

                        entry_link = entry.get('link', entry.get('id', '')).strip()
                        if not entry_link.startswith(('http://', 'https://')): continue
                        if entry_time < lookback_threshold or entry_link in processed_links: continue

                        raw_description = entry.summary if 'summary' in entry else (entry.description if 'description' in entry else "")
                        cleaned_description = strip_html(raw_description)

                        full_content_for_counting = clean_text(entry.title + " " + cleaned_description, keep_hashtags=keep_hashtags)
                        if rule['txt'] and len(full_content_for_counting.split()) < min_words: continue

                        # Smart Scraper Extract Logic (Simplified for performance)
                        img_urls = []
                        try:
                            web_res = requests.get(entry_link, headers=HEADERS, timeout=10)
                            if web_res.status_code == 200:
                                og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', web_res.text, re.IGNORECASE)
                                if og_match: img_urls.append(og_match.group(1))
                        except Exception: pass

                        final_post_text = clean_text(f"📝 {entry.title}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)
                        if not rule.get('title_only', False):
                            short_desc = (cleaned_description[:350] + "...") if len(cleaned_description) > 350 else cleaned_description
                            final_post_text = clean_text(f"📝 {entry.title}\n\n{short_desc}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)

                        photo_paths = []
                        if img_urls and rule.get('img', True):
                            for idx, url in enumerate(img_urls[:9]):
                                try:
                                    res = requests.get(url, headers=HEADERS, timeout=10)
                                    if res.status_code == 200:
                                        path = f"temp_{hash(entry_link)}_{idx}.jpg"
                                        with open(path, 'wb') as f: f.write(res.content)
                                        photo_paths.append(path)
                                except: pass

                        posted = False
                        if rule['txt']:
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token:
                                        if len(photo_paths) > 1: posted = post_multi_photo_to_facebook(dest_id, token, photo_paths, final_post_text)
                                        elif len(photo_paths) == 1: posted = post_photo_to_facebook(dest_id, token, photo_paths[0], final_post_text)
                                        else: posted = post_text_to_facebook(dest_id, token, final_post_text)

                        for path in photo_paths:
                            if os.path.exists(path): os.remove(path)
                        
                        if posted:
                            new_processed_links.append(entry_link)
                            print(f"  [+] Published: {entry.title}")

                    memory[rule_key] = new_processed_links[-50:]

                # --- C. YOUTUBE SOURCE (COBALT FAST-PROXY ENGINE) ---
                elif source_platform == "YouTube":
                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={source_id}"
                    feed = feedparser.parse(rss_url)

                    for entry in reversed(feed.entries[:5]):
                        if 'published_parsed' in entry and entry.published_parsed:
                            entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                        else:
                            entry_time = current_time

                        entry_link = entry.link
                        if entry_time < lookback_threshold or entry_link in processed_links: continue
                        print(f"🎥 Downloading YouTube Source: {entry.title}")

                        caption_text = clean_text(entry.title, keep_hashtags=keep_hashtags)
                        video_path = f"temp_yt_{hash(entry_link)}.mp4"
                        
                        dl_ok = False
                        if rule.get('vid', True):
                            dl_ok = download_youtube_video(entry_link, video_path)

                        posted = False
                        for dest_id in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(fb_user_token, dest_id)
                                if token:
                                    if dl_ok and os.path.exists(video_path):
                                        posted = post_video_to_facebook(dest_id, token, video_path, caption_text)
                                    else:
                                        posted = post_text_to_facebook(dest_id, token, f"🎥 {entry.title}\n\n{entry_link}")
                        
                        if video_path and os.path.exists(video_path): os.remove(video_path)
                        if posted:
                            print(f"  [+] Published: {entry.title}")
                            new_processed_links.append(entry_link)

                    memory[rule_key] = new_processed_links[-50:]

            except Exception as e:
                print(f"  [!] PIPELINE EXCEPTION on source {source_id}: {e}")

    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    updated = await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {}))
    save_json(MEMORY_FILE, updated)

if __name__ == "__main__":
    asyncio.run(main())