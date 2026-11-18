# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
import requests
import feedparser
from bs4 import BeautifulSoup, NavigableString
from config_manager import HEADERS, clean_feed_url

_PAGE_HTML_CACHE = {}

_NOISE_CLASS_RE = re.compile(
    r'(related|sidebar|widget|comment|respond|footer|recommend|yarpp|jp-relatedposts|'
    r'crp_related|toc|table-of-contents|ez-toc|lwptoc|rank-math|author-box|share|'
    r'social|popular|recent|breadcrumb|menu|post-navigation|nav-links|wp-post-image|'
    r'post-thumbnail|featured-image|post-image|newsletter|calculator|hot-job|'
    r'whatsapp-channel|telegram-channel|join-whatsapp|rating|vote)',
    re.I,
)

_BAD_IMG_RE = re.compile(
    r'(logo|icon|avatar|emoji|button|badge|qrcode|qr-code|favicon|gravatar|spinner|'
    r'placeholder|blank\.gif|whatsapp|telegram|facebook|messenger|share|ad-|advert|'
    r'150x150|300x169|300x200|32x32|64x64|wp-content/themes|\.svg(?:\?|$)|\.gif(?:\?|$))',
    re.I,
)

_STOP_SECTION_MARKERS = [
    "সাধারণ জিজ্ঞাসা (FAQ)",
    "সাধারণ জিজ্ঞাসা",
    "সরকারি চাকরি: আরও চলমান",
    "আরও অন্যান্য চাকরির",
    "সর্বশেষ প্রকাশিত",
    "গত ৭ দিনের জনপ্রিয়",
    "গত ৭ দিনের জনপ্রিয়",
    "শীঘ্রই আবেদন শেষ",
    "প্রস্তুতি ও এক্সপার্ট টিপস",
    "লিখেছেন ও যাচাই করেছেন",
    "আপনার মন্তব্য বা প্রশ্ন",
    "Leave a Comment",
    "Your email address will not be published",
    "নিচে সাম্প্রতিক আরও",
    "ভুল তথ্য সমাধান",
    "ডিক্লারেশন (Declaration)",
    "গুরুত্বপূর্ণ সতর্কতা",
    "সবার আগে সরকারি ও বেসরকারি",
    "🔥 হট জব সার্কুলার",
    "হট জব সার্কুলার",
    "চাকরির ক্যাটাগরি",
    "বয়স ক্যালকুলেটর",
    "বয়স ক্যালকুলেটর",
    "Recent Posts",
    "Recent Comments",
]

_SKIP_BLOCK_TRIGGERS = (
    "আরো দেখুন",
    "আরো দেখতে পারেন",
    "আরও দেখুন",
    "আরও দেখতে পারেন",
    "এছাড়া দেখতে পারেন",
    "এছাড়া দেখতে পারেন",
    "দেখে নিনঃ চলমান",
    "Join WhatsApp Channel",
    "সবার আগে নতুন চাকরির আপডেট পেতে",
    "এ পোস্টে আপনি এক নজরে পাবেন",
    "সূচিপত্র (",
    "সব ১৩টি অংশ দেখুন",
    "সকল তথ্যের টেবিল",
    "হট জবস ·",
)


def _fetch_html_cached(page_url):
    if not page_url:
        return ""
    if page_url in _PAGE_HTML_CACHE:
        return _PAGE_HTML_CACHE[page_url]
    try:
        resp = requests.get(page_url, headers={**HEADERS, "Referer": page_url}, timeout=40)
        if resp.status_code == 200 and resp.text:
            if len(_PAGE_HTML_CACHE) > 30:
                _PAGE_HTML_CACHE.clear()
            _PAGE_HTML_CACHE[page_url] = resp.text
            return resp.text
    except Exception as e:
        print(f"  [!] Fetch notice for {page_url}: {e}")
    return ""


def _normalize_img_stem(url):
    base = str(url or "").split("?")[0].lower()
    base = re.sub(r'-\d{2,4}x\d{2,4}(?=\.[a-z]+$)', '', base)
    base = re.sub(r'-scaled(?=\.[a-z]+$)', '', base)
    return base


