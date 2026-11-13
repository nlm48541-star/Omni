# -*- coding: utf-8 -*-
import os
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

def render_tiktok_motion_video(job_data, audio_path, output_path, fps=24, design_id=None, save_poster_path=None):
    print(f"  [🎨 Poster Video Engine] Generating Video from Poster Image: '{output_path}'")
    if not os.path.exists(audio_path): return False

    from tiktok_designer import render_poster_image

    audio_duration = get_audio_duration(audio_path)
    temp_poster_img = save_poster_path or f"_tmp_poster_{random.randint(100000, 999999)}.png"

    render_poster_image(job_data, temp_poster_img, design_id=design_id)

    if os.path.exists(output_path): os.remove(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-t", str(audio_duration),
        "-i", temp_poster_img,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
        if success:
            print(f"  ✅ [SUCCESS] Poster Video Rendered ({round(os.path.getsize(output_path)/(1024*1024), 2)} MB, {round(audio_duration, 1)}s)")
    except Exception as e:
        print(f"  ❌ [FFmpeg Error]: {e}")
        success = False

    if not save_poster_path and os.path.exists(temp_poster_img):
        try: os.remove(temp_poster_img)
        except Exception: pass

    return success

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

    frame_count = 0
    for idx, img_path in enumerate(valid_images):
        try:
            with Image.open(img_path) as raw_img:
                img = raw_img.convert('RGB')
                if img.size[1] == 0: continue
                num_f = frames_per_image + (1 if idx < remainder else 0)
                if num_f <= 0: continue
                resized = img.resize((720, 1280), resampling)
                base_frame = os.path.join(temp_dir, f"base_{idx}.jpg")
                resized.save(base_frame, "JPEG", quality=88)
                for _ in range(num_f):
                    shutil.copyfile(base_frame, os.path.join(temp_dir, f"frame_{frame_count:05d}.jpg"))
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
    except Exception:
        success = False

    shutil.rmtree(temp_dir, ignore_errors=True)
    return success
