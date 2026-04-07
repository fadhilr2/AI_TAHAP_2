from TikTokApi import TikTokApi
import asyncio
import os
import sys # Imported to check for Windows
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


ms_token=os.getenv("MS_TOKEN")
print(ms_token)
async def trending_videos():
    async with TikTokApi() as api:
        await api.create_sessions(ms_tokens=[ms_token], 
                                  num_sessions=1, 
                                  sleep_after=7, 
                                  browser="chromium",
                                  headless=False) 
        
        async for video in api.trending.videos(count=5):
            # Get the massive dictionary
            v_dict = video.as_dict
            
            # Safely extract just the data we care about
            author = v_dict.get('author', {}).get('uniqueId', 'Unknown')
            description = v_dict.get('desc', 'No description')
            views = v_dict.get('stats', {}).get('playCount', 0)
            likes = v_dict.get('stats', {}).get('diggCount', 0)
            
            # Print a nice, readable summary
            print(f"👤 Author: @{author}")
            print(f"👀 Views: {views:,} | ❤️ Likes: {likes:,}")
            print(f"📝 Desc: {description[:50]}...") # cuts off long descriptions
            print("-" * 40)



if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(trending_videos())