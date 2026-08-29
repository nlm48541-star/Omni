# -*- coding: utf-8 -*-
import os
import re
import asyncio
import requests
from PIL import Image
from telethon import TelegramClient
from telethon.sessions import StringSession

from config_manager import (
    CONFIG_FILE, MEMORY_FILE, HEADERS,
    load_json, save_json, get_credential,
    clean_text, clean_telegram_id, sanitize_filename
)
from ai_service import generate_job_data_and_script
from audio_engine import generate_voiceover_audio_pipeline
from tiktok_designer import prepare_tiktok_slides
from video_engine import render_vertical_video
from feed_manager import fetch_feed_entries, extract_article_images
from uploader_service import (
    get_page_access_token, post_photo_to_facebook,
    post_multi_photo_to_facebook, post_reel_to_facebook,
    post_video_to_facebook, upload_video_to_youtube,
    upload_video_to_tiktok_buffer, post_to_whatsapp_channel
)

def is_forbidden_title(title):
    """শুধুমাত্র টাইটেলে এনজিও বা ব্যাংক থাকলে তা স্কিপ করবে"""
    if not title: return False
    title_lower = str(title).lower()
    forbidden_keywords = ['এনজিও', 'ngo', 'ব্যাংক', 'bank']
    return any(k in title_lower for k in forbidden_keywords)

