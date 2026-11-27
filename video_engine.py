# -*- coding: utf-8 -*-
import os
import math
import shutil
import random
import subprocess
from PIL import Image, ImageOps


def get_audio_duration(audio_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 30.0


def _find_front_overlay_path():
    """রিপোজিটরির রুট বা সাব-ফোল্ডার থেকে Front.png খুঁজে বের করে"""
    candidates = [
        "Front.png", "front.png",
        os.path.join("Element", "Front.png"), os.path.join("Element", "front.png"),
        os.path.join("Elements", "Front.png"), os.path.join("Elements", "front.png"),
        os.path.join("Images", "Front.png"), os.path.join("Images", "front.png"),
        os.path.join("images", "Front.png"), os.path.join("images", "front.png"),
        os.path.join("Assets", "Front.png"), os.path.join("Assets", "front.png"),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    for d in [".", "Element", "Elements", "Images", "images", "Assets", "assets"]:
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.lower() == "front.png":
                    full_p = os.path.join(d, fn)
                    if os.path.isfile(full_p):
                        return full_p
    return None


def _prepare_front_overlay(W, H):
    """Front.png-কে ৭২০x১২৮০ ফ্রেমের জন্য প্রস্তুত করে এবং ভাসমান কি না নির্ধারণ করে"""
    front_path = _find_front_overlay_path()
    if not front_path:
        print("  ⚠️ [Standard Video] Front.png not found in repository; rendering without overlay.")
        return None

    try:
        with Image.open(front_path) as raw_im:
            im = raw_im.convert("RGBA")
        fw, fh = im.size
        if fw <= 0 or fh <= 0:
            return None

        try:
            resampling = Image.Resampling.LANCZOS
        except AttributeError:
            resampling = Image.ANTIALIAS

        ratio = fw / float(fh)
        target_ratio = W / float(H)

        # ১. যদি Front.png নিজেই 9:16 ক্যানভাস হয়
        if abs(ratio - target_ratio) <= 0.12:
            scaled = im.resize((W, H), resampling)
            bbox = scaled.getbbox()
            # স্বচ্ছ ক্যানভাসের ভেতর উপর-নিচে মার্জিন থাকলে হালকা ভাসানো (float) যাবে
            can_float = bool(bbox and bbox[1] >= 14 and (H - bbox[3]) >= 14)
            print(f"  [🖼️ Standard Video] Loaded 9:16 Front.png '{front_path}' ({fw}x{fh}, float={can_float})")
            return {
                "img": scaled,
                "x": 0,
                "y": 0,
                "float_amp": 10 if can_float else 0,
            }

        # ২. যদি Front.png একটি ব্যানার/স্টিকার/লোগো PNG হয়
        if ratio >= 1.4:
            new_w = int(round(W * 0.88))
            new_h = max(1, int(round(fh * (new_w / float(fw)))))
        else:
            scale = min((W * 0.50) / float(fw), (H * 0.25) / float(fh))
            new_w = max(1, int(round(fw * scale)))
            new_h = max(1, int(round(fh * scale)))

        scaled = im.resize((new_w, new_h), resampling)
        base_x = (W - new_w) // 2
        base_y = max(20, H - new_h - 125)
        print(f"  [🖼️ Standard Video] Loaded Floating Front.png '{front_path}' ({fw}x{fh} -> {new_w}x{new_h})")
        return {
            "img": scaled,
            "x": base_x,
            "y": base_y,
            "float_amp": 10,
        }
    except Exception as e:
        print(f"  ⚠️ [Standard Video] Failed to load Front.png: {e}")
        return None


def _overlay_front(frame_rgb, front_cfg, abs_t):
    if not front_cfg:
        return frame_rgb
    sp = front_cfg["img"]
    amp = front_cfg["float_amp"]
    dy = int(round(amp * math.sin(2.0 * math.pi * abs_t / 3.2))) if amp > 0 else 0
    out = frame_rgb.copy()
    out.paste(sp, (front_cfg["x"], front_cfg["y"] + dy), sp.getchannel("A"))
    return out


def render_tiktok_motion_video(job_data, audio_path, output_path, fps=24, design_id=None, save_poster_path=None, style_id=1, script_index=0):
    print(f"  [🎬 Motion Video Dispatcher] Rendering Style #{style_id}: '{output_path}'")
    if not os.path.exists(audio_path):
        return False

    try:
        if style_id == 2:
            from tiktok_motion_style2 import render_motion_style_2
            if render_motion_style_2(job_data, audio_path, output_path, fps=fps, script_index=script_index):
                return True
        elif style_id == 3:
            from tiktok_motion_style3 import render_motion_style_3
            if render_motion_style_3(job_data, audio_path, output_path, fps=fps, script_index=script_index):
                return True
        else:
            from tiktok_motion_engine import render_motion_graphics_video
            if render_motion_graphics_video(job_data, audio_path, output_path, fps=fps, script_index=script_index):
                return True
    except Exception as e:
        print(f"  ⚠️ [Motion Engine Style #{style_id} Fallback Notice] {e}")

    from tiktok_designer import render_poster_image
    audio_duration = get_audio_duration(audio_path)
    temp_poster_img = save_poster_path or f"_tmp_poster_{random.randint(100000, 999999)}.png"
    render_poster_image(job_data, temp_poster_img, design_id=design_id)

    if os.path.exists(output_path):
        os.remove(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-t", str(audio_duration),
        "-i", temp_poster_img, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        success = False

    if not save_poster_path and os.path.exists(temp_poster_img):
        try:
            os.remove(temp_poster_img)
        except Exception:
            pass
    return success


def render_vertical_video(image_paths, audio_path, output_path, fps=24):
    if not image_paths or not os.path.exists(audio_path):
        return False
    valid_images = [p for p in image_paths if os.path.exists(p)]
    if not valid_images:
        return False

    W, H = 720, 1280
    target_ratio = W / float(H)
    audio_duration = max(3.0, get_audio_duration(audio_path))
    total_frames = max(int(math.ceil(audio_duration * fps)), fps * 3)

    try:
        resampling = Image.Resampling.LANCZOS
    except AttributeError:
        resampling = Image.ANTIALIAS

    front_cfg = _prepare_front_overlay(W, H)

    # প্রতিটি ছবি প্রস্তুত করা (চাপানো ছাড়া; লম্বা হলে স্ক্রল, চওড়া হলে কালো ব্যাকগ্রাউন্ডে ফিট)
    prepared_slides = []
    for img_path in valid_images:
        try:
            with Image.open(img_path) as raw_img:
                img = ImageOps.exif_transpose(raw_img).convert("RGB")
                iw, ih = img.size
                if iw <= 0 or ih <= 0:
                    continue

                img_ratio = iw / float(ih)
                if img_ratio < (target_ratio - 0.02):
                    # 9:16-এর চেয়ে লম্বা ছবি: আসল অনুপাতে W প্রস্থে রেখে উপর থেকে নিচে স্মুথ স্ক্রল
                    new_h = int(round(ih * (W / float(iw))))
                    if new_h > H + 12:
                        tall_im = img.resize((W, new_h), resampling)
                        prepared_slides.append({"mode": "scroll_v", "img": tall_im, "max_scroll": new_h - H})
                        continue

                # 9:16 বা প্রস্থে বড় ছবি: চাপানো/ডান-বাম স্ক্রল ছাড়াই স্ক্রিনে ফিট ও উপরে-নিচে কালো ব্যাকগ্রাউন্ড
                scale = min(W / float(iw), H / float(ih))
                new_w = max(1, int(round(iw * scale)))
                new_h = max(1, int(round(ih * scale)))
                fitted = img.resize((new_w, new_h), resampling)
                canvas = Image.new("RGB", (W, H), (0, 0, 0))
                canvas.paste(fitted, ((W - new_w) // 2, (H - new_h) // 2))
                prepared_slides.append({"mode": "static", "img": canvas})
        except Exception:
            pass

    if not prepared_slides:
        return False

    num_slides = len(prepared_slides)
    frames_per_slide = total_frames // num_slides
    remainder = total_frames % num_slides

    if os.path.exists(output_path):
        os.remove(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
        "-i", "-", "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", output_path
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        global_frame = 0
        for s_idx, slide in enumerate(prepared_slides):
            num_f = frames_per_slide + (1 if s_idx < remainder else 0)
            if num_f <= 0:
                continue

            if slide["mode"] == "scroll_v":
                tall_im = slide["img"]
                max_scroll = slide["max_scroll"]
                hold_f = min(int(fps * 0.75), num_f // 6)
                scroll_f = max(1, num_f - 2 * hold_f)
                for f_i in range(num_f):
                    if f_i < hold_f:
                        p = 0.0
                    elif f_i >= num_f - hold_f:
                        p = 1.0
                    else:
                        t = (f_i - hold_f) / float(scroll_f)
                        # শুরু ও শেষে হালকা মসৃণ গতির সাথে উপর থেকে নিচে স্ক্রল
                        p = 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))
                    y_off = int(round(max_scroll * p))
                    frame = tall_im.crop((0, y_off, W, y_off + H))
                    frame = _overlay_front(frame, front_cfg, global_frame / float(fps))
                    proc.stdin.write(frame.tobytes())
                    global_frame += 1
            else:
                base_canvas = slide["img"]
                if not front_cfg or front_cfg["float_amp"] == 0:
                    static_bytes = _overlay_front(base_canvas, front_cfg, 0.0).tobytes()
                    for _ in range(num_f):
                        proc.stdin.write(static_bytes)
                        global_frame += 1
                else:
                    for _ in range(num_f):
                        frame = _overlay_front(base_canvas, front_cfg, global_frame / float(fps))
                        proc.stdin.write(frame.tobytes())
                        global_frame += 1

        proc.stdin.close()
        err_msg = proc.stderr.read().decode("utf-8", errors="ignore")
        ret = proc.wait(timeout=300)
        if ret != 0 and err_msg:
            print(f"  ⚠️ [FFmpeg Standard Notice] {err_msg[:180]}")
    except Exception as e:
        print(f"  ❌ [Standard Video Error] {e}")
        try:
            proc.kill()
        except Exception:
            pass
        return False

    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
