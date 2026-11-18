# -*- coding: utf-8 -*-
import sys, os, random, shutil, socket, asyncio, hashlib, requests, builtins
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
    CONFIG_FILE, MEMORY_FILE, HEADERS, load_json, save_json,
    get_credential, clean_text, clean_telegram_id, sanitize_filename
)
from ai_service import generate_job_data_and_script
from audio_engine import (
    clean_script_for_speech, generate_voiceover_audio_pipeline,
    generate_voiceover_batch_pipeline
)
from tiktok_designer import ALL_DESIGN_IDS, prepare_tiktok_slides
from video_engine import render_vertical_video, render_tiktok_motion_video
from feed_manager import fetch_feed_entries, extract_article_images, scrape_full_webpage_content
from uploader_service import (
    get_page_access_token, post_photo_to_facebook, post_multi_photo_to_facebook,
    post_reel_to_facebook, post_video_to_facebook, upload_video_to_youtube,
    upload_video_via_rclone, post_to_whatsapp_channel, get_all_youtube_targets,
    get_all_tiktok_buffer_targets, upload_to_specific_buffer_account
)

def is_forbidden_title(title):
    return bool(title) and any(k in str(title).lower() for k in ['এনজিও', 'ngo', 'ব্যাংক', 'bank', 'চলমান'])

def filter_wide_banner_images(downloaded_imgs):
    valid_imgs = []
    for p in downloaded_imgs:
        try:
            with Image.open(p) as img:
                img.load()
                w, h = img.size
                if h > 0 and (w / h) < 1.68: valid_imgs.append(p)
        except Exception: pass
    return valid_imgs

def pick_random_design_id(used_designs):
    pool = [d for d in ALL_DESIGN_IDS if d not in used_designs] or list(ALL_DESIGN_IDS)
    chosen = random.choice(pool); used_designs.append(chosen); return chosen

def split_motion_and_standard_targets(items, spec_str, id_getter=None, max_motion=3):
    if not items: return [], []
    spec = str(spec_str or "").strip()
    if not spec: return list(items[:max_motion]), list(items[max_motion:])
    chosen = []
    for tok in [t.strip() for t in spec.split(',') if t.strip()]:
        if tok.isdigit() and 1 <= int(tok) <= len(items):
            idx = int(tok) - 1
            if idx not in chosen: chosen.append(idx)
        elif id_getter:
            for i, it in enumerate(items):
                if str(id_getter(it)).strip() == tok and i not in chosen:
                    chosen.append(i); break
        if len(chosen) >= max_motion: break
    if not chosen: return list(items[:max_motion]), list(items[max_motion:])
    return [items[i] for i in chosen], [items[i] for i in range(len(items)) if i not in chosen]

def _post_fb_photos(fb_did, token, poster_path, valid_circular_imgs, caption):
    try:
        fb_photos = [poster_path] + valid_circular_imgs
        print(f"  [+] Posting {len(fb_photos)} Photo(s) to Facebook Page {fb_did}...")
        if len(fb_photos) > 1: post_multi_photo_to_facebook(fb_did, token, fb_photos, caption)
        else: post_photo_to_facebook(fb_did, token, fb_photos[0], caption)
    except Exception as e:
        print(f"  ⚠️ [Facebook Photo Notice] {e}")

def _publish_yt_and_fb(vid_path, vid_title, post_text, yt_ch, fb_did, fb_user_token, poster_fn, valid_imgs, label):
    if yt_ch:
        try:
            print(f"  [+] Uploading {label} to YouTube Channel #{yt_ch.get('index')}...")
            upload_video_to_youtube(yt_ch['client_id'], yt_ch['client_secret'], yt_ch['refresh_token'], vid_path, vid_title, post_text)
        except Exception as ye:
            print(f"  ⚠️ [YouTube Error] {ye}")
    if fb_did:
        try:
            token = get_page_access_token(fb_user_token, fb_did)
            if token:
                poster_p = poster_fn()
                _post_fb_photos(fb_did, token, poster_p, valid_imgs, post_text)
                print(f"  [+] Uploading {label} Reel to Facebook Page {fb_did}...")
                if not post_reel_to_facebook(fb_did, token, vid_path, vid_title, post_text):
                    post_video_to_facebook(fb_did, token, vid_path, post_text)
        except Exception as fe:
            print(f"  ⚠️ [Facebook Error] {fe}")

