# -*- coding: utf-8 -*-
import os
import re
import subprocess

from tiktok_designer import remove_emojis, clean_org_name
from ai_service import clean_bengali_text, normalize_bengali_nukta

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_BAD_DISPLAY_VALS = {
    "নির্দিষ্ট নয়", "উল্লেখ নেই", "জানা যায়নি", "অনির্দিষ্ট",
    "নেই", "n/a", "none", "null", "unspecified", ""
}


def to_bn_num(n):
    return str(int(n)).translate(BN_DIGITS)


def _clean_text_val(text):
    return clean_bengali_text(remove_emojis(str(text or ""))).strip()


def _is_bad_val(val):
    norm = normalize_bengali_nukta(_clean_text_val(val)).lower()
    return norm in _BAD_DISPLAY_VALS


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
    clean_full = _clean_text_val(script_text)
    raw = re.split(r'[।!?]+', clean_full)
    cleaned = []
    for s in raw:
        t = re.sub(r'\s+', ' ', s).strip(" ,;:-–—")
        if len(t) < 8:
            continue
        if any(k in t for k in ["হোয়াটসঅ্যাপ", "whatsapp"]) and "যোগাযোগ করুন" in t:
            continue
        cleaned.append(t)
    return cleaned


def _clip_phrase(text, max_len=84):
    t = re.sub(r'\s+', ' ', _clean_text_val(text)).strip(" ,;:-–—।")
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


def _split_sentence_to_chips(sentence, max_chips=3, max_len=82):
    clean_s = re.sub(r'\s+', ' ', _clean_text_val(sentence)).strip(" ,;:-–—।")
    if not clean_s:
        return []
    if len(clean_s) <= max_len:
        return [clean_s]

    # শুধুমাত্র স্বতন্ত্র সংযোজক শব্দ বা যতিচিহ্নে ভাগ করা (শব্দের শেষের 'ও' যেমন 'এখানেও' ভাঙবে না)
    raw_parts = [
        p.strip(" ,;:-–—")
        for p in re.split(r'[,;–—]|(?<![\u0980-\u09FF])(?:এবং|ও|পাশাপাশি|অথবা|তবে)(?![\u0980-\u09FF])', clean_s)
        if p.strip(" ,;:-–—")
    ]

    # খুব ছোট ১ শব্দের টুকরো (যেমন 'এখানে') পাশের অংশের সাথে জোড়া দেওয়া
    merged_parts = []
    for p in raw_parts:
        if merged_parts and (len(p) < 14 or len(p.split()) < 2):
            if len(merged_parts[-1]) + 1 + len(p) <= max_len:
                merged_parts[-1] = f"{merged_parts[-1]} {p}"
                continue
        if merged_parts and (len(merged_parts[-1]) < 14 or len(merged_parts[-1].split()) < 2):
            if len(merged_parts[-1]) + 1 + len(p) <= max_len:
                merged_parts[-1] = f"{merged_parts[-1]} {p}"
                continue
        merged_parts.append(p)

    # বড় বাক্যাংশ কোনো কমা ছাড়াই ৮২ অক্ষরের বেশি হলে শব্দের মাঝখান থেকে সুষমভাবে ভাগ করা (শেষ অংশ বাদ যাবে না)
    expanded = []
    for p in merged_parts:
        if len(p) <= max_len:
            expanded.append(p)
        else:
            words = p.split()
            cur = []
            for w in words:
                cand = " ".join(cur + [w])
                if len(cand) <= max_len or not cur:
                    cur.append(w)
                else:
                    expanded.append(" ".join(cur))
                    cur = [w]
            if cur:
                expanded.append(" ".join(cur))

    chips = []
    for p in expanded:
        c = _clip_phrase(p, max_len=max_len)
        if c and c not in chips:
            chips.append(c)
        if len(chips) >= max_chips:
            break
    return chips or [_clip_phrase(clean_s, max_len=max_len)]


