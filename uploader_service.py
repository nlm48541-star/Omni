# 🌟 গুগল ড্রাইভ ফোল্ডার থেকে ব্যাকগ্রাউন্ড ভিডিও শতভাগ নিশ্চিতভাবে ডাউনলোডের ফাংশন
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

    print(f"  📥 [Google Drive] Fetching background videos from Folder ID: '{bg_folder_id}'...")

    # পদ্ধতি ১: Rclone এ ফোল্ডার আইডি নির্দিষ্ট করে ডাউনলোড
    rclone_conf_str = get_credential(config, "rclone_conf", "RCLONE_CONF")
    if rclone_conf_str:
        conf_path = "_tmp_rclone_bg.conf"
        try:
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write(rclone_conf_str.strip())
            match = re.search(r'\[(.*?)\]', rclone_conf_str)
            remote_name = match.group(1).strip() if match else "gdrive"

            # 🌟 --drive-root-folder-id দিয়ে নির্দিষ্ট ফোল্ডার আইডিতে রুট সেট করা
            cmd = [
                "rclone", "--config", conf_path,
                "--drive-root-folder-id", bg_folder_id,
                "copy", f"{remote_name}:", "Backgrounds/",
                "--include", "*.mp4", "--include", "*.MP4",
                "--include", "*.mov", "--include", "*.MOV",
                "--include", "*.mkv", "--include", "*.webm",
                "--max-files", "5"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            downloaded = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
            if downloaded:
                print(f"  ✅ [Rclone] Successfully downloaded {len(downloaded)} video(s) from Google Drive: {downloaded}")
                return True
        except Exception as e:
            print(f"  ⚠️ Rclone sync note: {e}")
        finally:
            if os.path.exists(conf_path):
                os.remove(conf_path)

    # পদ্ধতি ২: পাবলিক লিঙ্ক হলে gdown দিয়ে ফোল্ডারের ভিডিও সরাসরি ডাউনলোড
    try:
        print("  📥 [Public Drive Link] Attempting download via gdown...")
        folder_url = f"https://drive.google.com/drive/folders/{bg_folder_id}"
        subprocess.run([
            "gdown", "--folder", folder_url,
            "-O", "Backgrounds/",
            "--remaining-ok", "--quiet"
        ], timeout=180)
        downloaded = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
        if downloaded:
            print(f"  ✅ [gdown] Successfully downloaded {len(downloaded)} video(s): {downloaded}")
            return True
    except Exception as e:
        print(f"  ⚠️ gdown notice: {e}")

    downloaded = [f for f in os.listdir("Backgrounds") if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm'))]
    return len(downloaded) > 0