def _sync_kaggle_env_from_config(config):
    keys = ["KAGGLE_API_TOKEN", "KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_DATASET_SLUG",
            "KAGGLE_WORKER_SLUG", "KAGGLE_DEFAULT_VOICE", "KAGGLE_SPEECH_SPEED",
            "KAGGLE_NFE_STEP", "KAGGLE_REF_AUDIO_PATH", "KAGGLE_REF_TEXT", "DISABLE_KAGGLE_TTS"]
    for env_key in keys:
        val = get_credential(config, env_key.lower(), env_key)
        if val and not os.environ.get(env_key, "").strip():
            os.environ[env_key] = val

def _prepare_article_audios(expected_audio_files, total_scripts_needed, memory):
    audio_paths, first_valid, ninada_cache = [], None, {}
    for a_idx, (a_file, s_text) in enumerate(expected_audio_files):
        if os.path.exists(a_file) and os.path.getsize(a_file) > 1000:
            audio_paths.append(a_file)
            if not first_valid: first_valid = a_file
            continue
        clean_s = clean_script_for_speech(s_text)
        if clean_s in ninada_cache and os.path.exists(ninada_cache[clean_s]):
            shutil.copy2(ninada_cache[clean_s], a_file)
            audio_paths.append(a_file)
            if not first_valid: first_valid = a_file
            continue
        print(f"  [🎙️ Audio Backup {a_idx+1}/{total_scripts_needed}] Synthesizing with Priority #2 (Ninada TTS)...")
        if generate_voiceover_audio_pipeline(s_text, a_file, key_offset=a_idx, memory=memory, skip_kaggle=True) and os.path.exists(a_file):
            ninada_cache[clean_s] = a_file
            audio_paths.append(a_file)
            if not first_valid: first_valid = a_file
        else:
            audio_paths.append(None)
    return [a if a is not None else first_valid for a in audio_paths], first_valid

