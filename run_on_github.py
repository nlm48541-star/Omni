# -*- coding: utf-8 -*-
import sys
import os
import re
import time
import random
import shutil
import asyncio
import requests
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

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
from video_engine import render_vertical_video, render_tiktok_motion_video
from feed_manager import fetch_feed_entries, extract_article_images, scrape_full_webpage_content
from uploader_service import (
    get_page_access_token, post_photo_to_facebook,
    post_multi_photo_to_facebook, post_reel_to_facebook,
    post_video_to_facebook, upload_video_to_youtube,
    upload_video_via_rclone, post_to_whatsapp_channel,
    get_all_youtube_targets, get_all_tiktok_buffer_targets,
    upload_to_specific_buffer_account
)

def is_forbidden_title(title):
    if not title: return False
    title_lower = str(title).lower()
    return any(k in title_lower for k in ['এনজিও', 'ngo', 'ব্যাংক', 'bank', 'চলমান'])

def filter_banner_first_image(downloaded_imgs):
    if not downloaded_imgs or len(downloaded_imgs) == 1:
        return list(downloaded_imgs)
    try:
        with Image.open(downloaded_imgs[0]) as first_img:
            w, h = first_img.size
            if h > 0 and (w / h) >= 1.70:
                return list(downloaded_imgs[1:])
    except Exception: pass
    return list(downloaded_imgs)

