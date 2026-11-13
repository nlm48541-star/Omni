# -*- coding: utf-8 -*-
import sys
import os
import random
import socket
import asyncio
import requests
import builtins
from PIL import Image

socket.setdefaulttimeout(600.0)

def _disabled_ci_input(prompt=""):
    raise EOFError(f"Interactive input('{prompt}') is permanently disabled in CI/CD automation.")
builtins.input = _disabled_ci_input

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
from tiktok_designer import ALL_DESIGN_IDS, prepare_tiktok_slides
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

def filter_wide_banner_images(downloaded_imgs):
    """১৬:৯ বা তার বেশি প্রস্থের (w/h >= 1.68) সব ব্যানার/থাম্বনেইল ছবি বাদ দিয়ে মূল সার্কুলার ছবি রাখে।"""
    valid_imgs = []
    for p in downloaded_imgs:
        try:
            with Image.open(p) as img:
                img.load()
                w, h = img.size
                if h <= 0:
                    continue
                ratio = w / h
                if ratio >= 1.68:
                    print(f"  [~] Excluding wide/16:9 banner image ({w}x{h}, ratio={ratio:.2f}): {os.path.basename(p)}")
                    continue
                valid_imgs.append(p)
        except Exception as e:
            print(f"  [!] Skipping invalid image file {p}: {e}")
    return valid_imgs

def pick_random_design_id(used_designs):
    pool = [d for d in ALL_DESIGN_IDS if d not in used_designs] or list(ALL_DESIGN_IDS)
    chosen = random.choice(pool)
    used_designs.append(chosen)
    return chosen

