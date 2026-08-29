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
                    print(f"\n🔥 [NEW CIRCULAR] Found: '{title}'")
                    new_processed_links.append(entry_link)

                    raw_desc = entry.get('summary', '') or entry.get('description', '')
                    raw_desc_clean = clean_text(raw_desc)
                    if rule.get('txt', True) and len(clean_text(title + " " + raw_desc_clean).split()) < min_words:
                        print(f"  [~] Skipping due to short word count (< {min_words} words).")
                        continue

                    # ১. ইমেজ ডাউনলোড
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

                    # ২. এআই দিয়ে স্ট্রাকচার্ড ডাটা ও ১-মিনিটের স্ক্রিপ্ট তৈরি
                    job_data = generate_job_data_and_script(title, downloaded_imgs)
                    voiceover_script = job_data.get("voiceover_script", "")

                    # ৩. ElevenLabs দিয়ে একবারই অডিও জেনারেট
                    gen_audio_path = f"tmp_voice_{hash(entry_link)}.mp3"
                    audio_success = generate_voiceover_audio_pipeline(voiceover_script, gen_audio_path)

                    # ৪. TikTok / Reels এর জন্য ব্যাকগ্রাউন্ড + ফন্ট দিয়ে স্লাইড তৈরি
                    slide_paths = prepare_tiktok_slides(job_data, output_prefix=f"slide_{hash(entry_link)}")

                    # ৫. টেক্সট পোস্ট ডেলিভারি (Telegram / Facebook Feed / WhatsApp)
                    contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন whatsapp 01540503092"
                    final_post_text = f"{clean_text(title)}{contact_sfx}" if rule.get('title_only', False) else f"{clean_text(title)}\n\n{raw_desc_clean[:280]}...{contact_sfx}"

                    for did in dest_ids:
                        if dest_platform == "Telegram" and tg_client:
                            clean_tg = clean_telegram_id(did)
                            try:
                                if downloaded_imgs: await tg_client.send_file(clean_tg, downloaded_imgs, caption=final_post_text)
                                else: await tg_client.send_message(clean_tg, final_post_text)
                            except Exception: pass

                        elif dest_platform == "Facebook":
                            token = get_page_access_token(fb_user_token, did)
                            if token:
                                if len(downloaded_imgs) > 1: post_multi_photo_to_facebook(did, token, downloaded_imgs, final_post_text)
                                elif len(downloaded_imgs) == 1: post_photo_to_facebook(did, token, downloaded_imgs[0], final_post_text)

                        elif dest_platform == "WhatsApp":
                            post_to_whatsapp_channel(render_wa_url, did, final_post_text, downloaded_imgs)

                    # ৬. ভিডিও রেন্ডারিং ও একক অডিও দিয়ে সর্বত্র আপলোড (FB Reel, YouTube Shorts, TikTok)
                    if audio_success and os.path.exists(gen_audio_path) and slide_paths:
                        video_out = f"final_reel_{hash(entry_link)}.mp4"
                        if render_vertical_video(slide_paths, gen_audio_path, video_out):
                            # Facebook Reel
                            if dest_platform == "Facebook":
                                for did in dest_ids:
                                    token = get_page_access_token(fb_user_token, did)
                                    if token:
                                        if not post_reel_to_facebook(did, token, video_out, title, final_post_text):
                                            post_video_to_facebook(did, token, video_out, final_post_text)
                            
                            # YouTube Shorts
                            if yt_client_id and yt_client_secret and yt_refresh_token:
                                upload_video_to_youtube(yt_client_id, yt_client_secret, yt_refresh_token, video_out, job_data.get("optimized_title", title), job_data.get("video_description", final_post_text))
                                print(f"  [+] Published to YouTube Shorts!")

                            # TikTok via Buffer
                            upload_video_to_tiktok_buffer(video_out, final_post_text, config)

                        # ক্লিনআপ
                        if os.path.exists(video_out): os.remove(video_out)

                    # টেম্প ফাইল ডিলিট
                    if os.path.exists(gen_audio_path): os.remove(gen_audio_path)
                    for sp in slide_paths:
                        if os.path.exists(sp): os.remove(sp)
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
