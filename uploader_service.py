# -*- coding: utf-8 -*-
import os
import re
import json
import random
import base64
import subprocess
import requests
from config_manager import HEADERS, get_credential

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
        return False
    if "drive.google.com" in bg_folder_id:
        m = re.search(r'folders/([a-zA-Z0-9_-]+)', bg_folder_id)
        if m: bg_folder_id = m.group(1)

    rclone_conf_str = get_credential(config, "rclone_conf", "RCLONE_CONF")
    if rclone_conf_str:
        conf_path = "_tmp_rclone_bg.conf"
        try:
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write(rclone_conf_str.strip())
            match = re.search(r'\[(.*?)\]', rclone_conf_str)
            remote_name = match.group(1).strip() if match else "gdrive"
            cmd = [
                "rclone", "--config", conf_path, "--drive-root-folder-id", bg_folder_id,
                "copy", f"{remote_name}:", "Backgrounds/",
                "--include", "*.mp4", "--include", "*.MP4", "--include", "*.mov",
                "--include", "*.MOV", "--include", "*.mkv", "--include", "*.webm", "--max-files", "8"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]:
                return True
        except Exception as e:
            print(f"  ⚠️ Rclone sync safely bypassed: {e}")
        finally:
            if os.path.exists(conf_path): os.remove(conf_path)

    try:
        import gdown
        gdown.download_folder(url=f"https://drive.google.com/drive/folders/{bg_folder_id}", output="Backgrounds", quiet=True, use_cookies=False)
    except Exception:
        pass
    return len([f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]) > 0

def get_all_youtube_targets(config=None):
    if config is None: config = {}
    targets = []
    raw_json = os.environ.get("YT_CHANNELS_JSON", "").strip() or get_credential(config, "yt_channels_json", "YT_CHANNELS_JSON")
    if raw_json:
        try:
            ch_list = json.loads(raw_json)
            if isinstance(ch_list, list):
                for idx, ch in enumerate(ch_list[:8], start=1):
                    cid = str(ch.get("client_id", "")).strip()
                    csec = str(ch.get("client_secret", "")).strip()
                    rtok = str(ch.get("refresh_token", "")).strip()
                    ch_name = str(ch.get("name", f"Channel #{idx}")).strip()
                    if cid and csec and rtok:
                        targets.append({"client_id": cid, "client_secret": csec, "refresh_token": rtok, "name": ch_name, "index": idx})
                if targets: return targets
        except Exception as e:
            print(f"  ⚠️ [YouTube JSON Config Parse Notice] {e}")

    for i in range(1, 9):
        cid = os.environ.get(f"YT_CLIENT_ID_{i}", "").strip() or os.environ.get(f"CLIENT_ID_{i}", "").strip() or (os.environ.get("YT_CLIENT_ID", "").strip() if i == 1 else "") or (os.environ.get("CLIENT_ID", "").strip() if i == 1 else "") or get_credential(config, f"yt_client_id_{i}", f"YT_CLIENT_ID_{i}")
        csec = os.environ.get(f"YT_CLIENT_SECRET_{i}", "").strip() or os.environ.get(f"CLIENT_SECRET_{i}", "").strip() or (os.environ.get("YT_CLIENT_SECRET", "").strip() if i == 1 else "") or (os.environ.get("CLIENT_SECRET", "").strip() if i == 1 else "") or get_credential(config, f"yt_client_secret_{i}", f"YT_CLIENT_SECRET_{i}")
        rtok = os.environ.get(f"YT_REFRESH_TOKEN_{i}", "").strip() or os.environ.get(f"REFRESH_TOKEN_{i}", "").strip() or (os.environ.get("YT_REFRESH_TOKEN", "").strip() if i == 1 else "") or (os.environ.get("REFRESH_TOKEN", "").strip() if i == 1 else "") or get_credential(config, f"yt_refresh_token_{i}", f"YT_REFRESH_TOKEN_{i}")
        if cid and csec and rtok:
            targets.append({"client_id": cid, "client_secret": csec, "refresh_token": rtok, "name": f"Channel #{i}", "index": i})

    if not targets:
        master_cid = os.environ.get("YT_CLIENT_ID", "").strip() or os.environ.get("CLIENT_ID", "").strip()
        master_csec = os.environ.get("YT_CLIENT_SECRET", "").strip() or os.environ.get("CLIENT_SECRET", "").strip()
        raw_tokens = os.environ.get("YT_REFRESH_TOKENS", "").strip()
        if raw_tokens and master_cid and master_csec:
            tokens = [t.strip() for t in re.split(r'[\r\n]+', raw_tokens) if t.strip() and not t.strip().startswith('#')]
            for idx, rtok in enumerate(tokens[:8], start=1):
                targets.append({"client_id": master_cid, "client_secret": master_csec, "refresh_token": rtok, "name": f"Channel #{idx}", "index": idx})
    return targets

