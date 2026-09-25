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
        print(f"  [🎬 Motion Background Video Selected] '{chosen}'")
        return chosen
    return None

def find_front_overlay_file():
    for f in ["Front.png", "front.png", "FRONT.PNG"]:
        if os.path.exists(f): return f
    return None

# 🌟 মোশন গ্রাফিক্স টেক্সট অ্যানিমেশনসহ TikTok ভিডিও রেন্ডারার
def render_tiktok_motion_video(job_data, audio_path, output_path, fps=24):
    print(f"  [~] Rendering Animated Motion Graphics TikTok Video: '{output_path}'")
    if not os.path.exists(audio_path): return False

    from tiktok_designer import generate_tiktok_animated_overlay_frames

    audio_duration = get_audio_duration(audio_path)
    bg_video = find_random_background_video()

    # অ্যানিমেশন ফ্রেম জেনারেট (২.৫ সেকেন্ড = ৬০ ফ্রেম)
    temp_anim_dir = f"_tmp_motion_anim_{random.randint(100000, 999999)}"
    hold_frame_path = generate_tiktok_animated_overlay_frames(job_data, temp_anim_dir, num_frames=60, fps=fps)

    # ব্যাকগ্রাউন্ড ভিডিও না থাকলে সাধারণ মোডে ফলব্যাক
    if not bg_video or not os.path.exists(bg_video):
        print("  ⚠️ No motion background videos found in 'Backgrounds/'. Falling back...")
        res = render_vertical_video([hold_frame_path], audio_path, output_path, fps)
        shutil.rmtree(temp_anim_dir, ignore_errors=True)
        return res

    w, h, vid_dur = get_video_properties(bg_video)

    # র্যান্ডম স্নাইপেট কাটা (অডিওর দৈর্ঘ্য অনুযায়ী)
    if vid_dur > audio_duration:
        max_start = max(0.0, vid_dur - audio_duration - 1.0)
        start_time = round(random.uniform(0.0, max_start), 2)
    else:
        start_time = 0.0

    print(f"  [✂️ Video Snippet] Cutting from {start_time}s to {round(start_time + audio_duration, 2)}s")

    # ১৬:৯ হলে ৯০ ডিগ্রি রোটেট করে ৯:১৬ পোর্ট্রেট (১০৮০x১৯২০) করা
    if w > h:
        print("  [🔄 Auto-Rotate] 16:9 Landscape Video detected. Rotating 90° to 9:16 Portrait...")
        video_filter = "transpose=1,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[bg]"
    else:
        video_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[bg]"

    # ইনপুটসমূহ
    inputs = [
        "-ss", str(start_time), "-t", str(audio_duration), "-i", bg_video,
        "-i", audio_path,
        "-framerate", str(fps), "-i", os.path.join(temp_anim_dir, "overlay_%04d.png"),
        "-loop", "1", "-t", str(audio_duration), "-i", hold_frame_path
    ]

    # Front.png হ্যান্ডলিং (নির্দিষ্ট ধীরগতি ও র্যান্ডম স্টার্টিং পজিশন)
    front_file = find_front_overlay_file()
    has_front = front_file and os.path.exists(front_file)
    if has_front:
        inputs.extend(["-loop", "1", "-t", str(audio_duration), "-i", front_file])

    filter_complex = [video_filter]

    # ইন্ট্রো অ্যানিমেশন (0 to 2.5s) এবং পরে স্ট্যাটিক হোল্ড ফ্রেম (2.5s to end)
    filter_complex.append("[bg][2:v]overlay=0:0:enable='lt(t,2.5)'[v_anim]")
    filter_complex.append("[v_anim][3:v]overlay=0:0:enable='gte(t,2.5)'[v_base]")
    last_v = "[v_base]"

    if has_front:
        front_idx = 4
        speed_x = random.choice([35, 42, -35, -42])
        speed_y = random.choice([28, 35, -28, -35])
        start_x = random.randint(50, 700)
        start_y = random.randint(100, 1200)

        max_fx = 1080 - 290
        max_fy = 1920 - 160
        x_expr = f"abs(mod({start_x}+({speed_x}*t),2*{max_fx})-{max_fx})"
        y_expr = f"abs(mod({start_y}+({speed_y}*t),2*{max_fy})-{max_fy})"

        filter_complex.append(f"[{front_idx}:v]scale=290:-1[front_scaled]")
        filter_complex.append(f"{last_v}[front_scaled]overlay=x='{x_expr}':y='{y_expr}'[final_v]")
        final_video_label = "[final_v]"
    else:
        final_video_label = last_v

    if os.path.exists(output_path): os.remove(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filter_complex),
        "-map", final_video_label,
        "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"  ❌ [FFmpeg Motion Video Error]: {e}")
        success = False

    shutil.rmtree(temp_anim_dir, ignore_errors=True)
    return success

# সাধারণ ফেসবুক/ইউটিউব ভিডিও রেন্ডারার
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
