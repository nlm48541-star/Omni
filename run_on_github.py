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
# The deadly weapon added here
COOKIES_FILE = "cookies.txt"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
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
    if not keep_hashtags: text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n+', '\n\n', text).strip()

# --- ADVANCED YOUTUBE (COOKIE & ANTI-BAN BYPASS) ENGINE ---
def download_youtube_video(video_url, output_path):
    print("  [~] System attempting high-end Google Bot-Bypass Mechanism...")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        # Making Youtube believe request comes from standard ios or Android phone to skip blocking
        'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web']}},
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
    }
    
    try:
        if not os.path.exists(COOKIES_FILE):
            print("  [!] System Alert: No cookies.txt found. Action may still trigger IP blockage. Retrying directly...")
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
            
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print("  [+] Video Bypassed & Harvested Complete! HD Chunk File generated.")
            return True
        else: 
            return False
    except Exception as e:
        print(f"  [!!!] Critical Data center lock from Google detected: {e}")
        return False

# --- FACEBOOK API TIMEOUT INCREASED (FOR LARGE MEDIA FILES) ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        r = requests.get(f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}", timeout=30).json()
        for p in r.get('data', []):
            if p['id'] == page_id: return p['access_token']
    except Exception: pass
    return None

def post_text_to_facebook(page_id, page_token, text):
    try: return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': text, 'access_token': page_token}, timeout=45).status_code == 200
    except: return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try: return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': open(photo_path, 'rb')}, timeout=120).status_code == 200
    except: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': open(path, 'rb')}, timeout=120)
            if r.status_code == 200: att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        r_f = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token}, timeout=60)
        return r_f.status_code == 200
    except: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    # Added max timeout (3 mins) for Facebook processing chunk sized uploads slowly to stop random skipping error
    try: return requests.post(f"https://graph.facebook.com/v20.0/{page_id}/videos", data={'description': caption, 'access_token': page_token}, files={'file': open(video_path, 'rb')}, timeout=180).status_code == 200
    except: return False

def post_to_wordpress(wp_url, username, app_password, title, content):
    try: return requests.post(f"{wp_url}/wp-json/wp/v2/posts", json={'title': title, 'content': content, 'status': 'publish'}, headers={'Content-Type': 'application/json'}, auth=(username, app_password), timeout=60).status_code == 201
    except: return False

