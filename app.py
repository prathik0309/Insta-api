import os
import re
import time
import json
import uuid
from flask import Flask, jsonify, request
from flask_cors import CORS
import undetected_playwright as up
import asyncio
import requests

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.environ.get("PORT", 10000))
CACHE_DURATION = 1800  # 30 minutes cache
video_cache = {}

class InstagramScraper:
    """Free Instagram Video Scraper using Undetected Browser"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        
    async def start_browser(self):
        """Launch a stealth browser instance"""
        print("🚀 Launching stealth browser...")
        self.browser = await up.chromium.launch(
            headless=True,  # Run in background
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        
        # Create context with realistic viewport
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US'
        )
        
        # Block unnecessary resources to speed up
        await self.context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())
        
        self.page = await self.context.new_page()
        
    async def extract_video_from_page(self, url):
        """Navigate to Instagram and extract video URL"""
        print(f"🌐 Navigating to: {url}")
        
        try:
            # Go to the Instagram URL
            await self.page.goto(url, wait_until='networkidle', timeout=60000)
            
            # Wait for page to load
            await self.page.wait_for_timeout(3000)
            
            # Scroll a bit to trigger lazy loading
            await self.page.evaluate("window.scrollBy(0, 300)")
            await self.page.wait_for_timeout(2000)
            
            # Method 1: Look for video URL in page content
            page_content = await self.page.content()
            
            # Try multiple patterns to find video URL
            patterns = [
                r'"video_url":"([^"]+\.mp4[^"]*)"',
                r'"contentUrl":"([^"]+\.mp4[^"]*)"',
                r'src="([^"]+\.mp4[^"]*)"',
                r'property="og:video" content="([^"]+)"',
                r'<video[^>]+src="([^"]+)"'
            ]
            
            video_url = None
            thumbnail_url = None
            caption = "Instagram Reel"
            
            for pattern in patterns:
                matches = re.findall(pattern, page_content)
                for match in matches:
                    if '.mp4' in match and 'instagram' in match:
                        video_url = match.replace('\\u0026', '&')
                        break
                if video_url:
                    break
            
            # Method 2: If no video found, try to click play button and intercept network requests
            if not video_url:
                print("  No video in HTML, trying network interception...")
                
                # Click on video if possible
                video_element = await self.page.query_selector('video')
                if video_element:
                    await video_element.click()
                    await self.page.wait_for_timeout(2000)
                    
                    # Listen for network responses
                    video_urls = []
                    
                    def handle_response(response):
                        url = response.url
                        if '.mp4' in url and 'instagram' in url:
                            video_urls.append(url)
                    
                    self.page.on("response", handle_response)
                    await self.page.wait_for_timeout(5000)
                    
                    if video_urls:
                        video_url = video_urls[0]
            
            # Get thumbnail
            thumbnail_patterns = [
                r'"thumbnail_url":"([^"]+)"',
                r'property="og:image" content="([^"]+)"',
                r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"'
            ]
            
            for pattern in thumbnail_patterns:
                matches = re.findall(pattern, page_content)
                if matches:
                    thumbnail_url = matches[0].replace('\\u0026', '&')
                    break
            
            # Get caption if available
            caption_patterns = [
                r'"caption":"([^"]+)"',
                r'<title>[^<]*Instagram[^<]*([^<]+)</title>',
                r'property="og:title" content="([^"]+)"'
            ]
            
            for pattern in caption_patterns:
                matches = re.findall(pattern, page_content)
                if matches and len(matches[0]) > 10:
                    caption = matches[0][:100]
                    break
            
            if video_url:
                print(f"  ✅ Found video: {video_url[:80]}...")
                return {
                    "success": True,
                    "video_url": video_url,
                    "thumbnail": thumbnail_url or "",
                    "title": caption,
                    "method": "browser_automation"
                }
            else:
                print("  ❌ No video found")
                return None
                
        except Exception as e:
            print(f"  ⚠️ Browser error: {str(e)[:100]}")
            return None
    
    async def get_video(self, instagram_url):
        """Main function to get video from Instagram URL"""
        try:
            # Start browser if not already started
            if not self.browser:
                await self.start_browser()
            
            # Extract video
            result = await self.extract_video_from_page(instagram_url)
            
            if result and result.get('success'):
                return result
            
            # Try one more time with a fresh page
            print("  Retrying with fresh page...")
            await self.page.close()
            self.page = await self.context.new_page()
            
            result = await self.extract_video_from_page(instagram_url)
            return result or {
                "success": False,
                "error": "Could not extract video after multiple attempts"
            }
            
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            return {
                "success": False,
                "error": f"Scraping failed: {str(e)[:100]}"
            }
    
    async def close(self):
        """Close browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

