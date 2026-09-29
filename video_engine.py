# -*- coding: utf-8 -*-
import os
import math
import shutil
import random
import subprocess
from PIL import Image

BACKGROUNDS_DIR = "Backgrounds"

def get_audio_duration(audio_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 30.0

def get_video_properties(video_path):
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "default=noprint_wrappers=1", video_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        lines = res.stdout.strip().split('\n')
        info = {}
        for line in lines:
            if '=' in line:
                k, v = line.split('=', 1)
                info[k.strip()] = v.strip()
        w = int(info.get('width', 1920))
        h = int(info.get('height', 1080))
        dur = float(info.get('duration', 60.0))
        return w, h, dur
    except Exception:
        return 1920, 1080, 60.0

def find_random_background_video():
    valid_exts = ('.mp4', '.mov', '.mkv', '.webm', '.avi')
    video_files = []
    if os.path.exists(BACKGROUNDS_DIR) and os.path.isdir(BACKGROUNDS_DIR):
        for f in os.listdir(BACKGROUNDS_DIR):
            if f.lower().endswith(valid_exts):
                video_files.append(os.path.join(BACKGROUNDS_DIR, f))

    if video_files:
        chosen = random.choice(video_files)
        print(f"  [🎬 Background Video Selected] '{chosen}'")
        return chosen
    return None

def find_front_overlay_file():
    for f in ["Front.png", "front.png", "FRONT.PNG"]:
        if os.path.exists(f): return f
    return None

# 🌟 TikTok-এর জন্য ৬টি এলিমেন্ট ও মোশন গ্রাফিক্স রেন্ডারার
def render_tiktok_motion_video(job_data, audio_path, output_path, fps=24):
    print(f"  [~] Rendering Animated TikTok Video (Elements Overlay): '{output_path}'")
    if not os.path.exists(audio_path): return False

    from tiktok_designer import generate_tiktok_animated_overlay_frames

    audio_duration = get_audio_duration(audio_path)
    total_frames = int(audio_duration * fps)

    temp_anim_dir = f"_tmp_elements_anim_{random.randint(100000, 999999)}"
    generate_tiktok_animated_overlay_frames(job_data, temp_anim_dir, total_frames=total_frames, fps=fps)

    bg_video = find_random_background_video()
    temp_dyn_bg = None

    # 🌟 ব্যাকগ্রাউন্ড ভিডিও না থাকলে কখনো কালো স্ক্রিন হবে না; ডায়নামিক মোশন ব্যাকগ্রাউন্ড তৈরি হবে
    if not bg_video or not os.path.exists(bg_video):
        print("  ⚠️ No background video in 'Backgrounds/'. Generating dynamic animated motion background...")
        temp_dyn_bg = f"_tmp_dyn_bg_{random.randint(100000, 999999)}.mp4"
        bg_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"gradients=s=1080x1920:r={fps}:c0=0x060d1b:c1=0x0f2b46:c2=0x1e1e38:c3=0x0a192f:duration={math.ceil(audio_duration)+2}:speed=0.01",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            temp_dyn_bg
        ]
        try:
            subprocess.run(bg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            if os.path.exists(temp_dyn_bg) and os.path.getsize(temp_dyn_bg) > 1000:
                bg_video = temp_dyn_bg
        except Exception:
            pass

    if not bg_video or not os.path.exists(bg_video):
        temp_dyn_bg = f"_tmp_dyn_bg_{random.randint(100000, 999999)}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0b132b:s=1080x1920:r={fps}:d={math.ceil(audio_duration)+2}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", temp_dyn_bg
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        bg_video = temp_dyn_bg

    w, h, vid_dur = get_video_properties(bg_video)

    if vid_dur > audio_duration:
        max_start = max(0.0, vid_dur - audio_duration - 1.0)
        start_time = round(random.uniform(0.0, max_start), 2)
    else:
        start_time = 0.0

    print(f"  [✂️ Video Snippet] Cutting from {start_time}s (Duration: {round(audio_duration, 1)}s)")

    if w > h:
        video_filter = "transpose=1,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[bg]"
    else:
        video_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[bg]"

    # 🌟 টিকটক ভিডিওতে front.png যুক্ত করা হয়নি (শুধুমাত্র মোশন ফ্রেম ওভারলে হবে)
    inputs = [
        "-ss", str(start_time), "-t", str(audio_duration), "-i", bg_video,
        "-i", audio_path,
        "-framerate", str(fps), "-i", os.path.join(temp_anim_dir, "overlay_%04d.png")
    ]

    filter_complex = [
        video_filter,
        "[bg][2:v]overlay=0:0[final_v]"
    ]

    if os.path.exists(output_path): os.remove(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filter_complex),
        "-map", "[final_v]",
        "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"  ❌ [FFmpeg Error]: {e}")
        success = False

    shutil.rmtree(temp_anim_dir, ignore_errors=True)
    if temp_dyn_bg and os.path.exists(temp_dyn_bg):
        try: os.remove(temp_dyn_bg)
        except Exception: pass

    return success

# সাধারণ ফেসবুক/ইউটিউব ভিডিও রেন্ডারার (এখানে front.png যথারীতি থাকবে)
def render_vertical_video(image_paths, audio_path, output_path, fps=24):
    if not image_paths or not os.path.exists(audio_path): return False
    valid_images = [p for p in image_paths if os.path.exists(p)]
    if not valid_images: return False

    audio_duration = get_audio_duration(audio_path)
    total_frames = int(audio_duration * fps)
    num_images = len(valid_images)
    frames_per_image = total_frames // num_images
    remainder = total_frames % num_images

    temp_dir = f"_tmp_frames_{random.randint(100000, 999999)}"
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try: resampling = Image.Resampling.LANCZOS
    except AttributeError: resampling = Image.ANTIALIAS

    front_overlay = None
    overlay_filename = find_front_overlay_file()
    if overlay_filename:
        try:
            overlay_raw = Image.open(overlay_filename).convert("RGBA")
            target_w = 290
            target_h = max(1, int(overlay_raw.size[1] * (target_w / overlay_raw.size[0])))
            front_overlay = overlay_raw.resize((target_w, target_h), resampling)
        except Exception: pass

    max_x = max(1, 720 - (front_overlay.size[0] if front_overlay else 290))
    max_y = max(1, 1280 - (front_overlay.size[1] if front_overlay else 150))
    start_pos_x = random.randint(0, int(max_x))
    start_pos_y = random.randint(0, int(max_y))
    speed_x = random.choice([-1, 1]) * random.uniform(30.0, 45.0)
    speed_y = random.choice([-1, 1]) * random.uniform(25.0, 40.0)

    frame_count = 0
    for idx, img_path in enumerate(valid_images):
        try:
            img = Image.open(img_path).convert('RGB')
            if img.size[1] == 0: continue
            num_f = frames_per_image + (1 if idx < remainder else 0)
            resized = img.resize((720, 1280), resampling)

            for f in range(num_f):
                frame = resized.copy()
                if front_overlay:
                    curr_time = frame_count / fps
                    raw_x = (start_pos_x + speed_x * curr_time) % (2 * max_x)
                    ox = int(raw_x if raw_x <= max_x else (2 * max_x - raw_x))
                    raw_y = (start_pos_y + speed_y * curr_time) % (2 * max_y)
                    oy = int(raw_y if raw_y <= max_x else (2 * max_y - raw_y))
                    
                    frame_rgba = frame.convert("RGBA")
                    frame_rgba.paste(front_overlay, (ox, oy), front_overlay)
                    frame = frame_rgba.convert("RGB")

                frame.save(os.path.join(temp_dir, f"frame_{frame_count:05d}.jpg"), "JPEG", quality=88)
                frame_count += 1
        except Exception: pass

    if frame_count == 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    if os.path.exists(output_path): os.remove(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(temp_dir, "frame_%05d.jpg"),
        "-i", audio_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-shortest", output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception: success = False

    shutil.rmtree(temp_dir, ignore_errors=True)
    return success
