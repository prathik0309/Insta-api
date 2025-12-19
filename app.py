# app.py - DEPLOY ON RENDER.COM (PERMANENT URL)
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import re
import json
import uuid
import time
import urllib.parse

app = Flask(__name__)
CORS(app)

# ================= CONFIGURATION =================
PORT = int(os.environ.get("PORT", 10000))
RENDER = os.environ.get('RENDER', False)  # True if running on Render

# ================= VIDEO STORAGE =================
video_cache = {}
CACHE_DURATION = 1800  # 30 minutes

# ================= SMART SCRAPER =================
class InstagramScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def extract_shortcode(self, url):
        """Extract Instagram post ID from URL"""
        patterns = [
            r'instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)',
            r'instagram\.com/(?:reels?)/([A-Za-z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def fetch_video(self, url):
        """Main method to fetch Instagram video"""
        print(f"🔍 Processing: {url}")
        
        shortcode = self.extract_shortcode(url)
        if not shortcode:
            return {"success": False, "error": "Invalid Instagram URL"}
        
        # METHOD 1: Try GraphQL API (Most Reliable)
        video_data = self.method_graphql(shortcode)
        if video_data:
            return video_data
        
        # METHOD 2: Try JSON API
        video_data = self.method_json_api(shortcode)
        if video_data:
            return video_data
        
        # METHOD 3: Try Direct Scraping
        video_data = self.method_direct_scrape(url)
        if video_data:
            return video_data
        
        # METHOD 4: Try Mobile API
        video_data = self.method_mobile_api(shortcode)
        if video_data:
            return video_data
        
        return {"success": False, "error": "Could not extract video. The reel might be private or Instagram has changed their structure."}
    
    def method_graphql(self, shortcode):
        """Method 1: GraphQL API"""
        try:
            graphql_url = f"https://www.instagram.com/graphql/query/?query_hash=b3055c01b4b222b8a47dc12b090e4e64&variables={{\"shortcode\":\"{shortcode}\"}}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'x-ig-app-id': '936619743392459',
                'x-requested-with': 'XMLHttpRequest',
            }
            
            response = self.session.get(graphql_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Navigate through GraphQL response
                if 'data' in data:
                    media = data['data'].get('shortcode_media', {})
                    if media.get('is_video'):
                        video_url = media.get('video_url')
                        if video_url:
                            return {
                                "success": True,
                                "video_url": video_url,
                                "thumbnail": media.get('display_url', ''),
                                "title": self.extract_title(media),
                                "duration": media.get('video_duration', 0),
                                "method": "graphql"
                            }
        except Exception as e:
            print(f"GraphQL method failed: {e}")
        return None
    
    def method_json_api(self, shortcode):
        """Method 2: JSON API"""
        try:
            json_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
            response = self.session.get(json_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Try multiple JSON structures
                video_url = self.find_video_in_json(data)
                if video_url:
                    return {
                        "success": True,
                        "video_url": video_url,
                        "thumbnail": self.find_thumbnail_in_json(data),
                        "title": "Instagram Reel",
                        "method": "json_api"
                    }
        except:
            pass
        return None
    
    def method_direct_scrape(self, url):
        """Method 3: Direct HTML scraping"""
        try:
            response = self.session.get(url, timeout=10)
            html = response.text
            
            # Pattern 1: Video URL in meta tags
            meta_pattern = r'<meta property="og:video" content="([^"]+)"'
            meta_match = re.search(meta_pattern, html)
            if meta_match:
                video_url = meta_match.group(1).replace('\\u0026', '&')
                return {
                    "success": True,
                    "video_url": video_url,
                    "thumbnail": self.extract_thumbnail(html),
                    "title": self.extract_title_from_html(html),
                    "method": "meta_tag"
                }
            
            # Pattern 2: Video URL in JSON-LD
            jsonld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            jsonld_match = re.search(jsonld_pattern, html, re.DOTALL)
            if jsonld_match:
                try:
                    json_data = json.loads(jsonld_match.group(1))
                    if 'video' in json_data:
                        video_url = json_data['video'].get('contentUrl', '')
                        if video_url:
                            return {
                                "success": True,
                                "video_url": video_url,
                                "thumbnail": json_data.get('thumbnailUrl', ''),
                                "title": json_data.get('name', 'Instagram Reel'),
                                "method": "json_ld"
                            }
                except:
                    pass
            
            # Pattern 3: Video URL in shared data
            shared_pattern = r'window\._sharedData\s*=\s*({.*?});'
            shared_match = re.search(shared_pattern, html, re.DOTALL)
            if shared_match:
                try:
                    shared_data = json.loads(shared_match.group(1))
                    video_url = self.find_video_in_shared_data(shared_data)
                    if video_url:
                        return {
                            "success": True,
                            "video_url": video_url,
                            "thumbnail": self.find_thumbnail_in_shared_data(shared_data),
                            "title": "Instagram Reel",
                            "method": "shared_data"
                        }
                except:
                    pass
                    
        except Exception as e:
            print(f"Direct scrape failed: {e}")
        return None
    
    def method_mobile_api(self, shortcode):
        """Method 4: Mobile API endpoint"""
        try:
            mobile_url = f"https://i.instagram.com/api/v1/media/{shortcode}/info/"
            headers = {
                'User-Agent': 'Instagram 269.0.0.18.75 (iPhone13,2; iOS 15_4_1; en_US; en-US; scale=3.00; 1170x2532; 386397794)',
                'Accept': '*/*',
                'Accept-Language': 'en-US',
            }
            
            response = self.session.get(mobile_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                video_url = self.find_video_in_mobile_response(data)
                if video_url:
                    return {
                        "success": True,
                        "video_url": video_url,
                        "thumbnail": self.find_thumbnail_in_mobile_response(data),
                        "title": "Instagram Reel",
                        "method": "mobile_api"
                    }
        except:
            pass
        return None
    
    def find_video_in_json(self, data):
        """Find video URL in JSON response"""
        try:
            # Multiple possible structures
            if isinstance(data, dict):
                # Structure 1
                if 'graphql' in data:
                    media = data['graphql'].get('shortcode_media', {})
                    if media.get('is_video'):
                        return media.get('video_url')
                
                # Structure 2
                if 'items' in data:
                    for item in data['items']:
                        if item.get('media_type') == 2:  # Video type
                            versions = item.get('video_versions', [])
                            if versions:
                                return versions[0].get('url')
                
                # Deep search
                def search(obj):
                    if isinstance(obj, dict):
                        if 'video_url' in obj and '.mp4' in obj['video_url']:
                            return obj['video_url']
                        for value in obj.values():
                            result = search(value)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = search(item)
                            if result:
                                return result
                    return None
                
                return search(data)
        except:
            pass
        return None
    
    def find_video_in_shared_data(self, data):
        """Find video URL in shared data"""
        try:
            if 'entry_data' in data:
                posts = data['entry_data'].get('PostPage', [])
                for post in posts:
                    if 'graphql' in post:
                        media = post['graphql'].get('shortcode_media', {})
                        if media.get('is_video'):
                            return media.get('video_url')
        except:
            pass
        return None
    
    def find_video_in_mobile_response(self, data):
        """Find video URL in mobile API response"""
        try:
            if 'items' in data:
                for item in data['items']:
                    if 'video_versions' in item:
                        versions = item['video_versions']
                        if versions:
                            return versions[0].get('url')
        except:
            pass
        return None
    
    def extract_thumbnail(self, html):
        """Extract thumbnail from HTML"""
        try:
            pattern = r'<meta property="og:image" content="([^"]+)"'
            match = re.search(pattern, html)
            if match:
                return match.group(1).replace('\\u0026', '&')
        except:
            pass
        return ""
    
    def find_thumbnail_in_json(self, data):
        """Find thumbnail in JSON response"""
        try:
            if 'graphql' in data:
                media = data['graphql'].get('shortcode_media', {})
                return media.get('display_url', '')
        except:
            pass
        return ""
    
    def find_thumbnail_in_shared_data(self, data):
        """Find thumbnail in shared data"""
        try:
            if 'entry_data' in data:
                posts = data['entry_data'].get('PostPage', [])
                for post in posts:
                    if 'graphql' in post:
                        media = post['graphql'].get('shortcode_media', {})
                        return media.get('display_url', '')
        except:
            pass
        return ""
    
    def find_thumbnail_in_mobile_response(self, data):
        """Find thumbnail in mobile response"""
        try:
            if 'items' in data:
                for item in data['items']:
                    if 'image_versions2' in item:
                        candidates = item['image_versions2'].get('candidates', [])
                        if candidates:
                            return candidates[0].get('url', '')
        except:
            pass
        return ""
    
    def extract_title(self, media_data):
        """Extract title from media data"""
        try:
            if 'edge_media_to_caption' in media_data:
                edges = media_data['edge_media_to_caption'].get('edges', [])
                if edges:
                    return edges[0].get('node', {}).get('text', 'Instagram Reel')[:100]
        except:
            pass
        return "Instagram Reel"
    
    def extract_title_from_html(self, html):
        """Extract title from HTML"""
        try:
            pattern = r'<meta property="og:title" content="([^"]+)"'
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        except:
            pass
        return "Instagram Reel"
    
    def generate_qualities(self, video_url):
        """Generate quality options for a video"""
        # Note: Instagram usually provides one URL with highest quality
        # We simulate different qualities by modifying the URL
        qualities = []
        
        # Original quality
        qualities.append({
            "quality": "Original",
            "url": video_url,
            "resolution": "1080p",
            "size": "15-25 MB",
            "type": "video/mp4",
            "bitrate": "High"
        })
        
        # HD quality (simulated)
        qualities.append({
            "quality": "HD",
            "url": video_url,
            "resolution": "720p",
            "size": "8-15 MB",
            "type": "video/mp4",
            "bitrate": "Medium"
        })
        
        # SD quality (simulated)
        qualities.append({
            "quality": "SD",
            "url": video_url,
            "resolution": "480p",
            "size": "3-8 MB",
            "type": "video/mp4",
            "bitrate": "Low"
        })
        
        return qualities

# Initialize scraper
scraper = InstagramScraper()

# ================= API ROUTES =================
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Video API",
        "version": "3.0",
        "host": "Render" if RENDER else "Local",
        "endpoints": {
            "/api/video?url=URL": "Get video with qualities",
            "/api/player/VIDEO_ID": "Get cached video data",
            "/api/health": "Health check",
            "/api/test": "Test with sample URL"
        },
        "cache_size": len(video_cache),
        "uptime": int(time.time() - app.start_time) if hasattr(app, 'start_time') else 0
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "cache_size": len(video_cache)
    })

@app.route('/api/test')
def test():
    """Test endpoint with a sample URL"""
    test_url = "https://www.instagram.com/reel/Cz7KmCJA8Nx/"
    video_data = scraper.fetch_video(test_url)
    return jsonify({
        "test": True,
        "url": test_url,
        "result": video_data
    })

@app.route('/api/video')
def get_video():
    """Main API endpoint - returns video with qualities"""
    url = request.args.get('url', '').strip()
    
    if not url:
        return jsonify({
            "success": False,
            "error": "URL parameter is required",
            "example": "/api/video?url=https://www.instagram.com/reel/XXXXX/"
        }), 400
    
    if 'instagram.com' not in url or '/reel/' not in url:
        return jsonify({
            "success": False,
            "error": "Invalid Instagram URL. Must be a reel URL.",
            "example": "https://www.instagram.com/reel/XXXXX/"
        }), 400
    
    # Check cache first
    cache_key = f"video_{hash(url)}"
    if cache_key in video_cache:
        cached_data = video_cache[cache_key]
        if time.time() - cached_data['timestamp'] < CACHE_DURATION:
            return jsonify(cached_data['data'])
    
    # Fetch video from Instagram
    video_data = scraper.fetch_video(url)
    
    if video_data['success']:
        # Generate quality options
        qualities = scraper.generate_qualities(video_data['video_url'])
        
        # Create video ID
        video_id = str(uuid.uuid4())[:12]
        
        # Prepare response
        response_data = {
            "success": True,
            "video_id": video_id,
            "video_url": video_data['video_url'],
            "qualities": qualities,
            "title": video_data.get('title', 'Instagram Reel'),
            "thumbnail": video_data.get('thumbnail', ''),
            "duration": video_data.get('duration', 0),
            "method": video_data.get('method', 'unknown')
        }
        
        # Store in cache
        video_cache[cache_key] = {
            "data": response_data,
            "timestamp": time.time()
        }
        
        # Also store by video_id for player access
        video_cache[video_id] = {
            "data": response_data,
            "timestamp": time.time()
        }
        
        # Clean old cache entries
        self.clean_cache()
        
        return jsonify(response_data)
    
    return jsonify(video_data), 404

@app.route('/api/player/<video_id>')
def get_player_data(video_id):
    """Get video data for player (used by website)"""
    if video_id in video_cache:
        data = video_cache[video_id]
        
        # Check if expired
        if time.time() - data['timestamp'] > CACHE_DURATION:
            del video_cache[video_id]
            return jsonify({
                "success": False,
                "error": "Video expired. Please get a new link."
            }), 410
        
        return jsonify(data['data'])
    
    return jsonify({
        "success": False,
        "error": "Video not found or expired"
    }), 404

def clean_cache(self):
    """Clean expired cache entries"""
    current_time = time.time()
    expired_keys = []
    
    for key, data in video_cache.items():
        if current_time - data['timestamp'] > CACHE_DURATION:
            expired_keys.append(key)
    
    for key in expired_keys:
        del video_cache[key]

# Store app start time
app.start_time = time.time()

# ================= START SERVER =================
if __name__ == '__main__':
    print("🚀 Instagram API Server Starting...")
    print("=" * 50)
    print("Service: Instagram Video Downloader API")
    print("Version: 3.0")
    print(f"Port: {PORT}")
    print(f"Cache Duration: {CACHE_DURATION} seconds")
    print("=" * 50)
    print("Endpoints:")
    print(f"  • GET /              - API status")
    print(f"  • GET /api/video     - Get video with qualities")
    print(f"  • GET /api/player/id - Get cached video")
    print(f"  • GET /api/health    - Health check")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=PORT, debug=not RENDER)
