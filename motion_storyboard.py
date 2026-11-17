# -*- coding: utf-8 -*-
import os
import re
import subprocess

from tiktok_designer import remove_emojis, clean_org_name

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def to_bn_num(n):
    return str(int(n)).translate(BN_DIGITS)

def detect_audio_silences(audio_path):
    """অডিও ফাইলের আসল শ্বাস-পজ (silence) টাইমস্ট্যাম্প বের করে যাতে সিন বদল কথার সাথে মিলে যায়।"""
    if not audio_path or not os.path.exists(audio_path):
        return []
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-i", audio_path,
            "-af", "silencedetect=noise=-32dB:d=0.16",
            "-f", "null", "-"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        pauses = []
        cur_start = None
        for line in res.stderr.splitlines():
            m_st = re.search(r'silence_start:\s*([0-9.]+)', line)
            if m_st:
                cur_start = float(m_st.group(1))
            m_ed = re.search(r'silence_end:\s*([0-9.]+)', line)
            if m_ed:
                ed = float(m_ed.group(1))
                pauses.append((cur_start + ed) / 2.0 if cur_start is not None else ed)
                cur_start = None
        return pauses
    except Exception:
        return []

def split_script_sentences(script_text):
    if not script_text:
        return []
    raw = re.split(r'[।!?]+', str(script_text))
    cleaned = []
    for s in raw:
        t = re.sub(r'\s+', ' ', remove_emojis(s)).strip(" ,;:-–—")
        if len(t) < 8:
            continue
        if any(k in t for k in ["হোয়াটসঅ্যাপ", "হোয়াটসঅ্যাপ", "whatsapp"]) and "যোগাযোগ করুন" in t:
            continue
        cleaned.append(t)
    return cleaned

def _clip_phrase(text, max_len=58):
    t = re.sub(r'\s+', ' ', remove_emojis(str(text or ""))).strip(" ,;:-–—।")
    if len(t) <= max_len:
        return t
    words = t.split()
    out = []
    for w in words:
        cand = " ".join(out + [w])
        if len(cand) <= max_len or not out:
            out.append(w)
        else:
            break
    return " ".join(out)

def _split_sentence_to_chips(sentence, max_chips=3, max_len=46):
    parts = [p.strip(" ,;:-–—") for p in re.split(r'[,;–—]|এবং|ও(?=\s)|পাশাপাশি|অথবা|তবে', sentence) if len(p.strip()) > 4]
    chips = []
    for p in parts:
        c = _clip_phrase(p, max_len=max_len)
        if c and c not in chips:
            chips.append(c)
        if len(chips) >= max_chips:
            break
    if not chips:
        words = sentence.split()
        if len(words) > 7:
            mid = len(words) // 2
            chips = [_clip_phrase(" ".join(words[:mid]), max_len), _clip_phrase(" ".join(words[mid:]), max_len)]
        else:
            chips = [_clip_phrase(sentence, max_len)]
    return chips[:max_chips]

