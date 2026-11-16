# -*- coding: utf-8 -*-
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config_manager import HEADERS, clean_feed_url

def _get_real_img_url(img):
    for attr in ['data-lazy-src', 'data-src', 'data-orig-file', 'data-full-url', 'data-original', 'data-url', 'src']:
        val = img.get(attr)
        if val and isinstance(val, str):
            v = val.strip()
            if v and not v.startswith('data:') and not any(b in v.lower() for b in ['placeholder', 'spinner', 'blank.gif']):
                return v
    for s_attr in ['data-srcset', 'srcset']:
        ss = img.get(s_attr)
        if ss and isinstance(ss, str):
            first_u = ss.split(',')[0].strip().split()[0]
            if first_u and not first_u.startswith('data:'):
                return first_u
    parent_a = img.find_parent('a')
    if parent_a and parent_a.get('href'):
        href = parent_a['href'].strip()
        if href.lower().split('?')[0].endswith(('.jpg', '.jpeg', '.png', '.webp')):
            return href
    return None

def extract_article_images(entry, entry_link, raw_desc=""):
    content_imgs = []
    fallback_imgs = []

    try:
        resp = requests.get(entry_link, headers={**HEADERS, "Referer": entry_link}, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')

            og_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
            if og_img and og_img.get('content'):
                fallback_imgs.append(og_img.get('content'))

            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            for junk in soup.find_all(['div', 'section', 'ul'], class_=re.compile(r'(related|sidebar|widget|comment|footer|recommend|yarpp|jp-relatedposts|author-box|popular|recent)', re.I)):
                junk.decompose()

            container = soup.find(['div', 'article', 'section', 'main'], class_=re.compile(r'(entry-content|post-content|article-body|main-content|post-entry|inside-article)', re.I))
            target_element = container if container else (soup.find('article') or soup.find('main') or soup.find('body'))

            if target_element:
                for source in target_element.find_all('source'):
                    ss = source.get('data-srcset') or source.get('srcset')
                    if ss:
                        u = ss.split(',')[0].strip().split()[0]
                        if u and not u.startswith('data:') and not any(x in u.lower() for x in ['logo', 'icon', 'avatar', 'emoji', 'badge', 'ad-']):
                            content_imgs.append(urljoin(entry_link, u))

                for img in target_element.find_all('img'):
                    src = _get_real_img_url(img)
                    if src:
                        sl = src.lower()
                        if not any(x in sl for x in ['logo', 'icon', 'avatar', 'emoji', 'button', 'badge', 'ad-', 'advert', 'gravatar', '150x150', '32x32']):
                            content_imgs.append(urljoin(entry_link, src))
    except Exception as e:
        print(f"  [!] Web scrape image notice: {e}")

    if 'enclosures' in entry and entry.enclosures:
        fallback_imgs.extend([enc.get('href', '') for enc in entry.enclosures if enc.get('href', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    if 'media_content' in entry and entry.media_content:
        fallback_imgs.extend([mc.get('url') for mc in entry.media_content])
    if not content_imgs and raw_desc:
        fallback_imgs.extend(re.findall(r'<img[^>]+(?:data-lazy-src|data-src|src)=["\']([^"\']+)["\']', raw_desc, re.I))

    raw_pool = content_imgs if content_imgs else fallback_imgs
    cleaned, seen_bases = [], set()
    for u in raw_pool:
        if not u or not isinstance(u, str) or u.startswith('data:'):
            continue
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
            raw_html = resp.text
            soup = BeautifulSoup(raw_html, 'html.parser')

            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'iframe']):
                tag.decompose()
            for junk in soup.find_all(['div', 'section', 'ul', 'aside'], class_=re.compile(r'(related|sidebar|widget|comment|footer|recommend|yarpp|toc|ez-toc|author-box|share|social|popular|recent|breadcrumb|menu)', re.I)):
                junk.decompose()
            for junk_id in soup.find_all(id=re.compile(r'(comments|respond|sidebar|toc|ez-toc|secondary|footer)', re.I)):
                junk_id.decompose()

            container = soup.find(['div', 'article', 'section', 'main'], class_=re.compile(r'(entry-content|post-content|article-body|main-content|inside-article)', re.I))
            element = container if container else (soup.find('article') or soup.find('main') or soup)

            # টেবিলের ডেটাগুলো সুন্দরভাবে লাইন বাই লাইন ফরম্যাট করা যাতে এআই স্পষ্ট পড়তে পারে
            for table in element.find_all('table'):
                rows_txt = []
                for tr in table.find_all('tr'):
                    cols = [re.sub(r'\s+', ' ', c.get_text(" ", strip=True)) for c in tr.find_all(['td', 'th'])]
                    cols = [c for c in cols if c]
                    if cols:
                        rows_txt.append(" | ".join(cols))
                table.replace_with(soup.new_string("\n" + "\n".join(rows_txt) + "\n"))

            text_out = element.get_text(separator='\n', strip=True)
            text_out = re.sub(r'\n{2,}', '\n', text_out)
            return text_out, raw_html
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
        resp2 = requests.get(target_feed_url, headers=HEADERS, timeout=36)
        return feedparser.parse(resp2.content if resp2.status_code == 200 else target_feed_url)
    except Exception:
        return feedparser.parse(target_feed_url)
