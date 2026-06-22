import os
import re
import json
import asyncio
import requests
import feedparser
from time import mktime
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

CONFIG_FILE = "automation_config.json"
MEMORY_FILE = "bot_memory.json"

# Helper functions to handle config and memory checkpoints
def load_json(filepath, default_val):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default_val

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

# --- 1. CONTENT CLEANER REGEX (HASHTAG/TAG REMOVER) ---
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

# --- 2. FACEBOOK ACCESS ENGINE ---
def get_page_access_token(master_user_token, page_id):
    url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}"
    try:
        r = requests.get(url).json()
        pages = r.get('data', [])
        for page in pages:
            if page['id'] == page_id:
                return page['access_token']
    except Exception as e:
        print(f"[!] Error fetching Page Token from User Token: {e}")
    return None

def post_text_to_facebook(page_id, page_token, text):
    url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
    payload = {'message': text, 'access_token': page_token}
    r = requests.post(url, data=payload)
    return r.status_code == 200

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
    payload = {'caption': caption, 'access_token': page_token}
    files = {'source': open(photo_path, 'rb')}
    r = requests.post(url, data=payload, files=files)
    return r.status_code == 200

def post_video_to_facebook(page_id, page_token, video_path, caption):
    url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
    payload = {'description': caption, 'access_token': page_token}
    files = {'file': open(video_path, 'rb')}
    r = requests.post(url, data=payload, files=files)
    return r.status_code == 200

# --- 3. WEBSITE (WORDPRESS REST API) ENGINE ---
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

