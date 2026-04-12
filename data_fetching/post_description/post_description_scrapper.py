from dotenv import load_dotenv, find_dotenv
from TikTokApi import TikTokApi
import asyncio
import sys
import os
import json
import csv
import time
from pathlib import Path
import pandas as pd
import random

load_dotenv(find_dotenv())

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("❌ TikTokApi not installed. Run: pip install TikTokApi playwright && playwright install chromium")
    sys.exit(1)

MS_TOKEN       = os.getenv("MS_TOKEN")

def save_csv(posts: list[dict]) -> None:

    SCRIPT_DIR = Path(__file__).resolve().parent
    folder = SCRIPT_DIR / f"datasets/data.csv"
    filepath = SCRIPT_DIR / folder

    file_exists = os.path.isfile(filepath)

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=posts[0].keys())
    
        # Only write the header if the file is brand new
        if not file_exists or os.path.getsize(filepath) == 0:
            writer.writeheader()
        writer.writerows(posts)

    print(f"✅ CSV  saved → {filepath}")

async def get_user_posts(username: str, limit: int = 100) -> list[dict]:
    """Fetch posts + descriptions from a TikTok user account."""
 
    posts = []
 
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[MS_TOKEN] if MS_TOKEN else [],
            num_sessions=1,
            sleep_after=3,
            headless=False,          # Set False to see the browser
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
            if len(posts) >= limit:
                print(f"\nReached the limit of {limit} posts. Stopping fetch.")
                break
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

                save_csv([post])
 
                # Pretty console output
                print(video_id)
                print()

                await asyncio.sleep(random.uniform(5.0, 10.0))
 
            except Exception as e:
                print(f"[Warning] Skipping a video due to error: {e}")
                continue
 
    return posts


async def main():

    SCRIPT_DIR = Path(__file__).resolve().parent
    filepath = SCRIPT_DIR / "accounts.json"
    df = pd.read_json(filepath)
    # 0 done
    # 1 done
    # 2 done
    # 3 done
    # 4 done 
    #6 nanti skip aja
    posts = await get_user_posts(df["account_name"][5])


        
 


if __name__ == "__main__":
    asyncio.run(main())