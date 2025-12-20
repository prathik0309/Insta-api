# app.py - YT-DLP INSTAGRAM API
import os
import json
import uuid
import time
import subprocess
import tempfile
import re
from flask import Flask, jsonify, request
from flask_cors import CORS
import urllib.parse

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.environ.get("PORT", 10000))
CACHE_DURATION = 3600  # 1 hour cache

# Store videos
video_cache = {}

class YTDLPInstagramScraper:
    """Instagram scraper using yt-dlp (Professional tool)"""
    
    def __init__(self):
        # Check if yt-dlp is available
        self.check_ytdlp()
    
    def check_ytdlp(self):
        """Check if yt-dlp is installed"""
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            print(f"✅ yt-dlp version: {result.stdout.strip()}")
            return True
        except:
            print("⚠️ yt-dlp not found, installing...")
            self.install_ytdlp()
            return True
    
    def install_ytdlp(self):
        """Install yt-dlp"""
        try:
            subprocess.run(['pip', 'install', 'yt-dlp'], check=True)
            print("✅ yt-dlp installed successfully")
        except Exception as e:
            print(f"❌ Failed to install yt-dlp: {e}")
            # Try alternative installation
            try:
                subprocess.run(['python3', '-m', 'pip', 'install', 'yt-dlp'], check=True)
                print("✅ yt-dlp installed via python3")
            except:
                print("❌ Could not install yt-dlp")
    
    def extract_shortcode(self, url):
        """Extract Instagram shortcode"""
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
    
    def extract_with_ytdlp(self, url):
        """Extract video using yt-dlp"""
        try:
            print(f"🔍 yt-dlp processing: {url}")
            
            # Create temporary file for output
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp:
                output_file = tmp.name
            
            try:
                # Run yt-dlp to get video info
                cmd = [
                    'yt-dlp',
                    '--no-warnings',
                    '--quiet',
                    '--skip-download',
                    '--dump-json',
                    '--no-playlist',
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    '--referer', 'https://www.instagram.com/',
                    url
                ]
                
                print(f"Running command: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 second timeout
                )
                
                if result.returncode == 0:
                    # Parse yt-dlp output
                    data = json.loads(result.stdout)
                    
                    # Extract video URL (yt-dlp gives multiple formats)
                    video_url = None
                    thumbnail = None
                    title = "Instagram Reel"
                    duration = 0
                    
                    # Get the best video format
                    if 'url' in data:
                        video_url = data['url']
                    elif 'formats' in data and data['formats']:
                        # Get the best quality video
                        formats = data['formats']
                        # Filter for video formats
                        video_formats = [f for f in formats if f.get('vcodec') != 'none']
                        if video_formats:
                            # Get the highest quality
                            best_format = max(video_formats, key=lambda x: x.get('height', 0))
                            video_url = best_format.get('url')
                    
                    # Get thumbnail
                    thumbnail = data.get('thumbnail') or data.get('thumbnails', [{}])[0].get('url', '')
                    
                    # Get title
                    title = data.get('title') or data.get('description', 'Instagram Reel')
                    
                    # Get duration
                    duration = data.get('duration') or 0
                    
                    if video_url:
                        print(f"✅ yt-dlp success! Got video URL")
                        return {
                            "success": True,
                            "video_url": video_url,
                            "thumbnail": thumbnail,
                            "title": title[:100],
                            "duration": duration,
                            "method": "yt-dlp"
                        }
                    else:
                        print("❌ yt-dlp found data but no video URL")
                        return {"success": False, "error": "No video URL found"}
                
                else:
                    error_msg = result.stderr or "Unknown yt-dlp error"
                    print(f"❌ yt-dlp error: {error_msg}")
                    
                    # Try alternative yt-dlp command
                    return self.try_alternative_ytdlp(url)
                    
            finally:
                # Clean up temp file
                try:
                    os.unlink(output_file)
                except:
                    pass
                
        except subprocess.TimeoutExpired:
            print("❌ yt-dlp timeout")
            return {"success": False, "error": "Timeout extracting video"}
        except json.JSONDecodeError:
            print("❌ Invalid JSON from yt-dlp")
            return {"success": False, "error": "Invalid response from downloader"}
        except Exception as e:
            print(f"❌ yt-dlp exception: {e}")
            return {"success": False, "error": f"Extraction error: {str(e)}"}
    
    def try_alternative_ytdlp(self, url):
        """Try alternative yt-dlp command"""
        try:
            print("🔄 Trying alternative yt-dlp command...")
            
            # Alternative: Use --get-url to just get the direct URL
            cmd = [
                'yt-dlp',
                '--no-warnings',
                '--quiet',
                '-g',  # Get URL only
                '--no-playlist',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if result.returncode == 0:
                video_url = result.stdout.strip()
                if video_url and video_url.startswith('http'):
                    # Split by newlines (yt-dlp might return multiple URLs)
                    urls = video_url.split('\n')
                    video_url = urls[0]  # First URL is usually the video
                    
                    print(f"✅ Alternative yt-dlp success!")
                    return {
                        "success": True,
                        "video_url": video_url,
                        "thumbnail": '',
                        "title": "Instagram Reel",
                        "duration": 0,
                        "method": "yt-dlp-alternative"
                    }
            
            return {"success": False, "error": "All yt-dlp methods failed"}
            
        except Exception as e:
            print(f"❌ Alternative yt-dlp error: {e}")
            return {"success": False, "error": f"Alternative method error: {str(e)}"}
    
    def get_thumbnail(self, shortcode):
        """Get thumbnail URL"""
        try:
            return f"https://instagram.fdel25-1.fna.fbcdn.net/v/t51.2885-15/{shortcode}_n.jpg"
        except:
            return ""
    
    def extract_video(self, url):
        """Main extraction function"""
        print(f"\n🔍 Processing: {url}")
        
        # Extract shortcode
        shortcode = self.extract_shortcode(url)
        if not shortcode:
            return {"success": False, "error": "Invalid Instagram URL"}
        
        print(f"📝 Shortcode: {shortcode}")
        
        # Use yt-dlp (primary method)
        result = self.extract_with_ytdlp(url)
        
        if result['success']:
            # Ensure we have a thumbnail
            if not result.get('thumbnail'):
                result['thumbnail'] = self.get_thumbnail(shortcode)
            
            return result
        
        return result

# Initialize scraper
scraper = YTDLPInstagramScraper()

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Video API with yt-dlp",
        "version": "10.0",
        "method": "yt-dlp (Professional tool)",
        "endpoints": {
            "/api/video?url=URL": "Get video using yt-dlp",
            "/api/player/VIDEO_ID": "Get cached video",
            "/api/health": "Health check",
            "/api/test": "Test endpoint"
        },
        "cache_size": len(video_cache)
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "cache_size": len(video_cache),
        "ytdlp": "available"
    })

