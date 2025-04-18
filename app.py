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

app = Flask(__name__)

# Configure download folder
if os.environ.get('FLASK_ENV') == 'production':
    DOWNLOAD_FOLDER = '/tmp/downloads'
else:
    if platform.system() == 'Windows':
        DOWNLOAD_FOLDER = os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads')
    else:
        DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')

# Ensure download folder exists
try:
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
except Exception as e:
    print(f"Error creating download folder: {e}")
    DOWNLOAD_FOLDER = tempfile.mkdtemp()
    print(f"Using temporary download folder: {DOWNLOAD_FOLDER}")

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
            print(f"Could not extract video ID from URL: {url}")
            raise Exception("Could not extract video ID")

        print(f"Extracted video ID: {video_id}")

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
        print(f"Error in get_video_info: {str(e)}")
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            url = request.form.get('url', '').strip()
            if not url:
                return jsonify({'error': 'Please enter a YouTube URL'}), 400
                
            quality = request.form.get('quality', 'audio')
            audio_only = quality == 'audio'

            # Validate URL format
            if not re.match(r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+', url):
                return jsonify({'error': 'Invalid YouTube URL format'}), 400

            # Get video info first
            try:
                info = get_video_info(url)
                if not info:
                    return jsonify({'error': 'Could not get video information. Please try a different video.'}), 400
            except Exception as e:
                print(f"Error getting video info: {str(e)}")
                return jsonify({'error': 'Failed to get video information. Please try again.'}), 400

            # Configure yt-dlp options
            output_template = os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
            
            ydl_opts = {
                'format': 'bestaudio/best' if audio_only else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': True,
                'progress_hooks': [lambda d: print(f"Download progress: {d.get('_percent_str', 'unknown')}")]
            }
            
            if audio_only:
                ydl_opts.update({
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                })

            # Download video
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url)
                    if not info:
                        return jsonify({'error': 'Download failed. Please try again.'}), 400
                        
                    # Get output file path
                    if audio_only:
                        output_file = output_template % {'title': info['title'], 'ext': 'mp3'}
                    else:
                        output_file = output_template % {'title': info['title'], 'ext': 'mp4'}
                    
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
                print(f"Download error: {str(e)}")
                return jsonify({'error': f'Download failed: {str(e)}'}), 400
                
        except Exception as e:
            print(f"General error: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred'}), 500

    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Please enter a YouTube URL'}), 400
            
        audio_only = request.form.get('audio_only', 'false').lower() == 'true'

        # Validate URL format
        if not re.match(r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+', url):
            return jsonify({'error': 'Invalid YouTube URL format'}), 400

        # Create new session and visitor data
        session = create_session()
        visitor_data = generate_visitor_data()

        def progress_hook(d):
            if d['status'] == 'downloading':
                progress = float(d['_percent_str'].replace('%', ''))
                return jsonify({
                    'progress': progress,
                    'status': f"Downloading: {d['_percent_str']} of {d['_total_bytes_str']} at {d['_speed_str']}"
                })
            elif d['status'] == 'finished':
                return jsonify({
                    'progress': 100,
                    'status': 'Processing video...'
                })

        # Configure yt-dlp options with session handling
        output_template = os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
        
        ydl_opts = {
            'format': 'bestaudio/best' if audio_only else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
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
                output_file = output_template % {'title': info['title'], 'ext': 'mp3'}
            else:
                output_file = output_template % {'title': info['title'], 'ext': 'mp4'}
            
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
        print(f"Download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 400

if __name__ == '__main__':
    app.run(debug=True)         