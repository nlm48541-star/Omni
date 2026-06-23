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

def download_youtube_video(video_url, output_path):
    print(f"  [~] Advanced Protocol Fetching initiated for {video_url}...")
    ydl_opts_primary = {
        'format': 'b', 
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {'player_client': ['tv', 'mweb', 'android']}
        }
    }
    
    if os.path.exists(COOKIES_FILE): ydl_opts_primary['cookiefile'] = COOKIES_FILE
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts_primary) as ydl: ydl.download([video_url])
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"  [!] Extraction Failed! Mostly expired cookies or restriction: {e}")
        return False

def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        r = requests.get(f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}", timeout=20)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if p['id'] == page_id: return p['access_token']
    except Exception: pass
    return None

def post_text_to_facebook(page_id, page_token, text):
    try: return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': text, 'access_token': page_token}, timeout=25).status_code == 200
    except Exception: return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try: return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': open(photo_path, 'rb')}, timeout=60).status_code == 200
    except Exception: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': open(path, 'rb')}, timeout=45)
            if r.status_code == 200: att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token}, timeout=30).status_code == 200
    except Exception: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try: return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/videos", data={'description': caption, 'access_token': page_token}, files={'file': open(video_path, 'rb')}, timeout=120).status_code == 200
    except Exception: return False

def post_to_wordpress(wp_url, username, app_password, title, content):
    try: return requests.post(f"{wp_url}/wp-json/wp/v2/posts", json={'title': title, 'content': content, 'status': 'publish'}, headers={'Content-Type': 'application/json'}, auth=(username, app_password), timeout=30).status_code == 201
    except Exception: return False