def extract_motion_core(job_data):
    m = job_data.get("motion") if isinstance(job_data.get("motion"), dict) else {}
    p = job_data.get("poster") if isinstance(job_data.get("poster"), dict) else {}

    org = clean_org_name(_clean_text_val(m.get("org_name") or job_data.get("org_name") or "নিয়োগ বিজ্ঞপ্তি"))
    cat_badge = _clean_text_val(m.get("category_badge") or "নিয়োগ বিজ্ঞপ্তি")
    raw_hook = _clean_text_val(m.get("hook_subtitle") or p.get("hero_top") or "যোগ্যতানুযায়ী আবেদন")
    hook_short = _clip_phrase(raw_hook, 54)

    vac_num = m.get("total_vacancy_num", 0)
    try:
        vac_num = int(str(vac_num).translate(EN_DIGITS)) if vac_num else 0
    except Exception:
        vac_num = 0

    vac_display = _clean_text_val(m.get("total_vacancy_display") or "")
    if _is_bad_val(vac_display):
        vac_display = ""
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
        hh = _clean_text_val(h)
        if hh and not _is_bad_val(hh):
            short_tag = _clip_phrase(hh, 48)
            break
    if not short_tag:
        short_tag = _clip_phrase(p.get("hero_bottom") or "আকর্ষণীয় ক্যারিয়ার", 48)

    raw_posts = m.get("posts") if isinstance(m.get("posts"), list) and m.get("posts") else job_data.get("posts", [])
    posts = []
    for item in raw_posts[:20]:
        if isinstance(item, dict) and item.get("post_name"):
            pn = _clean_text_val(item.get("post_name"))
            if _is_bad_val(pn):
                continue
            pv = _clean_text_val(item.get("vacancy", ""))
            if _is_bad_val(pv):
                pv = "নিয়োগ"
            elif re.fullmatch(r'[\d০-৯]+', pv):
                pv = pv + "টি"

            qual = _clean_text_val(item.get("qualification", ""))
            if _is_bad_val(qual):
                qual = ""
            grade = _clean_text_val(item.get("salary_grade", ""))
            if _is_bad_val(grade):
                grade = ""
            meta = " | ".join([x for x in [qual, grade] if x]) or "বিজ্ঞপ্তি অনুযায়ী"
            posts.append({
                "post_name": _clip_phrase(pn, 88),
                "vacancy": _clip_phrase(pv, 20),
                "qualification": _clip_phrase(qual or "বিজ্ঞপ্তি মতে", 68),
                "salary_grade": _clip_phrase(grade or "বিজ্ঞপ্তি মতে", 44),
                "meta": _clip_phrase(meta, 82)
            })

    if not posts:
        for k1, k2 in [("highlight_1_badge", "highlight_1_text"), ("highlight_2_badge", "highlight_2_text")]:
            b, t = _clean_text_val(p.get(k1, "")), _clean_text_val(p.get(k2, ""))
            if b or t:
                posts.append({
                    "post_name": _clip_phrase(b or "প্রধান পদ", 64),
                    "vacancy": "নিয়োগ",
                    "qualification": _clip_phrase(t, 68),
                    "salary_grade": "বিজ্ঞপ্তি মতে",
                    "meta": _clip_phrase(t, 82)
                })

    age_limit = re.sub(r'\s*\(.*?\)', '', _clean_text_val(m.get("age_limit") or "১৮–৩২ বছর")).strip()
    if _is_bad_val(age_limit):
        age_limit = "বিজ্ঞপ্তি অনুযায়ী"

    salary_range = _clean_text_val(m.get("salary_range") or "বিজ্ঞপ্তি অনুযায়ী")
    if _is_bad_val(salary_range):
        salary_range = "বিজ্ঞপ্তি অনুযায়ী"

    app_fee = _clean_text_val(m.get("application_fee") or p.get("fee_box_text") or "বিজ্ঞপ্তিমতে")
    if _is_bad_val(app_fee):
        app_fee = "বিজ্ঞপ্তি অনুযায়ী"

    apply_method = _clean_text_val(m.get("apply_method") or "অনলাইন")
    if _is_bad_val(apply_method):
        apply_method = "বিজ্ঞপ্তি অনুযায়ী"

    sd = _clean_text_val(m.get("start_date") or job_data.get("start_date") or "চলমান")
    ed = _clean_text_val(m.get("end_date") or job_data.get("end_date") or "শীঘ্রই")
    if sd == "চলমান" and p.get("date_box_text"):
        ed = _clip_phrase(p.get("date_box_text"), 48)

    wa_num = os.environ.get("WHATSAPP_NUMBER", "01540503092").strip() or "01540503092"
    wa_formatted = (wa_num[:5] + "-" + wa_num[5:]) if (len(wa_num) == 11 and wa_num.startswith("01") and "-" not in wa_num) else wa_num

    return {
        "org": org, "cat_badge": cat_badge, "hook_short": hook_short,
        "vac_num": vac_num, "vac_display": vac_display, "short_tag": short_tag,
        "posts": posts, "age_limit": _clip_phrase(age_limit, 44),
        "salary_range": _clip_phrase(salary_range, 48),
        "app_fee": _clip_phrase(app_fee, 44), "apply_method": _clip_phrase(apply_method, 44),
        "start_date": _clip_phrase(sd, 40), "end_date": _clip_phrase(ed, 44),
        "wa_formatted": wa_formatted,
        "summary": _clip_phrase(p.get("main_summary") or "", 110)
    }