async def process_sync(config, memory):
    rules = config.get("rules", [])
    if not rules:
        print("[!] No sync rules found in automation_config.json")
        return memory

    _sync_kaggle_env_from_config(config)

    tg_session = get_credential(config, "tg_session", "TG_SESSION")
    tg_api_id = get_credential(config, "tg_api_id", "TG_API_ID")
    tg_api_hash = get_credential(config, "tg_api_hash", "TG_API_HASH")
    tg_client = None
    if tg_session and tg_api_id and tg_api_hash:
        try:
            tg_client = TelegramClient(StringSession(str(tg_session).strip()), int(tg_api_id), str(tg_api_hash))
            await tg_client.connect()
            if await tg_client.is_user_authorized(): print("  [+] Telegram Client Authenticated!")
            else: await tg_client.disconnect(); tg_client = None
        except Exception as e:
            print(f"  ⚠️ Telegram connection skipped: {e}"); tg_client = None

    enable_tiktok = str(get_credential(config, "enable_tiktok", "ENABLE_TIKTOK")).lower() not in ["false", "0", "no", "off"]
    save_to_gdrive = str(get_credential(config, "save_to_gdrive", "SAVE_TO_GDRIVE")).lower() in ["true", "1", "yes", "on"]
    yt_targets = get_all_youtube_targets(config)
    tiktok_targets = get_all_tiktok_buffer_targets(config) if enable_tiktok else []

    clean_plat = lambda p: "Telegram" if "Telegram" in p else ("Facebook" if "Facebook" in p else ("YouTube" if "YouTube" in p else ("WhatsApp" if "WhatsApp" in p else "Website")))
    fb_dest_ids, tg_dest_ids, wa_dest_ids, source_feed_urls = [], [], [], set()
    for r in rules:
        sp, dp = clean_plat(r['source']), clean_plat(r['destination'])
        s_ids = [s.strip() for s in r['source_id'].split(',') if s.strip()]
        d_ids = [d.strip() for d in r['dest_id'].split(',') if d.strip()]
        if sp == "Website": source_feed_urls.update(s_ids)
        if dp == "Facebook": fb_dest_ids.extend([d for d in d_ids if d not in fb_dest_ids])
        elif dp == "Telegram": tg_dest_ids.extend([d for d in d_ids if d not in tg_dest_ids])
        elif dp == "WhatsApp": wa_dest_ids.extend([d for d in d_ids if d not in wa_dest_ids])

    motion_fb, rem_fb = split_motion_and_standard_targets(fb_dest_ids, get_credential(config, "motion_fb_pages", "MOTION_FB_PAGES"), lambda x: x, 3)
    motion_yt, rem_yt = split_motion_and_standard_targets(yt_targets, get_credential(config, "motion_yt_channels", "MOTION_YT_CHANNELS"), lambda ch: ch.get("name", ""), 3)
    style_spec = get_credential(config, "tiktok_style_map", "TIKTOK_STYLE_MAP") or "1,2,3"
    style_order = [int(x.strip()) for x in style_spec.split(',') if x.strip().isdigit() and int(x.strip()) in [1, 2, 3]] or [1, 2, 3]

    motion_count = min(3, max(len(tiktok_targets), len(motion_fb), len(motion_yt)))
    standard_count = max(len(rem_fb), len(rem_yt))
    total_scripts_needed = max(motion_count + standard_count, 1)

    rclone_conf = get_credential(config, "rclone_conf", "RCLONE_CONF")
    gdrive_folder_id = get_credential(config, "gdrive_folder_id", "GDRIVE_FOLDER_ID")
    fb_user_token = get_credential(config, "fb_token", "FB_TOKEN") or get_credential(config, "fb_user_token", "FB_USER_TOKEN")
    render_wa_url = get_credential(config, "render_wa_url", "RENDER_WA_URL") or "https://wa-channel-bridge.onrender.com"

    print(f"\n⚙️ [Master Automation Status - 3 Motion + 5 Standard Pipeline]")
    print(f"   ├─ TikTok (Buffer) Accounts   : {len(tiktok_targets)} ({'ENABLED' if enable_tiktok else 'DISABLED'})")
    print(f"   ├─ Motion Video Targets       : {motion_count} Styles -> FB:{len(motion_fb)}, YT:{len(motion_yt)}")
    print(f"   ├─ Standard Video Targets     : {standard_count} Videos -> FB:{len(rem_fb)}, YT:{len(rem_yt)}")
    print(f"   ├─ Total Scripts & Audios     : {total_scripts_needed}")
    print(f"   └─ Google Drive Save Mode     : {'✅ ON' if save_to_gdrive else '⚠️ OFF'}")

    processed_set = set(memory.get("processed_articles", []))
    for k, v in memory.items():
        if isinstance(v, list) and k.startswith("route_"): processed_set.update(v)

    # ধাপ ১: সব নতুন আর্টিকেল স্ক্র্যাপ ও স্ক্রিপ্ট প্রস্তুত করা
    prepared_articles, seen_links, all_batch_tasks = [], set(), []
    for feed_url in source_feed_urls:
        print(f"\n[~] Scanning Source Feed: {feed_url}")
        feed = fetch_feed_entries(feed_url)
        for entry in reversed(feed.entries[:10]):
            entry_link = entry.get('link', '').strip() or (entry.links[0].get('href', '').strip() if entry.get('links') else '') or entry.get('id', entry.get('guid', '')).strip()
            if not entry_link or entry_link in processed_set or entry_link in seen_links: continue
            seen_links.add(entry_link)

            article_title = clean_text(entry.get('title', '').strip())
            if is_forbidden_title(article_title):
                processed_set.add(entry_link); continue

            web_text, web_html = scrape_full_webpage_content(entry_link)
            raw_desc = entry.get('summary', '') or entry.get('description', '') or web_text
            raw_desc_clean = clean_text(raw_desc)
            link_hash = hashlib.md5(entry_link.encode("utf-8")).hexdigest()[:12]

            downloaded_imgs = []
            for i_idx, u in enumerate(extract_article_images(entry, entry_link, raw_desc)):
                try:
                    ir = requests.get(u, headers={**HEADERS, "Referer": entry_link}, timeout=25)
                    if ir.status_code == 200 and len(ir.content) > 2000:
                        p = f"tmp_raw_{link_hash}_{i_idx}.jpg"
                        with open(p, 'wb') as f: f.write(ir.content)
                        downloaded_imgs.append(p)
                except Exception: pass

            valid_circular_imgs = filter_wide_banner_images(downloaded_imgs)
            job_data = generate_job_data_and_script(
                article_title, web_text or raw_desc_clean, web_html,
                valid_circular_imgs or downloaded_imgs, scripts_count=total_scripts_needed, memory=memory
            )

            print(f"\n🔥 [CONTENT PREPARED] '{article_title}' (Circulars: {len(valid_circular_imgs)})")
            scripts = job_data.get("scripts", [job_data.get("voiceover_script", "")])
            expected_audio_files = []
            for a_idx in range(total_scripts_needed):
                a_file = f"tmp_voice_{link_hash}_{a_idx+1}.mp3"
                s_text = scripts[a_idx % len(scripts)]
                expected_audio_files.append((a_file, s_text))
                all_batch_tasks.append({"filename": a_file, "text": s_text, "target_path": a_file})

            prepared_articles.append({
                "entry_link": entry_link, "article_title": article_title,
                "raw_desc_clean": raw_desc_clean, "link_hash": link_hash,
                "downloaded_imgs": downloaded_imgs, "valid_circular_imgs": valid_circular_imgs,
                "job_data": job_data, "expected_audio_files": expected_audio_files,
            })

    # ধাপ ২: Priority #1 — Kaggle IndicF5 দিয়ে ১টি ব্যাচে সব অডিও একসাথে তৈরি
    batch_audio_dir = f"tmp_kaggle_batch_{os.getpid()}"
    try:
        if all_batch_tasks:
            print(f"\n🎙️ [Audio Phase] Synthesizing {len(all_batch_tasks)} voiceover(s) across {len(prepared_articles)} article(s)...")
            generate_voiceover_batch_pipeline(all_batch_tasks, batch_work_dir=batch_audio_dir, allow_ninada_backup=False)
    finally:
        if os.path.exists(batch_audio_dir): shutil.rmtree(batch_audio_dir, ignore_errors=True)

    # ধাপ ৩: প্রতিটি আর্টিকেলের ব্যাকআপ অডিও (Ninada), ভিডিও রেন্ডার ও আপলোড
    for art in prepared_articles:
        entry_link, article_title = art["entry_link"], art["article_title"]
        raw_desc_clean, link_hash = art["raw_desc_clean"], art["link_hash"]
        downloaded_imgs, valid_circular_imgs, job_data = art["downloaded_imgs"], art["valid_circular_imgs"], art["job_data"]

        contact_sfx = "\n\nআবেদন করতে যোগাযোগ করুন WhatsApp: 01540503092"
        fb_yt_post_text = f"{article_title}\n\n{raw_desc_clean[:280]}...{contact_sfx}" if len(raw_desc_clean) > 20 else f"{article_title}{contact_sfx}"
        tiktok_caption = f"{article_title[:90]} | নতুন নিয়োগ বিজ্ঞপ্তি\n\nআবেদন করতে WhatsApp: 01540503092 নাম্বারে যোগাযোগ করুন।\n\n#bdjobs #jobcircular #career #bangladesh"
        video_final_title = article_title[:85].strip()

        audio_paths, first_valid_audio = _prepare_article_audios(art["expected_audio_files"], total_scripts_needed, memory)
        used_design_ids, poster_files_to_cleanup, article_poster_path = [], [], None

        def _make_poster(tag, _jd=job_data, _lh=link_hash, _used=used_design_ids, _cl=poster_files_to_cleanup):
            nonlocal article_poster_path
            d_id = pick_random_design_id(_used)
            p_path = prepare_tiktok_slides(_jd, f"tmp_poster_{_lh}_{tag}", design_id=d_id)[0]
            _cl.append(p_path)
            if not article_poster_path: article_poster_path = p_path
            return p_path

        for m_idx in range(motion_count):
            m_audio = audio_paths[m_idx] if m_idx < len(audio_paths) else first_valid_audio
            if not m_audio or not os.path.exists(m_audio): continue
            style_id = style_order[m_idx % len(style_order)]
            motion_vid_path = f"tmp_motion_{link_hash}_s{style_id}_{m_idx+1}.mp4"
            print(f"\n--- [Motion Phase #{m_idx+1}/{motion_count} | Style #{style_id}] ---")

            if render_tiktok_motion_video(job_data, m_audio, motion_vid_path, style_id=style_id, script_index=m_idx):
                if m_idx < len(tiktok_targets):
                    tk_acc = tiktok_targets[m_idx]
                    if save_to_gdrive:
                        try:
                            drive_name = f"{sanitize_filename(article_title[:42])}_style{style_id}.mp4"
                            upload_video_via_rclone(motion_vid_path, rclone_conf, folder_id=gdrive_folder_id, custom_filename=drive_name)
                        except Exception as ge: print(f"  ⚠️ [Google Drive Notice] {ge}")
                    try:
                        print(f"  [+] Uploading Style #{style_id} to TikTok Buffer Profile #{tk_acc.get('index')}...")
                        upload_to_specific_buffer_account(motion_vid_path, tiktok_caption, tk_acc['profile_id'], tk_acc['token'])
                    except Exception as be: print(f"  ⚠️ [TikTok Buffer Notice] {be}")

                _publish_yt_and_fb(
                    motion_vid_path, video_final_title, fb_yt_post_text,
                    motion_yt[m_idx] if m_idx < len(motion_yt) else None,
                    motion_fb[m_idx] if m_idx < len(motion_fb) else None,
                    fb_user_token, lambda t=f"m{m_idx+1}": _make_poster(t),
                    valid_circular_imgs, f"Motion Style #{style_id}"
                )
                if os.path.exists(motion_vid_path):
                    try: os.remove(motion_vid_path)
                    except Exception: pass

        for s_idx in range(standard_count):
            a_pos = motion_count + s_idx
            s_audio = audio_paths[a_pos] if a_pos < len(audio_paths) else first_valid_audio
            if not s_audio or not os.path.exists(s_audio): continue

            print(f"\n--- [Standard Phase #{s_idx+1}/{standard_count} | Audio #{a_pos+1}] ---")
            std_poster = _make_poster(f"s{s_idx+1}")
            std_vid_path = f"tmp_std_{link_hash}_{s_idx+1}.mp4"
            if render_vertical_video([std_poster] + valid_circular_imgs, s_audio, std_vid_path):
                _publish_yt_and_fb(
                    std_vid_path, video_final_title, fb_yt_post_text,
                    rem_yt[s_idx] if s_idx < len(rem_yt) else None,
                    rem_fb[s_idx] if s_idx < len(rem_fb) else None,
                    fb_user_token, lambda sp=std_poster: sp,
                    valid_circular_imgs, f"Standard Video #{s_idx+1}"
                )
                if os.path.exists(std_vid_path):
                    try: os.remove(std_vid_path)
                    except Exception: pass

        if not article_poster_path: _make_poster("social")
        social_imgs = ([article_poster_path] if article_poster_path and os.path.exists(article_poster_path) else []) + valid_circular_imgs

        if tg_client and tg_dest_ids and social_imgs:
            tg_images = social_imgs[:10]
            media_payload = tg_images[0] if len(tg_images) == 1 else tg_images
            for tg_id in tg_dest_ids:
                clean_tg = tg_id
                try:
                    clean_tg = clean_telegram_id(tg_id)
                    if clean_tg:
                        print(f"  [+] Posting {len(tg_images)} Photo(s) to Telegram Channel: @{clean_tg}")
                        await tg_client.send_file(clean_tg, media_payload, caption=fb_yt_post_text)
                        await asyncio.sleep(1.5)
                except Exception as e: print(f"  ⚠️ [Telegram Channel @{clean_tg} Notice] {e}")

        for did in wa_dest_ids:
            try: post_to_whatsapp_channel(render_wa_url, did, fb_yt_post_text, social_imgs)
            except Exception as e: print(f"  ⚠️ [WhatsApp Notice] {e}")

        for fp in set([a for a in audio_paths if a] + downloaded_imgs + poster_files_to_cleanup):
            if os.path.exists(fp):
                try: os.remove(fp)
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
