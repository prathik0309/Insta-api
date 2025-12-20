# app.py - SIMPLE WORKING INSTAGRAM API
import os
import json
import uuid
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.environ.get("PORT", 10000))
CACHE_DURATION = 3600  # 1 hour

# Store videos
video_cache = {}

class SimpleInstagramAPI:
    """Simple API using public Instagram downloaders"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
    
    def extract_shortcode(self, url):
        """Extract shortcode from URL"""
        patterns = [
            r'instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]{11})',
            r'instagram\.com/(?:reels?)/([A-Za-z0-9_-]+)',
            r'/([A-Za-z0-9_-]{11})/?$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def method_savefrom(self, url):
        """METHOD 1: SaveFrom.net API (Most reliable)"""
        try:
            api_url = "https://api.savefrom.net/api/convert"
            
            params = {
                'url': url,
                'format': 'mp4'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://savefrom.net',
                'Referer': 'https://savefrom.net/',
            }
            
            response = self.session.get(api_url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # SaveFrom returns different structures
                video_url = None
                
                if 'url' in data:
                    video_url = data['url']
                elif 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                    video_url = data['data'][0].get('url')
                elif 'links' in data and isinstance(data['links'], list) and len(data['links']) > 0:
                    video_url = data['links'][0].get('url')
                
                if video_url:
                    return {
                        "success": True,
                        "video_url": video_url,
                        "method": "savefrom",
                        "quality": "HD"
                    }
            
            return None
            
        except Exception as e:
            print(f"SaveFrom error: {e}")
            return None
    
    def method_sssinstagram(self, url):
        """METHOD 2: SSSInstagram API"""
        try:
            api_url = "https://sssinstagram.com/ajaxSearch"
            
            data = {
                'q': url,
                't': 'media',
                'lang': 'en'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://sssinstagram.com',
                'Referer': 'https://sssinstagram.com/',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(api_url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' and 'data' in data:
                    video_data = data['data']
                    video_url = None
                    
                    if 'medias' in video_data and video_data['medias']:
                        video_url = video_data['medias'][0].get('url')
                    elif 'url' in video_data:
                        video_url = video_data['url']
                    
                    if video_url:
                        return {
                            "success": True,
                            "video_url": video_url,
                            "method": "sssinstagram",
                            "quality": "720p"
                        }
            
            return None
            
        except Exception as e:
            print(f"SSSInstagram error: {e}")
            return None
    
    def method_igram(self, url):
        """METHOD 3: iGram.world API"""
        try:
            api_url = "https://igram.world/api/instagram"
            
            data = {
                'url': url,
                'lang_code': 'en'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://igram.world',
                'Referer': 'https://igram.world/'
            }
            
            response = self.session.post(api_url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' and 'url' in data:
                    return {
                        "success": True,
                        "video_url": data['url'],
                        "method": "igram",
                        "quality": "1080p"
                    }
            
            return None
            
        except Exception as e:
            print(f"iGram error: {e}")
            return None
    
    def extract_video(self, url):
        """Main extraction function"""
        print(f"\n🔍 Processing: {url}")
        
        # Extract shortcode
        shortcode = self.extract_shortcode(url)
        if not shortcode:
            return {"success": False, "error": "Invalid Instagram URL"}
        
        print(f"📝 Shortcode: {shortcode}")
        
        # Try all methods
        methods = [
            ("1. SaveFrom.net", lambda: self.method_savefrom(url)),
            ("2. SSSInstagram", lambda: self.method_sssinstagram(url)),
            ("3. iGram.world", lambda: self.method_igram(url)),
        ]
        
        for method_name, method_func in methods:
            print(f"  Trying {method_name}...")
            
            try:
                result = method_func()
                
                if result and result.get("success"):
                    print(f"  ✅ Success with {method_name}")
                    
                    # Get thumbnail
                    thumbnail = f"https://instagram.fdel25-1.fna.fbcdn.net/v/t51.2885-15/{shortcode}_n.jpg"
                    
                    return {
                        "success": True,
                        "video_url": result["video_url"],
                        "thumbnail": thumbnail,
                        "title": "Instagram Reel",
                        "quality": result.get("quality", "HD"),
                        "method": result["method"]
                    }
                    
            except Exception as e:
                print(f"  ⚠️ {method_name} failed: {str(e)[:50]}")
                continue
            
            time.sleep(1)  # Delay between methods
        
        print("  ❌ All methods failed")
        return {
            "success": False,
            "error": "All download methods failed. The services may be temporarily down.",
            "tip": "Try again in a few minutes or use a different reel"
        }

# Initialize API
instagram_api = SimpleInstagramAPI()

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Video API",
        "version": "11.0",
        "methods": "3 public APIs with fallback",
        "endpoints": {
            "/api/video?url=URL": "Get video",
            "/api/player/VIDEO_ID": "Get cached video",
            "/api/health": "Health check"
        },
        "cache_size": len(video_cache)
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "cache_size": len(video_cache)
    })

@app.route('/api/video')
def get_video():
    """Main API endpoint"""
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
    
    # Extract video
    result = instagram_api.extract_video(url)
    
    if result['success']:
        # Generate video ID
        video_id = str(uuid.uuid4())[:12]
        
        # Create quality options
        video_url = result['video_url']
        qualities = []
        
        qualities.append({
            "quality": "HD",
            "url": video_url,
            "resolution": "1080p",
            "size": "10-20 MB",
            "type": "video/mp4"
        })
        
        qualities.append({
            "quality": "SD",
            "url": video_url,
            "resolution": "720p",
            "size": "5-10 MB",
            "type": "video/mp4"
        })
        
        # Prepare response
        response_data = {
            "success": True,
            "video_id": video_id,
            "video_url": video_url,
            "qualities": qualities,
            "title": result.get('title', 'Instagram Reel'),
            "thumbnail": result.get('thumbnail', ''),
            "method": result.get('method', 'public_api')
        }
        
        # Cache the result
        video_cache[cache_key] = {
            'data': response_data,
            'timestamp': time.time()
        }
        
        video_cache[video_id] = {
            'data': response_data,
            'timestamp': time.time()
        }
        
        return jsonify(response_data)
    
    return jsonify(result), 404

@app.route('/api/player/<video_id>')
def get_player_data(video_id):
    """Get video data for player"""
    if video_id in video_cache:
        data = video_cache[video_id]
        
        # Check expiry
        if time.time() - data['timestamp'] > CACHE_DURATION:
            del video_cache[video_id]
            return jsonify({"success": False, "error": "Video expired"}), 410
        
        return jsonify(data['data'])
    
    return jsonify({"success": False, "error": "Video not found"}), 404

# ==================== START SERVER ====================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 SIMPLE INSTAGRAM API")
    print("=" * 60)
    print("Using public downloader APIs")
    print(f"Port: {PORT}")
    print("Methods: SaveFrom, SSSInstagram, iGram")
    print("=" * 60)
    print("Endpoints:")
    print("  GET /api/video?url=INSTAGRAM_URL")
    print("  GET /api/player/VIDEO_ID")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