def _pick_real_img_url(img, base_url):
    candidates = []
    parent_a = img.find_parent('a')
    if parent_a and parent_a.get('href'):
        href = urljoin(base_url, parent_a['href'].strip())
        hl = href.lower().split('?')[0]
        if hl.endswith(('.jpg', '.jpeg', '.png', '.webp')) or 'blogger.googleusercontent.com' in hl or 'i.ibb.co' in hl:
            candidates.append(href)

    for attr in ('data-lazy-src', 'data-src', 'data-orig-file', 'data-full-url', 'data-large_image', 'data-original', 'data-url'):
        val = img.get(attr)
        if val and isinstance(val, str):
            candidates.append(val.strip())

    for s_attr in ('data-lazy-srcset', 'data-srcset', 'srcset'):
        ss = img.get(s_attr)
        if ss and isinstance(ss, str):
            parts = [p.strip().split()[0] for p in ss.split(',') if p.strip()]
            if parts:
                candidates.append(parts[-1])

    if img.get('src'):
        candidates.append(str(img.get('src')).strip())

    for raw in candidates:
        if not raw or raw.startswith('data:'):
            continue
        full_u = urljoin(base_url, raw)
        low = full_u.lower()
        if not low.startswith('http') or _BAD_IMG_RE.search(low):
            continue
        return full_u
    return None


def _find_main_container(soup):
    for selector in (
        '.inside-article .entry-content',
        '.entry-content',
        '.post-content',
        '.article-body',
        '.main-content',
        '.post-entry',
        '.td-post-content',
        'article',
        'main',
    ):
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 120:
            return el
    return soup.find('body') or soup


def _strip_noise_dom(root):
    for tag in root(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'iframe', 'svg', 'button']):
        tag.decompose()
    for junk in list(root.find_all(['div', 'section', 'ul', 'aside', 'figure'])):
        if not getattr(junk, 'attrs', None):
            continue
        cls = " ".join(junk.get('class', [])) if isinstance(junk.get('class'), list) else str(junk.get('class', ''))
        jid = str(junk.get('id', ''))
        if _NOISE_CLASS_RE.search(f"{cls} {jid}"):
            junk.decompose()


def _is_inside_related_block(tag):
    for parent in tag.parents:
        if parent.name in ('body', 'html', '[document]'):
            break
        txt = parent.get_text(" ", strip=True)[:180]
        if any(k in txt for k in ("আরও চলমান", "আরো দেখুন", "আরো দেখতে পারেন", "সাম্প্রতিক আরও নিয়োগ", "হট জব সার্কুলার")):
            if len(parent.find_all('a')) >= 2:
                return True
    return False


def extract_article_images(entry, entry_link, raw_desc=""):
    content_imgs = []
    featured_urls = []
    featured_stems = set()
    fallback_imgs = []

    raw_html = _fetch_html_cached(entry_link)
    if raw_html:
        try:
            soup = BeautifulSoup(raw_html, 'html.parser')
            for m_prop, m_key in (('property', 'og:image'), ('name', 'twitter:image')):
                tag = soup.find('meta', attrs={m_prop: m_key})
                if tag and tag.get('content'):
                    fu = urljoin(entry_link, tag['content'].strip())
                    featured_urls.append(fu)
                    featured_stems.add(_normalize_img_stem(fu))

            for f_img in soup.select('.wp-post-image, .post-thumbnail img, .featured-image img, .post-image img'):
                fu = _pick_real_img_url(f_img, entry_link)
                if fu:
                    featured_urls.append(fu)
                    featured_stems.add(_normalize_img_stem(fu))

            container = _find_main_container(soup)
            _strip_noise_dom(container)

            for img in container.find_all('img'):
                if _is_inside_related_block(img):
                    continue
                u = _pick_real_img_url(img, entry_link)
                if not u:
                    continue
                if _normalize_img_stem(u) in featured_stems:
                    fallback_imgs.append(u)
                    continue
                content_imgs.append(u)
        except Exception as e:
            print(f"  [!] Web scrape image notice: {e}")

    if 'enclosures' in entry and entry.enclosures:
        fallback_imgs.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    if 'media_content' in entry and entry.media_content:
        fallback_imgs.extend([mc.get('url') for mc in entry.media_content if mc.get('url')])
    if not content_imgs and raw_desc:
        fallback_imgs.extend(re.findall(r'<img[^>]+(?:data-lazy-src|data-src|src)=["\']([^"\']+)["\']', raw_desc, re.I))

    fallback_imgs.extend(featured_urls)

    # আসল সার্কুলার ইমেজ থাকলে কভার/og:image ব্যানার বাদ দিয়ে আসল সার্কুলারগুলোই ফেরত দেবে
    raw_pool = content_imgs if content_imgs else fallback_imgs
    cleaned, seen_bases = [], set()
    for u in raw_pool:
        if not u or not isinstance(u, str) or u.startswith('data:'):
            continue
        u = urljoin(entry_link, u) if not u.startswith('http') else u
        if _BAD_IMG_RE.search(u.lower()):
            continue
        base_u = u.split('?')[0]
        if base_u not in seen_bases:
            seen_bases.add(base_u)
            cleaned.append(u)
    return cleaned