async def process_sync(config, memory):
    rules = config.get("rules", [])
    if not rules:
        print("[!] No sync rules found in automation_config.json")
        return memory

    # ১. টেলিগ্রাম ক্লায়েন্ট
    tg_session = get_credential(config, "tg_session", "TG_SESSION")
    tg_api_id = get_credential(config, "tg_api_id", "TG_API_ID")
    tg_api_hash = get_credential(config, "tg_api_hash", "TG_API_HASH")

    tg_client = None
    if tg_session and tg_api_id and tg_api_hash:
        try:
            tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
            await tg_client.connect()
            if await tg_client.is_user_authorized():
                print("  [+] Telegram Client Authenticated!")
            else:
                print("  ⚠️ Telegram Session unauthorized. Disabling Telegram.")
                await tg_client.disconnect()
                tg_client = None
        except Exception as e:
            print(f"  ⚠️ Telegram notice: {e}")
            tg_client = None

    # ২. কানেক্টেড অ্যাকাউন্টসমূহ
    yt_targets = get_all_youtube_targets(config)
    tiktok_targets = get_all_tiktok_buffer_targets(config)

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else ("WhatsApp" if "WhatsApp" in p_str else "Website")))
    fb_dest_ids = []
    tg_dest_ids = []
    wa_dest_ids = []
    source_feed_urls = set()

    for r in rules:
        s_plat = clean_platform(r['source'])
        d_plat = clean_platform(r['destination'])
        s_ids = [s.strip() for s in r['source_id'].split(',') if s.strip()]
        d_ids = [d.strip() for d in r['dest_id'].split(',') if d.strip()]

        if s_plat == "Website": source_feed_urls.update(s_ids)
        if d_plat == "Facebook": fb_dest_ids.extend([d for d in d_ids if d not in fb_dest_ids])
        elif d_plat == "Telegram": tg_dest_ids.extend([d for d in d_ids if d not in tg_dest_ids])
        elif d_plat == "WhatsApp": wa_dest_ids.extend([d for d in d_ids if d not in wa_dest_ids])

    main_needed_count = max(len(fb_dest_ids), len(yt_targets), 1)
    tiktok_needed_count = len(tiktok_targets)
    total_audio_needed = min(8, max(main_needed_count, tiktok_needed_count))

    rclone_conf = get_credential(config, "rclone_conf", "RCLONE_CONF")
    gdrive_folder_id = get_credential(config, "gdrive_folder_id", "GDRIVE_FOLDER_ID")
    save_to_gdrive = str(get_credential(config, "save_to_gdrive", "SAVE_TO_GDRIVE")).lower() in ["true", "1", "yes", "on"]

    print(f"\n⚙️ [Master Automation Status - Active & Protected]")
    print(f"   ├─ Active YouTube Channels  : {len(yt_targets)}")
    print(f"   ├─ Active Facebook Pages    : {len(fb_dest_ids)}")
    print(f"   ├─ Active TikTok Accounts   : {tiktok_needed_count}")
    print(f"   ├─ Total Required Audios    : {total_audio_needed}")
    print(f"   └─ Google Drive Save Mode   : {'✅ ENABLED (ON)' if save_to_gdrive else '⚠️ DISABLED (OFF)'}")

    fb_user_token = get_credential(config, "fb_token", "FB_TOKEN") or get_credential(config, "fb_user_token", "FB_USER_TOKEN")
    render_wa_url = get_credential(config, "render_wa_url", "RENDER_WA_URL") or "https://wa-channel-bridge.onrender.com"

    processed_set = set(memory.get("processed_articles", []))
    for k, v in memory.items():
        if isinstance(v, list) and k.startswith("route_"):
            processed_set.update(v)

    for feed_url in source_feed_urls:
        print(f"\n[~] Scanning Source Feed: {feed_url}")
        feed = fetch_feed_entries(feed_url)
        for entry in reversed(feed.entries[:10]):
            entry_link = entry.get('link', '').strip()
            if not entry_link and 'links' in entry and entry.links: entry_link = entry.links[0].get('href', '').strip()
            if not entry_link: entry_link = entry.get('id', entry.get('guid', '')).strip()

            if not entry_link or entry_link in processed_set: continue

            raw_title = entry.get('title', '').strip()
            article_title = clean_text(raw_title)

            if is_forbidden_title(article_title):
                processed_set.add(entry_link)
                continue

            web_text, web_html = scrape_full_webpage_content(entry_link)
            raw_desc = entry.get('summary', '') or entry.get('description', '') or web_text
            raw_desc_clean = clean_text(raw_desc)

            img_urls = extract_article_images(entry, entry_link, raw_desc)
            downloaded_imgs = []
            for i_idx, u in enumerate(img_urls):
                try:
                    ir = requests.get(u, headers=HEADERS)
                    if ir.status_code == 200:
                        p = f"tmp_raw_{hash(entry_link)}_{i_idx}.jpg"
                        with open(p, 'wb') as f: f.write(ir.content)
                        downloaded_imgs.append(p)
                except Exception: pass

            # এআই প্রসেসিং
            job_data = generate_job_data_and_script(article_title, web_text or raw_desc_clean, web_html, downloaded_imgs, memory=memory)

            print(f"\n🔥 [CREATING POSTER CONTENT] '{article_title}'")
            scripts = job_data.get("scripts", [job_data.get("voiceover_script", "")])

            # অডিও তৈরি
            generated_audios = []
            for idx in range(total_audio_needed):
                audio_file = f"tmp_voice_{hash(entry_link)}_{idx+1}.mp3"
                s_text = scripts[idx % len(scripts)]
                if generate_voiceover_audio_pipeline(s_text, audio_file, memory=memory):
                    generated_audios.append(audio_file)
                # 🌟 প্রতিটি অডিও কলের মাঝে ২ সেকেন্ডের ছোট বিরতি যাতে গুগল সার্ভার স্টল না হয়
                time.sleep(2)

            if not generated_audios:
                print("  ❌ [ERROR] Could not generate audio. Skipping...")
                continue

            contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন WhatsApp: 01540503092"
            fb_yt_post_text = f"{article_title}\n\n{raw_desc_clean[:280]}...{contact_sfx}" if len(raw_desc_clean) > 20 else f"{article_title}{contact_sfx}"
            tiktok_caption = f"{article_title[:90]} | নতুন নিয়োগ বিজ্ঞপ্তি\n\nআবেদন করতে WhatsApp: 01540503092 নাম্বারে যোগাযোগ করুন।\n\n#bdjobs #jobcircular #career #bangladesh"
            video_final_title = article_title[:85].strip()

            # ১. মেইন ভিডিও তৈরি ও FB / YouTube-এ আপলোড
            valid_source_imgs = filter_banner_first_image(downloaded_imgs)
            fb_yt_source = valid_source_imgs if valid_source_imgs else prepare_tiktok_slides(job_data, f"fb_fallback_{hash(entry_link)}")

            for y_idx, yt_channel in enumerate(yt_targets):
                audio_for_yt = generated_audios[y_idx % len(generated_audios)]
                yt_vid_path = f"tmp_main_yt_{hash(entry_link)}_{y_idx+1}.mp4"
                if render_vertical_video(fb_yt_source, audio_for_yt, yt_vid_path):
                    print(f"  [+] Uploading Video #{y_idx+1} to YouTube Channel #{yt_channel.get('index')}...")
                    upload_video_to_youtube(yt_channel['client_id'], yt_channel['client_secret'], yt_channel['refresh_token'], yt_vid_path, video_final_title, fb_yt_post_text)
                    if os.path.exists(yt_vid_path): os.remove(yt_vid_path)

            for f_idx, did in enumerate(fb_dest_ids):
                token = get_page_access_token(fb_user_token, did)
                if token:
                    audio_for_fb = generated_audios[f_idx % len(generated_audios)]
                    fb_vid_path = f"tmp_main_fb_{hash(entry_link)}_{f_idx+1}.mp4"
                    if render_vertical_video(fb_yt_source, audio_for_fb, fb_vid_path):
                        if not post_reel_to_facebook(did, token, fb_vid_path, video_final_title, fb_yt_post_text):
                            post_video_to_facebook(did, token, fb_vid_path, fb_yt_post_text)
                        if os.path.exists(fb_vid_path): os.remove(fb_vid_path)

            # ২. TikTok পোস্টার ভিডিও তৈরি, ড্রাইভে সেভ এবং Buffer-এ আপলোড
            for t_idx, tk_account in enumerate(tiktok_targets):
                tk_audio = generated_audios[t_idx % len(generated_audios)]
                tk_vid_path = f"tmp_tiktok_{hash(entry_link)}_{t_idx+1}.mp4"

                print(f"  🎬 Rendering TikTok Poster Video #{t_idx+1} for Account #{tk_account.get('index')}...")
                if render_tiktok_motion_video(job_data, tk_audio, tk_vid_path):
                    if save_to_gdrive:
                        drive_clean_name = f"{sanitize_filename(article_title[:45])}_{t_idx+1}.mp4"
                        upload_video_via_rclone(tk_vid_path, rclone_conf, folder_id=gdrive_folder_id, custom_filename=drive_clean_name)

                    print(f"  [+] Uploading Poster Video #{t_idx+1} to TikTok via Buffer Profile #{tk_account.get('index')}...")
                    upload_to_specific_buffer_account(tk_vid_path, tiktok_caption, tk_account['profile_id'], tk_account['token'])

                    if os.path.exists(tk_vid_path): os.remove(tk_vid_path)

            # টেলিগ্রাম ও হোয়াটসঅ্যাপ
            if tg_client:
                clean_tg = clean_telegram_id(tg_dest_ids[0]) if tg_dest_ids else ""
                if clean_tg:
                    try:
                        if downloaded_imgs: await tg_client.send_file(clean_tg, downloaded_imgs, caption=fb_yt_post_text)
                        else: await tg_client.send_message(clean_tg, fb_yt_post_text)
                    except Exception: pass

            for did in wa_dest_ids:
                post_to_whatsapp_channel(render_wa_url, did, fb_yt_post_text, downloaded_imgs)

            # ক্লিনআপ
            for a_f in generated_audios:
                if os.path.exists(a_f): os.remove(a_f)
            for dp in downloaded_imgs:
                if os.path.exists(dp): os.remove(dp)

            # মেমোরি সেভ
            processed_set.add(entry_link)
            memory["processed_articles"] = list(processed_set)[-300:]
            save_json(MEMORY_FILE, memory)
            print(f"  💾 [SAVED CHECKPOINT] '{article_title[:35]}' saved to memory.")

    if tg_client:
        try: await tg_client.disconnect()
        except Exception: pass

    return memory

async def main():
    config = load_json(CONFIG_FILE, {})
    memory = load_json(MEMORY_FILE, {})
    updated_memory = await process_sync(config, memory)
    save_json(MEMORY_FILE, updated_memory)
    print("\n✅ Task Executed & All Memory Checkpoints Finalized.")

if __name__ == "__main__":
    asyncio.run(main())
