# -*- coding: utf-8 -*-
import os
import json
import uuid
import random
import requests
from config_manager import HEADERS, get_credential

# --- FACEBOOK HANDLERS ---
def get_page_access_token(master_user_token, page_id):
    if not master_user_token: return None
    try:
        url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={master_user_token}&limit=100"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            for p in r.json().get('data', []):
                if str(p.get('id')) == str(page_id): return p.get('access_token')
    except Exception: pass
    return master_user_token

def post_photo_to_facebook(page_id, page_token, photo_path, caption):
    try:
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'caption': caption, 'access_token': page_token}, files={'source': open(photo_path, 'rb')}, timeout=60)
        return res.status_code == 200
    except Exception: return False

def post_multi_photo_to_facebook(page_id, page_token, photo_paths, caption):
    try:
        att = []
        for path in photo_paths:
            r = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/photos", data={'published': 'false', 'access_token': page_token}, files={'source': open(path, 'rb')}, timeout=45)
            if r.status_code == 200: att.append({"media_fbid": r.json().get('id')})
        if not att: return False
        res = requests.post(f"https://graph.facebook.com/v20.0/{page_id}/feed", data={'message': caption, 'attached_media': json.dumps(att), 'access_token': page_token}, timeout=30)
        return res.status_code == 200
    except Exception: return False

def post_reel_to_facebook(page_id, page_token, video_path, title, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        res = requests.post(url, data={'upload_phase': 'start', 'access_token': page_token}, timeout=25)
        if res.status_code != 200: return False
        data = res.json()
        video_id, upload_url = data.get("video_id"), data.get("upload_url")
        if not video_id or not upload_url: return False
            
        file_size = os.path.getsize(video_path)
        headers = {"Authorization": f"OAuth {page_token}", "offset": "0", "file_size": str(file_size), "Content-Type": "application/octet-stream"}
        with open(video_path, "rb") as f:
            up_res = requests.post(upload_url, headers=headers, data=f, timeout=180)
        if up_res.status_code != 200: return False
            
        finish_payload = {"video_id": video_id, "upload_phase": "finish", "video_state": "PUBLISHED", "description": caption, "title": title, "access_token": page_token}
        pub_res = requests.post(url, data=finish_payload, timeout=40)
        return pub_res.status_code == 200
    except Exception: return False

def post_video_to_facebook(page_id, page_token, video_path, caption):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
        files = {'file': open(video_path, 'rb')}
        data = {'description': caption, 'access_token': page_token}
        res = requests.post(url, data=data, files=files, timeout=120)
        return res.status_code == 200
    except Exception: return False

# --- YOUTUBE SHORTS HANDLER ---
def get_youtube_access_token(client_id, client_secret, refresh_token):
    if not client_id or not client_secret or not refresh_token: return None
    url = "https://oauth2.googleapis.com/token"
    payload = {"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}
    try:
        res = requests.post(url, data=payload, timeout=20)
        if res.status_code == 200: return res.json().get("access_token")
    except Exception: pass
    return None

def upload_video_to_youtube(client_id, client_secret, refresh_token, video_path, title, description):
    access_token = get_youtube_access_token(client_id, client_secret, refresh_token)
    if not access_token: return False
    try:
        init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(os.path.getsize(video_path)), "X-Upload-Content-Type": "video/mp4"}
        metadata = {"snippet": {"title": title[:80] + " #shorts", "description": description + "\n\n#shorts #reels", "categoryId": "22"}, "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
        res = requests.post(init_url, headers=headers, json=metadata, timeout=30)
        upload_url = res.headers.get("Location")
        if not upload_url: return False
            
        with open(video_path, "rb") as f:
            up_res = requests.put(upload_url, headers={"Content-Length": str(os.path.getsize(video_path)), "Content-Type": "video/mp4"}, data=f, timeout=300)
        return up_res.status_code in [200, 201]
    except Exception: return False

# --- TIKTOK BUFFER HANDLER ---
def upload_to_public_host(video_path):
    clean_filename = f"reel_{random.randint(100000, 999999)}.mp4"
    hosts = [
        ("Catbox", lambda: requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": (clean_filename, open(video_path, 'rb'), "video/mp4")}, headers=HEADERS, timeout=45)),
        ("Litterbox", lambda: requests.post("https://litterbox.catbox.moe/resources/internals/api.php", data={"reqtype": "fileupload", "time": "24h"}, files={"fileToUpload": (clean_filename, open(video_path, 'rb'), "video/mp4")}, headers=HEADERS, timeout=45)),
        ("Pixeldrain", lambda: requests.post("https://pixeldrain.com/api/file", files={"file": (clean_filename, open(video_path, 'rb'), "video/mp4")}, headers=HEADERS, timeout=45))
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

def upload_video_to_tiktok_buffer(video_path, description, config=None):
    if config is None: config = {}
    buffer_profile_id = get_credential(config, "buffer_profile_id", "BUFFER_PROFILE_ID")
    buffer_access_token = get_credential(config, "buffer_access_token", "BUFFER_ACCESS_TOKEN")
    if not buffer_profile_id or not buffer_access_token: return False

    video_url = upload_to_public_host(video_path)
    if not video_url: return False

    clean_desc = description[:100] + " #jobcircular #jobs #bangladesh"
    graphql_url = "https://api.buffer.com"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {buffer_access_token}"}
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """
    for mode in ["shareNow", "addToQueue"]:
        payload = {"query": mutation, "variables": {"input": {"channelId": buffer_profile_id, "text": clean_desc, "schedulingType": "automatic", "mode": mode, "assets": [{"video": {"url": video_url}}]}}}
        try:
            res = requests.post(graphql_url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200 and "post" in res.json().get("data", {}).get("createPost", {}):
                print(f"  [+] TikTok posted via Buffer ({mode})!")
                return True
        except Exception: pass
    return False

# --- WHATSAPP HANDLER ---
def post_to_whatsapp_channel(render_url, channel_id, text, image_paths):
    if not render_url: return False
    try:
        import base64
        clean_id = channel_id.split('/')[-1].replace('@newsletter', '').strip()
        encoded = []
        for p in image_paths[:5]:
            if os.path.exists(p):
                with open(p, 'rb') as f: encoded.append(base64.b64encode(f.read()).decode('utf-8'))
        payload = {"channel_id": clean_id, "text": text, "images": encoded}
        res = requests.post(f"{render_url.rstrip('/')}/send", json=payload, timeout=90)
        return res.status_code == 200
    except Exception: return False
