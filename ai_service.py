# ai_service.py এর শেষের অংশটুকু নিচের কোড দিয়ে আপডেট করুন

def generate_job_data_and_script(title, article_text, raw_html, image_paths, memory=None):
    clean_title = remove_years(re.sub(r'[\r\n\t]+', ' ', str(title)).strip())
    full_content = f"Title: {clean_title}\n\nWebpage Article Details:\n{article_text[:3000]}"

    prompt = f"""You are a professional Bengali Job Circular Content Engine and Voiceover Writer.
Analyze this circular and circular images:

Content:
{full_content}

CRITICAL RULES:
1. APPLICATION METHOD ANALYSIS:
   - "is_online_application": true/false (true ONLY if candidates can apply online via website/portal/form/teletalk/email).
   - "application_method": "online" | "postal" | "courier" | "in_person"
   - "offline_reason": reason in Bengali if false.

2. MULTI-SCRIPT GENERATION (VERY IMPORTANT):
   - Provide "scripts": Array of 8 UNIQUE spoken Bengali voiceover scripts (each 100-130 words).
   - Each script must have a DIFFERENT hook and sentence structure (e.g. hook 1: "বেকার তরুণ-তরুণীদের জন্য দারুণ সুযোগ...", hook 2: "নতুন সরকারি চাকরির বিজ্ঞপ্তি প্রকাশিত হয়েছে...", hook 3: "আকর্ষণীয় বেতনে ক্যারিয়ার গড়ার সুযোগ...", etc.).
   - All 8 scripts MUST strictly end with WhatsApp CTA: "আবেদনটি নির্ভুলভাবে সম্পন্ন করতে স্ক্রিনে দেওয়া হোয়াটসঅ্যাপ নাম্বারে আজই মেসেজ দিন।"
   - NO years (2026/২০২৬), NO website mentions, NO like/subscribe mentions.

3. DATA EXTRACTION:
   - "org_name": Official institution name.
   - "start_date": e.g. "০১ অক্টোবর".
   - "end_date": e.g. "৩০ অক্টোবর".
   - "posts": List of post objects: {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}.

Return strictly valid JSON:
{{
  "org_name": "...",
  "is_online_application": true,
  "application_method": "online",
  "offline_reason": "",
  "start_date": "...",
  "end_date": "...",
  "posts": [
    {{"post_name": "...", "vacancy": "০১", "qualification": "..."}}
  ],
  "scripts": [
    "স্ক্রিপ্ট ১...",
    "স্ক্রিপ্ট ২...",
    "স্ক্রিপ্ট ৩...",
    "স্ক্রিপ্ট ৪...",
    "স্ক্রিপ্ট ৫...",
    "স্ক্রিপ্ট ৬...",
    "স্ক্রিপ্ট ৭...",
    "স্ক্রিপ্ট ৮..."
  ],
  "optimized_title": "...",
  "video_description": "..."
}}"""

    base64_imgs = [encode_image_base64(p) for p in image_paths[:3] if encode_image_base64(p)]
    ollama_endpoint = get_ollama_chat_endpoint()

    # ১. Ollama Cloud
    ollama_keys = get_all_ollama_keys()
    if ollama_keys:
        total_k = len(ollama_keys)
        start_idx = (memory.get("ollama_key_index", 0) if isinstance(memory, dict) else 0) % total_k

        for offset in range(total_k):
            k_idx = (start_idx + offset) % total_k
            api_key = ollama_keys[k_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

            for model in OLLAMA_MODELS:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": base64_imgs}],
                    "stream": False,
                    "options": {"temperature": 0.4}
                }
                try:
                    resp = requests.post(ollama_endpoint, headers=headers, json=payload, timeout=135)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and data.get("org_name") and data.get("posts"):
                            if isinstance(memory, dict): memory["ollama_key_index"] = k_idx
                            return normalize_eight_scripts(data)
                except Exception: pass

    # ২. Groq AI ব্যাকআপ
    if GROQ_API:
        headers = {"Authorization": f"Bearer {GROQ_API}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            payload = {
                "model": g_model,
                "messages": [
                    {"role": "system", "content": "You are a Bengali job circular analyst. Return 8 distinct voiceover scripts strictly ending with WhatsApp CTA."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
                "max_tokens": 3000
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=90)
                if resp.status_code == 200:
                    data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                    if data and data.get("org_name") and data.get("posts"):
                        return normalize_eight_scripts(data)
            except Exception: pass

    fallback = smart_fallback_data(title, article_text, raw_html)
    return normalize_eight_scripts(fallback)

# নিশ্চিত করা যে ঠিক ৮টি স্ক্রিপ্টই প্রস্তুত রয়েছে
def normalize_eight_scripts(data):
    scripts = data.get("scripts", [])
    single = data.get("voiceover_script", "")
    if single and not scripts:
        scripts = [single]

    hooks = [
        "চাকরিপ্রার্থীদের জন্য সুখবর! নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে।",
        "দারুণ সুযোগ! সরকারি ও স্বনামধন্য প্রতিষ্ঠানে নতুন চাকরির বিজ্ঞপ্তি।",
        "আবেদন শুরু হয়ে গেছে! ঘরে বসে চাকরির সুযোগ হাতছাড়া করবেন না।",
        "বেকারত্ব দূর করতে আজই আবেদন করুন নতুন প্রকাশিত এই সার্কুলারে।",
        "যোগ্যতা অনুযায়ী এখনই আবেদন করুন, আকর্ষণীয় ক্যারিয়ার গড়ার দারুণ সুযোগ।",
        "বিজ্ঞপ্তিতে উল্লেখিত বিভিন্ন পদে বিপুল সংখ্যক লোকবল নেওয়া হচ্ছে।",
        "আপনার স্বপ্নের চাকরির সন্ধান পেতে এখনই বিস্তারিত জেনে নিন।",
        "নতুন প্রকাশিত এই চাকরির সার্কুলারে দ্রুত আবেদন সম্পন্ন করতে পারেন।"
    ]
    base_text = scripts[0] if scripts else "নতুন নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে। আগ্রহী প্রার্থীরা প্রয়োজনীয় যোগ্যতা নিয়ে দ্রুত আবেদন সম্পন্ন করতে পারেন।"
    clean_base = re.sub(r'^(?:.*?)(?=এর জন্য|এ বিভিন্ন|পদে|বিজ্ঞপ্তি)', '', base_text).strip()

    final_8 = []
    for i in range(8):
        if i < len(scripts) and len(scripts[i].strip()) > 20:
            final_8.append(sanitize_voiceover_script(scripts[i]))
        else:
            varied = f"{hooks[i]} {clean_base}"
            final_8.append(sanitize_voiceover_script(varied))

    data["scripts"] = final_8[:8]
    data["voiceover_script"] = final_8[0]
    return data
