# -*- coding: utf-8 -*-
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


def _get_kaggle_username() -> str:
    return os.environ.get("KAGGLE_USERNAME", "yusufadnan").strip() or "yusufadnan"


def _get_kernel_slug_base() -> str:
    return os.environ.get("KAGGLE_WORKER_SLUG", "indicf5-tts-worker").strip() or "indicf5-tts-worker"


def _get_dataset_slug() -> str:
    return os.environ.get("KAGGLE_DATASET_SLUG", "yusufadnan/indicf5-bd-fast").strip() or "yusufadnan/indicf5-bd-fast"


def has_kaggle_credentials() -> bool:
    return (
        bool(os.environ.get("KAGGLE_API_TOKEN", "").strip())
        or (bool(os.environ.get("KAGGLE_USERNAME", "").strip()) and bool(os.environ.get("KAGGLE_KEY", "").strip()))
        or (Path.home() / ".kaggle" / "kaggle.json").exists()
        or (Path.home() / ".kaggle" / "access_token").exists()
    )


_GPU_WORKER_TEMPLATE = r'''import json
import os
import sys
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

bundle_dir = Path(sys.argv[1])
ref_wav = sys.argv[2]
ref_text = sys.argv[3]
jobs_path = sys.argv[4]
worker_id = int(sys.argv[5])
num_workers = int(sys.argv[6])
speech_speed = float(sys.argv[7])
nfe_step = int(sys.argv[8])
cfg_strength = float(sys.argv[9])
sway_coef = float(sys.argv[10])

sys.path.insert(0, str(bundle_dir))
import numpy as np
import soundfile as sf
import torch
import torchaudio

torch.backends.cudnn.benchmark = True


def _patched_load(fp, **kw):
    d, sr = sf.read(str(fp), dtype="float32")
    d = d[np.newaxis, :] if d.ndim == 1 else d.T
    return torch.from_numpy(d), sr


torchaudio.load = _patched_load

from safetensors.torch import load_file
from f5_tts.infer.utils_infer import (
    get_tokenizer,
    infer_process,
    load_vocoder,
    n_mel_channels,
    preprocess_ref_audio_text,
)
from f5_tts.model import CFM, DiT

device = "cuda" if torch.cuda.is_available() else "cpu"
vmap, vsize = get_tokenizer(str(bundle_dir / "vocab.txt"), "custom")
model = CFM(
    transformer=DiT(
        dim=1024, depth=22, heads=16, ff_mult=2,
        text_dim=512, conv_layers=4, text_num_embeds=vsize, mel_dim=n_mel_channels,
    ),
    mel_spec_kwargs=dict(
        n_fft=1024, hop_length=256, win_length=1024,
        n_mel_channels=n_mel_channels, target_sample_rate=24000, mel_spec_type="vocos",
    ),
    odeint_kwargs=dict(method="euler"),
    vocab_char_map=vmap,
)

st_path = bundle_dir / "indicf5_bd_ema.safetensors"
if st_path.exists():
    cleaned = load_file(str(st_path))
else:
    ckpt = torch.load(str(bundle_dir / "model_40000.pt"), map_location="cpu", weights_only=False)
    raw_sd = ckpt.get("ema_model_state_dict", ckpt.get("model_state_dict", ckpt))
    cleaned = {
        (k[10:] if k.startswith("ema_model.") else (k[7:] if k.startswith("module.") else k)): v
        for k, v in raw_sd.items()
        if k not in ("initted", "step")
    }

model.load_state_dict(cleaned, strict=False)
model = model.float().to(device).eval()

vocoder = load_vocoder(vocoder_name="vocos", is_local=True, local_path=str(bundle_dir / "vocos"), device=device)
clean_ref, clean_ref_txt = preprocess_ref_audio_text(ref_wav, ref_text)

all_jobs = json.loads(Path(jobs_path).read_text(encoding="utf-8"))
my_jobs = [job for idx, job in enumerate(all_jobs) if idx % num_workers == worker_id]
print(f"[Worker {worker_id}] Assigned {len(my_jobs)} / {len(all_jobs)} chunks on {device} (MAX Quality: nfe={nfe_step}, cfg={cfg_strength}, speed={speech_speed})")

for job in my_jobs:
    wav_seg, sr_final, _ = infer_process(
        clean_ref, clean_ref_txt, job["text"], model, vocoder,
        mel_spec_type="vocos", cross_fade_duration=0.15,
        nfe_step=nfe_step, cfg_strength=cfg_strength, sway_sampling_coef=sway_coef,
        speed=speech_speed, device=device,
    )
    sf.write(job["out_path"], np.asarray(wav_seg, dtype=np.float32).reshape(-1), sr_final)

print(f"[Worker {worker_id}] Done!")
'''