def _clean_structured_text(raw_text, page_title=""):
    lines_out = []
    skip_until_blank = False
    is_current_2026 = ("২০২৬" in page_title or "2026" in page_title or "২০২৬" in raw_text[:800])

    for raw_line in raw_text.splitlines():
        line = re.sub(r'[ \t]+', ' ', raw_line).strip()
        if not line:
            skip_until_blank = False
            continue

        if any(m in line for m in _STOP_SECTION_MARKERS):
            break

        if any(trig in line for trig in _SKIP_BLOCK_TRIGGERS):
            skip_until_blank = True
            continue

        if skip_until_blank:
            if line.startswith("### ") or "|" in line:
                skip_until_blank = False
            else:
                continue

        # projobsbd-র নিচের পুরোনো ২০২১-২০২৪ কপি-পেস্ট অংশ বাদ দেওয়া (যদি মূল পোস্ট ২০২৬-এর হয়)
        if is_current_2026 and len(lines_out) > 12:
            if re.search(r'(?:২০২[১-৪]|202[1-4])', line) and not re.search(r'(?:প্রতিষ্ঠিত|স্থাপিত|আইন|অধ্যাদেশ|১৯[৭-৯]\d|201\d)', line):
                continue

        lines_out.append(line)

    text_out = "\n".join(lines_out)
    text_out = re.sub(r'\n{3,}', '\n\n', text_out)
    return text_out.strip()


def scrape_full_webpage_content(page_url):
    raw_html = _fetch_html_cached(page_url)
    if not raw_html:
        return "", ""
    try:
        soup = BeautifulSoup(raw_html, 'html.parser')
        h1 = soup.find('h1')
        page_title = h1.get_text(" ", strip=True) if h1 else (soup.title.get_text(" ", strip=True) if soup.title else "")

        element = _find_main_container(soup)
        _strip_noise_dom(element)

        # হেডিংগুলোকে স্পষ্টভাবে চিহ্নিত করা যাতে AI কাঠামো বুঝতে পারে
        for hdr in element.find_all(['h1', 'h2', 'h3', 'h4']):
            htxt = re.sub(r'\s+', ' ', hdr.get_text(" ", strip=True))
            if htxt:
                hdr.replace_with(NavigableString(f"\n\n### {htxt}\n"))

        # টেবিলের ডেটাগুলো সুন্দরভাবে পাইপ (|) ফরম্যাটে সাজানো
        for table in element.find_all('table'):
            rows_txt = []
            for tr in table.find_all('tr'):
                cols = [re.sub(r'\s+', ' ', c.get_text(" ", strip=True)) for c in tr.find_all(['td', 'th'])]
                cols = [c for c in cols if c]
                if cols:
                    rows_txt.append(" | ".join(cols))
            table.replace_with(NavigableString("\n" + "\n".join(rows_txt) + "\n\n"))

        # লিস্ট আইটেমগুলো সাজানো
        for li in element.find_all('li'):
            ltxt = re.sub(r'\s+', ' ', li.get_text(" ", strip=True))
            if ltxt and len(ltxt) > 3:
                li.replace_with(NavigableString(f"\n- {ltxt}"))

        raw_text = element.get_text(separator='\n', strip=True)
        clean_out = _clean_structured_text(raw_text, page_title=page_title)
        return clean_out, raw_html
    except Exception as e:
        print(f"  [!] Webpage scrape notice for {page_url}: {e}")
    return "", raw_html


def fetch_feed_entries(source_url):
    target_feed_url = clean_feed_url(source_url)
    rss_target = target_feed_url if target_feed_url.endswith(('/feed', '/feed/', '/rss', '/rss/')) else target_feed_url.rstrip('/') + '/feed/'
    try:
        resp = requests.get(rss_target, headers=HEADERS, timeout=36)
        if resp.status_code == 200:
            return feedparser.parse(resp.content)
        resp2 = requests.get(target_feed_url, headers=HEADERS, timeout=36)
        return feedparser.parse(resp2.content if resp2.status_code == 200 else target_feed_url)
    except Exception:
        return feedparser.parse(target_feed_url)
