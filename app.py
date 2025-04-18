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

# YouTube consent cookie
YOUTUBE_CONSENT = 'YES+cb.20240318-17-p0.en-GB+FX+{}'.format(random.randint(100, 999))

# reCAPTCHA settings
RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

if not RECAPTCHA_SITE_KEY or not RECAPTCHA_SECRET_KEY:
    print("Warning: reCAPTCHA keys not set. Please set RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY environment variables.")
    if os.environ.get('FLASK_ENV') == 'development':
        RECAPTCHA_SITE_KEY = "YOUR_SITE_KEY"
        RECAPTCHA_SECRET_KEY = "YOUR_SECRET_KEY"

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

# List of free SOCKS5 proxies (update these regularly)
PROXY_LIST = [
    'socks5://192.111.137.34:18765',
    'socks5://192.111.129.145:16894',
    'socks5://98.162.25.16:4145',
    'socks5://72.210.221.197:4145',
    'socks5://192.111.135.17:18302',
    'socks5://192.111.137.37:18762',
    'socks5://192.111.139.165:4145',
    'socks5://192.111.130.2:4145'
]

# YouTube API constants
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
INNERTUBE_API_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
INNERTUBE_CLIENT_VERSION = '2.20240321.04.00'
INNERTUBE_CONTEXT = {
    'client': {
        'clientName': 'ANDROID',
        'clientVersion': '18.11.36',
        'androidSdkVersion': 33,
        'osName': 'Android',
        'osVersion': '13',
        'platform': 'MOBILE'
    }
}

# Add these constants at the top after imports
ANDROID_HEADERS = {
    'User-Agent': 'com.google.android.youtube/17.31.35 (Linux; U; Android 11)',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en',
    'Accept-Encoding': 'gzip',
    'x-goog-api-format-version': '2',
    'x-goog-api-key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
    'x-youtube-client-name': '3',
    'x-youtube-client-version': '17.31.35',
    'content-type': 'application/json'
}

# Configuration
API_VERSION = "v1"
DOWNLOAD_STATES = {
    'INIT': 0,
    'EXTRACTING': 1,
    'DOWNLOADING': 2,
    'CONVERTING': 3,
    'COMPLETE': 4,
    'ERROR': -1
}

class DownloadTracker:
    def __init__(self):
        self.downloads = {}
        
    def create_download(self, video_id):
        download_id = hashlib.md5(f"{video_id}_{time.time()}".encode()).hexdigest()
        self.downloads[download_id] = {
            'video_id': video_id,
            'state': DOWNLOAD_STATES['INIT'],
            'progress': 0,
            'title': '',
            'error': None,
            'output_file': None,
            'format': None,
            'start_time': time.time()
        }
        return download_id
    
    def update_download(self, download_id, **kwargs):
        if download_id in self.downloads:
            self.downloads[download_id].update(kwargs)
    
    def get_download(self, download_id):
        return self.downloads.get(download_id)
    
    def cleanup_old_downloads(self, max_age_hours=1):
        current_time = time.time()
        to_remove = []
        for download_id, download in self.downloads.items():
            if current_time - download['start_time'] > max_age_hours * 3600:
                to_remove.append(download_id)
                if download['output_file'] and os.path.exists(download['output_file']):
                    try:
                        os.remove(download['output_file'])
                    except:
                        pass
        for download_id in to_remove:
            del self.downloads[download_id]

download_tracker = DownloadTracker()

def get_working_proxy():
    """Test and return a working proxy"""
    random.shuffle(PROXY_LIST)
    for proxy in PROXY_LIST:
        try:
            proxies = {
                'http': proxy,
                'https': proxy
            }
            response = requests.get('https://www.youtube.com', 
                                 proxies=proxies,
                                 timeout=10)
            if response.status_code == 200:
                print(f"Found working proxy: {proxy}")
                return proxies
        except:
            continue
    return None

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/122.0.2365.66',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ]
    return random.choice(user_agents)

