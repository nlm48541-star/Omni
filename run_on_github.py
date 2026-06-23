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
    if not text: return ""
    clean_re = re.compile('<.*?>')
    return re.sub(clean_re, '', text)

def clean_text(text, keep_hashtags=False):
    if not text: return ""
    text = re.sub(r'@\w+', '', text)
    if not keep_hashtags:
        text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

# --- YOUTUBE DOWNLOADER (DUAL-STRATEGY NATIVE + PROXY) ---
def download_youtube_video(video_url, output_path):
    print("  [~] Executing Strategy 1 (Native Engine Bypass)...")
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
        print(f"  [!] Native Alert: YouTube Block Detected.")

    # Strategy 2
    print("  [~] Executing Strategy 2 (Public Proxy Network)...")
    public_nodes = [
        "https://api.cobalt.tools", "https://co.eepy.ing",
        "https://cobalt.catterall.us", "https://cobalt.api.zluo.xyz"
    ]
    try:
        wiki_req = requests.get("https://instances.cobalt.wiki/instances.json", timeout=8).json()
        dynamic_nodes = [n['api'] for n in wiki_req if isinstance(n, dict) and 'api' in n]
        for dn in dynamic_nodes:
            if dn not in public_nodes: public_nodes.append(dn)
    except Exception:
        pass

    custom_h = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    for api_url in public_nodes[:10]:
        try:
            node_ep = api_url.rstrip('/')
            print(f"      -> Contacting node: {node_ep}")
            payload = {"url": video_url, "vQuality": "720", "videoQuality": "720"}
            
            req = requests.post(node_ep, headers=custom_h, json=payload, timeout=12)
            if req.status_code in [404, 400]:
                req = requests.post(f"{node_ep}/api/json", headers=custom_h, json=payload, timeout=12)
                
            if req.status_code == 200:
                resp = req.json()
                if resp.get("url"):
                    vid_req = requests.get(resp["url"], stream=True, timeout=60)
                    if vid_req.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in vid_req.iter_content(chunk_size=1024*1024):
                                if chunk: f.write(chunk)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 10240:
                            print("  [+] Strategy 2 SUCCESS! Proxy bypassed firewall.")
                            return True
        except Exception:
            pass
            
    print("  [!!!] Critical: All global strategies exhausted!")
    return False

# --- FACEBOOK API HELPERS ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}"
    try:
        r = requests.get(url).json()
        for p in r.get('data', []):
            if p['id'] == page_id: return p['access_token']
    except Exception: pass
    return None

def post_text_to_facebook(page_id, page_token, text):
    try:
        r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': text, 'access_token': page_token})
        return r.status_code == 200
    except: return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try:
        r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': open(photo_path, 'rb')})
        return r.status_code == 200
    except: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        attached_media = []
        for path in photo_paths:
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': open(path, 'rb')})
            if r.status_code == 200: attached_media.append({"media_fbid": r.json().get('id')})
        if not attached_media: return False
        r_feed = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(attached_media), 'access_token': page_token})
        return r_feed.status_code == 200
    except: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/videos", data={'description': caption, 'access_token': page_token}, files={'file': open(video_path, 'rb')})
        if r.status_code != 200: print(f"  [!] FB Video Reject: {r.text}")
        return r.status_code == 200
    except: return False

def post_to_wordpress(wp_url, username, app_password, title, content):
    r = requests.post(f"{wp_url}/wp-json/wp/v2/posts", json={'title': title, 'content': content, 'status': 'publish'}, headers={'Content-Type': 'application/json'}, auth=(username, app_password))
    return r.status_code == 201