async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    if not rules: return memory

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else "Website"))
    
    tg_session, tg_api_id, tg_api_hash = credentials.get('tg_session', ''), credentials.get('tg_api_id', ''), credentials.get('tg_api_hash', '')
    fb_user_token = credentials.get('fb_user_token', credentials.get('fb_token', ''))

    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        if tg_session and tg_api_id and tg_api_hash:
            try:
                print("  [~] Authenticating Telegram Telethon Client...")
                tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
                await tg_client.start()
            except Exception as e:
                print(f"  [!!!] Telegram Session failed! Details: {e}")
                tg_client = None

    current_time = datetime.now(timezone.utc)

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
                # --- A. TELEGRAM AUTOMATION (WITH ALBUM MULTI-PICTURE SUPPORT) ---
                if source_platform == "Telegram" and tg_client:
                    clean_tg_source_id = source_id.split('/')[-1] if 't.me' in source_id else source_id
                    
                    last_id = memory.get(rule_key, 0)
                    if isinstance(last_id, list): last_id = 0
                    
                    try:
                        messages = await tg_client.get_messages(clean_tg_source_id, limit=30)
                    except Exception as access_err:
                        print(f"  [X] Failed accessing TG Source '{clean_tg_source_id}'. Errr: {access_err}")
                        continue

                    # Group messages by Album (grouped_id) 
                    grouped_msgs = {}
                    for msg in reversed(messages):
                        if msg.date < lookback_threshold or msg.id <= last_id: continue
                        if msg.grouped_id:
                            if msg.grouped_id not in grouped_msgs: grouped_msgs[msg.grouped_id] = []
                            grouped_msgs[msg.grouped_id].append(msg)
                        else:
                            grouped_msgs[f"single_{msg.id}"] = [msg]

                    # Loop logic to Process Albums / Posts as complete packages
                    for group_key, msg_list in grouped_msgs.items():
                        temp_last_id = max(m.id for m in msg_list)
                        
                        raw_text = ""
                        for m in msg_list:
                            if m.text: 
                                raw_text = m.text
                                break
                                
                        cleaned_text = clean_text(raw_text, keep_hashtags=keep_hashtags)
                        word_count = len(cleaned_text.split())
                        has_media = any(bool(m.photo or m.video) for m in msg_list)
                        
                        if not has_media and rule['txt']:
                            if word_count < min_words:
                                print(f"  [-] TG Post ID {temp_last_id} Dropped: It was pure text, words({word_count}) below limit.")
                                last_id = max(last_id, temp_last_id)
                                continue

                        photo_paths = []
                        video_paths = []
                        for m in msg_list:
                            if rule.get('img', True) and m.photo:
                                photo_paths.append(await m.download_media())
                            elif rule.get('vid', True) and m.video:
                                video_paths.append(await m.download_media())

                        photo_paths = [p for p in photo_paths if p and os.path.exists(p)]
                        video_paths = [p for p in video_paths if p and os.path.exists(p)]

                        post_successful = False
                        for dest_id in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(fb_user_token, dest_id)
                                if token: 
                                    if len(photo_paths) > 1:
                                        print(f"  [>] Processing Album! ({len(photo_paths)} Photos) Facebook Sync..")
                                        if post_multi_photo_to_facebook(dest_id, token, photo_paths, cleaned_text):
                                            post_successful = True
                                    elif len(photo_paths) == 1:
                                        print(f"  [>] Processing Single Picture Facebook Sync..")
                                        if post_photo_to_facebook(dest_id, token, photo_paths[0], cleaned_text):
                                            post_successful = True
                                    elif len(video_paths) >= 1:
                                        print(f"  [>] Processing Video Facebook Sync..")
                                        if post_video_to_facebook(dest_id, token, video_paths[0], cleaned_text):
                                            post_successful = True
                                    elif rule['txt'] and cleaned_text:
                                        print(f"  [>] Processing Plain-text Facebook Sync..")
                                        if post_text_to_facebook(dest_id, token, cleaned_text):
                                            post_successful = True
                                            
                            elif dest_platform == "Website":
                                if cleaned_text:
                                    post_to_wordpress(dest_id, credentials.get('wp_username',''), credentials.get('wp_app_password',''), "Telegram Update", cleaned_text)
                                    post_successful = True

                        for p in photo_paths + video_paths:
                            if os.path.exists(p): os.remove(p)

                        if post_successful:
                            print(f"  [$$$] Successfully Pushed Telegram Post/Album to Facebook -> ID: {temp_last_id}")
                            
                        last_id = max(last_id, temp_last_id)
                            
                    memory[rule_key] = last_id

                # --- B. WEBSITE SOURCE (RSS FEED) AUTOMATION ---
                elif source_platform == "Website":
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
                        
                        raw_description = entry.summary if 'summary' in entry else (entry.description if 'description' in entry else "")
                        cleaned_description = strip_html(raw_description)

                        if rule['txt'] and len(clean_text(entry.title + " " + cleaned_description, keep_hashtags=keep_hashtags).split()) < min_words: continue

                        img_urls = []
                        if 'enclosures' in entry and entry.enclosures: img_urls.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('type', '').startswith('image/') or enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))])
                        if 'media_content' in entry and entry.media_content: img_urls.extend([mc.get('url') for mc in entry.media_content if mc.get('url') and mc.get('url') not in img_urls])
                        if 'media_thumbnail' in entry and entry.media_thumbnail: img_urls.extend([mt.get('url') for mt in entry.media_thumbnail if mt.get('url') and mt.get('url') not in img_urls])
                        img_urls.extend([url for url in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_description, re.IGNORECASE) if url not in img_urls])

                        try:
                            web_res = requests.get(entry_link, headers=HEADERS, timeout=10)
                            if web_res.status_code == 200:
                                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', web_res.text, re.IGNORECASE)
                                scraped_imgs = [og_match.group(1)] if og_match else []
                                scraped_imgs.extend([url for url in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE) if url not in scraped_imgs and not any(l in url.lower() for l in ['logo', 'icon', 'avatar', 'gravatar', 'banner', 'loader', 'theme', 'spinner', 'widget', 'footer', 'header'])])
                                img_urls.extend([i for i in scraped_imgs if i not in img_urls])
                        except Exception: pass

                        cleaned_img_urls = [url if url.startswith(('http://', 'https://')) else urljoin(entry_link, url) for url in img_urls[:9]]
                        cleaned_img_urls = list(dict.fromkeys(cleaned_img_urls)) 
                        
                        final_post_text = clean_text(f"📝 {entry.title}", keep_hashtags=keep_hashtags) if rule.get('title_only', False) else clean_text(f"📝 {entry.title}\n\n{cleaned_description[:350]+'...' if len(cleaned_description)>350 else cleaned_description}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)

                        photo_paths = []
                        if cleaned_img_urls and rule.get('img', True):
                            for idx, url in enumerate(cleaned_img_urls):
                                try:
                                    ir = requests.get(url, headers=HEADERS, timeout=10)
                                    if ir.status_code == 200:
                                        p = f"tmp_rss_{hash(entry_link)}_{idx}.jpg"
                                        with open(p, 'wb') as f: f.write(ir.content)
                                        photo_paths.append(p)
                                except Exception: pass

                        posted_success = False
                        if rule['txt']:
                            for did in dest_ids:
                                if dest_platform == "Telegram" and tg_client:
                                    if photo_paths: await tg_client.send_file(did, photo_paths, caption=final_post_text)
                                    else: await tg_client.send_message(did, final_post_text)
                                    posted_success = True
                                elif dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token:
                                        if len(photo_paths) > 1: posted_success = post_multi_photo_to_facebook(did, token, photo_paths, final_post_text)
                                        elif len(photo_paths) == 1: posted_success = post_photo_to_facebook(did, token, photo_paths[0], final_post_text)
                                        else: posted_success = post_text_to_facebook(did, token, final_post_text)

                        for path in photo_paths:
                            if os.path.exists(path): os.remove(path)
                        
                        if posted_success: new_processed_links.append(entry_link)
                    memory[rule_key] = new_processed_links[-50:]

                # --- C. YOUTUBE SOURCE AUTOMATION ---
                elif source_platform == "YouTube":
                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list): processed_links = []
                    new_processed_links = list(processed_links)

                    feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={source_id}")

                    for entry in reversed(feed.entries[:5]):
                        entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc) if ('published_parsed' in entry and entry.published_parsed) else current_time
                        if entry_time < lookback_threshold or entry.link in processed_links: continue

                        video_path = f"tmp_yt_{hash(entry.link)}.mp4"
                        caption = clean_text(entry.title, keep_hashtags=keep_hashtags)
                        dl_ok = rule.get('vid', True) and download_youtube_video(entry.link, video_path)

                        posted = False
                        for did in dest_ids:
                            if dest_platform == "Telegram" and tg_client:
                                if dl_ok and os.path.exists(video_path): await tg_client.send_file(did, video_path, caption=caption)
                                else: await tg_client.send_message(did, f"🎥 {entry.title}\n\nWatch here: {entry.link}")
                                posted = True
                            elif dest_platform == "Facebook":
                                token = get_page_access_token(fb_user_token, did)
                                if token:
                                    if dl_ok and os.path.exists(video_path): posted = post_video_to_facebook(did, token, video_path, caption)
                                    else: posted = post_text_to_facebook(did, token, f"🎥 {entry.title}\n\nWatch here: {entry.link}")
                                        
                        if video_path and os.path.exists(video_path): os.remove(video_path)
                        if posted: new_processed_links.append(entry.link)
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