def create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def create_cookie_file():
    cookie_file = os.path.join(tempfile.gettempdir(), 'youtube_cookies.txt')
    
    # Create cookie file in Netscape format
    with open(cookie_file, 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n')
        f.write('# https://curl.haxx.se/rfc/cookie_spec.html\n')
        f.write('# This file was generated by yt-dlp.  Do not edit.\n\n')
        
        # Current timestamp and one year from now
        current_time = int(datetime.now().timestamp())
        expiry = current_time + 31536000  # 1 year from now
        
        # Add required YouTube cookies with proper domain format
        cookies = [
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tCONSENT\t{YOUTUBE_CONSENT}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tVISITOR_INFO1_LIVE\t{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{current_time + 3600}\tGPS\t1',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tPREF\tf6=8&hl=en&f5=30000',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tYSC\t{random.randint(10**10, (10**11)-1)}',
            # Add SAPISID cookie for authentication
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tSAPISID\t{random.randint(10**10, (10**11)-1)}',
            # Add additional session cookies
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\t__Secure-1PSID\t{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\t__Secure-3PSID\t{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tLOGIN_INFO\tAFmmF2swRQIgC{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tSID\tv{random.randint(10**10, (10**11)-1)}'
        ]
        
        # Write each cookie on a new line
        for cookie in cookies:
            f.write(cookie + '\n')
    
    return cookie_file

def get_video_info_with_proxy(url, proxy=None):
    """Get video info using proxy"""
    try:
        ua = UserAgent()
        headers = {
            'User-Agent': ua.random,
            'Accept': 'text/html,application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.youtube.com',
            'Referer': 'https://www.youtube.com/'
        }

        # Try with proxy first
        if proxy:
            try:
                response = requests.get(url, headers=headers, proxies=proxy, timeout=15)
                if response.status_code == 200:
                    return response
            except:
                pass

        # Try without proxy as fallback
        return requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        print(f"Error getting video info: {str(e)}")
        raise

def get_browser_like_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.5563.57 Mobile Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Origin': 'https://m.youtube.com',
        'Referer': 'https://m.youtube.com/',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': INNERTUBE_CLIENT_VERSION,
        'X-Goog-Api-Format-Version': '2',
        'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Range': 'bytes=0-',  # Add range header for resumable downloads
        'Cookie': f'CONSENT={YOUTUBE_CONSENT}; VISITOR_INFO1_LIVE={random.randint(10**10, (10**11)-1)}; YSC={random.randint(10**10, (10**11)-1)}'
    }

def verify_recaptcha(response):
    try:
        data = {
            'secret': RECAPTCHA_SECRET_KEY,
            'response': response
        }
        r = requests.post(RECAPTCHA_VERIFY_URL, data=data)
        result = r.json()
        return result.get('success', False)
    except Exception as e:
        print(f"reCAPTCHA verification error: {e}")
        return False

def download_with_progress(url, ydl_opts, max_segments=10):
    """Download video in segments with progress tracking"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First get video info without downloading
            info = ydl.extract_info(url, download=False)
            if not info:
                raise Exception("Could not get video information")

            # Get video format
            formats = info.get('formats', [])
            if not formats:
                raise Exception("No formats available")

            # Select format based on quality settings
            selected_format = None
            for f in formats:
                if f.get('format_id') == ydl_opts.get('format', ''):
                    selected_format = f
                    break
            
            if not selected_format:
                # Use best available format
                selected_format = formats[-1]

            # Get file size
            filesize = selected_format.get('filesize', 0)
            if filesize == 0:
                filesize = selected_format.get('filesize_approx', 0)

            if filesize == 0:
                print("Warning: Could not determine file size, proceeding anyway")
                # Try direct download
                return ydl.extract_info(url, download=True)

            # Calculate segment size
            segment_size = max(filesize // max_segments, 1024 * 1024)  # Minimum 1MB segments
            
            # Create temporary directory for segments
            temp_dir = tempfile.mkdtemp()
            segment_files = []

            try:
                # Download in segments
                for i in range(0, filesize, segment_size):
                    end_byte = min(i + segment_size - 1, filesize - 1)
                    
                    # Update headers for this segment
                    ydl_opts['http_headers']['Range'] = f'bytes={i}-{end_byte}'
                    
                    # Unique name for this segment
                    segment_file = os.path.join(temp_dir, f'segment_{i}_{end_byte}.part')
                    
                    # Try to download this segment with retries
                    max_retries = 5
                    for retry in range(max_retries):
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as segment_ydl:
                                segment_info = segment_ydl.extract_info(url, download=True)
                                if os.path.exists(segment_file) and os.path.getsize(segment_file) > 0:
                                    segment_files.append(segment_file)
                                    print(f"Successfully downloaded segment {len(segment_files)}/{max_segments}")
                                    break
                        except Exception as e:
                            print(f"Error downloading segment {i}: {str(e)}")
                            if retry < max_retries - 1:
                                sleep_time = min(30, 5 * (retry + 1))
                                print(f"Retrying in {sleep_time} seconds...")
                                time.sleep(sleep_time)
                            else:
                                raise Exception(f"Failed to download segment after {max_retries} attempts")

                # Verify all segments were downloaded
                if len(segment_files) != max_segments:
                    raise Exception(f"Only downloaded {len(segment_files)}/{max_segments} segments")

                # Combine segments
                output_file = os.path.join(temp_dir, 'combined_file')
                with open(output_file, 'wb') as outfile:
                    for segment in sorted(segment_files):
                        with open(segment, 'rb') as infile:
                            outfile.write(infile.read())

                # Clean up segments
                for segment in segment_files:
                    try:
                        os.remove(segment)
                    except:
                        pass

                return info

            finally:
                # Clean up temp directory
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

    except Exception as e:
        print(f"Download error: {str(e)}")
        raise

def generate_session_token():
    """Generate a random session token"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def get_video_info(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"Error getting video info: {str(e)}")
        return None

@app.route('/api/v1/init', methods=['GET'])
def init_download():
    try:
        # Get authorization token (implement your own auth logic)
        auth_token = request.args.get('a')
        if not auth_token:
            return jsonify({'error': 1, 'message': 'Missing authorization'})
            
        # Create convert URL
        base_url = request.url_root.rstrip('/')
        convert_url = f"{base_url}/api/v1/convert"
        
        return jsonify({
            'error': 0,
            'convertURL': convert_url
        })
    except Exception as e:
        return jsonify({'error': 1, 'message': str(e)})

@app.route('/api/v1/convert', methods=['GET'])
def convert():
    try:
        video_id = request.args.get('v')
        format_type = request.args.get('f', 'mp3')
        
        if not video_id:
            return jsonify({'error': 1, 'message': 'Missing video ID'})
            
        # Create download entry
        download_id = download_tracker.create_download(video_id)
        
        # Get video info
        info = get_video_info(video_id)
        if not info:
            return jsonify({'error': 2, 'message': 'Could not get video info'})
            
        # Update download info
        download_tracker.update_download(
            download_id,
            state=DOWNLOAD_STATES['EXTRACTING'],
            title=info.get('title', ''),
            format=format_type
        )
        
        # Create progress and download URLs
        base_url = request.url_root.rstrip('/')
        progress_url = f"{base_url}/api/v1/progress/{download_id}"
        download_url = f"{base_url}/api/v1/download/{download_id}"
        
        return jsonify({
            'error': 0,
            'progressURL': progress_url,
            'downloadURL': download_url,
            'title': info.get('title', '')
        })
    except Exception as e:
        return jsonify({'error': 1, 'message': str(e)})

@app.route('/api/v1/progress/<download_id>', methods=['GET'])
def progress(download_id):
    try:
        download = download_tracker.get_download(download_id)
        if not download:
            return jsonify({'error': 1, 'message': 'Invalid download ID'})
            
        return jsonify({
            'error': 0,
            'progress': download['state'],
            'title': download['title']
        })
    except Exception as e:
        return jsonify({'error': 1, 'message': str(e)})

@app.route('/api/v1/download/<download_id>', methods=['GET'])
def download_file(download_id):
    try:
        download = download_tracker.get_download(download_id)
        if not download:
            return jsonify({'error': 1, 'message': 'Invalid download ID'})
            
        video_id = download['video_id']
        format_type = download['format']
        
        # Configure yt-dlp options
        output_template = os.path.join(tempfile.gettempdir(), f'{video_id}.%(ext)s')
        
        ydl_opts = {
            'format': 'bestaudio/best' if format_type == 'mp3' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True,
            'progress_hooks': [lambda d: download_tracker.update_download(
                download_id,
                state=DOWNLOAD_STATES['DOWNLOADING'],
                progress=d.get('downloaded_bytes', 0)
            )]
        }
        
        if format_type == 'mp3':
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            })
        
        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}")
            if not info:
                raise Exception("Failed to download video")
                
            # Get output file path
            if format_type == 'mp3':
                output_file = output_template.replace('.%(ext)s', '.mp3')
            else:
                output_file = output_template.replace('.%(ext)s', '.mp4')
            
            if not os.path.exists(output_file):
                raise Exception("Download failed - file not found")
                
            # Update download status
            download_tracker.update_download(
                download_id,
                state=DOWNLOAD_STATES['COMPLETE'],
                output_file=output_file
            )
            
            # Send file
            return send_file(
                output_file,
                as_attachment=True,
                download_name=f"{info.get('title', video_id)}.{format_type}",
                mimetype='audio/mpeg' if format_type == 'mp3' else 'video/mp4'
            )
            
    except Exception as e:
        download_tracker.update_download(
            download_id,
            state=DOWNLOAD_STATES['ERROR'],
            error=str(e)
        )
        return jsonify({'error': 1, 'message': str(e)})

@app.route('/')
def index():
    return render_template('index.html')

# Cleanup task
@app.before_request
def cleanup():
    download_tracker.cleanup_old_downloads()

if __name__ == '__main__':
    app.run(debug=True)         