_MAIN_RUNNER_TEMPLATE = r'''import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

t_boot = time.time()

BUNDLE_DIR = None
for fname in ("indicf5_bd_ema.safetensors", "model_40000.pt"):
    for p in Path("/kaggle/input").rglob(fname):
        BUNDLE_DIR = p.parent
        break
    if BUNDLE_DIR is not None:
        break

if BUNDLE_DIR is None:
    raise FileNotFoundError("indicf5-bd-fast / indicf5-bd-bundle ডাটাসেট খুঁজে পাওয়া যায়নি!")

wheels = sorted(str(p) for p in (BUNDLE_DIR / "wheels").glob("*.whl"))
if wheels:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--no-index", "--no-deps", *wheels],
        check=True,
    )

sys.path.insert(0, str(BUNDLE_DIR))

import numpy as np
import soundfile as sf
import torch

TASKS = json.loads(__TASKS_JSON__)
REF_AUDIO_B64 = __REF_AUDIO_B64__
REF_EXT = __REF_EXT__
CUSTOM_REF_TEXT = json.loads(__REF_TEXT_JSON__)
DEFAULT_VOICE = __DEFAULT_VOICE__
SPEECH_SPEED = __SPEECH_SPEED__
NFE_STEP = __NFE_STEP__
CFG_STRENGTH = __CFG_STRENGTH__
SWAY_COEF = __SWAY_COEF__
GPU_WORKER_CODE = base64.b64decode(__GPU_WORKER_B64__).decode("utf-8")

if REF_AUDIO_B64:
    raw_ref = Path(f"/tmp/custom_ref_raw{REF_EXT}")
    raw_ref.write_bytes(base64.b64decode(REF_AUDIO_B64))
    ref_wav = Path("/tmp/custom_ref_24k.wav")
    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw_ref), "-ar", "24000", "-ac", "1", str(ref_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        from pydub import AudioSegment
        AudioSegment.from_file(str(raw_ref)).set_frame_rate(24000).set_channels(1).export(str(ref_wav), format="wav")
    ref_text = CUSTOM_REF_TEXT.strip()
else:
    voice_file = "ref_female.wav" if DEFAULT_VOICE == "female" else "ref_male.wav"
    ref_wav = BUNDLE_DIR / "ref_voice" / voice_file
    ref_text = (BUNDLE_DIR / "ref_voice" / "ref_text.txt").read_text(encoding="utf-8").strip()

ref_dur = sf.info(str(ref_wav)).duration
avail_sec = max(10.0, 25.0 - ref_dur)
MAX_CHARS = int(min(220, max(140, avail_sec * 12)))


def split_bengali_for_indicf5(text: str, max_chars: int = MAX_CHARS):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    raw_sents = [s.strip() for s in re.split(r"(?<=[।\.\?\!\n])\s*", text) if s.strip()]
    pieces = []
    for s in raw_sents:
        if len(s) <= max_chars:
            pieces.append(s)
        else:
            sub_parts = [p.strip() for p in re.split(r"(?<=[,;—\-])\s*", s) if p.strip()]
            for sp in sub_parts:
                if len(sp) <= max_chars:
                    pieces.append(sp)
                else:
                    words = sp.split()
                    cur = ""
                    for w in words:
                        if len(cur) + len(w) + 1 <= max_chars:
                            cur = f"{cur} {w}".strip()
                        else:
                            if cur:
                                pieces.append(cur)
                            cur = w
                    if cur:
                        pieces.append(cur)

    merged = []
    buf = ""
    for p in pieces:
        if not buf:
            buf = p
        elif len(buf) + len(p) + 1 <= max_chars:
            buf = f"{buf} {p}"
        else:
            if len(buf) < 28:
                buf = f"{buf} {p}"
            else:
                merged.append(buf)
                buf = p
    if buf:
        if merged and len(buf) < 28 and len(merged[-1]) + len(buf) + 1 <= max_chars + 35:
            merged[-1] = f"{merged[-1]} {buf}"
        else:
            merged.append(buf)
    return merged


CHUNKS_DIR = Path("/tmp/all_chunks")
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
flat_jobs = []
task_chunk_map = {}

for t_idx, item in enumerate(TASKS):
    chunks = split_bengali_for_indicf5(item["text"].strip(), max_chars=MAX_CHARS)
    chunk_paths = []
    for c_idx, ch in enumerate(chunks):
        c_path = str(CHUNKS_DIR / f"t{t_idx}_c{c_idx:04d}.wav")
        flat_jobs.append({"text": ch, "out_path": c_path})
        chunk_paths.append(c_path)
    task_chunk_map[item["filename"]] = chunk_paths

jobs_file = Path("/tmp/flat_jobs.json")
jobs_file.write_text(json.dumps(flat_jobs, ensure_ascii=False), encoding="utf-8")

worker_py = Path("/tmp/gpu_chunk_worker.py")
worker_py.write_text(GPU_WORKER_CODE, encoding="utf-8")

num_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 1
num_workers = 2 if (num_gpus >= 2 and len(flat_jobs) >= 2) else 1
print(f"⚡ Boot & Setup: {round(time.time() - t_boot, 1)}s | GPUs: {num_gpus} | Workers: {num_workers} | Chunks: {len(flat_jobs)} | nfe_step: {NFE_STEP}")

procs = []
for wid in range(num_workers):
    env = os.environ.copy()
    w_tmp = Path(f"/tmp/w_{wid}_tmp")
    w_tmp.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(w_tmp)
    env["TEMP"] = str(w_tmp)
    env["TMP"] = str(w_tmp)
    if torch.cuda.is_available():
        env["CUDA_VISIBLE_DEVICES"] = str(wid)
    p = subprocess.Popen(
        [
            sys.executable, str(worker_py),
            str(BUNDLE_DIR), str(ref_wav), ref_text, str(jobs_file),
            str(wid), str(num_workers), str(SPEECH_SPEED), str(NFE_STEP),
            str(CFG_STRENGTH), str(SWAY_COEF),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    procs.append((wid, p))

for wid, p in procs:
    out, _ = p.communicate()
    print(f"--- Worker {wid} Log ---")
    print(out)
    if p.returncode != 0:
        raise RuntimeError(f"GPU Worker {wid} failed with exit code {p.returncode}")

out_dir = Path("/tmp/generated_wavs")
out_dir.mkdir(parents=True, exist_ok=True)
zip_path = Path("/kaggle/working/audio_bundle.zip")

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for item in TASKS:
        fname = Path(item["filename"]).name
        chunk_paths = task_chunk_map.get(item["filename"], [])
        sr_final = 24000
        parts = []
        pause = np.zeros(int(sr_final * 0.16), dtype=np.float32)

        for idx_c, cp in enumerate(chunk_paths):
            seg, sr_final = sf.read(cp, dtype="float32")
            seg_arr = np.asarray(seg, dtype=np.float32).reshape(-1).copy()
            # ১২ মিলিসেকেন্ডের স্মুথ ফেড-ইন/ফেড-আউট যাতে বাক্যের সংযোগে কোনো ক্লিক সাউন্ড না আসে
            fade_n = min(int(sr_final * 0.012), len(seg_arr) // 4)
            if fade_n > 1:
                ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
                seg_arr[:fade_n] *= ramp
                seg_arr[-fade_n:] *= ramp[::-1]
            parts.append(seg_arr)
            if idx_c < len(chunk_paths) - 1:
                parts.append(pause)

        if not parts:
            final_wav = np.zeros(int(sr_final * 0.5), dtype=np.float32)
        else:
            final_wav = np.concatenate(parts) if len(parts) > 1 else parts[0]
        wav_path = out_dir / fname
        sf.write(str(wav_path), final_wav, sr_final, subtype="PCM_16")
        zf.write(wav_path, arcname=fname)

print(f"✅ Total Dual-GPU Wall Time: {round(time.time() - t_boot, 1)}s")
'''


