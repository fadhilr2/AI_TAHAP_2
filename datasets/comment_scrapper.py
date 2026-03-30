import asyncio
import csv
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("❌ TikTokApi not installed. Run: pip install TikTokApi playwright && playwright install chromium")
    sys.exit(1)

# ─── Configuration ────────────────────────────────────────────────────────────

MAX_COMMENTS   = 5000       # Target number of comments to collect
BATCH_SIZE     = 50         # Comments per API request (TikTok's page size)
DELAY_SECONDS  = 15        # Polite delay between requests (avoid rate limiting)
OUTPUT_CSV     = "tiktok_comments.csv"
OUTPUT_JSON    = "tiktok_comments.json"
MS_TOKEN       = os.getenv("MS_TOKEN")

# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def ts_to_datetime(ts) -> str:
    """Convert a Unix timestamp to a readable ISO-8601 string safely."""
    if not ts:
        return ""
    try:
        if ts_float > 1e11: 
            ts_float /= 1000.0
            
        dt = datetime.fromtimestamp(ts_float, tz=timezone.utc)
        
        # Output a true ISO-8601 format (e.g., 2026-03-25T15:25:46Z)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Cast to int in case the API returns a string
    except (ValueError, TypeError):
        return ""


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
        "created_at":       ts_to_datetime(c.get("create_time", 0)),
        "is_author_digged": c.get("is_author_digged", False),
        "pinned":           c.get("stick_position", 0) != 0,
    }


def save_csv(comments: list[dict], path: str) -> None:
    if not comments:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=comments[0].keys())
        writer.writeheader()
        writer.writerows(comments)
    print(f"  ✅ CSV saved → {path}")


def save_json(comments: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)
    print(f"  ✅ JSON saved → {path}")


# ─── Core scraper ─────────────────────────────────────────────────────────────

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
                    await asyncio.sleep(DELAY_SECONDS)

        except Exception as e:
            print(f"\n⚠️ Stopped early due to API error: {e}")
            print("  (TikTok might have blocked the token, saving what we have so far...)")

    return collected[:max_comments]


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 55)
    print("  TikTok Comments Scraper  (one-shot, up to 5000)")
    print("=" * 55)

    #CAN BE REMOVED FOR COMPOUND INPUT
    video_url = input("\nPaste TikTok video URL: ").strip()
    if not video_url:
        print("No URL provided. Exiting.")
        sys.exit(0)

    target = input(f"How many comments? [default={MAX_COMMENTS}]: ").strip()
    target = int(target) if target.isdigit() else MAX_COMMENTS
    target = min(target, MAX_COMMENTS)

    start = time.time()
    comments = await scrape_comments(video_url, max_comments=target)
    elapsed = time.time() - start

    print(f"\n📊 Collected {len(comments)} comments in {elapsed:.1f}s")

    if comments:
        print("\n💾 Saving results …")
        save_csv(comments, OUTPUT_CSV)
        save_json(comments, OUTPUT_JSON)
    else:
        print("⚠️ No comments were collected. Check the URL and try again.")


if __name__ == "__main__":
    # Fix for Playwright/Asyncio crashing on Windows when the event loop closes
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())