# Global scraper instance
scraper = InstagramScraper()

def run_async(coro):
    """Helper to run async functions in sync context"""
    return asyncio.run(coro)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Free Instagram Video API",
        "method": "Browser Automation (Playwright)",
        "warning": "This is against Instagram's ToS. Use responsibly.",
        "endpoints": {
            "/api/video?url=URL": "Get Instagram video"
        }
    })

@app.route('/api/video')
def get_video():
    """API endpoint to download Instagram video"""
    url = request.args.get('url', '').strip()
    
    if not url:
        return jsonify({"success": False, "error": "URL parameter required"}), 400
    
    if 'instagram.com' not in url:
        return jsonify({"success": False, "error": "Invalid Instagram URL"}), 400
    
    # Check cache
    cache_key = f"video_{hash(url)}"
    if cache_key in video_cache:
        cached = video_cache[cache_key]
        if time.time() - cached['timestamp'] < CACHE_DURATION:
            return jsonify(cached['data'])
    
    try:
        # Extract video using browser automation
        print(f"\n🔍 Processing: {url}")
        result = run_async(scraper.get_video(url))
        
        if result and result.get('success'):
            # Prepare response
            video_id = str(uuid.uuid4())[:12]
            video_url = result['video_url']
            
            response_data = {
                "success": True,
                "video_id": video_id,
                "video_url": video_url,
                "qualities": [{
                    "quality": "HD",
                    "url": video_url,
                    "resolution": "1080p",
                    "type": "video/mp4"
                }],
                "title": result.get('title', 'Instagram Reel'),
                "thumbnail": result.get('thumbnail', ''),
                "method": result.get('method', 'browser'),
                "warning": "Downloaded via automated browser. Respect copyright."
            }
            
            # Cache the result
            video_cache[cache_key] = {
                'data': response_data,
                'timestamp': time.time()
            }
            
            return jsonify(response_data)
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Failed to extract video'),
                "tip": "Try a different reel or wait a few minutes"
            }), 500
            
    except Exception as e:
        print(f"❌ API Error: {e}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)[:100]}",
            "tip": "The scraper might need restarting"
        }), 500

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "cache_size": len(video_cache),
        "method": "browser_automation"
    })

# Cleanup on server shutdown
import atexit
@atexit.register
def cleanup():
    print("🛑 Closing browser...")
    run_async(scraper.close())

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🆓 FREE INSTAGRAM VIDEO SCRAPER")
    print("=" * 60)
    print("Method: Undetected Playwright Browser")
    print("Warning: Against Instagram ToS. Use for personal purposes only.")
    print(f"Port: {PORT}")
    print("=" * 60)
    
    # Test the scraper on startup
    print("🧪 Testing scraper with a sample URL...")
    try:
        # Use a known working reel for testing
        test_url = "https://www.instagram.com/reel/Cz7KmCJA8Nx/"
        test_result = run_async(scraper.get_video(test_url))
        if test_result and test_result.get('success'):
            print(f"✅ Scraper test PASSED")
        else:
            print(f"⚠️ Scraper test may have issues: {test_result.get('error', 'Unknown')}")
    except Exception as e:
        print(f"⚠️ Scraper test error: {e}")
    
    print("=" * 60)
    app.run(host='0.0.0.0', port=PORT, debug=False)
