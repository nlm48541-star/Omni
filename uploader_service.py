# -*- coding: utf-8 -*-
import os
import re
import json
import random
import base64
import subprocess
import requests
from config_manager import HEADERS, get_credential

# =========================================================================
# 🌟 ১. গুগল ড্রাইভ থেকে ব্যাকগ্রাউন্ড ভিডিও সিঙ্ক
# =========================================================================
def sync_background_videos_from_gdrive(config=None):
    if config is None: config = {}
    
    bg_folder_id = (
        os.environ.get("GDRIVE_BG_FOLDER_ID", "").strip() or
        os.environ.get("BG_FOLDER_ID", "").strip() or
        get_credential(config, "gdrive_bg_folder_id", "GDRIVE_BG_FOLDER_ID") or
        get_credential(config, "bg_folder_id", "BG_FOLDER_ID")
    )

    os.makedirs("Backgrounds", exist_ok=True)
    existing_videos = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
    if len(existing_videos) >= 2:
        print(f"  📁 [Backgrounds] Found {len(existing_videos)} existing background video(s) locally.")
        return True

    if not bg_folder_id:
        print("  ℹ️ [Backgrounds] 'GDRIVE_BG_FOLDER_ID' not provided in Secrets. Local/Dynamic backgrounds will be used.")
        return False

    if "drive.google.com" in bg_folder_id:
        m = re.search(r'folders/([a-zA-Z0-9_-]+)', bg_folder_id)
        if m: bg_folder_id = m.group(1)

    print(f"  📥 [Google Drive] Fetching background videos from Folder ID: '{bg_folder_id}'...")

    rclone_conf_str = get_credential(config, "rclone_conf", "RCLONE_CONF")
    if rclone_conf_str:
        conf_path = "_tmp_rclone_bg.conf"
        try:
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write(rclone_conf_str.strip())
            match = re.search(r'\[(.*?)\]', rclone_conf_str)
            remote_name = match.group(1).strip() if match else "gdrive"

            cmd = [
                "rclone", "--config", conf_path,
                "--drive-root-folder-id", bg_folder_id,
                "copy", f"{remote_name}:", "Backgrounds/",
                "--include", "*.mp4", "--include", "*.MP4",
                "--include", "*.mov", "--include", "*.MOV",
                "--include", "*.mkv", "--include", "*.webm",
                "--max-files", "8"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            downloaded = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
            if downloaded:
                print(f"  ✅ [Rclone] Successfully downloaded {len(downloaded)} video(s) from Google Drive: {downloaded}")
                return True
        except Exception as e:
            print(f"  ⚠️ Rclone sync notice: {e}")
        finally:
            if os.path.exists(conf_path):
                os.remove(conf_path)

    try:
        print("  📥 [Public Drive Link] Attempting download via gdown Python API...")
        import gdown
        folder_url = f"https://drive.google.com/drive/folders/{bg_folder_id}"
        gdown.download_folder(url=folder_url, output="Backgrounds", quiet=True, use_cookies=False)
        downloaded = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
        if downloaded:
            print(f"  ✅ [gdown] Successfully downloaded {len(downloaded)} video(s): {downloaded}")
            return True
    except Exception as e:
        print(f"  ⚠️ gdown notice: {e}")

    downloaded = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
    return len(downloaded) > 0

# =========================================================================
# 🌟 ২. YouTube Shorts মাল্টি-চ্যানেল হ্যান্ডলার
# =========================================================================
def get_all_youtube_targets(config=None):
    if config is None: config = {}
    targets = []

    for i in range(1, 9):
        cid = os.environ.get(f"YT_CLIENT_ID_{i}", "").strip()
        csec = os.environ.get(f"YT_CLIENT_SECRET_{i}", "").strip()
        rtok = os.environ.get(f"YT_REFRESH_TOKEN_{i}", "").strip()
        if cid and csec and rtok:
            targets.append({"client_id": cid, "client_secret": csec, "refresh_token": rtok, "index": i})

    if not targets:
        cid1 = os.environ.get("YT_CLIENT_ID", "").strip() or os.environ.get("CLIENT_ID", "").strip()
        csec1 = os.environ.get("YT_CLIENT_SECRET", "").strip() or os.environ.get("CLIENT_SECRET", "").strip()
        rtok1 = os.environ.get("YT_REFRESH_TOKEN", "").strip() or os.environ.get("REFRESH_TOKEN", "").strip()
        if cid1 and csec1 and rtok1:
            targets.append({"client_id": cid1, "client_secret": csec1, "refresh_token": rtok1, "index": 1})

        cid2 = os.environ.get("YT_CLIENT_ID_2", "").strip() or os.environ.get("CLIENT_ID_2", "").strip()
        csec2 = os.environ.get("YT_CLIENT_SECRET_2", "").strip() or os.environ.get("CLIENT_SECRET_2", "").strip()
        rtok2 = os.environ.get("YT_REFRESH_TOKEN_2", "").strip() or os.environ.get("REFRESH_TOKEN_2", "").strip()
        if cid2 and csec2 and rtok2:
            targets.append({"client_id": cid2, "client_secret": csec2, "refresh_token": rtok2, "index": 2})

    return targets

def get_youtube_access_token(client_id, client_secret, refresh_token):
    if not client_id or not client_secret or not refresh_token: return None
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    try:
        res = requests.post(url, data=payload, timeout=60)
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception: pass
    return None

def upload_video_to_youtube(client_id, client_secret, refresh_token, video_path, title, description):
    access_token = get_youtube_access_token(client_id, client_secret, refresh_token)
    if not access_token:
        print("  ❌ [YOUTUBE ERROR] Could not refresh Access Token.")
        return False

    try:
        init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(os.path.getsize(video_path)),
            "X-Upload-Content-Type": "video/mp4"
        }
        
        safe_title = re.sub(r'[\<\>]', '', str(title)).strip()[:80]
        if not safe_title.lower().endswith('#shorts'):
            safe_title = f"{safe_title} #shorts"

        metadata = {
            "snippet": {
                "title": safe_title,
                "description": f"{description}\n\n#shorts #reels #jobcircular",
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        res = requests.post(init_url, headers=headers, json=metadata, timeout=90)
        if res.status_code != 200:
            print(f"  ❌ [YOUTUBE INIT ERROR] HTTP {res.status_code}: {res.text[:200]}")
            return False

        upload_url = res.headers.get("Location")
        if not upload_url: return False

        with open(video_path, "rb") as f:
            up_res = requests.put(
                upload_url,
                headers={"Content-Length": str(os.path.getsize(video_path)), "Content-Type": "video/mp4"},
                data=f,
                timeout=900
            )

        if up_res.status_code in [200, 201]:
            video_id = up_res.json().get("id")
            if video_id:
                print(f"  ✅ [YOUTUBE SUCCESS] Video Published! Live Link: https://youtu.be/{video_id}")
                return True
        else:
            print(f"  ❌ [YOUTUBE UPLOAD ERROR] HTTP {up_res.status_code}: {up_res.text[:200]}")
            return False

    except Exception as e:
        print(f"  ❌ [YOUTUBE EXCEPTION] {e}")
        return False
    return False

# =========================================================================
# 🌟 ৩. TikTok / Buffer মাল্টি-অ্যাকাউন্ট হ্যান্ডলার
# =========================================================================
def get_all_tiktok_buffer_targets(config=None):
    if config is None: config = {}
    targets = []
    
    for i in range(1, 5):
        token = os.environ.get(f"BUFFER_TOKEN_{i}", "").strip()
        profiles_str = os.environ.get(f"BUFFER_PROFILES_{i}", os.environ.get(f"BUFFER_PROFILE_{i}", "")).strip()

        if token and profiles_str:
            profile_ids = [p.strip() for p in profiles_str.split(',') if p.strip()]
            for pid in profile_ids:
                targets.append({
                    "profile_id": pid,
                    "token": token,
                    "account_index": i,
                    "index": len(targets) + 1
                })

    if not targets:
        pid_def = os.environ.get("BUFFER_PROFILE_ID", "").strip()
        tok_def = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
        if pid_def and tok_def:
            p_list = [p.strip() for p in pid_def.split(',') if p.strip()]
            for p in p_list:
                targets.append({
                    "profile_id": p,
                    "token": tok_def,
                    "account_index": 1,
                    "index": len(targets) + 1
                })

    return targets[:8]

def upload_to_public_host(video_path):
    clean_filename = f"reel_{random.randint(100000, 999999)}.mp4"
    hosts = [
        ("Catbox", lambda: requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": (clean_filename, open(video_path, 'rb'), "video/mp4")}, headers=HEADERS, timeout=135)),
        ("Litterbox", lambda: requests.post("https://litterbox.catbox.moe/resources/internals/api.php", data={"reqtype": "fileupload", "time": "24h"}, files={"fileToUpload": (clean_filename, open(video_path, 'rb'), "video/mp4")}, headers=HEADERS, timeout=135)),
        ("Pixeldrain", lambda: requests.post("https://pixeldrain.com/api/file", files={"file": (clean_filename, open(video_path, 'rb'), "video/mp4")}, headers=HEADERS, timeout=135))
    ]
    for name, fn in hosts:
        try:
            r = fn()
            if r.status_code in [200, 201]:
                if name == "Pixeldrain":
                    fid = r.json().get("id")
                    if fid: return f"https://pixeldrain.com/api/file/{fid}"
                elif r.text.strip().startswith("http"):
                    return r.text.strip()
        except Exception: pass
    return None

def upload_to_specific_buffer_account(video_path, description, profile_id, access_token):
    if not profile_id or not access_token: return False

    video_url = upload_to_public_host(video_path)
    if not video_url: return False

    clean_desc = description[:100] + " #jobcircular #jobs #bangladesh"
    graphql_url = "https://api.buffer.com"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """
    for mode in ["shareNow", "addToQueue"]:
        payload = {
            "query": mutation,
            "variables": {
                "input": {
                    "channelId": profile_id,
                    "text": clean_desc,
                    "schedulingType": "automatic",
                    "mode": mode,
                    "assets": [{"video": {"url": video_url}}]
                }
            }
        }
        try:
            res = requests.post(graphql_url, json=payload, headers=headers, timeout=180)
            if res.status_code == 200 and "post" in res.json().get("data", {}).get("createPost", {}):
                return True
        except Exception: pass
    return False

def upload_video_to_tiktok_buffer(video_path, description, config=None):
    targets = get_all_tiktok_buffer_targets(config)
    if not targets: return False
    first = targets[0]
    return upload_to_specific_buffer_account(video_path, description, first['profile_id'], first['token'])

# =========================================================================
# 🌟 ৪. RCLONE গুগল ড্রাইভ আপলোড হ্যান্ডলার
# =========================================================================
def upload_video_via_rclone(file_path, rclone_conf_str, folder_id="", custom_filename=None):
    if not rclone_conf_str:
        print("  ⚠️ [Google Drive Error] 'RCLONE_CONF' secret is empty or missing!")
        return False

    if not os.path.exists(file_path):
        print(f"  ⚠️ [Google Drive Error] Video file not found: {file_path}")
        return False

    clean_folder_id = str(folder_id).strip()
    if "drive.google.com" in clean_folder_id:
        m = re.search(r'folders/([a-zA-Z0-9_-]+)', clean_folder_id)
        if m: clean_folder_id = m.group(1)

    conf_path = "_tmp_rclone_upload.conf"
    try:
        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(rclone_conf_str.strip())
        match = re.search(r'\[(.*?)\]', rclone_conf_str)
        remote_name = match.group(1).strip() if match else "gdrive"

        target_name = custom_filename or os.path.basename(file_path)
        print(f"  📤 [Google Drive] Uploading '{target_name}' to Remote: '{remote_name}' (Folder ID: '{clean_folder_id}')...")

        if clean_folder_id:
            cmd = [
                "rclone", "--config", conf_path,
                "--drive-root-folder-id", clean_folder_id,
                "copyto", file_path, f"{remote_name}:{target_name}",
                "-v"
            ]
        else:
            cmd = [
                "rclone", "--config", conf_path,
                "copyto", file_path, f"{remote_name}:{target_name}",
                "-v"
            ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res.returncode == 0:
            print(f"  ✅ [Google Drive SUCCESS] Video saved to Google Drive: '{target_name}'")
            return True
        else:
            print(f"  ❌ [Google Drive Upload Failed] Exit code {res.returncode}")
            print(f"  ⚠️ Rclone Error Output: {res.stderr.strip()[:300]}")
            return False

    except Exception as e:
        print(f"  ❌ [Google Drive Exception] {e}")
        return False
    finally:
        if os.path.exists(conf_path):
            os.remove(conf_path)

# =========================================================================
# 🌟 ৫. FACEBOOK GRAPH API হ্যান্ডলার
# =========================================================================
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}&limit=100"
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if str(p.get('id')) == str(page_id):
                    return p.get('access_token')
    except Exception: pass
    return master_user_token

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try:
        with open(photo_path, 'rb') as f:
            res = requests.post(
                f"https://graph.facebook.com/v20.0/{page_id}/photos",
                data={'caption': caption, 'access_token': page_token},
                files={'source': f},
                timeout=180
            )
        return res.status_code == 200
    except Exception: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            with open(path, 'rb') as f:
                r = requests.post(
                    f"https://graph.facebook.com/v20.0/{page_id}/photos",
                    data={'published': 'false', 'access_token': page_token},
                    files={'source': f},
                    timeout=135
                )
            if r.status_code == 200:
                att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        res = requests.post(
            f"https://graph.facebook.com/v20.0/{page_id}/feed",
            data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token},
            timeout=90
        )
        return res.status_code == 200
    except Exception: return False

def post_reel_to_facebook(page_id, page_token, video_path, title, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        res = requests.post(url, data={'upload_phase': 'start', 'access_token': page_token}, timeout=75)
        if res.status_code != 200: return False
        data = res.json()
        video_id, upload_url = data.get("video_id"), data.get("upload_url")
        if not video_id or not upload_url: return False
            
        file_size = os.path.getsize(video_path)
        headers = {
            "Authorization": f"OAuth {page_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        with open(video_path, "rb") as f:
            up_res = requests.post(upload_url, headers=headers, data=f, timeout=540)
        if up_res.status_code != 200: return False
            
        finish_payload = {
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": caption,
            "title": title,
            "access_token": page_token
        }
        pub_res = requests.post(url, data=finish_payload, timeout=120)
        return pub_res.status_code == 200
    except Exception: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
        with open(video_path, 'rb') as f:
            res = requests.post(
                url,
                data={'description': caption, 'access_token': page_token},
                files={'file': f},
                timeout=360
            )
        return res.status_code == 200
    except Exception: return False

# =========================================================================
# 🌟 ৬. WHATSAPP চ্যানেল হ্যান্ডলার
# =========================================================================
def post_to_whatsapp_channel(render_url, channel_id, text, image_paths):
    if not render_url: return False
    try:
        clean_id = channel_id.split('/')[-1].replace('@newsletter', '').strip()
        encoded = []
        for p in image_paths[:5]:
            if os.path.exists(p):
                with open(p, 'rb') as f:
                    encoded.append(base64.b64encode(f.read()).decode('utf-8'))
        payload = {"channel_id": clean_id, "text": text, "images": encoded}
        res = requests.post(f"{render_url.rstrip('/')}/send", json=payload, timeout=270)
        return res.status_code == 200
    except Exception: return False
