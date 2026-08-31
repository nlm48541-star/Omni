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
from audio_engine import generate_voiceover_audio_pipeline, get_fallback_music_file
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
    """টাইটেলে এনজিও বা ব্যাংক থাকলে তা বাদ দেবে"""
    if not title: return False
    title_lower = str(title).lower()
    return any(k in title_lower for k in ['এনজিও', 'ngo', 'ব্যাংক', 'bank'])

def filter_banner_first_image(downloaded_imgs):
    """একাধিক ছবি থাকলে এবং প্রথম ছবিটি ১৬:৯ ব্যানার সাইজ হলে তা বাদ দেবে"""
    if not downloaded_imgs or len(downloaded_imgs) == 1:
        return list(downloaded_imgs)

    try:
        with Image.open(downloaded_imgs[0]) as first_img:
            w, h = first_img.size
            if h > 0 and (w / h) >= 1.70:
                print("  [~] First image is 16:9 Banner thumbnail. Excluding it from circular video.")
                return list(downloaded_imgs[1:])
    except Exception: pass
    return list(downloaded_imgs)

async def process_sync(config, memory):
    rules = config.get("rules", [])
    if not rules:
        print("[!] No sync rules found in automation_config.json")
        return memory

    # ক্রেডেনশিয়াল লোড
    tg_session = get_credential(config, "tg_session", "TG_SESSION")
    tg_api_id = get_credential(config, "tg_api_id", "TG_API_ID")
    tg_api_hash = get_credential(config, "tg_api_hash", "TG_API_HASH")
    fb_user_token = get_credential(config, "fb_token", "FB_TOKEN") or get_credential(config, "fb_user_token", "FB_USER_TOKEN")
    render_wa_url = get_credential(config, "render_wa_url", "RENDER_WA_URL") or "https://wa-channel-bridge.onrender.com"

    # ১ ও ২ নম্বর ইউটিউব চ্যানেল
    yt1_client_id = get_credential(config, "yt_client_id", "YT_CLIENT_ID") or get_credential(config, "yt_client_id", "CLIENT_ID")
    yt1_client_secret = get_credential(config, "yt_client_secret", "YT_CLIENT_SECRET") or get_credential(config, "yt_client_secret", "CLIENT_SECRET")
    yt1_refresh_token = get_credential(config, "yt_refresh_token", "YT_REFRESH_TOKEN") or get_credential(config, "yt_refresh_token", "REFRESH_TOKEN")

    yt2_client_id = get_credential(config, "yt2_client_id", "YT_CLIENT_ID_2") or get_credential(config, "yt2_client_id", "CLIENT_ID_2")
    yt2_client_secret = get_credential(config, "yt2_client_secret", "YT_CLIENT_SECRET_2") or get_credential(config, "yt2_client_secret", "CLIENT_SECRET_2")
    yt2_refresh_token = get_credential(config, "yt2_refresh_token", "YT_REFRESH_TOKEN_2") or get_credential(config, "yt2_refresh_token", "REFRESH_TOKEN_2")

    # ফ্লেক্সিবল টগল
    enable_tiktok = str(get_credential(config, "enable_tiktok", "ENABLE_TIKTOK")).lower() not in ["false", "0", "no", "off"]
    use_local_music = str(get_credential(config, "use_local_music", "USE_LOCAL_MUSIC")).lower() in ["true", "1", "yes", "on"]

    # টেলিগ্রাম ক্লায়েন্ট চালু
    tg_client = None
    if tg_session and tg_api_id and tg_api_hash:
        try:
            tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
            await tg_client.start()
            print("  [+] Telegram Client Authenticated!")
        except Exception: pass

    # সব ডেস্টিনেশন আইডি আলাদা করা
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

        if s_plat == "Website":
            source_feed_urls.update(s_ids)

        if d_plat == "Facebook":
            fb_dest_ids.extend([d for d in d_ids if d not in fb_dest_ids])
        elif d_plat == "Telegram":
            tg_dest_ids.extend([d for d in d_ids if d not in tg_dest_ids])
        elif d_plat == "WhatsApp":
            wa_dest_ids.extend([d for d in d_ids if d not in wa_dest_ids])

    # গ্লোবাল প্রসেসড মেমরি
    processed_links = memory.get("processed_articles", [])
    if not isinstance(processed_links, list): processed_links = []
    new_processed_links = list(processed_links)

    for feed_url in source_feed_urls:
        print(f"\n========================================================")
        print(f"[~] Checking Website Feed: '{feed_url}'")
        print(f"========================================================")

        feed = fetch_feed_entries(feed_url)
        for entry in reversed(feed.entries[:10]):
            entry_link = entry.get('link', '').strip()
            if not entry_link and 'links' in entry and entry.links:
                entry_link = entry.links[0].get('href', '').strip()
            if not entry_link: entry_link = entry.get('id', entry.get('guid', '')).strip()

            if not entry_link or not entry_link.startswith(('http://', 'https://')): continue
            if entry_link in new_processed_links: continue

            title = entry.get('title', '').strip()

            # ১. টাইটেল ফিল্টার (এনজিও/ব্যাংক বাদ)
            if is_forbidden_title(title):
                print(f"🚫 [FILTERED] Skipping '{title}' (Title contains NGO / Bank).")
                new_processed_links.append(entry_link)
                continue

            print(f"\n🔥 [NEW ARTICLE DETECTED] '{title}'")
            new_processed_links.append(entry_link)

            raw_desc = entry.get('summary', '') or entry.get('description', '')
            raw_desc_clean = clean_text(raw_desc)

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

            # ৩. এআই দিয়ে ডাটা ও ১-মিনিটের স্ক্রিপ্ট তৈরি
            job_data = generate_job_data_and_script(title, downloaded_imgs)
            voiceover_script = job_data.get("voiceover_script", "")

            # ৪. একক অডিও প্রস্তুত
            single_audio_path = f"tmp_voice_{hash(entry_link)}.mp3"
            audio_ready = False

            if use_local_music:
                print("  [🎵 Audio Mode] Using local music from 'Music/' folder...")
                fallback_music = get_fallback_music_file()
                if fallback_music and os.path.exists(fallback_music):
                    import shutil
                    shutil.copyfile(fallback_music, single_audio_path)
                    audio_ready = True
            else:
                audio_ready = generate_voiceover_audio_pipeline(voiceover_script, single_audio_path)

            # ৫. পোস্ট ক্যাপশন টেক্সট
            contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন whatsapp 01540503092"
            final_post_text = f"{clean_text(title)}\n\n{raw_desc_clean[:280]}...{contact_sfx}"

            # ৬. ১ম ভিডিও (মূল বিজ্ঞপ্তির ছবি + অডিও) ➔ Facebook & YouTube Shorts 1
            main_video_path = f"tmp_main_video_{hash(entry_link)}.mp4"
            valid_source_imgs = filter_banner_first_image(downloaded_imgs)
            fb_yt_source = valid_source_imgs if valid_source_imgs else prepare_tiktok_slides(job_data, f"fb_fallback_{hash(entry_link)}")
            
            main_video_ready = False
            if audio_ready and os.path.exists(single_audio_path):
                main_video_ready = render_vertical_video(fb_yt_source, single_audio_path, main_video_path)

            # ৭. ফেসবুক পেজগুলোতে পোস্ট (ছবি+টেক্সট পোস্ট এবং রিলস ভিডিও আপলোড)
            for did in fb_dest_ids:
                token = get_page_access_token(fb_user_token, did)
                if token:
                    # ক) ফেসবুক পেজে ফটো / মাল্টি-ফটো অ্যালবাম পোস্ট (Photo Feed Post)
                    if downloaded_imgs:
                        print(f"  [+] Posting Photos & Caption to Facebook Page '{did}'...")
                        if len(downloaded_imgs) > 1:
                            post_multi_photo_to_facebook(did, token, downloaded_imgs, final_post_text)
                        else:
                            post_photo_to_facebook(did, token, downloaded_imgs[0], final_post_text)

                    # খ) ফেসবুক পেজে রিলস ভিডিও আপলোড (Facebook Reel / Video)
                    if main_video_ready:
                        print(f"  [+] Uploading Video Reel to Facebook Page '{did}'...")
                        if not post_reel_to_facebook(did, token, main_video_path, title, final_post_text):
                            post_video_to_facebook(did, token, main_video_path, final_post_text)

            # ৮. ১ম YouTube চ্যানেলে (Shorts 1) আপলোড
            if main_video_ready and yt1_client_id and yt1_client_secret and yt1_refresh_token:
                print("  [+] Uploading Video to 1st YouTube Channel (Shorts 1)...")
                upload_video_to_youtube(
                    yt1_client_id, yt1_client_secret, yt1_refresh_token,
                    main_video_path,
                    job_data.get("optimized_title", title),
                    job_data.get("video_description", final_post_text)
                )

            # ৯. ২য় ভিডিও (কাস্টম ইনফোগ্রাফিক স্লাইড + একই অডিও) ➔ TikTok & YouTube Shorts 2
            if enable_tiktok and audio_ready and os.path.exists(single_audio_path):
                print("  [~] Rendering Custom Infographic Video for TikTok & 2nd YouTube...")
                tiktok_slides = prepare_tiktok_slides(job_data, output_prefix=f"tt_slide_{hash(entry_link)}")
                tiktok_video_path = f"tmp_tiktok_video_{hash(entry_link)}.mp4"

                if render_vertical_video(tiktok_slides, single_audio_path, tiktok_video_path):
                    # ক) TikTok আপলোড (Buffer)
                    print("  [+] Uploading Custom Video to TikTok via Buffer...")
                    upload_video_to_tiktok_buffer(tiktok_video_path, final_post_text, config)

                    # খ) ২য় YouTube চ্যানেলে (Shorts 2) আপলোড (টোকেন থাকলে আপলোড হবে, না থাকলে অটো স্কিপ)
                    if yt2_client_id and yt2_client_secret and yt2_refresh_token:
                        print("  [+] Uploading Custom Video to 2nd YouTube Channel (Shorts 2)...")
                        upload_video_to_youtube(
                            yt2_client_id, yt2_client_secret, yt2_refresh_token,
                            tiktok_video_path,
                            job_data.get("optimized_title", title),
                            job_data.get("video_description", final_post_text)
                        )
                    else:
                        print("  [~] 2nd YouTube credentials not configured. Skipping cleanly.")

                # টিকটক টেম্প ক্লিনআপ
                if os.path.exists(tiktok_video_path): os.remove(tiktok_video_path)
                for sp in tiktok_slides:
                    if os.path.exists(sp): os.remove(sp)

            # ১০. Telegram ও WhatsApp চ্যানেলে পোস্ট ডেলিভারি
            for did in tg_dest_ids:
                if tg_client:
                    clean_tg = clean_telegram_id(did)
                    try:
                        if downloaded_imgs: await tg_client.send_file(clean_tg, downloaded_imgs, caption=final_post_text)
                        else: await tg_client.send_message(clean_tg, final_post_text)
                    except Exception: pass

            for did in wa_dest_ids:
                post_to_whatsapp_channel(render_wa_url, did, final_post_text, downloaded_imgs)

            # ১১. ক্লিনআপ
            if os.path.exists(main_video_path): os.remove(main_video_path)
            if os.path.exists(single_audio_path): os.remove(single_audio_path)
            for dp in downloaded_imgs:
                if os.path.exists(dp): os.remove(dp)

    # মেমরিতে শেষ ১০০টি প্রসেসড লিঙ্ক সংরক্ষণ
    memory["processed_articles"] = new_processed_links[-100:]

    if tg_client:
        await tg_client.disconnect()
    return memory

async def main():
    config = load_json(CONFIG_FILE, {})
    memory = load_json(MEMORY_FILE, {})
    updated_memory = await process_sync(config, memory)
    save_json(MEMORY_FILE, updated_memory)
    print("\n✅ Execution Finished Perfectly.")

if __name__ == "__main__":
    asyncio.run(main())