# --- THE MAIN SYSTEM ENGINE LOOP ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    if not rules: return memory

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else "Website"))

    tg_session = credentials.get('tg_session', '')
    tg_api_id, tg_api_hash = credentials.get('tg_api_id', ''), credentials.get('tg_api_hash', '')
    fb_user_token = credentials.get('fb_user_token', credentials.get('fb_token', ''))

    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        if tg_session and tg_api_id:
            try:
                tg_client = TelegramClient(StringSession(tg_session), int(tg_api_id), tg_api_hash)
                await tg_client.start()
            except Exception: tg_client = None

    curr_t = datetime.now(timezone.utc)

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        s_plat, d_plat = clean_platform(rule['source']), clean_platform(rule['destination'])
        s_ids, d_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()], [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        
        min_words, l_thres, kh_f = rule.get("min_words", 60), curr_t - timedelta(hours=rule.get("lookback_hours", 24.0)), rule.get("keep_hashtags", False)

        print(f"\n⚡ Processing Main Operation Matrix: {s_plat} ➔ {d_plat}")

        for s_id in s_ids:
            # A. T_GRAM
            if s_plat == "Telegram" and tg_client:
                last_id = memory.get(rule_key, 0)
                if isinstance(last_id, list): last_id = 0
                    
                for msg in reversed(await tg_client.get_messages(s_id, limit=30)):
                    if msg.date < l_thres or msg.id <= last_id: continue
                    c_txt = clean_text(msg.text, kh_f) if msg.text else ""
                    if rule['txt'] and len(c_txt.split()) < min_words: continue

                    if rule['txt'] and c_txt:
                        for d_id in d_ids:
                            if d_plat == "Facebook":
                                t = get_page_access_token(fb_user_token, d_id)
                                if t: post_text_to_facebook(d_id, t, c_txt)
                            elif d_plat == "Website": post_to_wordpress(d_id, credentials.get('wp_username'), credentials.get('wp_app_password'), "TG Update", c_txt)

                    if rule.get('img', True) and msg.photo:
                        p_path = await msg.download_media()
                        for d_id in d_ids:
                            if d_plat == "Facebook":
                                t = get_page_access_token(fb_user_token, d_id)
                                if t: post_photo_to_facebook(d_id, t, p_path, c_txt)
                        if os.path.exists(p_path): os.remove(p_path)

                    if rule['vid'] and msg.video:
                        v_path = await msg.download_media()
                        for d_id in d_ids:
                            if d_plat == "Facebook":
                                t = get_page_access_token(fb_user_token, d_id)
                                if t: post_video_to_facebook(d_id, t, v_path, c_txt)
                        if os.path.exists(v_path): os.remove(v_path)
                    last_id = max(last_id, msg.id)
                memory[rule_key] = last_id

            # B. WEB RSS (Fixed for server timeout fails when website gives blank connection delays)
            elif s_plat == "Website":
                try:
                    feed, p_links = feedparser.parse(s_id), memory.get(rule_key, [])
                    if not isinstance(p_links, list): p_links = []
                    new_links = list(p_links)

                    for e in reversed(feed.entries[:15]):
                        e_time = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc) if 'published_parsed' in e else curr_t
                        e_lnk = e.get('link', e.get('id', '')).strip()
                        
                        if not e_lnk.startswith('http') or e_time < l_thres or e_lnk in p_links: continue

                        r_d = e.summary if 'summary' in e else e.description if 'description' in e else ""
                        c_desc, f_cnt = strip_html(r_d), clean_text(e.title + " " + strip_html(r_d), kh_f)
                        if rule['txt'] and len(f_cnt.split()) < min_words: continue

                        img_urls = [enc.get('href') for enc in e.get('enclosures', []) if enc.get('href', '').endswith(('.jpg', '.png'))]
                        img_urls.extend(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', r_d, re.IGNORECASE))
                        try:
                            # 15s delay proxy server bypass request block error fix.
                            web_res = requests.get(e_lnk, headers=HEADERS, timeout=15)
                            if web_res.status_code == 200:
                                o_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)
                                if o_m and o_m.group(1) not in img_urls: img_urls.insert(0, o_m.group(1))
                        except Exception: pass

                        cln_img_urls = [u if u.startswith('http') else urljoin(e_lnk, u) for u in img_urls[:9]]
                        c_ti = clean_text(f"📝 {e.title}", kh_f)
                        final_tx = c_ti if rule.get('title_only', False) else f"{c_ti}\n\n{c_desc[:350]}...\n\n🔗 {e_lnk}"

                        photo_paths = []
                        if cln_img_urls and rule.get('img', True):
                            for idx, url in enumerate(cln_img_urls):
                                try:
                                    img_r = requests.get(url, headers=HEADERS, timeout=20)
                                    if img_r.status_code == 200:
                                        pt = f"tmpr_{hash(e_lnk)}_{idx}.jpg"
                                        with open(pt, 'wb') as fl: fl.write(img_r.content)
                                        photo_paths.append(pt)
                                except Exception: pass

                        posted = False
                        if rule['txt']:
                            for did in d_ids:
                                if d_plat == "Telegram" and tg_client:
                                    if photo_paths: await tg_client.send_file(did, photo_paths, caption=final_tx)
                                    else: await tg_client.send_message(did, final_tx)
                                    posted = True
                                elif d_plat == "Facebook":
                                    t = get_page_access_token(fb_user_token, did)
                                    if t:
                                        if len(photo_paths) > 1: posted = post_multi_photo_to_facebook(did, t, photo_paths, final_tx)
                                        elif len(photo_paths) == 1: posted = post_photo_to_facebook(did, t, photo_paths[0], final_tx)
                                        else: posted = post_text_to_facebook(did, t, final_tx)
                                            
                        for pt in photo_paths:
                            if os.path.exists(pt): os.remove(pt)
                        if posted:
                            print(f"  [+] Synced Latest Website Release Published Successfully! >> {e.title}")
                            new_links.append(e_lnk)
                            
                    memory[rule_key] = new_links[-50:]
                except Exception as ex: print(f"  [!] Fail in Secure Request Flow. Network API delay hit -> Website timeout Error!")

            # --- C. YOUTUBE COOKIE MASTER SCRIPT ---
            elif s_plat == "YouTube":
                try:
                    plinks = memory.get(rule_key, [])
                    if not isinstance(plinks, list): plinks = []
                    new_links = list(plinks)

                    feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={s_id}")

                    for e in reversed(feed.entries[:5]):
                        e_time = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc) if 'published_parsed' in e else curr_t
                        e_lnk = e.link
                        
                        if e_time < l_thres or e_lnk in plinks: continue
                        print(f"\n📺 Analyzing Unprocessed Missing Server Entry Frame >> {e.title}")

                        c_text = clean_text(e.title, kh_f)
                        v_path = f"tmp_v_{hash(e_lnk)}.mp4"
                        
                        dl_ok = False
                        if rule.get('vid', True):
                            dl_ok = download_youtube_video(e_lnk, v_path)
                            
                        posted = False
                        for did in d_ids:
                            if d_plat == "Facebook":
                                t = get_page_access_token(fb_user_token, did)
                                if t:
                                    if dl_ok and os.path.exists(v_path):
                                        print("  [>] Transmitting fully processed mp4 object backlink structure chunk network block Wait approximately roughly ±60 sec !!")
                                        posted = post_video_to_facebook(did, t, v_path, c_text)
                                    else:
                                        print("  [X] Failed native pull due to Extreme IP blockage. Doing Link Output Only Text Strategy Mode >> Post...")
                                        posted = post_text_to_facebook(did, t, f"🎥 {e.title}\n\n🔗 Source Watch: {e_lnk}")
                            
                            elif d_plat == "Telegram" and tg_client:
                                if dl_ok and os.path.exists(v_path):
                                    await tg_client.send_file(did, v_path, caption=c_text)
                                else: await tg_client.send_message(did, f"🎥 {e.title}\n\nWatch here: {e_lnk}")
                                posted = True

                        if v_path and os.path.exists(v_path): os.remove(v_path)
                        if posted:
                            new_links.append(e_lnk)
                            print("  [$$$] Upload Action Authenticated Safe Pass Sent Execution Loop Data Successful OK!")
                            
                    memory[rule_key] = new_links[-50:]
                except Exception as ex: print(f"  [!] Global Application Layer Failed Target Sync {ex}")

    if tg_client: await tg_client.disconnect()
    return memory

async def main():
    u = await process_sync(load_json(CONFIG_FILE, {}), load_json(MEMORY_FILE, {}))
    save_json(MEMORY_FILE, u)
    print("\n[■] Shutting down Main Instance Controller ")

if __name__ == "__main__":
    asyncio.run(main())