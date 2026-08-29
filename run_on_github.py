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
from ai_service import generate_job_data_and_multi_scripts
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

                    # ১. মূল নিয়োগ বিজ্ঞপ্তির ছবি ডাউনলোড
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

                    # ২. ফেসবুক পেজের সংখ্যা অনুযায়ী এআই স্ক্রিপ্ট ও স্ট্রাকচার্ড ডাটা তৈরি
                    fb_dest_ids = dest_ids if dest_platform == "Facebook" else []
                    num_fb_pages = max(1, len(fb_dest_ids))

                    job_data = generate_job_data_and_multi_scripts(title, downloaded_imgs, num_scripts=num_fb_pages)
                    scripts = job_data.get("voiceover_scripts", [])

                    # ৩. প্রতিটি ফেসবুক পেজের জন্য আলাদা আলাদা ভয়েস দিয়ে অডিও তৈরি
                    fb_audios = []
                    for v_idx, script in enumerate(scripts):
                        a_path = f"tmp_voice_{hash(entry_link)}_{v_idx}.mp3"
                        if generate_voiceover_audio_pipeline(script, a_path, voice_index=v_idx):
                            fb_audios.append(a_path)
                        else:
                            if fb_audios: fb_audios.append(fb_audios[0])

                    # ৪. ফেসবুক ও ইউটিউবের জন্য ভিডিও রেন্ডারিং (মূল সার্কুলার ইমেজ দিয়ে)
                    fb_source_imgs = downloaded_imgs if downloaded_imgs else prepare_tiktok_slides(job_data, f"fallback_{hash(entry_link)}")
                    fb_videos = []

                    for v_idx, a_path in enumerate(fb_audios):
                        v_path = f"tmp_fb_reel_{hash(entry_link)}_{v_idx}.mp4"
                        if render_vertical_video(fb_source_imgs, a_path, v_path):
                            fb_videos.append({"video": v_path, "audio": a_path})

                    # ৫. পোস্টের টেক্সট ও কল-টু-অ্যাকশন
                    contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন whatsapp 01540503092"
                    final_post_text = f"{clean_text(title)}{contact_sfx}" if rule.get('title_only', False) else f"{clean_text(title)}\n\n{raw_desc_clean[:280]}...{contact_sfx}"

                    # ৬. ফেসবুক পেজগুলোতে ভিন্ন ভিন্ন ভিডিও আপলোড
                    if dest_platform == "Facebook" and fb_videos:
                        for idx_p, did in enumerate(dest_ids):
                            token = get_page_access_token(fb_user_token, did)
                            if token:
                                current_v = fb_videos[idx_p % len(fb_videos)]["video"]
                                print(f"  [+] Uploading Facebook Reel (Voice #{ (idx_p % len(fb_videos)) + 1 }) to Page '{did}'...")
                                if not post_reel_to_facebook(did, token, current_v, title, final_post_text):
                                    post_video_to_facebook(did, token, current_v, final_post_text)

                    # ৭. YouTube Shorts আপলোড (১ম ফেসবুক পেজের তৈরি ভিডিও সরাসরি ব্যবহার করবে)
                    if fb_videos and yt_client_id and yt_client_secret and yt_refresh_token:
                        primary_video = fb_videos[0]["video"]
                        print("  [+] Uploading Primary Video to YouTube Shorts...")
                        upload_video_to_youtube(
                            yt_client_id, yt_client_secret, yt_refresh_token,
                            primary_video,
                            job_data.get("optimized_title", title),
                            job_data.get("video_description", final_post_text)
                        )

                    # ৮. TikTok-এর জন্য আলাদা ভিডিও জেনারেশন ও আপলোড (Backgrounds + 4 Fonts + Voice 1 অডিও)
                    if fb_audios:
                        primary_audio = fb_audios[0]
                        print("  [~] Preparing Custom TikTok Infographic Slide(s) on Background...")
                        
                        # Backgrounds ফোল্ডার ও ফন্ট ব্যবহার করে টিকটক স্লাইড প্রস্তুত
                        tiktok_slides = prepare_tiktok_slides(job_data, output_prefix=f"tiktok_slide_{hash(entry_link)}")
                        tiktok_video_path = f"tmp_tiktok_{hash(entry_link)}.mp4"

                        if render_vertical_video(tiktok_slides, primary_audio, tiktok_video_path):
                            print("  [+] Uploading Custom Infographic Video to TikTok via Buffer...")
                            upload_video_to_tiktok_buffer(tiktok_video_path, final_post_text, config)

                        # টিকটকের টেম্প ফাইল মুছে ফেলা
                        if os.path.exists(tiktok_video_path): os.remove(tiktok_video_path)
                        for sp in tiktok_slides:
                            if os.path.exists(sp): os.remove(sp)

                    # ৯. Telegram, WhatsApp ও Facebook Photo Albums ডেলিভারি
                    for did in dest_ids:
                        if dest_platform == "Telegram" and tg_client:
                            clean_tg = clean_telegram_id(did)
                            try:
                                if downloaded_imgs: await tg_client.send_file(clean_tg, downloaded_imgs, caption=final_post_text)
                                else: await tg_client.send_message(clean_tg, final_post_text)
                            except Exception: pass

                        elif dest_platform == "WhatsApp":
                            post_to_whatsapp_channel(render_wa_url, did, final_post_text, downloaded_imgs)

                    # ১০. ক্লিনআপ (সার্কুলার ছবি ও ফেসবুক ভিডিও/অডিও মুছে ফেলা)
                    for fv in fb_videos:
                        if os.path.exists(fv["video"]): os.remove(fv["video"])
                        if os.path.exists(fv["audio"]): os.remove(fv["audio"])
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