def get_youtube_access_token(client_id, client_secret, refresh_token):
    if not client_id or not client_secret or not refresh_token: return None
    try:
        res = requests.post("https://oauth2.googleapis.com/token", data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=45)
        if res.status_code == 200:
            return res.json().get("access_token")
        print(f"  ⚠️ [YouTube Token Notice] Refresh failed (HTTP {res.status_code}): {res.text[:150]}")
    except Exception as e:
        print(f"  ⚠️ [YouTube Token Error] {e}")
    return None

def upload_video_to_youtube(client_id, client_secret, refresh_token, video_path, title, description):
    access_token = get_youtube_access_token(client_id, client_secret, refresh_token)
    if not access_token:
        print("  ⚠️ [YouTube Skip] Invalid/Expired Token. Skipping this channel safely.")
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
            "snippet": {"title": safe_title, "description": f"{description}\n\n#shorts #reels #jobcircular", "categoryId": "22"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
        res = requests.post(init_url, headers=headers, json=metadata, timeout=60)
        if res.status_code != 200:
            print(f"  ⚠️ [YouTube Init Error] HTTP {res.status_code}: {res.text[:150]}")
            return False
        upload_url = res.headers.get("Location")
        if not upload_url: return False
        with open(video_path, "rb") as f:
            up_res = requests.put(upload_url, headers={"Content-Length": str(os.path.getsize(video_path)), "Content-Type": "video/mp4"}, data=f, timeout=600)
        if up_res.status_code in [200, 201]:
            video_id = up_res.json().get("id")
            if video_id:
                print(f"  ✅ [YOUTUBE SUCCESS] Live Link: https://youtu.be/{video_id}")
                return True
        print(f"  ⚠️ [YouTube Upload Notice] HTTP {up_res.status_code}: {up_res.text[:150]}")
    except Exception as e:
        print(f"  ⚠️ [YouTube Exception Safely Handled] {e}")
    return False

def get_all_tiktok_buffer_targets(config=None):
    if config is None: config = {}
    targets = []
    for i in range(1, 5):
        token = os.environ.get(f"BUFFER_TOKEN_{i}", "").strip()
        profiles_str = os.environ.get(f"BUFFER_PROFILES_{i}", os.environ.get(f"BUFFER_PROFILE_{i}", "")).strip()
        if token and profiles_str:
            for pid in [p.strip() for p in profiles_str.split(',') if p.strip()]:
                targets.append({"profile_id": pid, "token": token, "account_index": i, "index": len(targets) + 1})
    if not targets:
        pid_def = os.environ.get("BUFFER_PROFILE_ID", "").strip()
        tok_def = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
        if pid_def and tok_def:
            for p in [p.strip() for p in pid_def.split(',') if p.strip()]:
                targets.append({"profile_id": p, "token": tok_def, "account_index": 1, "index": len(targets) + 1})
    return targets[:8]

def upload_to_public_host(video_path):
    clean_filename = f"reel_{random.randint(100000, 999999)}.mp4"

    try:
        with open(video_path, 'rb') as vf:
            r = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": (clean_filename, vf, "video/mp4")}, timeout=120)
        if r.status_code == 200:
            raw_u = (r.json().get("data") or {}).get("url", "").strip()
            if raw_u.startswith("http"):
                pub_url = raw_u.replace("http://", "https://").replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
                print(f"    🌐 [Host OK (tmpfiles.org)] {pub_url}")
                return pub_url
        print(f"    ⚠️ [Host Notice (tmpfiles.org)] HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"    ⚠️ [Host Error (tmpfiles.org)] {e}")

    try:
        with open(video_path, 'rb') as vf:
            r = requests.post("https://tmpfile.link/api/upload", files={"file": (clean_filename, vf, "video/mp4")}, headers={"Accept": "application/json"}, timeout=120)
        if r.status_code in [200, 201]:
            body = r.json()
            pub_url = (body.get("downloadLink") or body.get("downloadUrl") or "").strip()
            if pub_url.startswith("http"):
                print(f"    🌐 [Host OK (tmpfile.link)] {pub_url}")
                return pub_url
        print(f"    ⚠️ [Host Notice (tmpfile.link)] HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"    ⚠️ [Host Error (tmpfile.link)] {e}")

    try:
        with open(video_path, 'rb') as vf:
            r = requests.post("https://uguu.se/upload", files={"files[]": (clean_filename, vf, "video/mp4")}, timeout=120)
        if r.status_code == 200:
            files_arr = r.json().get("files") or []
            if files_arr and str(files_arr[0].get("url", "")).startswith("http"):
                pub_url = files_arr[0]["url"].strip()
                print(f"    🌐 [Host OK (uguu.se)] {pub_url}")
                return pub_url
        print(f"    ⚠️ [Host Notice (uguu.se)] HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"    ⚠️ [Host Error (uguu.se)] {e}")

    try:
        with open(video_path, 'rb') as vf:
            r = requests.put(f"https://ul.sto.care/{clean_filename}", data=vf, headers={"Content-Type": "video/mp4"}, timeout=120)
        if r.status_code in [200, 201]:
            m_url = re.search(r'https?://\S+', r.text.strip())
            if m_url:
                pub_url = m_url.group(0)
                print(f"    🌐 [Host OK (sto.care)] {pub_url}")
                return pub_url
        print(f"    ⚠️ [Host Notice (sto.care)] HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"    ⚠️ [Host Error (sto.care)] {e}")

    for name, url, data, file_key in [
        ("Litterbox", "https://litterbox.catbox.moe/resources/internals/api.php", {"reqtype": "fileupload", "time": "24h"}, "fileToUpload"),
        ("Catbox", "https://catbox.moe/user/api.php", {"reqtype": "fileupload"}, "fileToUpload"),
    ]:
        try:
            with open(video_path, 'rb') as vf:
                r = requests.post(url, data=data, files={file_key: (clean_filename, vf, "video/mp4")}, headers={"User-Agent": "curl/8.5.0"}, timeout=90)
            if r.status_code in [200, 201] and r.text.strip().startswith("http"):
                pub_url = r.text.strip()
                print(f"    🌐 [Host OK ({name})] {pub_url}")
                return pub_url
            print(f"    ⚠️ [Host Notice ({name})] HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"    ⚠️ [Host Error ({name})] {e}")

    pd_key = os.environ.get("PIXELDRAIN_API_KEY", "").strip()
    if pd_key:
        try:
            with open(video_path, 'rb') as vf:
                r = requests.post("https://pixeldrain.com/api/file", files={"file": (clean_filename, vf, "video/mp4")}, auth=("", pd_key), timeout=90)
            if r.status_code in [200, 201] and r.json().get("id"):
                pub_url = f"https://pixeldrain.com/api/file/{r.json()['id']}"
                print(f"    🌐 [Host OK (Pixeldrain)] {pub_url}")
                return pub_url
        except Exception as e:
            print(f"    ⚠️ [Host Error (Pixeldrain)] {e}")

    print("    ❌ [Public Host FAILED] All media hosts rejected the video upload!")
    return None

def upload_to_specific_buffer_account(video_path, description, profile_id, access_token):
    if not profile_id or not access_token:
        print("    ⚠️ [Buffer Skip] Missing profile_id or access_token.")
        return False

    video_url = upload_to_public_host(video_path)
    if not video_url:
        return False

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
            res = requests.post(graphql_url, json=payload, headers=headers, timeout=120)
            if res.status_code == 200:
                body = res.json()
                cp = body.get("data", {}).get("createPost", {}) or {}
                if "post" in cp and cp["post"].get("id"):
                    print(f"    ✅ [TikTok Buffer SUCCESS] Mode={mode}, PostID={cp['post']['id']}, Channel={profile_id}")
                    return True
                else:
                    print(f"    ⚠️ [Buffer Mutation Notice ({mode})] {json.dumps(body, ensure_ascii=False)[:220]}")
            else:
                print(f"    ⚠️ [Buffer HTTP {res.status_code} ({mode})] {res.text[:180]}")
        except Exception as e:
            print(f"    ⚠️ [Buffer Request Notice ({mode})] {e}")
    return False

def upload_video_to_tiktok_buffer(video_path, description, config=None):
    targets = get_all_tiktok_buffer_targets(config)
    if not targets: return False
    first = targets[0]
    return upload_to_specific_buffer_account(video_path, description, first['profile_id'], first['token'])

def upload_video_via_rclone(file_path, rclone_conf_str, folder_id="", custom_filename=None):
    if not rclone_conf_str or not os.path.exists(file_path): return False
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
        print(f"  📤 [Google Drive] Uploading '{target_name}'...")
        cmd = ["rclone", "--config", conf_path]
        if clean_folder_id:
            cmd.extend(["--drive-root-folder-id", clean_folder_id])
        cmd.extend(["copyto", file_path, f"{remote_name}:{target_name}"])
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
        if res.returncode == 0:
            print(f"  ✅ [Google Drive SUCCESS] Saved: '{target_name}'")
            return True
        print(f"  ⚠️ [Google Drive Notice] Exit code {res.returncode}: {res.stderr.strip()[:150]}")
    except Exception as e:
        print(f"  ⚠️ [Google Drive Exception Handled] {e}")
    finally:
        if os.path.exists(conf_path): os.remove(conf_path)
    return False

def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        r = requests.get(f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}&limit=100", timeout=30)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if str(p.get('id')) == str(page_id):
                    return p.get('access_token')
    except Exception: pass
    return master_user_token

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try:
        with open(photo_path, 'rb') as f:
            res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': f}, timeout=90)
        return res.status_code == 200
    except Exception: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            with open(path, 'rb') as f:
                r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': f}, timeout=60)
            if r.status_code == 200:
                att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token}, timeout=60)
        return res.status_code == 200
    except Exception: return False

def post_reel_to_facebook(page_id, page_token, video_path, title, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        res = requests.post(url, data={'upload_phase': 'start', 'access_token': page_token}, timeout=45)
        if res.status_code != 200: return False
        data = res.json()
        video_id, upload_url = data.get("video_id"), data.get("upload_url")
        if not video_id or not upload_url: return False
        headers = {"Authorization": f"OAuth {page_token}", "offset": "0", "file_size": str(os.path.getsize(video_path)), "Content-Type": "application/octet-stream"}
        with open(video_path, "rb") as f:
            up_res = requests.post(upload_url, headers=headers, data=f, timeout=300)
        if up_res.status_code != 200: return False
        pub_res = requests.post(url, data={"video_id": video_id, "upload_phase": "finish", "video_state": "PUBLISHED", "description": caption, "title": title, "access_token": page_token}, timeout=60)
        return pub_res.status_code == 200
    except Exception as e:
        print(f"  ⚠️ [Facebook Reel Notice] {e}")
        return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        with open(video_path, 'rb') as f:
            res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/videos", data={'description': caption, 'access_token': page_token}, files={'file': f}, timeout=180)
        return res.status_code == 200
    except Exception: return False

def post_to_whatsapp_channel(render_url, channel_id, text, image_paths):
    if not render_url: return False
    try:
        clean_id = channel_id.split('/')[-1].replace('@newsletter', '').strip()
        encoded = []
        for p in image_paths[:5]:
            if os.path.exists(p):
                with open(p, 'rb') as f:
                    encoded.append(base64.b64encode(f.read()).decode('utf-8'))
        res = requests.post(f"{render_url.rstrip('/')}/send", json={"channel_id": clean_id, "text": text, "images": encoded}, timeout=120)
        if res.status_code == 200:
            print(f"  ✅ [WhatsApp SUCCESS] Posted to @{clean_id} with {len(encoded)} image(s)!")
            return True
        print(f"  ⚠️ [WhatsApp Notice] Render returned HTTP {res.status_code}: {res.text[:120]}")
    except Exception as e:
        print(f"  ⚠️ [WhatsApp Channel Exception] {e}")
    return False