def _classify_sentence_to_beat(sentence, core, state):
    s = normalize_bengali_nukta(sentence)

    if not state["used_vacancy"] and re.search(
        r'(?:শূন্যপদ|মোট\s*(?:[\d০-৯]+|একটি|দুইটি|তিনটি|কয়েকটি)?\s*(?:পদ|শূন্যপদ|ক্যাটাগরি|জনবল)|নিয়োগের\s*ঘোষণা|লোকবল\s*নিয়োগ)',
        s
    ):
        state["used_vacancy"] = True
        return {
            "kind": "vacancy", "header": "মোট শূন্যপদ",
            "value": core["vac_display"], "num": core["vac_num"],
            "tag": core["short_tag"], "sub_chips": _split_sentence_to_chips(s, 2, 78)
        }

    if (
        not state["used_deadline"]
        and not re.search(r'(?:প্রকাশিত|প্রকাশ\s*করা|দৈনিক)', s)
        and re.search(r'(?:আবেদনের\s*(?:শুরু|শেষ|সময়সীমা)|আবেদন\s*শুরু|জমা\s*দেওয়ার\s*শেষ|শেষ\s*তারিখ|শুরুর\s*তারিখ)', s)
    ):
        state["used_deadline"] = True
        return {
            "kind": "deadline", "header": "আবেদনের সময়সীমা",
            "start_date": core["start_date"], "end_date": core["end_date"],
            "sub_chips": _split_sentence_to_chips(s, 2, 78)
        }

    # শুধুমাত্র প্রকৃত 'ফি' শব্দ বা পেমেন্ট মাধ্যম ম্যাচ করবে (কখনোই 'অফিস' বা 'অফিসার' নয়!)
    if re.search(
        r'(?:আবেদন\s*ফি|পরীক্ষার\s*ফি|(?<![\u0980-\u09FF])ফি(?![\u0980-\u09FF])|৭২\s*ঘণ্টা|টেলিটক\s*প্রিপেইড|বিনামূল্যে|পোস্টাল\s*অর্ডার|ব্যাংক\s*ড্রাফট|পে-অর্ডার)',
        s
    ):
        return {
            "kind": "focus_card", "icon": "fee", "header": "আবেদন ফি ও পেমেন্ট",
            "main_label": "আবেদন ফি", "main_val": core["app_fee"],
            "sub_chips": _split_sentence_to_chips(s, 3, 82)
        }

    if re.search(r'(?:বয়সসীমা|বয়স|কোটা|মুক্তিযোদ্ধা|স্বাধীনতা|শারীরিক\s*প্রতিবন্ধী|আদিবাসী|নাগরিক)', s):
        return {
            "kind": "focus_card", "icon": "age", "header": "বয়স ও শর্তাবলি",
            "main_label": "বয়সসীমা", "main_val": core["age_limit"],
            "sub_chips": _split_sentence_to_chips(s, 3, 82)
        }

    if re.search(
        r'(?:শিক্ষাগত|যোগ্যতা|অভিজ্ঞতা|ডিগ্রি|স্নাতকোত্তর|স্নাতক|মাস্টার্স|এইচএসসি|এসএসসি|ভোকেশনাল|অষ্টম|৮ম|টাইপিং|লাইসেন্স|কম্পিউটার|দক্ষতা|পারদর্শী|পাটিগণিত)',
        s
    ):
        return {
            "kind": "focus_card", "icon": "qual", "header": "শিক্ষাগত যোগ্যতা ও দক্ষতা",
            "main_label": "প্রয়োজনীয় যোগ্যতা", "main_val": core["hook_short"],
            "sub_chips": _split_sentence_to_chips(s, 3, 82)
        }

    if re.search(r'(?:বেতন\s*স্কেল|বেতন|ভাতা|গ্রেড|সুযোগ-সুবিধা|কর্মস্থল|কাজের\s*স্থান)', s):
        if not state["used_posts"] and len(core["posts"]) > 0 and ("গ্রেড" in s or "ক্যাটাগরি" in s):
            state["used_posts"] = True
            return {
                "kind": "posts", "header": "প্রধান পদসমূহ",
                "posts": core["posts"], "sub_chips": _split_sentence_to_chips(s, 2, 78)
            }
        return {
            "kind": "focus_card", "icon": "salary", "header": "বেতন ও কর্মস্থল",
            "main_label": "বেতন স্কেল", "main_val": core["salary_range"],
            "sub_chips": _split_sentence_to_chips(s, 3, 82)
        }

    if re.search(
        r'(?:অনলাইন|টেলিটক|বিডিজবস|ই-?মেইল|ডাকযোগে|কুরিয়ার|সরাসরি|আবেদনপত্র|ফরম|পোর্টাল|কাগজপত্র|সত্যায়িত|বাইসাইকেল|বরাবর)',
        s
    ):
        return {
            "kind": "steps", "icon": "method", "header": "আবেদন প্রক্রিয়া",
            "main_label": "আবেদন মাধ্যম", "main_val": core["apply_method"],
            "sub_chips": _split_sentence_to_chips(s, 3, 82)
        }

    if re.search(r'(?:পরীক্ষা|লিখিত|মৌখিক|সাক্ষাৎকার|প্রবেশপত্র|নির্বাচন|বাছাই)', s):
        return {
            "kind": "steps", "icon": "exam", "header": "নির্বাচন ও পরীক্ষা",
            "main_label": "বাছাই প্রক্রিয়া", "main_val": "লিখিত ও মৌখিক পরীক্ষা",
            "sub_chips": _split_sentence_to_chips(s, 3, 82)
        }

    return {
        "kind": "highlight", "icon": "info", "header": "গুরুত্বপূর্ণ তথ্য",
        "main_label": core["org"], "main_val": _clip_phrase(s, 72),
        "sub_chips": _split_sentence_to_chips(s, 3, 82)
    }


def _expand_posts_into_beats(posts):
    """পদের সংখ্যা অনুযায়ী প্রতিটি পদের বা জোড়ায় জোড়ায় স্লাইড বানায়।"""
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

    # কেবলমাত্র একই kind ও একই icon হলে তবেই পাশাপাশি বিট মার্জ করবে (বয়স আর বেতন কখনো মিশবে না)
    max_middle_beats = max(6, int(duration / 3.8))
    merged = []
    for b in beats_raw:
        if (
            merged and len(merged) > 1
            and b["kind"] == merged[-1]["kind"]
            and b.get("icon") == merged[-1].get("icon")
            and b["kind"] in ["highlight", "steps", "focus_card"]
            and (merged[-1]["weight"] + b["weight"]) <= 30
        ):
            prev = merged[-1]
            for ch in b.get("sub_chips", []):
                if ch not in prev.get("sub_chips", []) and len(prev["sub_chips"]) < 3:
                    prev["sub_chips"].append(ch)
            prev["weight"] += b["weight"]
        else:
            merged.append(b)

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