def _run_kaggle(args: List[str], stdin_text: Optional[str] = None) -> str:
    if not has_kaggle_credentials():
        raise RuntimeError("KAGGLE_API_TOKEN সেট করা নেই! GitHub Secrets-এ KAGGLE_API_TOKEN যোগ করুন।")
    env = os.environ.copy()
    for k in ("KAGGLE_API_TOKEN", "KAGGLE_USERNAME", "KAGGLE_KEY"):
        if not env.get(k, "").strip():
            env.pop(k, None)
    if env.get("KAGGLE_API_TOKEN") and not env.get("KAGGLE_KEY"):
        env.pop("KAGGLE_USERNAME", None)

    cmd = [sys.executable, "-m", "kaggle", *args]
    proc = subprocess.run(
        cmd,
        input=stdin_text,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Kaggle CLI ত্রুটি ({' '.join(args)}):\n{proc.stdout}")
    return proc.stdout


def _delete_kernel_safely(kernel_id: str):
    """আটকে থাকা বা পুরনো জব ডিলিট করে GPU স্লট ফ্রি করে"""
    try:
        _run_kaggle(["kernels", "delete", kernel_id, "-y"], stdin_text="yes\n")
        print(f"🧹 [Kaggle Cleanup] Deleted kernel '{kernel_id}' to free GPU slot.")
        time.sleep(5)
    except Exception:
        pass


def _cleanup_stale_workers():
    """আগের কোনো রানে জব QUEUED হয়ে থাকলে সেটি পরিষ্কার করে"""
    username = _get_kaggle_username()
    slug_base = _get_kernel_slug_base()
    for suffix in ("", "-r2", "-r3"):
        kid = f"{username}/{slug_base}{suffix}"
        try:
            st = _run_kaggle(["kernels", "status", kid]).lower()
            if any(x in st for x in ("queued", "running", "error", "cancel")):
                _delete_kernel_safely(kid)
        except Exception:
            pass


def _find_repo_reference_voice() -> tuple[Optional[Path], str]:
    """রিপোজিটরির ref_voice/ ফোল্ডার থেকে কাস্টম রেফারেন্স অডিও ও টেক্সট খুঁজে বের করে"""
    env_audio = os.environ.get("KAGGLE_REF_AUDIO_PATH", "").strip()
    env_text = os.environ.get("KAGGLE_REF_TEXT", "").strip()
    if env_audio and Path(env_audio).exists() and env_text:
        return Path(env_audio), env_text

    ref_dir = Path("ref_voice")
    if ref_dir.exists():
        txt_file = ref_dir / "ref_text.txt"
        ref_txt = txt_file.read_text(encoding="utf-8").strip() if txt_file.exists() else ""
        for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
            cand = ref_dir / f"ref.{ext}"
            if cand.exists() and ref_txt:
                return cand, ref_txt
        for f in sorted(ref_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in {".wav", ".mp3", ".m4a", ".ogg", ".flac"} and ref_txt:
                return f, ref_txt
    return None, ""


def _build_worker_script(
    tasks: List[Dict[str, str]],
    ref_audio_b64: str,
    ref_ext: str,
    ref_text: str,
    default_voice: str,
    speech_speed: float = 0.93,
    nfe_step: int = 64,
    cfg_strength: float = 2.0,
    sway_coef: float = -1.0,
) -> str:
    tasks_json = json.dumps(tasks, ensure_ascii=False)
    ref_text_json = json.dumps(ref_text, ensure_ascii=False)
    gpu_worker_b64 = base64.b64encode(_GPU_WORKER_TEMPLATE.encode("utf-8")).decode("ascii")

    script = _MAIN_RUNNER_TEMPLATE
    script = script.replace("__TASKS_JSON__", json.dumps(tasks_json))
    script = script.replace("__REF_AUDIO_B64__", json.dumps(ref_audio_b64))
    script = script.replace("__REF_EXT__", json.dumps(ref_ext))
    script = script.replace("__REF_TEXT_JSON__", json.dumps(ref_text_json))
    script = script.replace("__DEFAULT_VOICE__", json.dumps(default_voice))
    script = script.replace("__SPEECH_SPEED__", repr(float(speech_speed)))
    script = script.replace("__NFE_STEP__", repr(int(nfe_step)))
    script = script.replace("__CFG_STRENGTH__", repr(float(cfg_strength)))
    script = script.replace("__SWAY_COEF__", repr(float(sway_coef)))
    script = script.replace("__GPU_WORKER_B64__", json.dumps(gpu_worker_b64))
    return script


def _is_fatal_kaggle_error(msg: str) -> bool:
    low = (msg or "").lower()
    return any(tok in low for tok in ("401", "403", "unauthorized", "forbidden", "quota", "maximum gpu", "not found"))


def _push_with_fallback_slug(job_dir: Path, base_script: str, run_timeout_sec: int) -> str:
    """কোনো কারণে স্লাগ আটকে থাকলে বিকল্প স্লাগে পুশ করে"""
    username = _get_kaggle_username()
    slug_base = _get_kernel_slug_base()
    dataset_slug = _get_dataset_slug()
    suffixes = ("", "-r2", "-r3")
    last_err = None
    for suffix in suffixes:
        slug = f"{slug_base}{suffix}"
        kernel_id = f"{username}/{slug}"
        metadata = {
            "id": kernel_id,
            "title": f"IndicF5 TTS Worker{suffix.upper()}",
            "code_file": "tts_job.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": False,
            "machine_shape": "NvidiaTeslaT4",
            "dataset_sources": [dataset_slug],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
        }
        (job_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (job_dir / "tts_job.py").write_text(base_script, encoding="utf-8")
        try:
            push_out = _run_kaggle(["kernels", "push", "-p", str(job_dir), "-t", str(run_timeout_sec + 1200)])
            print("  ", push_out.strip())
            return kernel_id
        except Exception as exc:
            last_err = exc
            if _is_fatal_kaggle_error(str(exc)):
                raise RuntimeError(f"Kaggle auth/quota error on '{kernel_id}': {exc}") from exc
            print(f"⚠️ Slug '{kernel_id}' push failed ({exc}). Trying next slug...")
    raise RuntimeError(f"Kaggle push failed on all slugs: {last_err}")


def generate_voices_batch(
    tasks: List[Dict[str, str]],
    output_dir: str | Path,
    ref_audio_path: Optional[str | Path] = None,
    ref_text: str = "",
    default_voice: str = "male",
    speech_speed: float = 0.93,
    nfe_step: int = 64,
    cfg_strength: float = 2.0,
    sway_coef: float = -1.0,
    poll_interval: int = 15,
    max_attempts: int = 3,
    retry_interval_sec: int = 1200,
    run_timeout_sec: int = 7200,
) -> Dict[str, Path]:
    if not tasks:
        return {}

    run_timeout_sec = int(os.environ.get("KAGGLE_RUN_TIMEOUT_SEC", str(run_timeout_sec)) or run_timeout_sec)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not ref_audio_path:
        auto_ref, auto_txt = _find_repo_reference_voice()
        if auto_ref:
            ref_audio_path = auto_ref
            ref_text = auto_txt

    ref_b64 = ""
    ref_ext = ".wav"
    if ref_audio_path:
        rp = Path(ref_audio_path)
        if rp.exists() and ref_text.strip():
            print(f"🎤 [Kaggle TTS] Using Custom Reference Voice: {rp}")
            ref_b64 = base64.b64encode(rp.read_bytes()).decode("ascii")
            ref_ext = rp.suffix.lower() or ".wav"

    script_code = _build_worker_script(
        tasks, ref_b64, ref_ext, ref_text, default_voice,
        speech_speed=speech_speed, nfe_step=nfe_step,
        cfg_strength=cfg_strength, sway_coef=sway_coef,
    )

    _cleanup_stale_workers()

    for attempt in range(1, max_attempts + 1):
        failure_kind = None
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            job_dir = tmp_path / "job"
            dl_dir = tmp_path / "out"
            job_dir.mkdir()
            dl_dir.mkdir()

            print(f"\n🚀 [Kaggle TTS | Attempt {attempt}/{max_attempts}] Pushing {len(tasks)} script(s) (T4 x2 | MAX Quality nfe={nfe_step} | speed={speech_speed})...")
            attempt_start = time.time()
            active_kernel_id = _push_with_fallback_slug(job_dir, script_code, run_timeout_sec)

            running_started_at = None
            time.sleep(10)

            while True:
                status_out = _run_kaggle(["kernels", "status", active_kernel_id]).strip()
                elapsed = int(time.time() - attempt_start)
                print(f"⏳ [Attempt {attempt}/{max_attempts} | {elapsed}s]: {status_out}")
                lower = status_out.lower()

                if "complete" in lower:
                    print("📥 [Kaggle TTS] Downloading generated audio bundle...")
                    _run_kaggle(["kernels", "output", active_kernel_id, "-p", str(dl_dir)])

                    zip_path = dl_dir / "audio_bundle.zip"
                    if not zip_path.exists():
                        raise FileNotFoundError(
                            f"audio_bundle.zip পাওয়া যায়নি! ফাইলসমূহ: {[p.name for p in dl_dir.iterdir()]}"
                        )

                    result_paths: Dict[str, Path] = {}
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(out_dir)
                        for item in tasks:
                            fname = Path(item["filename"]).name
                            result_paths[item["filename"]] = out_dir / fname

                    print(f"✅ [Kaggle TTS] All {len(tasks)} audio file(s) ready on Attempt #{attempt}!")
                    return result_paths

                if "error" in lower or "cancel" in lower:
                    log_txt = ""
                    try:
                        _run_kaggle(["kernels", "output", active_kernel_id, "-p", str(dl_dir)])
                        log_files = list(dl_dir.glob("*.log"))
                        log_txt = log_files[0].read_text(encoding="utf-8", errors="ignore")[-1500:] if log_files else ""
                    except Exception:
                        pass
                    print(f"❌ [Attempt {attempt} Error]: {status_out}\n{log_txt}")
                    _delete_kernel_safely(active_kernel_id)
                    if _is_fatal_kaggle_error(f"{status_out}\n{log_txt}"):
                        raise RuntimeError(f"Kaggle fatal error: {status_out}")
                    failure_kind = "kernel_error"
                    break

                if "running" in lower:
                    if running_started_at is None:
                        running_started_at = time.time()
                        print(f"⚡ [Attempt {attempt}] GPU RUNNING শুরু হয়েছে!")
                    if time.time() - running_started_at > run_timeout_sec:
                        print(f"⏰ [Attempt {attempt}] Running timeout ({run_timeout_sec}s) পার হয়েছে।")
                        _delete_kernel_safely(active_kernel_id)
                        failure_kind = "run_timeout"
                        break
                else:
                    if time.time() - attempt_start >= retry_interval_sec:
                        print(f"⏰ [Attempt {attempt}] ২০ মিনিট ধরে QUEUED অবস্থায় আছে। বাতিল করে পরের চেষ্টা করা হচ্ছে...")
                        _delete_kernel_safely(active_kernel_id)
                        failure_kind = "queued_timeout"
                        break

                time.sleep(poll_interval)

        if attempt < max_attempts:
            if failure_kind == "queued_timeout":
                remaining_wait = int(retry_interval_sec - (time.time() - attempt_start))
                if remaining_wait > 10:
                    print(f"⏱️ পরবর্তী চেষ্টার আগে {remaining_wait} সেকেন্ড অপেক্ষা করা হচ্ছে...")
                    time.sleep(remaining_wait)
            else:
                time.sleep(10)

    raise RuntimeError(f"Kaggle {max_attempts} বার (২০ মিনিট পরপর) চেষ্টা করেও GPU পায়নি।")