# --- 4. CORE PIPELINE CONTROLLER ---
async def process_sync(config, memory):
    credentials = config.get("credentials", {})
    rules = config.get("rules", [])
    
    if not rules:
        print("[!] No active routes configured. Exiting.")
        return memory

    # Determine real platform names after clearing emojis from config string
    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else "Website")

    # Pre-authorize Telegram Client only if needed
    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        tg_client = TelegramClient(StringSession(credentials['tg_session']), int(credentials['tg_api_id']), credentials['tg_api_hash'])
        await tg_client.start()

    current_time = datetime.now(timezone.utc)

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        last_id = memory.get(rule_key, 0)
        
        # Cleaned source and destination platforms from emoji decorators
        source_platform = clean_platform(rule['source'])
        dest_platform = clean_platform(rule['destination'])

        # Split multiple sources and destinations (comma-separated lists support)
        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        
        min_words = rule.get("min_words", 60)
        lookback_hours = rule.get("lookback_hours", 1.0)
        lookback_threshold = current_time - timedelta(hours=lookback_hours)

        print(f"\n⚡ Processing Sync: {source_platform} ({len(source_ids)} sources) ➔ {dest_platform} ({len(dest_ids)} outputs)")

        for source_id in source_ids:
            # --- A. TELEGRAM SOURCE AUTOMATION ---
            if source_platform == "Telegram" and tg_client:
                messages = await tg_client.get_messages(source_id, limit=30)
                for msg in reversed(messages):
                    if msg.date < lookback_threshold:
                        continue
                    if msg.id <= last_id:
                        continue

                    cleaned_text = clean_text(msg.text) if msg.text else ""
                    word_count = len(cleaned_text.split())

                    # Skip if the copied text is shorter than words limit
                    if rule['txt'] and word_count < min_words:
                        print(f"[-] Skipped TG Post: Word count ({word_count}) is less than required ({min_words}).")
                        continue

                    # Publish Texts to all destination outputs
                    if rule['txt'] and cleaned_text:
                        for dest_id in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(credentials['fb_user_token'], dest_id)
                                if token:
                                    post_text_to_facebook(dest_id, token, cleaned_text)
                            elif dest_platform == "Website":
                                post_to_wordpress(dest_id, credentials['wp_username'], credentials['wp_app_password'], "Telegram Update", cleaned_text)

                    # Publish Images to all destination outputs
                    if rule.get('img', True) and msg.photo:
                        photo_path = await msg.download_media()
                        for dest_id in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(credentials['fb_user_token'], dest_id)
                                if token:
                                    post_photo_to_facebook(dest_id, token, photo_path, cleaned_text)
                        if os.path.exists(photo_path):
                            os.remove(photo_path)

                    # Publish Videos to all destination outputs
                    if rule['vid'] and msg.video:
                        video_path = await msg.download_media()
                        for dest_id in dest_ids:
                            if dest_platform == "Facebook":
                                token = get_page_access_token(credentials['fb_user_token'], dest_id)
                                if token:
                                    post_video_to_facebook(dest_id, token, video_path, cleaned_text)
                        if os.path.exists(video_path):
                            os.remove(video_path)
                    
                    last_id = max(last_id, msg.id)

            # --- B. WEBSITE SOURCE (RSS FEED) AUTOMATION ---
            elif source_platform == "Website":
                feed = feedparser.parse(source_id)
                for entry in reversed(feed.entries[:15]):
                    entry_time = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                    if entry_time < lookback_threshold:
                        continue

                    entry_id = hash(entry.link)
                    if entry_id <= last_id:
                        continue

                    # 1. Extract raw description/content
                    raw_description = entry.summary if 'summary' in entry else (entry.description if 'description' in entry else "")
                    cleaned_description = strip_html(raw_description)

                    # 2. Count words on the FULL post content (Title + Description Body)
                    full_content_for_counting = clean_text(entry.title + " " + cleaned_description)
                    word_count = len(full_content_for_counting.split())

                    # Skip if the actual website post doesn't meet word limit requirements
                    if rule['txt'] and word_count < min_words:
                        print(f"[-] Skipped Web Post: Word count ({word_count}) is less than required ({min_words}).")
                        continue

                    # 3. Dynamic Image Extraction Logic from RSS Feed tags
                    img_url = None
                    if 'enclosures' in entry and len(entry.enclosures) > 0:
                        for enc in entry.enclosures:
                            if enc.get('type', '').startswith('image/'):
                                img_url = enc.get('href')
                                break
                    if not img_url and 'media_content' in entry and len(entry.media_content) > 0:
                        img_url = entry.media_content[0].get('url')
                    if not img_url and 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
                        img_url = entry.media_thumbnail[0].get('url')
                    # Fallback: Regex matching for any embedded HTML img tag inside raw description
                    if not img_url:
                        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_description)
                        if img_match:
                            img_url = img_match.group(1)

                    # Truncating description if too long to keep posts elegant
                    short_description = (cleaned_description[:350] + "...") if len(cleaned_description) > 350 else cleaned_description
                    
                    if short_description:
                        final_post_text = clean_text(f"📝 {entry.title}\n\n{short_description}\n\nRead more: {entry.link}")
                    else:
                        final_post_text = clean_text(f"📝 {entry.title}\n\nRead more: {entry.link}")

                    # Download RSS Image locally if image toggle is enabled
                    photo_path = None
                    if img_url and rule.get('img', True):
                        try:
                            img_response = requests.get(img_url, timeout=10)
                            if img_response.status_color == 200 or img_response.content:
                                photo_path = f"temp_rss_img_{entry_id}.jpg"
                                with open(photo_path, 'wb') as f:
                                    f.write(img_response.content)
                        except Exception as e:
                            print(f"[!] Warning: Failed to download RSS image: {e}")
                            photo_path = None

                    # 4. Post Publishing on Destination
                    if rule['txt']:
                        for dest_id in dest_ids:
                            if dest_platform == "Telegram" and tg_client:
                                if photo_path:
                                    await tg_client.send_file(dest_id, photo_path, caption=final_post_text)
                                else:
                                    await tg_client.send_message(dest_id, final_post_text)
                                    
                            elif dest_platform == "Facebook":
                                token = get_page_access_token(credentials['fb_user_token'], dest_id)
                                if token:
                                    if photo_path:
                                        # Posts on Facebook as a Photo Post with text as caption
                                        post_photo_to_facebook(dest_id, token, photo_path, final_post_text)
                                    else:
                                        # Posts as a Text Post
                                        post_text_to_facebook(dest_id, token, final_post_text)
                                        
                    # Delete the downloaded temp image to keep workflow clean
                    if photo_path and os.path.exists(photo_path):
                        os.remove(photo_path)
                    
                    last_id = entry_id

        # Save checkpoint
        memory[rule_key] = last_id

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