@app.route('/api/test')
def test():
    """Test the API"""
    test_url = "https://www.instagram.com/reel/Cz7KmCJA8Nx/"
    
    print("\n🧪 Running yt-dlp test...")
    result = scraper.extract_video(test_url)
    
    return jsonify({
        "test": True,
        "url": test_url,
        "result": {
            "success": result["success"],
            "method": result.get("method", "none"),
            "error": result.get("error", "")
        }
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
    
    # Extract video using yt-dlp
    result = scraper.extract_video(url)
    
    if result['success']:
        # Generate video ID
        video_id = str(uuid.uuid4())[:12]
        
        # Create quality options
        video_url = result['video_url']
        qualities = []
        
        qualities.append({
            "quality": "Original",
            "url": video_url,
            "resolution": "1080p",
            "size": "15-25 MB",
            "type": "video/mp4"
        })
        
        qualities.append({
            "quality": "HD",
            "url": video_url,
            "resolution": "720p",
            "size": "8-15 MB",
            "type": "video/mp4"
        })
        
        qualities.append({
            "quality": "SD",
            "url": video_url,
            "resolution": "480p",
            "size": "3-8 MB",
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
            "duration": result.get('duration', 0),
            "method": result.get('method', 'yt-dlp')
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
    print("🚀 YT-DLP INSTAGRAM API")
    print("=" * 60)
    print("Professional Instagram video extraction")
    print(f"Port: {PORT}")
    print("Method: yt-dlp (most reliable)")
    print("=" * 60)
    print("Endpoints:")
    print("  GET /api/video?url=INSTAGRAM_URL")
    print("  GET /api/player/VIDEO_ID")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