async def process_sync(config, memory):
    rules = config.get("rules", [])
    if not rules:
        print("[!] No sync rules found in automation_config.json")
        return memory

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
                print("  ⚠️ Telegram Session invalid/expired. Safely skipping Telegram.")
                await tg_client.disconnect()
                tg_client = None
        except Exception as e:
            print(f"  ⚠️ Telegram connection safely skipped: {e}")
            tg_client = None

    enable_tiktok = str(get_credential(config, "enable_tiktok", "ENABLE_TIKTOK")).lower() not in ["false", "0", "no", "off"]
    save_to_gdrive = str(get_credential(config, "save_to_gdrive", "SAVE_TO_GDRIVE")).lower() in ["true", "1", "yes", "on"]

    yt_targets = get_all_youtube_targets(config)
    tiktok_targets = get_all_tiktok_buffer_targets(config) if enable_tiktok else []

    clean_platform = lambda p_str: "Telegram" if "Telegram" in p_str else ("Facebook" if "Facebook" in p_str else ("YouTube" if "YouTube" in p_str else ("WhatsApp" if "WhatsApp" in p_str else "Website")))
    fb_dest_ids, tg_dest_ids, wa_dest_ids = [], [], []
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

    fb_count = len(fb_dest_ids)
    yt_count = len(yt_targets)
    tiktok_count = len(tiktok_targets)
    total_cycles = max(fb_count, yt_count, tiktok_count, 1)

    rclone_conf = get_credential(config, "rclone_conf", "RCLONE_CONF")
    gdrive_folder_id = get_credential(config, "gdrive_folder_id", "GDRIVE_FOLDER_ID")

    print(f"\n⚙️ [Master Automation Status - Progressive Sequential Pipeline]")
    print(f"   ├─ Connected YouTube Channels : {yt_count}")
    print(f"   ├─ Connected Facebook Pages   : {fb_count}")
    print(f"   ├─ Connected TikTok Accounts  : {tiktok_count} ({'ENABLED' if enable_tiktok else 'DISABLED'})")
    print(f"   ├─ Active Telegram Channels   : {len(tg_dest_ids)}")
    print(f"   ├─ Total Required Cycles      : {total_cycles}")
    print(f"   └─ Google Drive Save Mode     : {'✅ ENABLED (ON)' if save_to_gdrive else '⚠️ DISABLED (OFF)'}")

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
            if not entry_link and 'links' in entry and entry.links:
                entry_link = entry.links[0].get('href', '').strip()
            if not entry_link:
                entry_link = entry.get('id', entry.get('guid', '')).strip()
            if not entry_link or entry_link in processed_set:
                continue

            raw_title = entry.get('title', '').strip()
            article_title = clean_text(raw_title)
            if is_forbidden_title(article_title):
                processed_set.add(entry_link)
                continue

            web_text, web_html = scrape_full_webpage_content(entry_link)
            raw_desc = entry.get('summary', '') or entry.get('description', '') or web_text
            raw_desc_clean = clean_text(raw_desc)

            link_hash = abs(hash(entry_link))
            img_urls = extract_article_images(entry, entry_link, raw_desc)
            downloaded_imgs = []
            for i_idx, u in enumerate(img_urls):
                try:
                    ir = requests.get(u, headers=HEADERS, timeout=25)
                    if ir.status_code == 200:
                        p = f"tmp_raw_{link_hash}_{i_idx}.jpg"
                        with open(p, 'wb') as f:
                            f.write(ir.content)
                        downloaded_imgs.append(p)
                except Exception:
                    pass

            valid_circular_imgs = filter_wide_banner_images(downloaded_imgs)
            job_data = generate_job_data_and_script(
                article_title, web_text or raw_desc_clean, web_html,
                valid_circular_imgs or downloaded_imgs, scripts_count=total_cycles, memory=memory
            )

            print(f"\n🔥 [CONTENT PREPARED] '{article_title}' (Original Valid Circular Images: {len(valid_circular_imgs)})")
            scripts = job_data.get("scripts", [job_data.get("voiceover_script", "")])

            contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন WhatsApp: 01540503092"
            fb_yt_post_text = f"{article_title}\n\n{raw_desc_clean[:280]}...{contact_sfx}" if len(raw_desc_clean) > 20 else f"{article_title}{contact_sfx}"
            tiktok_caption = f"{article_title[:90]} | নতুন নিয়োগ বিজ্ঞপ্তি\n\nআবেদন করতে WhatsApp: 01540503092 নাম্বারে যোগাযোগ করুন।\n\n#bdjobs #jobcircular #career #bangladesh"
            video_final_title = article_title[:85].strip()

            used_design_ids = []
            poster_files_to_cleanup = []
            article_poster_path = None

            # =================================================================
            # 🌟 রেনডম পোস্টার তৈরি ➔ অডিও/ভিডিও রেন্ডার ➔ FB/YT/TikTok আপলোড
            # =================================================================
            for cycle_idx in range(total_cycles):
                print(f"\n--- [Cycle #{cycle_idx+1}/{total_cycles}] Starting Audio & Video Pipeline ---")

                audio_file = f"tmp_voice_{link_hash}_{cycle_idx+1}.mp3"
                s_text = scripts[cycle_idx % len(scripts)]
                audio_ok = generate_voiceover_audio_pipeline(s_text, audio_file, key_offset=cycle_idx, memory=memory)

                if not audio_ok or not os.path.exists(audio_file):
                    print(f"  ❌ Audio generation failed for Cycle #{cycle_idx+1}. Skipping.")
                    continue

                if cycle_idx < yt_count or cycle_idx < fb_count:
                    chosen_design = pick_random_design_id(used_design_ids)
                    cycle_posters = prepare_tiktok_slides(job_data, f"tmp_poster_{link_hash}_{cycle_idx+1}", design_id=chosen_design)
                    cycle_poster_path = cycle_posters[0]
                    poster_files_to_cleanup.append(cycle_poster_path)
                    if not article_poster_path:
                        article_poster_path = cycle_poster_path

                    fb_yt_source = [cycle_poster_path] + valid_circular_imgs
                    main_vid_path = f"tmp_main_{link_hash}_{cycle_idx+1}.mp4"

                    if render_vertical_video(fb_yt_source, audio_file, main_vid_path):
                        if cycle_idx < yt_count:
                            yt_ch = yt_targets[cycle_idx]
                            try:
                                print(f"  [+] Uploading Video #{cycle_idx+1} (Design #{chosen_design}) to YouTube Channel #{yt_ch.get('index')}...")
                                upload_video_to_youtube(yt_ch['client_id'], yt_ch['client_secret'], yt_ch['refresh_token'], main_vid_path, video_final_title, fb_yt_post_text)
                            except Exception as e:
                                print(f"  ⚠️ [YouTube Error] {e}")

                        if cycle_idx < fb_count:
                            fb_did = fb_dest_ids[cycle_idx]
                            try:
                                token = get_page_access_token(fb_user_token, fb_did)
                                if token:
                                    fb_photos = [cycle_poster_path] + valid_circular_imgs
                                    print(f"  [+] Posting {len(fb_photos)} Photo(s) (Poster #1 + {len(valid_circular_imgs)} circular(s)) to Facebook Page {fb_did}...")
                                    if len(fb_photos) > 1:
                                        post_multi_photo_to_facebook(fb_did, token, fb_photos, fb_yt_post_text)
                                    else:
                                        post_photo_to_facebook(fb_did, token, fb_photos[0], fb_yt_post_text)

                                    print(f"  [+] Uploading Reel Video #{cycle_idx+1} to Facebook Page {fb_did}...")
                                    if not post_reel_to_facebook(fb_did, token, main_vid_path, video_final_title, fb_yt_post_text):
                                        post_video_to_facebook(fb_did, token, main_vid_path, fb_yt_post_text)
                            except Exception as e:
                                print(f"  ⚠️ [Facebook Error] {e}")

                        if os.path.exists(main_vid_path):
                            try: os.remove(main_vid_path)
                            except Exception: pass

                if cycle_idx < tiktok_count:
                    tk_account = tiktok_targets[cycle_idx]
                    tk_vid_path = f"tmp_tiktok_{link_hash}_{cycle_idx+1}.mp4"
                    tk_design = pick_random_design_id(used_design_ids)
                    keep_tk_poster = None
                    if not article_poster_path:
                        keep_tk_poster = f"tmp_poster_{link_hash}_tk_{cycle_idx+1}.png"
                        poster_files_to_cleanup.append(keep_tk_poster)

                    if render_tiktok_motion_video(job_data, audio_file, tk_vid_path, design_id=tk_design, save_poster_path=keep_tk_poster):
                        if keep_tk_poster and os.path.exists(keep_tk_poster) and not article_poster_path:
                            article_poster_path = keep_tk_poster

                        if save_to_gdrive:
                            try:
                                drive_clean_name = f"{sanitize_filename(article_title[:45])}_{cycle_idx+1}.mp4"
                                upload_video_via_rclone(tk_vid_path, rclone_conf, folder_id=gdrive_folder_id, custom_filename=drive_clean_name)
                            except Exception as g_err:
                                print(f"  ⚠️ [Google Drive Notice] {g_err}")

                        try:
                            print(f"  [+] Uploading Poster Video #{cycle_idx+1} (Design #{tk_design}) to TikTok via Buffer Profile #{tk_account.get('index')}...")
                            upload_to_specific_buffer_account(tk_vid_path, tiktok_caption, tk_account['profile_id'], tk_account['token'])
                        except Exception as b_err:
                            print(f"  ⚠️ [TikTok Buffer Notice] {b_err}")

                        if os.path.exists(tk_vid_path):
                            try: os.remove(tk_vid_path)
                            except Exception: pass

                if os.path.exists(audio_file):
                    try: os.remove(audio_file)
                    except Exception: pass

            # কোনো ভিডিও তৈরি না হলে (যেমন শুধু TG/WA রুল থাকলে) রেনডম পোস্টার তৈরি
            if not article_poster_path:
                chosen_design = pick_random_design_id(used_design_ids)
                fallback_posters = prepare_tiktok_slides(job_data, f"tmp_poster_{link_hash}_social", design_id=chosen_design)
                article_poster_path = fallback_posters[0]
                poster_files_to_cleanup.append(article_poster_path)

            # সোশ্যাল ছবি পোস্ট: ১ নম্বরে ভিডিওর পোস্টার ইমেজ + এরপর মূল সার্কুলার ইমেজসমূহ (16:9 ব্যানার বাদে)
            social_images_to_share = ([article_poster_path] if article_poster_path and os.path.exists(article_poster_path) else []) + valid_circular_imgs

            if tg_client and tg_dest_ids and social_images_to_share:
                tg_images = social_images_to_share[:10]
                media_payload = tg_images[0] if len(tg_images) == 1 else tg_images
                for tg_id in tg_dest_ids:
                    try:
                        clean_tg = clean_telegram_id(tg_id)
                        if clean_tg:
                            print(f"  [+] Posting {len(tg_images)} Photo(s) (Poster #1 + circulars) to Telegram Channel: @{clean_tg}")
                            await tg_client.send_file(clean_tg, media_payload, caption=fb_yt_post_text)
                            await asyncio.sleep(1.5)
                    except Exception as e:
                        print(f"  ⚠️ [Telegram Channel @{clean_tg} Notice] {e}")

            for did in wa_dest_ids:
                try:
                    post_to_whatsapp_channel(render_wa_url, did, fb_yt_post_text, social_images_to_share)
                except Exception as e:
                    print(f"  ⚠️ [WhatsApp Notice] {e}")

            for dp in downloaded_imgs + poster_files_to_cleanup:
                if os.path.exists(dp):
                    try: os.remove(dp)
                    except Exception: pass

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