# --- THE MAIN BRAIN ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    
    if not rules:
        print("[!] Configurations empty. Setup tools via local panel.")
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
            except Exception as e: print(f"[!] Error Initializing Telegram: {e}")

    current_time = datetime.now(timezone.utc)

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        source_platform = clean_platform(rule['source'])
        dest_platform = clean_platform(rule['destination'])

        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        
        min_words = rule.get("min_words", 60)
        lookback_threshold = current_time - timedelta(hours=rule.get("lookback_hours", 1.0))
        keep_hashtags = rule.get("keep_hashtags", False)

        print(f"\n⚡ Master Pipeline Route: {source_platform} ➔ {dest_platform}")

        for source_id in source_ids:
            
            # --- TIER A: TELEGRAM AUTOMATION ---
            if source_platform == "Telegram" and tg_client:
                try:
                    last_id = memory.get(rule_key, 0)
                    if isinstance(last_id, list): last_id = 0
                        
                    messages = await tg_client.get_messages(source_id, limit=30)
                    for msg in reversed(messages):
                        if msg.date < lookback_threshold or msg.id <= last_id: continue

                        c_text = clean_text(msg.text, keep_hashtags) if msg.text else ""
                        if rule['txt'] and len(c_text.split()) < min_words: continue

                        if rule['txt'] and c_text:
                            for did in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token: post_text_to_facebook(did, token, c_text)
                                elif dest_platform == "Website": post_to_wordpress(did, wp_username, wp_app_password, "TG Sync", c_text)

                        if rule.get('img', True) and msg.photo:
                            p_path = await msg.download_media()
                            for did in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token: post_photo_to_facebook(did, token, p_path, c_text)
                            if os.path.exists(p_path): os.remove(p_path)

                        if rule['vid'] and msg.video:
                            v_path = await msg.download_media()
                            for did in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token: post_video_to_facebook(did, token, v_path, c_text)
                            if os.path.exists(v_path): os.remove(v_path)
                        last_id = max(last_id, msg.id)
                    memory[rule_key] = last_id
                except Exception as e: print(f"  [!] Fail in Telegram loop: {e}")

            # --- TIER B: WEBSITE SOURCING AUTOMATION ---
            elif source_platform == "Website":
                try:
                    feed = feedparser.parse(source_id)
                    plinks = memory.get(rule_key, [])
                    if not isinstance(plinks, list): plinks = []
                    new_links = list(plinks)

                    for entry in reversed(feed.entries[:15]):
                        if 'published_parsed' in entry and entry.published_parsed:
                            entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                        else: entry_time = current_time

                        e_link = entry.get('link', entry.get('id', '')).strip()
                        if not e_link.startswith('http'): continue
                        if entry_time < lookback_threshold or e_link in plinks: continue
                        print(f"📝 New WP Found: {entry.title}")

                        r_desc = entry.summary if 'summary' in entry else entry.description if 'description' in entry else ""
                        full_content = clean_text(entry.title + " " + strip_html(r_desc), keep_hashtags)
                        if rule['txt'] and len(full_content.split()) < min_words: continue

                        # Smart scraper
                        img_urls = [enc.get('href') for enc in entry.get('enclosures', []) if enc.get('href', '').endswith(('.jpg','.png'))]
                        img_urls.extend(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', r_desc, re.IGNORECASE))
                        try:
                            w_res = requests.get(e_link, headers=HEADERS, timeout=8)
                            if w_res.status_code == 200:
                                o_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', w_res.text, re.IGNORECASE)
                                if o_m and o_m.group(1) not in img_urls: img_urls.insert(0, o_m.group(1))
                        except: pass

                        cleaned_img_urls = []
                        for url in img_urls[:9]:
                            url = urljoin(e_link, url) if not url.startswith('http') else url
                            if url not in cleaned_img_urls: cleaned_img_urls.append(url)

                        c_title = clean_text(f"📝 {entry.title}", keep_hashtags)
                        final_txt = c_title if rule.get('title_only', False) else f"{c_title}\n\n{strip_html(r_desc)[:350]}\n\n🔗 Source: {e_link}"

                        p_paths = []
                        if cleaned_img_urls and rule.get('img', True):
                            for idx, u in enumerate(cleaned_img_urls):
                                try:
                                    img_r = requests.get(u, headers=HEADERS, timeout=10)
                                    if img_r.status_code == 200:
                                        p = f"t_img_{hash(e_link)}_{idx}.jpg"
                                        with open(p, 'wb') as f: f.write(img_r.content)
                                        p_paths.append(p)
                                except: pass

                        posted = False
                        if rule['txt']:
                            for did in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, did)
                                    if token:
                                        if len(p_paths) > 1: posted = post_multi_photo_to_facebook(did, token, p_paths, final_txt)
                                        elif len(p_paths) == 1: posted = post_photo_to_facebook(did, token, p_paths[0], final_txt)
                                        else: posted = post_text_to_facebook(did, token, final_txt)

                        for path in p_paths:
                            if os.path.exists(path): os.remove(path)
                        
                        if posted: new_links.append(e_link); print(f"  [+] Published Web Post Success.")

                    memory[rule_key] = new_links[-50:]
                except Exception as e: print(f"  [!] Fail in Website loop: {e}")

                # --- C. YOUTUBE VIDEO DOWNLOADER (THE MONSTER SCRIPT) ---
            elif source_platform == "YouTube":
                try:
                    plinks = memory.get(rule_key, [])
                    if not isinstance(plinks, list): plinks = []
                    new_links = list(plinks)

                    feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={source_id}")

                    for entry in reversed(feed.entries[:5]):
                        entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc) if 'published_parsed' in entry else current_time
                        e_link = entry.link
                        
                        if entry_time < lookback_threshold or e_link in plinks: continue
                        print(f"\n📺 YT Target Engaged: {entry.title}")

                        c_text = clean_text(entry.title, keep_hashtags)
                        v_path = f"t_vid_{hash(e_link)}.mp4"
                        
                        dl_ok = False
                        if rule.get('vid', True): dl_ok = download_youtube_video(e_link, v_path)

                        posted = False
                        for did in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(fb_user_token, did)
                                if token:
                                    if dl_ok and os.path.exists(v_path):
                                        print("  [>] Transmitting raw payload via Meta servers...")
                                        posted = post_video_to_facebook(did, token, v_path, c_text)
                                    else: posted = post_text_to_facebook(did, token, f"🎥 {entry.title}\n\n🔗 Video Source: {e_link}")
                            
                            elif dest_platform == "Telegram" and tg_client:
                                if dl_ok and os.path.exists(v_path): await tg_client.send_file(did, v_path, caption=c_text)
                                else: await tg_client.send_message(did, f"🎥 {entry.title}\n\nWatch here: {e_link}")
                                posted = True

                        if v_path and os.path.exists(v_path): os.remove(v_path)
                        if posted:
                            new_links.append(e_link)
                            print("  [$$$] Successfully Posted and Synced content.")

                    memory[rule_key] = new_links[-50:]
                except Exception as e: print(f"  [!] Fail in YouTube loop: {e}")

    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    updated = await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {}))
    save_json(MEMORY_FILE, updated)
    print("\n[■] Sequence Clean Exit.")

if __name__ == "__main__":
    asyncio.run(main())