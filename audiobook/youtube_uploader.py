#!/usr/bin/env python3
"""
YouTube Batch Uploader using Playwright
Automates the upload of chapter videos from the 'youtube_uploads' directory.
"""

import os
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

UPLOADS_DIR = Path(__file__).parent / "output" / "youtube_uploads"

async def upload_video(page, folder_path):
    """Automate the upload flow for a single folder."""
    video_files = list(folder_path.glob("*.mp4"))
    if not video_files:
        return
    
    video_file = video_files[0]
    description_file = folder_path / "description.txt"
    description = description_file.read_text() if description_file.exists() else ""
    
    # Extract title from description (first line with CHAPTER:) or filename
    title = video_file.stem.replace('_', ' ').replace('-', ' ').title()
    for line in description.splitlines():
        if "CHAPTER:" in line:
            title = line.split("CHAPTER:", 1)[1].strip()
            break

    print(f"🚀 Uploading: {title} ({video_file.name})...")

    # 1. Click Create -> Upload
    await page.click("#create-icon")
    await page.click("#text-item-0") # Upload video
    
    # 2. Select File
    async with page.expect_file_chooser() as fc_info:
        await page.click("#select-files-button")
    file_chooser = await fc_info.value
    await file_chooser.set_files(str(video_file))
    
    # 3. Wait for upload to start and fill details
    await page.wait_for_selector('div[aria-label="Add a title"]')
    
    # Title
    title_box = page.locator('div[aria-label="Add a title"]')
    await title_box.fill(title[:100]) # YouTube limit 100
    
    # Description
    desc_box = page.locator('div[aria-label="Tell viewers about your video"]')
    await desc_box.fill(description[:5000]) # YouTube limit 5000
    
    # Wait for "Made for kids" question
    await page.click('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MADE_FOR_KIDS"]')
    
    # Next, Next, Next (Details -> Video Elements -> Checks -> Visibility)
    for _ in range(3):
        await page.click("#next-button")
        await asyncio.sleep(1)
    
    # Visibility (Set to Public or Private)
    # Defaulting to Private/Draft for safety, user can change to Public
    # await page.click('tp-yt-paper-radio-button[name="PUBLIC"]') 
    await page.click('tp-yt-paper-radio-button[name="PRIVATE"]')
    
    # Save
    await page.click("#done-button")
    await page.wait_for_selector("#close-button", timeout=60000)
    await page.click("#close-button")
    
    print(f"✅ Finished: {title}")

async def main():
    if not UPLOADS_DIR.exists():
        print(f"❌ Directory not found: {UPLOADS_DIR}")
        return

    async with async_playwright() as p:
        # Using a persistent context to stay logged in
        user_data_dir = Path.home() / ".playwright_youtube_session"
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Show browser so user can log in if needed
            args=["--start-maximized"]
        )
        
        page = await browser_context.new_page()
        await page.goto("https://studio.youtube.com")
        
        print("\n🔑 Please ensure you are logged into YouTube Studio.")
        print("Waiting 10 seconds for you to check...")
        await asyncio.sleep(10)
        
        folders = sorted([f for f in UPLOADS_DIR.iterdir() if f.is_dir()])
        
        for folder in folders:
            try:
                await upload_video(page, folder)
                await asyncio.sleep(5) # Small buffer between uploads
            except Exception as e:
                print(f"⚠️ Failed to upload {folder.name}: {e}")
                
        print("\n🎉 Batch upload session complete!")
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(main())
