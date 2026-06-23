import os
import re
import json
import asyncio
import requests
import feedparser
import yt_dlp
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

# --- BULLET-PROOF YOUTUBE ENGINE (DUAL-STRATEGY) ---
def download_youtube_video(video_url, output_path):
    print("  [~] Executing Defense Strategy 1 (Local Emulation Bypass)...")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'source_address': '0.0.0.0', 
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web_safari']}}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if os.path.exists(output_path):
            print("  [+] Strategy 1 SUCCESS! Video Fetched Natively.")
            return True
    except Exception as e:
        print(f"  [!] Native Engine Alert: {e}")

    # STAGE 2 FALLBACK - NODE HOPPING PROXY (In case IP block holds)
    print("  [~] Initiating Strategy 2 (Public Secure Proxies)...")
    public_nodes = [
        "https://api.cobalt.tools",
        "https://cobalt.owo.top",
        "https://api.kwiateksbox.com",
        "https://cobalt.q-o-q.com"
    ]
    
    for api_url in public_nodes:
        try:
            print(f"      -> Attempting payload connection on node: {api_url}")
            node_ep = api_url if api_url.endswith('/') else f"{api_url}/"
            
            req = requests.post(
                node_ep,
                headers={"Accept": "application/json", "Content-Type": "application/json", "Origin": api_url},
                json={"url": video_url, "videoQuality": "720"},
                timeout=12
            )
            
            if req.status_code == 200:
                d_data = req.json()
                video_download_link = d_data.get("url")
                if video_download_link:
                    print("  [~] Node accepted link! Pulling heavy video file...")
                    vid_req = requests.get(video_download_link, stream=True, timeout=30)
                    if vid_req.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in vid_req.iter_content(chunk_size=1024*1024):
                                if chunk: f.write(chunk)
                        print("  [+] Strategy 2 SUCCESS! File stored.")
                        return True
        except Exception:
            pass # Fails gracefully to let next loop hop!
            
    print("  [!!!] Both strategies depleted and locked.")
    return False

# --- FACEBOOK MULTI-MEDIA API ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}"
    try:
        r = requests.get(url).json()
        for p in r.get('data', []):
            if p['id'] == page_id: return p['access_token']
    except Exception as e: print(f"  [!] Error parsing page acc: {e}")
    return None

def post_text_to_facebook(page_id, page_token, text):
    payload = {'message': text, 'access_token': page_token}
    try:
        r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data=payload)
        return r.status_code == 200
    except Exception as e: return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    payload = {'caption': caption, 'access_token': page_token}
    try:
        files = {'source': open(photo_path, 'rb')}
        r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data=payload, files=files)
        return r.status_code == 200
    except Exception as e: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        attached_media = []
        for path in photo_paths:
            payload = {'published': 'false', 'access_token': page_token}
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data=payload, files={'source': open(path, 'rb')})
            if r.status_code == 200:
                attached_media.append({"media_fbid": r.json().get('id')})

        if not attached_media: return False
        
        feed_payload = {
            'message': caption,
            'attached_media': json.dumps(attached_media),
            'access_token': page_token
        }
        r_feed = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data=feed_payload)
        return r_feed.status_code == 200
    except Exception as e: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    payload = {'description': caption, 'access_token': page_token}
    try:
        r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/videos", data=payload, files={'file': open(video_path, 'rb')})
        if r.status_code == 200: return True
        else: print(f"  [!] Reject Info FB: {r.text}"); return False
    except Exception as e:
        print(f"  [!] Fail Info Exception: {e}")
        return False

# --- WEB RSS SOURCING ---
def post_to_wordpress(wp_url, username, app_password, title, content):
    headers = {'Content-Type': 'application/json'}
    payload = {'title': title, 'content': content, 'status': 'publish'}
    r = requests.post(f"{wp_url}/wp-json/wp/v2/posts", json=payload, headers=headers, auth=(username, app_password))
    return r.status_code == 201