def extract_motion_core(job_data):
    m = job_data.get("motion") if isinstance(job_data.get("motion"), dict) else {}
    p = job_data.get("poster") if isinstance(job_data.get("poster"), dict) else {}

    org = clean_org_name(m.get("org_name") or job_data.get("org_name") or "নিয়োগ বিজ্ঞপ্তি")
    cat_badge = remove_emojis(m.get("category_badge") or "নিয়োগ বিজ্ঞপ্তি").strip()
    raw_hook = remove_emojis(m.get("hook_subtitle") or p.get("hero_top") or "যোগ্যতানুযায়ী আবেদন").strip()
    hook_short = _clip_phrase(raw_hook, 42)

    vac_num = m.get("total_vacancy_num", 0)
    try:
        vac_num = int(str(vac_num).translate(EN_DIGITS)) if vac_num else 0
    except Exception:
        vac_num = 0

    vac_display = remove_emojis(m.get("total_vacancy_display") or "").strip()
    if not vac_num and not vac_display:
        vm = re.search(r'([\d০-৯]+)\s*(?:টি|জন)?\s*পদে?', str(p.get("main_summary") or ""))
        if vm:
            try:
                vac_num = int(vm.group(1).translate(EN_DIGITS))
                vac_display = to_bn_num(vac_num) + "টি"
            except Exception:
                pass
    if not vac_display:
        vac_display = (to_bn_num(vac_num) + "টি") if vac_num > 0 else "বিভিন্ন পদ"

    highlights = m.get("highlights") if isinstance(m.get("highlights"), list) else []
    short_tag = ""
    for h in highlights:
        hh = remove_emojis(h).strip()
        if hh:
            short_tag = _clip_phrase(hh, 38)
            break
    if not short_tag:
        short_tag = _clip_phrase(p.get("hero_bottom") or "আকর্ষণীয় ক্যারিয়ার", 38)

    bad_vals = {"নির্দিষ্ট নয়", "উল্লেখ নেই", "জানা যায়নি", "n/a", "none", "null", ""}
    raw_posts = m.get("posts") if isinstance(m.get("posts"), list) and m.get("posts") else job_data.get("posts", [])
    posts = []
    for item in raw_posts[:20]:
        if isinstance(item, dict) and item.get("post_name"):
            pv = remove_emojis(item.get("vacancy", "")).strip()
            if pv.lower() in bad_vals:
                pv = "নিয়োগ"
            elif re.fullmatch(r'[\d০-৯]+', pv):
                pv = pv + "টি"
            qual = remove_emojis(item.get("qualification", "")).strip()
            if qual.lower() in bad_vals:
                qual = ""
            grade = remove_emojis(item.get("salary_grade", "")).strip()
            if grade.lower() in bad_vals:
                grade = ""
            meta = " | ".join([x for x in [qual, grade] if x]) or "বিজ্ঞপ্তি অনুযায়ী"
            posts.append({
                "post_name": _clip_phrase(item.get("post_name"), 44),
                "vacancy": _clip_phrase(pv, 16),
                "qualification": _clip_phrase(qual or "বিজ্ঞপ্তি মতে", 34),
                "salary_grade": _clip_phrase(grade or "বিজ্ঞপ্তি মতে", 26),
                "meta": _clip_phrase(meta, 48)
            })

    if not posts:
        for k1, k2 in [("highlight_1_badge", "highlight_1_text"), ("highlight_2_badge", "highlight_2_text")]:
            b, t = remove_emojis(p.get(k1, "")).strip(), remove_emojis(p.get(k2, "")).strip()
            if b or t:
                posts.append({
                    "post_name": _clip_phrase(b or "প্রধান পদ", 40),
                    "vacancy": "নিয়োগ",
                    "qualification": _clip_phrase(t, 36),
                    "salary_grade": "বিজ্ঞপ্তি মতে",
                    "meta": _clip_phrase(t, 48)
                })

    age_limit = re.sub(r'\s*\(.*?\)', '', remove_emojis(m.get("age_limit") or "১৮–৩০/৩২ বছর")).strip()
    salary_range = remove_emojis(m.get("salary_range") or "বিজ্ঞপ্তি অনুযায়ী").strip()
    if salary_range.lower() in bad_vals:
        salary_range = "বিজ্ঞপ্তি অনুযায়ী"
    app_fee = remove_emojis(m.get("application_fee") or p.get("fee_box_text") or "বিজ্ঞপ্তিমতে").strip()
    if app_fee.lower() in bad_vals:
        app_fee = "বিজ্ঞপ্তিমতে"
    apply_method = remove_emojis(m.get("apply_method") or "অনলাইন").strip()

    sd = remove_emojis(m.get("start_date") or job_data.get("start_date") or "চলমান").strip()
    ed = remove_emojis(m.get("end_date") or job_data.get("end_date") or "শীঘ্রই").strip()
    if sd == "চলমান" and p.get("date_box_text"):
        ed = _clip_phrase(p.get("date_box_text"), 40)

    wa_num = os.environ.get("WHATSAPP_NUMBER", "01540503092").strip() or "01540503092"
    wa_formatted = (wa_num[:5] + "-" + wa_num[5:]) if (len(wa_num) == 11 and wa_num.startswith("01") and "-" not in wa_num) else wa_num

    return {
        "org": org, "cat_badge": cat_badge, "hook_short": hook_short,
        "vac_num": vac_num, "vac_display": vac_display, "short_tag": short_tag,
        "posts": posts, "age_limit": _clip_phrase(age_limit, 32),
        "salary_range": _clip_phrase(salary_range, 36),
        "app_fee": _clip_phrase(app_fee, 34), "apply_method": _clip_phrase(apply_method, 34),
        "start_date": _clip_phrase(sd, 34), "end_date": _clip_phrase(ed, 38),
        "wa_formatted": wa_formatted,
        "summary": _clip_phrase(p.get("main_summary") or "", 96)
    }

