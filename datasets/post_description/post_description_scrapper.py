from dotenv import load_dotenv, find_dotenv
from TikTokApi import TikTokApi
import asyncio
import sys
import os
import json
import csv

load_dotenv(find_dotenv())

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("❌ TikTokApi not installed. Run: pip install TikTokApi playwright && playwright install chromium")
    sys.exit(1)

BATCH_SIZE     = 50         # Comments per API request (TikTok's page size)
DELAY_SECONDS  = 35        # Polite delay between requests (avoid rate limiting)
MS_TOKEN       = os.getenv("MS_TOKEN")

async def get_user_posts(username: str, limit: int = 30) -> list[dict]:
    """Fetch posts + descriptions from a TikTok user account."""
 
    posts = []
 
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[MS_TOKEN] if MS_TOKEN else [],
            num_sessions=1,
            sleep_after=3,
            headless=True,          # Set False to see the browser
        )
 
        user = api.user(username)
 
        # Fetch user info first
        try:
            user_info = await user.info()
            stats = user_info.get("userInfo", {}).get("stats", {})
            print(f"\n{'─'*55}")
            print(f"  Account  : @{username}")
            print(f"  Followers: {stats.get('followerCount', 'N/A'):,}")
            print(f"  Following: {stats.get('followingCount', 'N/A'):,}")
            print(f"  Likes    : {stats.get('heartCount', 'N/A'):,}")
            print(f"  Videos   : {stats.get('videoCount', 'N/A'):,}")
            print(f"{'─'*55}\n")
        except Exception as e:
            print(f"[Warning] Could not fetch user info: {e}\n")
 
        # Stream posts
        print(f"Fetching up to {limit} posts from @{username} ...\n")
 
        async for video in user.videos(count=limit):
            try:
                vid_data = video.as_dict
 
                # ── Core fields ──────────────────────────────────────────────
                video_id    = vid_data.get("id", "")
                description = vid_data.get("desc", "").strip()
 
 
                # ── Hashtags ─────────────────────────────────────────────────
                challenges  = vid_data.get("challenges", [])
                hashtags    = [f"#{c['title']}" for c in challenges if "title" in c]
 
                # ── Video URL ────────────────────────────────────────────────
                video_url   = f"https://www.tiktok.com/@{username}/video/{video_id}"
 
                post = {
                    "video_id"    : video_id,
                    "url"         : video_url,
                    "description" : description,
                    "hashtags"    : ", ".join(hashtags),
                }
 
                posts.append(post)
 
                # Pretty console output
                print(video_id)
                print()
 
            except Exception as e:
                print(f"[Warning] Skipping a video due to error: {e}")
                continue
 
    return posts


def save_json(posts: list[dict], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON saved → {filename}")


def save_csv(posts: list[dict], filename: str) -> None:
    if not posts:
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=posts[0].keys())
        writer.writeheader()
        writer.writerows(posts)
    print(f"✅ CSV  saved → {filename}")


async def main():
    TARGET_USERNAME = "funny.veb5"
    
    posts = await get_user_posts(TARGET_USERNAME, 10)
 
    if not posts:
        print("No posts retrieved. Check username or add an msToken.")
        return
 
    print(f"\n{'─'*55}")
    print(f"  Total posts fetched: {len(posts)}")
    print(f"{'─'*55}\n")
 
    # Save outputs
    save_json(posts, f"tiktok_{TARGET_USERNAME}.json")
    save_csv (posts, f"tiktok_{TARGET_USERNAME}.csv")

if __name__ == "__main__":
    asyncio.run(main())