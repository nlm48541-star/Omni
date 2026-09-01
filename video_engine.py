# -*- coding: utf-8 -*-
import os
import math
import shutil
import random
import subprocess
from PIL import Image

def get_audio_duration(audio_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 30.0

def find_front_overlay_file():
    for f in ["Front.png", "front.png", "FRONT.PNG"]:
        if os.path.exists(f): return f
    return None

def render_vertical_video(image_paths, audio_path, output_path, fps=24):
    print(f"  [~] Rendering 9:16 Vertical Video: '{output_path}'")
    if not image_paths or not os.path.exists(audio_path):
        return False

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

    # 🌟 Front.png সাইজ বড় করা (২৯০ পিক্সেল)
    front_overlay = None
    overlay_filename = find_front_overlay_file()
    if overlay_filename:
        try:
            overlay_raw = Image.open(overlay_filename).convert("RGBA")
            ow, oh = overlay_raw.size
            target_w = 290
            target_h = max(1, int(oh * (target_w / ow)))
            front_overlay = overlay_raw.resize((target_w, target_h), resampling)
            print(f"  [+] Loaded Front overlay (Size: {target_w}x{target_h})")
        except Exception:
            front_overlay = None

    # 🌟 র্যান্ডম স্টার্টিং পজিশন ও ধীরগতির গতিবেগ নির্ধারণ
    max_x = max(1, 720 - (front_overlay.size[0] if front_overlay else 290))
    max_y = max(1, 1280 - (front_overlay.size[1] if front_overlay else 150))
    
    start_pos_x = random.randint(0, int(max_x))
    start_pos_y = random.randint(0, int(max_y))
    
    # প্রতি সেকেন্ডে নির্দিষ্ট ধীর গতি (Pixel per second)
    speed_x = random.choice([-1, 1]) * random.uniform(30.0, 45.0)
    speed_y = random.choice([-1, 1]) * random.uniform(25.0, 40.0)

    frame_count = 0
    for idx, img_path in enumerate(valid_images):
        try:
            img = Image.open(img_path).convert('RGB')
            w, h = img.size
            if h == 0: continue
            num_f = frames_per_image + (1 if idx < remainder else 0)
            resized = img.resize((720, 1280), resampling)

            for f in range(num_f):
                frame = resized.copy()
                if front_overlay:
                    ow, oh = front_overlay.size
                    curr_time = frame_count / fps
                    
                    # বাউন্সিং ও স্মুথ মোশন
                    raw_x = (start_pos_x + speed_x * curr_time) % (2 * max_x)
                    ox = int(raw_x if raw_x <= max_x else (2 * max_x - raw_x))
                    
                    raw_y = (start_pos_y + speed_y * curr_time) % (2 * max_y)
                    oy = int(raw_y if raw_y <= max_y else (2 * max_y - raw_y))
                    
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

    ffmpeg_cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(temp_dir, "frame_%05d.jpg"),
        "-i", audio_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-shortest", output_path
    ]

    try:
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        success = False

    shutil.rmtree(temp_dir, ignore_errors=True)
    return success