def _classify_sentence_to_beat(sentence, core, state):
    s = sentence
    if any(k in s for k in ["শূন্যপদ", "মোট", "নিয়োগের সুযোগ", "জনবল", "পদ সংখ্যা"]) and not state["used_vacancy"]:
        state["used_vacancy"] = True
        return {
            "kind": "vacancy", "header": "মোট শূন্যপদ",
            "value": core["vac_display"], "num": core["vac_num"],
            "tag": core["short_tag"], "sub_chips": _split_sentence_to_chips(s, 2, 44)
        }

    if any(k in s for k in ["বয়স", "নাগরিক", "কোটা", "স্বাধীনতা", "মুক্তিযোদ্ধা", "উপজাতি"]):
        return {
            "kind": "focus_card", "icon": "age", "header": "বয়স ও শর্তাবলি",
            "main_label": "বয়সসীমা", "main_val": core["age_limit"],
            "sub_chips": _split_sentence_to_chips(s, 3, 46)
        }

    if any(k in s for k in ["শিক্ষাগত", "যোগ্যতা", "ডিগ্রি", "স্নাতক", "এইচএসসি", "এসএসসি", "অষ্টম", "কম্পিউটার", "অভিজ্ঞতা", "টাইপিং"]):
        return {
            "kind": "focus_card", "icon": "qual", "header": "শিক্ষাগত যোগ্যতা",
            "main_label": "প্রয়োজনীয় যোগ্যতা", "main_val": core["hook_short"],
            "sub_chips": _split_sentence_to_chips(s, 3, 46)
        }

    if any(k in s for k in ["বেতন", "স্কেল", "গ্রেড", "ভাতা", "সুবিধা", "কর্মস্থল"]):
        if not state["used_posts"] and len(core["posts"]) > 0 and ("গ্রেড" in s or "ক্যাটাগরি" in s):
            state["used_posts"] = True
            return {
                "kind": "posts", "header": "প্রধান পদসমূহ",
                "posts": core["posts"], "sub_chips": _split_sentence_to_chips(s, 2, 44)
            }
        return {
            "kind": "focus_card", "icon": "salary", "header": "বেতন ও সুযোগ-সুবিধা",
            "main_label": "বেতন স্কেল", "main_val": core["salary_range"],
            "sub_chips": _split_sentence_to_chips(s, 3, 46)
        }

    if any(k in s for k in ["ফি", "টাকা", "এসএমএস", "৭২ ঘণ্টা", "প্রিপেইড", "বিনামূল্যে", "জমাদান"]):
        return {
            "kind": "focus_card", "icon": "fee", "header": "আবেদন ফি ও পেমেন্ট",
            "main_label": "আবেদন ফি", "main_val": core["app_fee"],
            "sub_chips": _split_sentence_to_chips(s, 3, 46)
        }

    if any(k in s for k in ["অনলাইন", "টেলিটক", "ইমেইল", "ডাকযোগে", "সরাসরি", "ওয়েবসাইট", "ছবি", "স্বাক্ষর", "সাবমিট", "পোর্টাল", "কাগজপত্র", "সিভি"]):
        return {
            "kind": "steps", "icon": "method", "header": "আবেদন প্রক্রিয়া",
            "main_label": "আবেদন মাধ্যম", "main_val": core["apply_method"],
            "sub_chips": _split_sentence_to_chips(s, 3, 46)
        }

    if any(k in s for k in ["শুরু", "শেষ", "তারিখ", "সময়সীমা", "নভেম্বর", "ডিসেম্বর", "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর"]):
        state["used_deadline"] = True
        return {
            "kind": "deadline", "header": "আবেদনের সময়সীমা",
            "start_date": core["start_date"], "end_date": core["end_date"],
            "sub_chips": _split_sentence_to_chips(s, 2, 44)
        }

    if any(k in s for k in ["পরীক্ষা", "লিখিত", "মৌখিক", "সাক্ষাৎকার", "প্রবেশপত্র", "নির্বাচন", "বাছাই"]):
        return {
            "kind": "steps", "icon": "exam", "header": "নির্বাচন ও পরীক্ষা",
            "main_label": "বাছাই প্রক্রিয়া", "main_val": "লিখিত ও মৌখিক পরীক্ষা",
            "sub_chips": _split_sentence_to_chips(s, 3, 46)
        }

    return {
        "kind": "highlight", "icon": "info", "header": "গুরুত্বপূর্ণ তথ্য",
        "main_label": core["org"], "main_val": _clip_phrase(s, 54),
        "sub_chips": _split_sentence_to_chips(s, 3, 46)
    }

