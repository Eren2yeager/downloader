from flask import Flask, render_template, request, jsonify, send_file, Response
import yt_dlp
import os
import platform
import tempfile
import random
import re
import requests
import time
import json
import hashlib
from datetime import datetime, timedelta
from http.cookiejar import MozillaCookieJar
from urllib.parse import parse_qs, urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import shutil
from fake_useragent import UserAgent
import string
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/app.log', maxBytes=1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure download folder
if os.environ.get('FLASK_ENV') == 'production':
    DOWNLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'yt_downloads')
else:
    DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yt_downloads')

# Ensure download folder exists
try:
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
except Exception as e:
    logger.error(f"Error creating download folder: {e}")
    DOWNLOAD_FOLDER = tempfile.mkdtemp()
    logger.info(f"Using temporary download folder: {DOWNLOAD_FOLDER}")

# YouTube API constants
INNERTUBE_API_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
INNERTUBE_CLIENT_VERSION = '2.20240321.04.00'

def create_session():
    """Create a requests session with retry logic and proper headers"""
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def generate_visitor_data():
    """Generate visitor data for YouTube"""
    timestamp = int(time.time())
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    return {
        'visitorId': random_string,
        'timestamp': timestamp,
        'clientName': 'WEB',
        'clientVersion': '2.20240321.04.00',
        'osName': 'Windows',
        'osVersion': '10.0',
        'platform': 'DESKTOP',
        'browserName': 'Chrome',
        'browserVersion': '120.0.0.0',
    }

def get_browser_like_headers(visitor_data):
    """Generate browser-like headers with visitor data"""
    ua = UserAgent()
    headers = {
        'User-Agent': ua.chrome,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'X-YouTube-Client-Name': visitor_data['clientName'],
        'X-YouTube-Client-Version': visitor_data['clientVersion'],
        'X-YouTube-Visitor-Id': visitor_data['visitorId'],
    }
    return headers

def get_video_info(url):
    """Get video information with improved session handling"""
    try:
        # Create new session and visitor data
        session = create_session()
        visitor_data = generate_visitor_data()
        
        # Extract video ID
        video_id = None
        if 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]
        else:
            parsed_url = urlparse(url)
            video_id = parse_qs(parsed_url.query).get('v', [None])[0]
            if not video_id:
                video_id = parsed_url.path.split('/')[-1].split('?')[0]

        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")
            raise Exception("Could not extract video ID")

        logger.info(f"Extracted video ID: {video_id}")

        # Configure yt-dlp options with session handling
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'nocheckcertificate': True,
            'http_headers': get_browser_like_headers(visitor_data),
            'cookiesfrombrowser': ('chrome',),
            'extractor_args': {
                'youtube': {
                    'player_skip': ['js', 'configs', 'webpage'],
                    'player_client': ['web'],
                    'player_skip': ['webpage']
                }
            },
            'rate_limit': 1000000,  # 1MB/s
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'extract_flat': 'in_playlist',
            'playlist_items': '1',
            'match_filter': None,
            'geo_bypass': True,
            'geo_verification_proxy': None,
            'min_sleep_interval': 1,
            'max_sleep_interval': 5,
        }

        # Add rate limiting
        time.sleep(random.uniform(1, 3))

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    except Exception as e:
        logger.error(f"Error in get_video_info: {str(e)}")
        raise

def clean_filename(filename):
    """Clean the filename to remove invalid characters"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def cleanup_old_files():
    """Clean up files older than 1 hour"""
    try:
        now = datetime.now()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if (now - file_time).total_seconds() > 3600:  # 1 hour
                    try:
                        os.remove(filepath)
                        logger.info(f"Cleaned up old file: {filename}")
                    except Exception as e:
                        logger.error(f"Error removing file {filename}: {str(e)}")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

@app.before_request
def before_request():
    # Add security headers
    if request.is_secure:
        return

@app.after_request
def after_request(response):
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        # Clean up old files before processing new download
        cleanup_old_files()

        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Please enter a YouTube URL'}), 400
            
        audio_only = request.form.get('audio_only', 'false').lower() == 'true'

        # Validate URL format - more lenient pattern
        youtube_pattern = r'^(https?://)?(www\.)?(youtube\.com/(watch\?v=|embed/|v/|shorts/)|youtu\.be/)[a-zA-Z0-9_-]{11}.*$'
        if not re.match(youtube_pattern, url):
            return jsonify({'error': 'Invalid YouTube URL format. Please enter a valid YouTube URL.'}), 400

        # Create new session and visitor data
        session = create_session()
        visitor_data = generate_visitor_data()

        # Configure yt-dlp options with session handling
        output_template = os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
        
        ydl_opts = {
            'format': 'bestaudio/best' if audio_only else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True,
            'http_headers': get_browser_like_headers(visitor_data),
            'cookiesfrombrowser': ('chrome',),
            'extractor_args': {
                'youtube': {
                    'player_skip': ['js', 'configs', 'webpage'],
                    'player_client': ['web'],
                    'player_skip': ['webpage']
                }
            },
            'rate_limit': 1000000,  # 1MB/s
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'extract_flat': 'in_playlist',
            'playlist_items': '1',
            'match_filter': None,
            'geo_bypass': True,
            'geo_verification_proxy': None,
            'min_sleep_interval': 1,
            'max_sleep_interval': 5,
        }
        
        if audio_only:
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            })

        # Add rate limiting
        time.sleep(random.uniform(1, 3))

        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url)
            if not info:
                return jsonify({'error': 'Download failed. Please try again.'}), 400
                
            # Get output file path
            if audio_only:
                output_file = output_template % {'title': clean_filename(info['title']), 'ext': 'mp3'}
            else:
                output_file = output_template % {'title': clean_filename(info['title']), 'ext': 'mp4'}
            
            if not os.path.exists(output_file):
                return jsonify({'error': 'Download failed - output file not found'}), 400
                
            # Verify file size
            file_size = os.path.getsize(output_file)
            if file_size == 0:
                os.remove(output_file)
                return jsonify({'error': 'Download failed - empty file'}), 400
                
            # Send file
            return send_file(
                output_file,
                as_attachment=True,
                download_name=os.path.basename(output_file),
                mimetype='audio/mpeg' if audio_only else 'video/mp4'
            )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)         