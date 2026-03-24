"""
TikTok Comments Scraper
=======================
Scrapes up to 5000 comments from a public TikTok post.

Requirements:
    pip install TikTokApi playwright
    playwright install chromium

Usage:
    python tiktok_comments_scraper.py
    
    Then enter your TikTok video URL when prompted.
    Results are saved to tiktok_comments.csv and tiktok_comments.json
"""

import asyncio
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("❌ TikTokApi not installed. Run: pip install TikTokApi playwright && playwright install chromium")
    sys.exit(1)


# ─── Configuration ────────────────────────────────────────────────────────────

MAX_COMMENTS   = 5000       # Target number of comments to collect
BATCH_SIZE     = 50         # Comments per API request (TikTok's page size)
DELAY_SECONDS  = 1.5        # Polite delay between requests (avoid rate limiting)
OUTPUT_CSV     = "tiktok_comments.csv"
OUTPUT_JSON    = "tiktok_comments.json"
MS_TOKEN = "MS_TOKEN"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str:
    """Extract the numeric video ID from a TikTok URL."""
    # Handles formats:
    #   https://www.tiktok.com/@user/video/1234567890123456789
    #   https://vm.tiktok.com/XXXXXXX/   (short links – resolved by requests)
    patterns = [
        r"/video/(\d+)",
        r"tiktok\.com/.*?(\d{15,25})",   # fallback: long numeric ID anywhere
    ]

    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def ts_to_datetime(ts: int) -> str:
    """Convert a Unix timestamp to a readable ISO-8601 string."""
    if not ts:
        return ""
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %Human:%M:%S UTC")


def flatten_comment(c: dict) -> dict:
    """Return a clean, flat dictionary for one comment object."""
    return {
        "comment_id":    c.get("cid", ""),
        "text":          c.get("text", ""),
        "author":        c.get("user", {}).get("unique_id", ""),
        "author_id":     c.get("user", {}).get("uid", ""),
        "likes":         c.get("digg_count", 0),
        "reply_count":   c.get("reply_comment_total", 0),
        "created_at":    ts_to_datetime(c.get("create_time", 0)),
        "is_author_digged": c.get("is_author_digged", False),
        "pinned":        c.get("stick_position", 0) != 0,
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
    print(f"🎯 Target    : {max_comments} comments")
    print(f"📦 Batch size: {BATCH_SIZE}\n")

    collected   = []
    cursor      = 0
    page        = 1

    async with TikTokApi() as api:
        # TikTokApi needs a ms_token cookie for authenticated scraping.
        # Without it the library still works but may hit rate limits sooner.
        # To add one: api.generate_did()  or supply ms_token= below.
        await api.create_sessions(
            num_sessions=1,
            sleep_after=3,
            ms_tokens=[MS_TOKEN],   # optional but recommended
            headless=False,
        )

        video = api.video(id=video_id)

        while len(collected) < max_comments:
            needed = max_comments - len(collected)
            batch_count = min(BATCH_SIZE, needed)

            print(f"  📥 Page {page:>3} | cursor={cursor} | fetching {batch_count} …", end=" ", flush=True)

            try:
                batch = []
                async for comment in video.comments(count=batch_count, cursor=cursor):
                    raw = comment.as_dict
                    batch.append(flatten_comment(raw))

                if not batch:
                    print("no more comments – done.")
                    break

                collected.extend(batch)
                cursor += len(batch)
                print(f"got {len(batch)} | total={len(collected)}")
                page += 1

                # Be polite to TikTok's servers
                await asyncio.sleep(DELAY_SECONDS)

            except Exception as e:
                print(f"\n⚠️  Error on page {page}: {e}")
                print("   Retrying in 5 s …")
                await asyncio.sleep(5)
                # One retry; give up after that to avoid infinite loops
                try:
                    batch = []
                    async for comment in video.comments(count=batch_count, cursor=cursor):
                        batch.append(flatten_comment(comment.as_dict))
                    if not batch:
                        break
                    collected.extend(batch)
                    cursor += len(batch)
                    page += 1
                except Exception as e2:
                    print(f"   ❌ Retry failed: {e2} – stopping.")
                    break

    return collected[:max_comments]


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 55)
    print("  TikTok Comments Scraper  (one-shot, up to 5 000)")
    print("=" * 55)

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

        # Quick stats
        total_likes = sum(c["likes"] for c in comments)
        top5 = sorted(comments, key=lambda c: c["likes"], reverse=True)[:5]
        print(f"\n📈 Stats")
        print(f"   Total comments  : {len(comments)}")
        print(f"   Total likes     : {total_likes:,}")
        print(f"\n🏆 Top 5 most-liked comments:")
        for i, c in enumerate(top5, 1):
            preview = c["text"][:80].replace("\n", " ")
            print(f"  {i}. [{c['likes']:>5} ❤️ ] @{c['author']}: {preview}")
    else:
        print("⚠️  No comments were collected. Check the URL and try again.")


if __name__ == "__main__":
    asyncio.run(main())