async def process_sync(config, memory):
    rules = config.get("rules", [])
    if not rules:
        print("[!] No sync rules found in automation_config.json")
        return memory

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else ("WhatsApp" if "WhatsApp" in p_str else "Website")))
    
    tg_session = get_credential(config, "tg_session", "TG_SESSION")
    tg_api_id = get_credential(config, "tg_api_id", "TG_API_ID")
    tg_api_hash = get_credential(config, "tg_api_hash", "TG_API_HASH")
    fb_user_token = get_credential(config, "fb_token", "FB_TOKEN") or get_credential(config, "fb_user_token", "FB_USER_TOKEN")
    render_wa_url = get_credential(config, "render_wa_url", "RENDER_WA_URL") or "https://wa-channel-bridge.onrender.com"
    yt_client_id = get_credential(config, "yt_client_id", "YT_CLIENT_ID")
    yt_client_secret = get_credential(config, "yt_client_secret", "YT_CLIENT_SECRET")
    yt_refresh_token = get_credential(config, "yt_refresh_token", "YT_REFRESH_TOKEN")

    tg_client = None
    if any(clean_platform(r['source']) == "Telegram" or clean_platform(r['destination']) == "Telegram" for r in rules):
        if tg_session and tg_api_id and tg_api_hash:
            try:
                tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
                await tg_client.start()
                print("  [+] Telegram Client Authenticated!")
            except Exception as e:
                print(f"  [!] Telegram Client Error: {e}")

    for idx, rule in enumerate(rules):
        rule_key = f"route_{idx}_{rule['source']}_{rule['destination']}"
        source_platform = clean_platform(rule['source'])
        dest_platform = clean_platform(rule['destination'])
        source_ids = [s.strip() for s in rule['source_id'].split(',') if s.strip()]
        dest_ids = [d.strip() for d in rule['dest_id'].split(',') if d.strip()]
        min_words = rule.get("min_words", 60)

        for source_id in source_ids:
            print(f"\n========================================================")
            print(f"[~] Checking Route ({source_platform} ➔ {dest_platform}): '{source_id}'")
            print(f"========================================================")

            if source_platform == "Website":
                feed = fetch_feed_entries(source_id)
                processed_links = memory.get(rule_key, [])
                if not isinstance(processed_links, list): processed_links = []
                new_processed_links = list(processed_links)

                for entry in reversed(feed.entries[:10]):
                    entry_link = entry.get('link', '').strip()
                    if not entry_link and 'links' in entry and entry.links:
                        entry_link = entry.links[0].get('href', '').strip()
                    if not entry_link: entry_link = entry.get('id', entry.get('guid', '')).strip()

                    if not entry_link or not entry_link.startswith(('http://', 'https://')): continue
                    if entry_link in processed_links: continue

                    title = entry.get('title', '').strip()

                    # ১. টাইটেল ফিল্টার: এনজিও / ব্যাংক থাকলে সাথে সাথে স্কিপ
                    if is_forbidden_title(title):
                        print(f"🚫 [FILTERED] Skipping '{title}' (Title contains forbidden keyword: NGO / Bank).")
                        new_processed_links.append(entry_link)
                        continue

                    print(f"\n🔥 [NEW CIRCULAR] Found: '{title}'")
                    new_processed_links.append(entry_link)

                    raw_desc = entry.get('summary', '') or entry.get('description', '')
                    raw_desc_clean = clean_text(raw_desc)
                    if rule.get('txt', True) and len(clean_text(title + " " + raw_desc_clean).split()) < min_words:
                        print(f"  [~] Skipping due to short word count (< {min_words} words).")
                        continue

                    # ২. মূল বিজ্ঞপ্তির ছবি ডাউনলোড
                    img_urls = extract_article_images(entry, entry_link, raw_desc)
                    downloaded_imgs = []
                    for i_idx, u in enumerate(img_urls):
                        try:
                            ir = requests.get(u, headers=HEADERS, timeout=10)
                            if ir.status_code == 200:
                                p = f"tmp_raw_{hash(entry_link)}_{i_idx}.jpg"
                                with open(p, 'wb') as f: f.write(ir.content)
                                downloaded_imgs.append(p)
                        except Exception: pass

                    # ৩. এআই দিয়ে ডাটা ও একক ১-মিনিটের স্ক্রিপ্ট তৈরি
                    job_data = generate_job_data_and_script(title, downloaded_imgs)
                    voiceover_script = job_data.get("voiceover_script", "")

                    # ৪. ElevenLabs দিয়ে শুধুমাত্র একটি অডিও তৈরি
                    single_audio_path = f"tmp_voice_{hash(entry_link)}.mp3"
                    audio_success = generate_voiceover_audio_pipeline(voiceover_script, single_audio_path)

                    # ৫. পোস্ট ক্যাপশন টেক্সট
                    contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন whatsapp 01540503092"
                    final_post_text = f"{clean_text(title)}{contact_sfx}" if rule.get('title_only', False) else f"{clean_text(title)}\n\n{raw_desc_clean[:280]}...{contact_sfx}"

                    # ৬. Facebook ও YouTube Shorts-এর জন্য মূল বিজ্ঞপ্তির ছবি দিয়ে একক ভিডিও তৈরি
                    fb_video_path = f"tmp_fb_yt_{hash(entry_link)}.mp4"
                    fb_source_imgs = downloaded_imgs if downloaded_imgs else prepare_tiktok_slides(job_data, f"fallback_{hash(entry_link)}")
                    
                    video_ready = False
                    if audio_success and os.path.exists(single_audio_path):
                        video_ready = render_vertical_video(fb_source_imgs, single_audio_path, fb_video_path)

                    # ৭. সবগুলো ফেসবুক পেজে একই ভিডিও আপলোড
                    if dest_platform == "Facebook" and video_ready:
                        for did in dest_ids:
                            token = get_page_access_token(fb_user_token, did)
                            if token:
                                print(f"  [+] Uploading Reel to Facebook Page '{did}'...")
                                if not post_reel_to_facebook(did, token, fb_video_path, title, final_post_text):
                                    post_video_to_facebook(did, token, fb_video_path, final_post_text)

                    # ৮. YouTube Shorts আপলোড (একই ভিডিও সরাসরি আপলোড হবে)
                    if video_ready and yt_client_id and yt_client_secret and yt_refresh_token:
                        print("  [+] Uploading Video to YouTube Shorts...")
                        upload_video_to_youtube(
                            yt_client_id, yt_client_secret, yt_refresh_token,
                            fb_video_path,
                            job_data.get("optimized_title", title),
                            job_data.get("video_description", final_post_text)
                        )

                    # ৯. TikTok-এর জন্য সেই একই অডিও + কাস্টম ইনফোগ্রাফিক স্লাইড দিয়ে ভিডিও তৈরি ও আপলোড
                    if audio_success and os.path.exists(single_audio_path):
                        print("  [~] Rendering Custom TikTok Infographic Video...")
                        tiktok_slides = prepare_tiktok_slides(job_data, output_prefix=f"tiktok_slide_{hash(entry_link)}")
                        tiktok_video_path = f"tmp_tiktok_{hash(entry_link)}.mp4"

                        if render_vertical_video(tiktok_slides, single_audio_path, tiktok_video_path):
                            print("  [+] Uploading Video to TikTok via Buffer...")
                            upload_video_to_tiktok_buffer(tiktok_video_path, final_post_text, config)

                        # টিকটকের টেম্প ফাইল ক্লিনআপ
                        if os.path.exists(tiktok_video_path): os.remove(tiktok_video_path)
                        for sp in tiktok_slides:
                            if os.path.exists(sp): os.remove(sp)

                    # ১০. Telegram, WhatsApp ও Facebook Photo Albums ডেলিভারি
                    for did in dest_ids:
                        if dest_platform == "Telegram" and tg_client:
                            clean_tg = clean_telegram_id(did)
                            try:
                                if downloaded_imgs: await tg_client.send_file(clean_tg, downloaded_imgs, caption=final_post_text)
                                else: await tg_client.send_message(clean_tg, final_post_text)
                            except Exception: pass

                        elif dest_platform == "WhatsApp":
                            post_to_whatsapp_channel(render_wa_url, did, final_post_text, downloaded_imgs)

                    # ১১. ক্লিনআপ (সার্কুলার ছবি, মেইন ভিডিও ও অডিও ফাইল মুছে ফেলা)
                    if os.path.exists(fb_video_path): os.remove(fb_video_path)
                    if os.path.exists(single_audio_path): os.remove(single_audio_path)
                    for dp in downloaded_imgs:
                        if os.path.exists(dp): os.remove(dp)

                memory[rule_key] = new_processed_links[-50:]

    if tg_client:
        await tg_client.disconnect()
    return memory

async def main():
    config = load_json(CONFIG_FILE, {})
    memory = load_json(MEMORY_FILE, {})
    updated_memory = await process_sync(config, memory)
    save_json(MEMORY_FILE, updated_memory)
    print("\n✅ Task Executed Successfully.")

if __name__ == "__main__":
    asyncio.run(main())
