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

# Real Browser Headers to bypass Cloudflare / Security Blocks
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}

# Helper functions to handle config and memory checkpoints
def load_json(filepath, default_val):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default_val

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

# --- 1. CONTENT CLEANER REGEX & HTML STRIPPER ---
def strip_html(text):
    """Removes HTML tags from the website content description."""
    if not text:
        return ""
    clean_re = re.compile('<.*?>')
    return re.sub(clean_re, '', text)

def clean_text(text, keep_hashtags=False):
    """
    Cleans text content based on rules. Mentions (@word) are ALWAYS deleted.
    Hashtags (#word) are conditionally deleted based on the keep_hashtags flag.
    """
    if not text:
        return ""
    # Always remove @mentions
    text = re.sub(r'@\w+', '', text)
    
    # Conditionally remove hashtags and keywords attached to them
    if not keep_hashtags:
        text = re.sub(r'#\w+', '', text)
        
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

# --- 2. YOUTUBE VIDEO DOWNLOADER (YT-DLP WITH ANDROID CLIENT BYPASS) ---
def download_youtube_video(video_url, output_path):
    """Downloads YouTube Video or Shorts safely in MP4 format using Android client bypass."""
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        # BYPASS YOUTUBE BOT DETECTOR: Force emulating official Android App Client
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web_creator']
            }
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return True
    except Exception as e:
        print(f"  [!] yt-dlp download exception: {e}")
        return False

