# -*- coding: utf-8 -*-
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config_manager import HEADERS, clean_feed_url

def extract_article_images(entry, entry_link, raw_desc=""):
    img_urls = []
    if 'enclosures' in entry and entry.enclosures:
        img_urls.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    if 'media_content' in entry and entry.media_content:
        img_urls.extend([mc.get('url') for mc in entry.media_content])
    img_urls.extend(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_desc, re.IGNORECASE))

    try:
        # 🌟 নো টাইমআউট
        web_res = requests.get(entry_link, headers=HEADERS)
        if web_res.status_code == 200:
            scraped = [u for u in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', web_res.text, re.IGNORECASE) if not any(l in u.lower() for l in ['logo', 'icon', 'avatar', 'emoji'])]
            img_urls.extend([i for i in scraped if i not in img_urls])
    except Exception: pass

    cleaned = []
    seen_bases = set()
    for u in img_urls[:6]:
        u = urljoin(entry_link, u) if not u.startswith('http') else u
        base_u = u.split('?')[0]
        if base_u not in seen_bases:
            seen_bases.add(base_u)
            cleaned.append(u)
    return cleaned

def scrape_full_webpage_content(page_url):
    try:
        # 🌟 নো টাইমআউট
        resp = requests.get(page_url, headers=HEADERS)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            container = soup.find(['div', 'article', 'section'], class_=re.compile(r'(entry-content|post-content|article-body|main-content)', re.I))
            element = container if container else soup
            for tag in element(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            return element.get_text(separator=' ', strip=True), resp.text
    except Exception as e:
        print(f"  [!] Webpage scrape notice for {page_url}: {e}")
    return "", ""

def fetch_feed_entries(source_url):
    target_feed_url = clean_feed_url(source_url)
    rss_target = target_feed_url if target_feed_url.endswith(('/feed', '/feed/', '/rss', '/rss/')) else target_feed_url.rstrip('/') + '/feed/'
    
    for try_url in [rss_target, target_feed_url]:
        try:
            # 🌟 নো টাইমআউট
            resp = requests.get(try_url, headers=HEADERS)
            if resp.status_code == 200 and resp.content:
                parsed = feedparser.parse(resp.content)
                if parsed.entries:
                    return parsed
        except Exception:
            pass

    return feedparser.parse(b"")