def _expand_posts_into_beats(posts):
    """পদের সংখ্যা অনুযায়ী প্রতিটি পদের বা জোড়ায় জোড়ায় ছোট স্লাইড বানায় যাতে দীর্ঘক্ষণ এক স্ক্রিন স্থির না থাকে।"""
    items = list(posts[:20])
    if not items:
        return []
    if len(items) <= 3:
        return [{"kind": "post_spotlight", "header": f"পদ নং {to_bn_num(i + 1)}", "post": it, "index": i + 1, "total": len(items)} for i, it in enumerate(items)]
    batches = [items[i:i + 2] for i in range(0, len(items), 2)]
    return [{"kind": "post_pair", "header": "প্রধান পদসমূহ", "posts": b, "batch_idx": bi + 1, "total_batches": len(batches)} for bi, b in enumerate(batches)]

def build_dynamic_storyboard(job_data, audio_path, duration, script_index=0):
    core = extract_motion_core(job_data)
    scripts = job_data.get("scripts") if isinstance(job_data.get("scripts"), list) else []
    if scripts:
        s_idx = max(0, min(int(script_index or 0), len(scripts) - 1))
        script_text = scripts[s_idx]
    else:
        script_text = job_data.get("voiceover_script", "")

    sentences = split_script_sentences(script_text)
    silences = detect_audio_silences(audio_path)

    beats_raw = [{
        "kind": "intro", "header": core["org"], "cat_badge": core["cat_badge"],
        "hook_short": core["hook_short"], "weight": max(10, len(sentences[0].split()) if sentences else 14)
    }]

    state = {"used_vacancy": False, "used_posts": False, "used_deadline": False}
    body_sentences = sentences[1:] if len(sentences) > 1 else []

    for sent in body_sentences:
        b = _classify_sentence_to_beat(sent, core, state)
        w = max(9, len(sent.split()))
        if b["kind"] == "posts":
            post_beats = _expand_posts_into_beats(b["posts"])
            per_w = max(8, w // max(1, len(post_beats)))
            for pb in post_beats:
                pb["weight"] = per_w
                beats_raw.append(pb)
        else:
            b["weight"] = w
            beats_raw.append(b)

    if not state["used_vacancy"]:
        beats_raw.insert(1, {
            "kind": "vacancy", "header": "মোট শূন্যপদ", "value": core["vac_display"],
            "num": core["vac_num"], "tag": core["short_tag"], "sub_chips": [core["hook_short"]], "weight": 12
        })
    if not state["used_posts"] and core["posts"]:
        post_beats = _expand_posts_into_beats(core["posts"])
        ins_pos = min(2, len(beats_raw))
        for offset, pb in enumerate(post_beats):
            pb["weight"] = 12
            beats_raw.insert(ins_pos + offset, pb)
    if not state["used_deadline"]:
        beats_raw.append({
            "kind": "deadline", "header": "আবেদনের সময়সীমা",
            "start_date": core["start_date"], "end_date": core["end_date"],
            "sub_chips": ["সময়মতো আবেদন করুন"], "weight": 12
        })

    # কোনো বিট যেন ৬.৮ সেকেন্ডের বেশি স্থির না থাকে তার জন্য ওভার-লং বিট ভাগ করা
    max_middle_beats = max(6, int(duration / 3.8))
    merged = []
    for b in beats_raw:
        if (
            merged and len(merged) > 1
            and b["kind"] == merged[-1]["kind"]
            and b["kind"] in ["highlight", "steps", "focus_card"]
            and (merged[-1]["weight"] + b["weight"]) <= 28
        ):
            prev = merged[-1]
            for ch in b.get("sub_chips", []):
                if ch not in prev.get("sub_chips", []) and len(prev["sub_chips"]) < 3:
                    prev["sub_chips"].append(ch)
            prev["weight"] += b["weight"]
        else:
            merged.append(b)

    # খুব বেশি ছোট বিট হলে সীমিত করা, যাতে প্রতি সিন ন্যূনতম ~৩.৪ সেকেন্ড পায়
    while len(merged) > max_middle_beats and len(merged) > 5:
        idx_min = min(range(1, len(merged)), key=lambda i: merged[i]["weight"])
        tgt = idx_min - 1 if idx_min > 1 else idx_min + 1
        if tgt < len(merged):
            a, b = (merged[idx_min], merged[tgt]) if idx_min < tgt else (merged[tgt], merged[idx_min])
            a["weight"] += b["weight"]
            for ch in b.get("sub_chips", []):
                if ch not in a.get("sub_chips", []) and len(a.get("sub_chips", [])) < 3:
                    a.setdefault("sub_chips", []).append(ch)
            merged.remove(b)
        else:
            break

    cta_t = max(4.2, min(6.2, duration * 0.085))
    intro_t = max(3.6, min(5.4, duration * 0.075))
    mid_beats = merged[1:]
    if not mid_beats:
        mid_beats = [{
            "kind": "overview_grid", "header": "মূল তথ্য",
            "items": [
                ("age", "বয়স", core["age_limit"]), ("salary", "বেতন", core["salary_range"]),
                ("fee", "আবেদন ফি", core["app_fee"]), ("method", "মাধ্যম", core["apply_method"])
            ],
            "weight": 15
        }]

    mid_total_t = max(4.0, duration - intro_t - cta_t)
    total_w = float(sum(b["weight"] for b in mid_beats) or 1)

    timeline = [{"kind": "intro", "start": 0.0, "end": intro_t, **merged[0]}]
    cur_t = intro_t
    for i, mb in enumerate(mid_beats):
        seg_t = mid_total_t * (mb["weight"] / total_w)
        raw_end = duration - cta_t if i == len(mid_beats) - 1 else (cur_t + seg_t)
        snapped_end = raw_end
        if i < len(mid_beats) - 1 and silences:
            best_p = min(silences, key=lambda p: abs(p - raw_end))
            if abs(best_p - raw_end) <= 1.05 and (best_p - cur_t) >= 2.8 and ((duration - cta_t) - best_p) >= 2.8:
                snapped_end = best_p
        timeline.append({"start": cur_t, "end": snapped_end, **mb})
        cur_t = snapped_end

    timeline.append({
        "kind": "cta", "start": cur_t, "end": duration,
        "header": "যোগাযোগ (হোয়াটসঅ্যাপ)", "wa_formatted": core["wa_formatted"]
    })

    for idx, bt in enumerate(timeline):
        bt["id"] = idx
    return {"core": core, "beats": timeline, "duration": duration}
