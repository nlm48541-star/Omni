# -*- coding: utf-8 -*-
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config_manager import HEADERS, clean_feed_url

def extract_article_images(entry, entry_link, raw_desc=""):
    img_urls = []

    # ১. আরএসএস এনক্লোজার চেক
    if 'enclosures' in entry and entry.enclosures:
        img_urls.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    if 'media_content' in entry and entry.media_content:
        img_urls.extend([mc.get('url') for mc in entry.media_content])

    # ২. লাইভ ওয়েবপেজ স্ক্র্যাপ
    try:
        resp = requests.get(entry_link, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 🌟 (ক) OpenGraph og:image মেটা ট্যাগ চেক (ওয়ার্ডপ্রেসের মূল ফিচার্ড ইমেজ সবসময় এখানে থাকে)
            og_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
            if og_img and og_img.get('content'):
                img_urls.append(og_img.get('content'))

            # (খ) অপ্রাসঙ্গিক উইজেট, ফুটার ও বিজ্ঞাপন মুছে ফেলা
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            for junk in soup.find_all(['div', 'section', 'ul'], class_=re.compile(r'(related|sidebar|widget|comment|footer|recommend|yarpp|jp-relatedposts|author-box)', re.I)):
                junk.decompose()

            # (গ) মূল কন্টেন্ট ও ফিচার্ড ইমেজ এরিয়া
            container = soup.find(['div', 'article', 'section'], class_=re.compile(r'(entry-content|post-content|article-body|main-content|post-entry|post-thumbnail|featured-image)', re.I))
            target_element = container if container else soup.find('body')

            if target_element:
                for img in target_element.find_all('img'):
                    # 🌟 রেগুলার src সহ সব ধরণের লেজি-লোড অ্যাট্রিবিউট চেক
                    src = (
                        img.get('src') or 
                        img.get('data-src') or 
                        img.get('data-lazy-src') or 
                        img.get('data-orig-file') or 
                        img.get('data-full-url')
                    )
                    if not src and img.get('srcset'):
                        src = img.get('srcset').split(',')[0].split()[0]

                    if src:
                        s_lower = src.lower()
                        if not any(x in s_lower for x in ['logo', 'icon', 'avatar', 'emoji', 'button', 'badge', 'ad-', 'advert']):
                            full_u = urljoin(entry_link, src)
                            img_urls.append(full_u)
    except Exception as e:
        print(f"  [!] Web scrape image notice: {e}")

    # ৩. ফলব্যাক: raw_desc থেকে ছবি খোঁজা
    if not img_urls and raw_desc:
        img_urls.extend(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_desc, re.I))

    # ডুপ্লিকেট দূর করা ও ক্লিন ইউআরএল তৈরি
    cleaned = []
    seen_bases = set()
    for u in img_urls:
        if not u or not isinstance(u, str): continue
        u = urljoin(entry_link, u) if not u.startswith('http') else u
        base_u = u.split('?')[0]
        if base_u not in seen_bases:
            seen_bases.add(base_u)
            cleaned.append(u)
    return cleaned

def scrape_full_webpage_content(page_url):
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=45)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            for junk in soup.find_all(['div', 'section', 'ul'], class_=re.compile(r'(related|sidebar|widget|comment|footer|recommend|yarpp)', re.I)):
                junk.decompose()
            container = soup.find(['div', 'article', 'section'], class_=re.compile(r'(entry-content|post-content|article-body|main-content)', re.I))
            element = container if container else soup
            return element.get_text(separator=' ', strip=True), resp.text
    except Exception as e:
        print(f"  [!] Webpage scrape notice for {page_url}: {e}")
    return "", ""

def fetch_feed_entries(source_url):
    target_feed_url = clean_feed_url(source_url)
    rss_target = target_feed_url if target_feed_url.endswith(('/feed', '/feed/', '/rss', '/rss/')) else target_feed_url.rstrip('/') + '/feed/'
    try:
        resp = requests.get(rss_target, headers=HEADERS, timeout=36)
        if resp.status_code == 200:
            return feedparser.parse(resp.content)
        else:
            resp2 = requests.get(target_feed_url, headers=HEADERS, timeout=36)
            return feedparser.parse(resp2.content if resp2.status_code == 200 else target_feed_url)
    except Exception:
        return feedparser.parse(target_feed_url)