# --- SYSTEM BRAINS (THE ROUTER) ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    
    if not rules:
        print("[!] Configurations empty...")
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
                print(f"[!] Warning Tg Access Key Miss...")

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

        print(f"\n⚡ Master Pipeline Open: {source_platform} ({len(source_ids)} Source nodes) ➔ {dest_platform}")

        for source_id in source_ids:
            try:
                # --- Telegram Logic Block ---
                if source_platform == "Telegram" and tg_client:
                    last_id = memory.get(rule_key, 0)
                    if isinstance(last_id, list): last_id = 0
                        
                    messages = await tg_client.get_messages(source_id, limit=30)
                    for msg in reversed(messages):
                        if msg.date < lookback_threshold or msg.id <= last_id: continue

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

                # --- RSS WEBSITE AUTOMATION Logic Block ---
                elif source_platform == "Website":
                    feed = feedparser.parse(source_id)
                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    for entry in reversed(feed.entries[:15]):
                        if 'published_parsed' in entry and entry.published_parsed:
                            entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                        else: entry_time = current_time

                        entry_link = entry.get('link', entry.get('id', '')).strip()
                        if not entry_link.startswith(('http://', 'https://')): continue
                        if entry_time < lookback_threshold or entry_link in processed_links: continue

                        raw_description = entry.summary if 'summary' in entry else (entry.description if 'description' in entry else "")
                        cleaned_description = strip_html(raw_description)

                        full_content = clean_text(entry.title + " " + cleaned_description, keep_hashtags=keep_hashtags)
                        if rule['txt'] and len(full_content.split()) < min_words: continue

                        img_urls = []
                        if 'enclosures' in entry:
                            for enc in entry.enclosures:
                                href = enc.get('href', '')
                                if enc.get('type', '').startswith('image/') or href.lower().endswith(('.jpg', '.png')): img_urls.append(href)
                        
                        desc_imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_description, re.IGNORECASE)
                        for url in desc_imgs: img_urls.append(url)

                        try:
                            web_res = requests.get(entry_link, headers=HEADERS, timeout=10)
                            if web_res.status_code == 200:
                                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)
                                if og_match and og_match.group(1) not in img_urls: img_urls.insert(0, og_match.group(1))
                        except Exception: pass

                        cleaned_img_urls = []
                        for url in img_urls[:9]:
                            url = urljoin(entry_link, url) if not url.startswith('http') else url
                            if url not in cleaned_img_urls: cleaned_img_urls.append(url)

                        final_post_text = clean_text(f"📝 {entry.title}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)
                        if not rule.get('title_only', False):
                            short_description = (cleaned_description[:350] + "...") if len(cleaned_description) > 350 else cleaned_description
                            final_post_text = clean_text(f"📝 {entry.title}\n\n{short_description}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)

                        photo_paths = []
                        if cleaned_img_urls and rule.get('img', True):
                            for idx, url in enumerate(cleaned_img_urls):
                                try:
                                    res = requests.get(url, headers=HEADERS, timeout=10)
                                    if res.status_code == 200:
                                        path = f"temp_rss_{hash(entry_link)}_{idx}.jpg"
                                        with open(path, 'wb') as f: f.write(res.content)
                                        photo_paths.append(path)
                                except Exception: pass

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
                            print(f"  [+] Synced FB RSS Valid: {entry.title}")
                            new_processed_links.append(entry_link)

                    memory[rule_key] = new_processed_links[-50:]

                # --- C. YOUTUBE VIDEO DOWNLOADER (THE MONSTER SCRIPT) ---
                elif source_platform == "YouTube":
                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={source_id}"
                    feed = feedparser.parse(rss_url)

                    for entry in reversed(feed.entries[:5]):
                        if 'published_parsed' in entry and entry.published_parsed:
                            entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                        else: entry_time = current_time

                        entry_link = entry.link
                        if entry_time < lookback_threshold or entry_link in processed_links: continue
                        print(f"\n📺 Discovered Video Title: {entry.title}")

                        caption_text = clean_text(entry.title, keep_hashtags=keep_hashtags)
                        video_path = f"temp_vid_youtube_{hash(entry_link)}.mp4"
                        
                        dl_ok = False
                        if rule.get('vid', True):
                            dl_ok = download_youtube_video(entry_link, video_path)
                            
                        # Extremely resilient condition based post publish routing
                        posted_successfully = False
                        for dest_id in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(fb_user_token, dest_id)
                                if token:
                                    if dl_ok and os.path.exists(video_path):
                                        print("  [>] Handing heavy payload over to META Graphics processing API...")
                                        posted_successfully = post_video_to_facebook(dest_id, token, video_path, caption_text)
                                    else:
                                        posted_successfully = post_text_to_facebook(dest_id, token, f"🎥 {entry.title}\n\n🔗 Video Source: {entry_link}")
                            
                            elif dest_platform == "Telegram" and tg_client:
                                if dl_ok and os.path.exists(video_path):
                                    await tg_client.send_file(dest_id, video_path, caption=caption_text)
                                else:
                                    await tg_client.send_message(dest_id, f"🎥 {entry.title}\n\nWatch here: {entry_link}")
                                posted_successfully = True

                        if video_path and os.path.exists(video_path):
                            os.remove(video_path)
                            
                        if posted_successfully:
                            new_processed_links.append(entry_link)
                            print("  [$$$] Completely posted content securely online into active networks! ")
                            
                    memory[rule_key] = new_processed_links[-50:]
                    
            except Exception as e:
                print(f"  [!!!] Critical Node Failure on Channel: {source_id} - Error: {e}")

    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    updated = await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {}))
    save_json(MEMORY_FILE, updated)
    print("\n[■] Sequence Terminated. Automation Sleeping!")

if __name__ == "__main__":
    asyncio.run(main())