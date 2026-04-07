import os
from dotenv import load_dotenv, find_dotenv
import urllib.request
import re
import json
import sys
import asyncio
from TikTokApi import TikTokApi
import csv
import random


load_dotenv(find_dotenv())

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("❌ TikTokApi not installed. Run: pip install TikTokApi playwright && playwright install chromium")
    sys.exit(1)


MAX_COMMENTS   = 5000       # Target number of comments to collect
BATCH_SIZE     = 50         # Comments per API request (TikTok's page size)
DELAY_SECONDS  = 35        # Polite delay between requests (avoid rate limiting)
OUTPUT_JSON    = "tiktok_comments.json"
OUTPUT_CSV = "tiktok_comments.csv"
MS_TOKEN       = os.getenv("MS_TOKEN")



def extract_video_id(url: str) -> str:
    """Extract the numeric video ID from a TikTok URL."""
    
    # Automatically resolve mobile short-links (vm, vt, and a.b)
    if any(domain in url for domain in ["vm.tiktok.com", "vt.tiktok.com", "a.b.tiktok.com"]):
        try:
            req = urllib.request.Request(
                url, 
                # Expanded headers to avoid TikTok's basic anti-bot 403 blocks
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                url = response.geturl()
        except urllib.error.URLError as e:
            print(f"⚠️ Network/Resolution error for short URL: {e}")
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
 
    # Expanded patterns to handle standard videos, mobile web, and photo slideshows
    patterns = [
        r"/(?:video|v|photo)/(\d+)",     # Matches /video/123, /v/123, /photo/123
        r"tiktok\.com/.*?(\d{15,25})",   # Fallback: long numeric ID anywhere
    ]
 
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
            
    raise ValueError(f"Could not extract video ID from URL: {url}")


def flatten_comment(c: dict) -> dict:
    """Return a clean, flat dictionary for one comment object."""
    # Safety check: if "user" is explicitly null in the JSON, it returns None.
    # `or {}` ensures it falls back to an empty dict.
    user_data = c.get("user") or {}
    
    return {
        "comment_id":       c.get("cid", ""),
        "text":             c.get("text", ""),
        "author":           user_data.get("unique_id", ""),
        "author_id":        user_data.get("uid", ""),
        "likes":            c.get("digg_count", 0),
        "reply_count":      c.get("reply_comment_total", 0),
        "is_author_digged": c.get("is_author_digged", False),
        "pinned":           c.get("stick_position", 0) != 0,
    }

async def scrape_comments(video_url: str, max_comments: int = MAX_COMMENTS) -> list[dict]:
    video_id = extract_video_id(video_url)
    print(f"\n🎬 Video ID  : {video_id}")
    print(f"🎯 Target    : {max_comments} comments\n")
 
    collected = []
 
    async with TikTokApi() as api:
        await api.create_sessions(
            num_sessions=1,
            sleep_after=3,
            ms_tokens=[MS_TOKEN] if MS_TOKEN else None,
            headless=False,
        )
 
        video = api.video(id=video_id)
 
        try:
            async for comment in video.comments(count=max_comments):
                raw = comment.as_dict
                collected.append(flatten_comment(raw))
 
                # Be polite: Sleep every BATCH_SIZE (50) comments
                if len(collected) % BATCH_SIZE == 0:
                    print(f"  📥 Collected {len(collected)} comments...")
                    DELAY_SECONDS = random.uniform(30, 45)
                    await asyncio.sleep(DELAY_SECONDS)
 
        except Exception as e:
            print(f"\n⚠️ Stopped early due to API error: {e}")
            print("  (TikTok might have blocked the token, saving what we have so far...)")
 
    return collected[:max_comments]


def save_csv(comments: list[dict], path: str) -> None:
    file_exists = os.path.isfile(path) and os.path.getsize(path) > 0

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=comments[0].keys())
        
        if not file_exists:
            writer.writeheader()
            
        writer.writerows(comments)
    
    print(f"  ✅ CSV saved → {path}")


def save_json(comments: list[dict], path: str) -> None:
    data = []
    # 1. Load existing data if it exists
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = [] # Handle empty or corrupted files

    # 2. Append new comments to the list
    data.extend(comments)

    # 3. Overwrite the file with the full updated list
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"  ✅ JSON saved → {path}")

async def main() -> None:
    video_url = "https://www.tiktok.com/@cizicakeeee/video/7604653546641886482?is_from_webapp=1&sender_device=pc"

    comments = await scrape_comments(video_url, max_comments=100)

    if comments:
        save_csv(comments, OUTPUT_CSV)
        save_json(comments, OUTPUT_JSON)



if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())