# --- 3. FACEBOOK ACCESS ENGINE WITH DETAILED ERROR LOGGING ---
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
        if r.status_code == 200:
            return True
        else:
            print(f"  [!] Facebook API Error (Text Post Reject): {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"  [!] Facebook Request Exception (Text): {e}")
        return False

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
    payload = {'caption': caption, 'access_token': page_token}
    try:
        files = {'source': open(photo_path, 'rb')}
        r = requests.post(url, data=payload, files=files)
        if r.status_code == 200:
            return True
        else:
            print(f"  [!] Facebook API Error (Photo Post Reject): {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"  [!] Facebook Request Exception (Photo): {e}")
        return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        attached_media = []
        for idx, path in enumerate(photo_paths):
            url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
            payload = {
                'published': 'false',
                'access_token': page_token
            }
            files = {'source': open(path, 'rb')}
            r = requests.post(url, data=payload, files=files)
            if r.status_code == 200:
                photo_id = r.json().get('id')
                attached_media.append({"media_fbid": photo_id})
                print(f"  [+] Uploaded unpublished photo {idx+1}/{len(photo_paths)}: ID {photo_id}")
            else:
                print(f"  [!] Error uploading photo {idx+1}: {r.status_code} - {r.text}")

        if not attached_media:
            print("  [!] Error: No photos could be uploaded to Facebook.")
            return False

        feed_url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
        feed_payload = {
            'message': caption,
            'attached_media': json.dumps(attached_media),
            'access_token': page_token
        }
        r_feed = requests.post(feed_url, data=feed_payload)
        if r_feed.status_code == 200:
            return True
        else:
            print(f"  [!] Error publishing Album Feed Post: {r_feed.status_code} - {r_feed.text}")
            return False
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
            print(f"  [!] Facebook API Error (Video Post Reject): {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"  [!] Facebook Request Exception (Video): {e}")
        return False

# --- 4. WEBSITE (WORDPRESS REST API) ENGINE ---
def post_to_wordpress(wp_url, username, app_password, title, content):
    url = f"{wp_url}/wp-json/wp/v2/posts"
    headers = {'Content-Type': 'application/json'}
    payload = {
        'title': title,
        'content': content,
        'status': 'publish'
    }
    r = requests.post(url, json=payload, headers=headers, auth=(username, app_password))
    return r.status_code == 201

# --- 5. CORE PIPELINE CONTROLLER WITH MULTI-IMAGE ALBUMS ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    
    if not rules:
        print("[!] No active routes configured. Exiting.")
        return memory

    # Determine real platform names after clearing emojis from config string
    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else "Website"))

    # Safe Fallbacks for all dictionary credentials keys to prevent KeyErrors
    tg_session = credentials.get('tg_session', '')
    tg_api_id = credentials.get('tg_api_id', '')
    tg_api_hash = credentials.get('tg_api_hash', '')
    wp_username = credentials.get('wp_username', '')
    wp_app_password = credentials.get('wp_app_password', '')
    fb_user_token = credentials.get('fb_user_token', credentials.get('fb_token', ''))

    # Pre-authorize Telegram Client only if needed
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
        
        # Cleaned source and destination platforms from emoji decorators
        source_platform = clean_platform(rule['source'])
        dest_platform = clean_platform(rule['destination'])

        # Split multiple sources and destinations (comma-separated lists support)
        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        
        min_words = rule.get("min_words", 60)
        lookback_hours = rule.get("lookback_hours", 1.0)
        lookback_threshold = current_time - timedelta(hours=lookback_hours)
        keep_hashtags = rule.get("keep_hashtags", False)

        print(f"\n⚡ Processing Sync: {source_platform} ({len(source_ids)} sources) ➔ {dest_platform} ({len(dest_ids)} outputs)")

        for source_id in source_ids:
            try:
                # --- A. TELEGRAM SOURCE AUTOMATION ---
                if source_platform == "Telegram" and tg_client:
                    last_id = memory.get(rule_key, 0)
                    if isinstance(last_id, list): 
                        last_id = 0
                        
                    messages = await tg_client.get_messages(source_id, limit=30)
                    for msg in reversed(messages):
                        if msg.date < lookback_threshold:
                            continue
                        if msg.id <= last_id:
                            continue

                        cleaned_text = clean_text(msg.text, keep_hashtags=keep_hashtags) if msg.text else ""
                        word_count = len(cleaned_text.split())

                        # Skip if the copied text is shorter than words limit
                        if rule['txt'] and word_count < min_words:
                            print(f"[-] Skipped TG Post: Word count ({word_count}) is less than required ({min_words}).")
                            continue

                        # Publish Texts
                        if rule['txt'] and cleaned_text:
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token:
                                        post_text_to_facebook(dest_id, token, cleaned_text)
                                elif dest_platform == "Website":
                                    post_to_wordpress(dest_id, wp_username, wp_app_password, "Telegram Update", cleaned_text)

                        # Publish Images
                        if rule.get('img', True) and msg.photo:
                            photo_path = await msg.download_media()
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token:
                                        post_photo_to_facebook(dest_id, token, photo_path, cleaned_text)
                            if os.path.exists(photo_path):
                                os.remove(photo_path)

                        # Publish Videos
                        if rule['vid'] and msg.video:
                            video_path = await msg.download_media()
                            for dest_id in dest_ids:
                                if dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token:
                                        post_video_to_facebook(dest_id, token, video_path, cleaned_text)
                            if os.path.exists(video_path):
                                os.remove(video_path)
                        
                        last_id = max(last_id, msg.id)
                    memory[rule_key] = last_id

                # --- B. WEBSITE SOURCE (RSS FEED) AUTOMATION ---
                elif source_platform == "Website":
                    feed = feedparser.parse(source_id)
                    
                    processed_links = memory.get(rule_key, [])
                    if not isinstance(processed_links, list):
                        processed_links = []
                        
                    new_processed_links = list(processed_links)

                    for entry in reversed(feed.entries[:15]):
                        if 'published_parsed' in entry and entry.published_parsed:
                            entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                        else:
                            entry_time = current_time

                        # --- DYNAMIC SAFE URL EXTRACTION WITH FALLBACKS ---
                        entry_link = entry.get('link', '').strip()
                        if not entry_link and 'links' in entry and len(entry.links) > 0:
                            entry_link = entry.links[0].get('href', '').strip()
                        if not entry_link:
                            entry_link = entry.get('id', entry.get('guid', '')).strip()

                        # Safety gate: Skip if absolutely no valid URL can be parsed
                        if not entry_link or not entry_link.startswith(('http://', 'https://')):
                            print(f"📝 Found post: {entry.title} (Published: {entry_time})")
                            print(f"  [!] Skipped: Invalid or empty URL link.")
                            continue
                        
                        print(f"📝 Found post: {entry.title} (Published: {entry_time})")
                        print(f"  [~] Article URL: {entry_link}")

                        if entry_time < lookback_threshold:
                            print(f"  [-] Skipped: Post is older than lookback limit ({lookback_hours} hours).")
                            continue

                        if entry_link in processed_links:
                            print(f"  [-] Skipped: Already processed previously (Duplicate Guard).")
                            continue

                        # Extract description/summary
                        raw_description = entry.summary if 'summary' in entry else (entry.description if 'description' in entry else "")
                        cleaned_description = strip_html(raw_description)

                        # Count words on full post content (Title + Body)
                        full_content_for_counting = clean_text(entry.title + " " + cleaned_description, keep_hashtags=keep_hashtags)
                        word_count = len(full_content_for_counting.split())

                        if rule['txt'] and word_count < min_words:
                            print(f"  [-] Skipped: Word count ({word_count}) is less than required ({min_words}).")
                            continue

                        # --- MULTI-IMAGE EXTRACTION FLOW ---
                        img_urls = []
                        # 1. Grab image from enclosure
                        if 'enclosures' in entry and len(entry.enclosures) > 0:
                            for enc in entry.enclosures:
                                href = enc.get('href', '')
                                if enc.get('type', '').startswith('image/') or href.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                                    img_urls.append(href)
                        # 2. Grab from media tags
                        if 'media_content' in entry and len(entry.media_content) > 0:
                            for m_content in entry.media_content:
                                url = m_content.get('url')
                                if url and url not in img_urls:
                                    img_urls.append(url)
                        if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
                            for m_thumb in entry.media_thumbnail:
                                url = m_thumb.get('url')
                                if url and url not in img_urls:
                                    img_urls.append(url)
                        # 3. Grab from description HTML tags
                        desc_imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_description, re.IGNORECASE)
                        for url in desc_imgs:
                            if url and url not in img_urls:
                                img_urls.append(url)

                        # 4. ROBUST WEB SCRAPER FALLBACK (Scrapes actual website post for images with Chrome Headers)
                        try:
                            print(f"  [~] Scraping website body for multiple images: {entry_link}")
                            web_res = requests.get(entry_link, headers=HEADERS, timeout=10)
                            print(f"  [~] Web scrape HTTP Response Status: {web_res.status_code}")
                            if web_res.status_code == 200:
                                # Fetch og:image (featured image) first
                                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)
                                if not og_match:
                                    og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', web_res.text, re.IGNORECASE)
                                
                                # Temporary list to collect new scraped images
                                scraped_imgs = []
                                if og_match:
                                    page_img = og_match.group(1)
                                    scraped_imgs.append(page_img)

                                # Scan article body context for more images
                                body_imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE)
                                for url in body_imgs:
                                    # Filter out icons, UI elements
                                    if any(logo in url.lower() for logo in ['logo', 'icon', 'avatar', 'gravatar', 'banner', 'loader', 'theme', 'spinner', 'widget', 'footer', 'header']):
                                            continue
                                    if url not in scraped_imgs:
                                        scraped_imgs.append(url)
                                        
                                # Merge scraped images with existing RSS images safely
                                for img in scraped_imgs:
                                    if img not in img_urls:
                                        img_urls.append(img)
                        except Exception as e:
                            print(f"  [!] Failed to scrape website for multi-images: {e}")

                        # Clean relative URLs and limit total images to 9 (Facebook limit/safety)
                        cleaned_img_urls = []
                        for url in img_urls[:9]:
                            if not url.startswith(('http://', 'https://')):
                                url = urljoin(entry_link, url)
                            if url not in cleaned_img_urls:
                                cleaned_img_urls.append(url)

                        # Timing / Title Only Filter check
                        title_only_flag = rule.get('title_only', False)
                        
                        # Format final published text
                        if title_only_flag:
                            final_post_text = clean_text(f"📝 {entry.title}", keep_hashtags=keep_hashtags)
                        else:
                            short_description = (cleaned_description[:350] + "...") if len(cleaned_description) > 350 else cleaned_description
                            if short_description:
                                final_post_text = clean_text(f"📝 {entry.title}\n\n{short_description}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)
                            else:
                                final_post_text = clean_text(f"📝 {entry.title}\n\nRead more: {entry_link}", keep_hashtags=keep_hashtags)

                        # Download all found images locally using Chrome Headers
                        photo_paths = []
                        if cleaned_img_urls and rule.get('img', True):
                            for idx, url in enumerate(cleaned_img_urls):
                                try:
                                    print(f"  [+] Downloading image {idx+1}/{len(cleaned_img_urls)}: {url}")
                                    img_response = requests.get(url, headers=HEADERS, timeout=10)
                                    if img_response.status_code == 200:
                                        path = f"temp_rss_img_{hash(entry_link)}_{idx}.jpg"
                                        with open(path, 'wb') as f:
                                            f.write(img_response.content)
                                        photo_paths.append(path)
                                except Exception as e:
                                    print(f"  [!] Warning: Failed to download RSS image {idx+1}: {e}")

                        # Post Publishing logic based on photo counts
                        posted_successfully = False
                        if rule['txt']:
                            for dest_id in dest_ids:
                                if dest_platform == "Telegram" and tg_client:
                                    if photo_paths:
                                        await tg_client.send_file(dest_id, photo_paths, caption=final_post_text)
                                    else:
                                        await tg_client.send_message(dest_id, final_post_text)
                                    posted_successfully = True
                                        
                                elif dest_platform == "Facebook":
                                    token = get_page_access_token(fb_user_token, dest_id)
                                    if token:
                                        if len(photo_paths) > 1:
                                            # Publish as a multi-photo album post
                                            posted_successfully = post_multi_photo_to_facebook(dest_id, token, photo_paths, final_post_text)
                                        elif len(photo_paths) == 1:
                                            # Publish as a single photo post
                                            posted_successfully = post_photo_to_facebook(dest_id, token, photo_paths[0], final_post_text)
                                        else:
                                            # Publish as a text-only status post
                                            posted_successfully = post_text_to_facebook(dest_id, token, final_post_text)
                                            
                        # Delete all temporary files to clean workspace
                        for path in photo_paths:
                            if os.path.exists(path):
                                os.remove(path)
                        
                        if posted_successfully:
                            print(f"  [+] Success: Successfully posted '{entry.title}' with {len(photo_paths)} images!")
                            new_processed_links.append(entry_link)
                        else:
                            print(f"  [!] Fail: Skipping memory logging because post failed.")

                    if len(new_processed_links) > 50:
                        new_processed_links = new_processed_links[-50:]
                    memory[rule_key] = new_processed_links

            # --- C. YOUTUBE SOURCE AUTOMATION (Uses native RSS XML under the hood with Android client bypass) ---
            elif source_platform == "YouTube":
                processed_links = memory.get(rule_key, [])
                if not isinstance(processed_links, list):
                    processed_links = []
                new_processed_links = list(processed_links)

                rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={source_id}"
                feed = feedparser.parse(rss_url)

                for entry in reversed(feed.entries[:5]): # Scan latest 5 videos to prevent timeout limits
                    if 'published_parsed' in entry and entry.published_parsed:
                        entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                    else:
                        entry_time = current_time

                    entry_link = entry.link
                    print(f"📝 Found YouTube Video: {entry.title} (Published: {entry_time})")

                    if entry_time < lookback_threshold:
                        print(f"  [-] Skipped: Video is older than lookback limit ({lookback_hours} hours).")
                        continue

                    if entry_link in processed_links:
                        print(f"  [-] Skipped: Already processed previously (Duplicate Guard).")
                        continue

                    # Clean title for captioning
                    caption_text = clean_text(entry.title, keep_hashtags=keep_hashtags)

                    # Download YouTube Video if Video Sync is enabled in UI
                    video_path = f"temp_yt_video_{hash(entry_link)}.mp4"
                    download_success = False
                    
                    if rule.get('vid', True):
                        print(f"  [~] Downloading YouTube video via yt-dlp: {entry_link}")
                        download_success = download_youtube_video(entry_link, video_path)
                    
                    if not download_success:
                        print("  [!] Failed to download video, falling back to link post.")
                        video_path = None

                    posted_successfully = False
                    for dest_id in dest_ids:
                        if dest_platform == "Telegram" and tg_client:
                            if video_path and os.path.exists(video_path):
                                await tg_client.send_file(dest_id, video_path, caption=caption_text)
                            else:
                                await tg_client.send_message(dest_id, f"🎥 {entry.title}\n\nWatch here: {entry_link}")
                            posted_successfully = True
                                
                        elif dest_platform == "Facebook":
                            token = get_page_access_token(fb_user_token, dest_id)
                            if token:
                                if video_path and os.path.exists(video_path):
                                    posted_successfully = post_video_to_facebook(dest_id, token, video_path, caption_text)
                                else:
                                    posted_successfully = post_text_to_facebook(dest_id, token, f"🎥 {entry.title}\n\nWatch here: {entry_link}")
                                    
                    # Clean up temporary video file
                    if video_path and os.path.exists(video_path):
                        os.remove(video_path)
                        
                    if posted_successfully:
                        print(f"  [+] Success: Successfully posted '{entry.title}' to destination!")
                        new_processed_links.append(entry_link)
                    else:
                        print(f"  [!] Fail: Skipping memory logging because post failed.")

                if len(new_processed_links) > 50:
                    new_processed_links = new_processed_links[-50:]
                memory[rule_key] = new_processed_links
                
        except Exception as e:
            print(f"  [!] FATAL PIPELINE EXCEPTION during source {source_id}: {e}")

    if tg_client:
        await tg_client.disconnect()
        
    return memory

async def main():
    config = load_json(CONFIG_FILE, {})
    memory = load_json(MEMORY_FILE, {})
    
    updated_memory = await process_sync(config, memory)
    save_json(MEMORY_FILE, updated_memory)
    print("\n🎉 OmniSync Master Process Completed!")

if __name__ == "__main__":
    asyncio.run(main())