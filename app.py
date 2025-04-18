from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile
import random
import re
import requests
import time
import json
from datetime import datetime, timedelta
from http.cookiejar import MozillaCookieJar
from urllib.parse import parse_qs, urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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
    'socks5://51.79.51.246:443',
    'socks5://192.111.137.35:4145',
    'socks5://72.206.181.97:64943',
    'socks5://192.111.139.163:19404',
    'socks5://47.243.95.228:10080'
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

def get_working_proxy():
    """Test and return a working proxy"""
    for proxy in PROXY_LIST:
        try:
            response = requests.get('https://www.youtube.com', 
                                  proxies={'http': proxy, 'https': proxy},
                                  timeout=10)
            if response.status_code == 200:
                return proxy
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

def get_video_info(url):
    try:
        video_id = None
        if 'youtu.be' in url:
            video_id = url.split('/')[-1]
        else:
            parsed_url = urlparse(url)
            video_id = parse_qs(parsed_url.query).get('v', [None])[0]
            if not video_id:
                video_id = parsed_url.path.split('/')[-1]
        
        if not video_id:
            raise Exception("Could not extract video ID")

        session = create_session()
        
        # First, get the initial page data
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.5563.57 Mobile Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://m.youtube.com',
            'Referer': 'https://m.youtube.com/',
        }
        
        # Get video info using InnerTube API
        data = {
            'videoId': video_id,
            'context': INNERTUBE_CONTEXT,
            'playbackContext': {
                'contentPlaybackContext': {
                    'html5Preference': 'HTML5_PREF_WANTS',
                }
            },
            'racyCheckOk': True,
            'contentCheckOk': True
        }
        
        response = session.post(
            'https://www.youtube.com/youtubei/v1/player',
            params={'key': INNERTUBE_API_KEY},
            headers={
                **headers,
                'Content-Type': 'application/json',
            },
            json=data
        )
        
        response.raise_for_status()
        return response.json()
    
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
        
        # Add required YouTube cookies
        cookies = [
            # CONSENT cookie
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tCONSENT\t{YOUTUBE_CONSENT}',
            # VISITOR_INFO1_LIVE cookie
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tVISITOR_INFO1_LIVE\t{random.randint(10**10, (10**11)-1)}',
            # GPS cookie
            f'.youtube.com\tTRUE\t/\tFALSE\t{current_time + 3600}\tGPS\t1',
            # PREF cookie
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tPREF\tf6=8&hl=en&f5=30000',
            # YSC cookie
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tYSC\t{random.randint(10**10, (10**11)-1)}',
            # Additional cookies
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tLOGIN_INFO\tdummy_token',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tSAPISID\t{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tSID\tdummy_sid',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tSSID\t{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tHSID\t{random.randint(10**10, (10**11)-1)}',
            f'.youtube.com\tTRUE\t/\tFALSE\t{expiry}\tAEC\t{random.randint(10**10, (10**11)-1)}'
        ]
        
        # Write each cookie on a new line
        for cookie in cookies:
            f.write(cookie + '\n')
    
    # Verify the cookie file
    if not os.path.exists(cookie_file):
        raise Exception("Failed to create cookie file")
        
    return cookie_file

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)

@app.route("/download", methods=["POST"])
def download():
    # Verify reCAPTCHA first
    recaptcha_response = request.form.get('g-recaptcha-response')
    if not recaptcha_response:
        return jsonify({
            "error": "Please complete the reCAPTCHA verification.",
            "details": "reCAPTCHA verification is required"
        })

    if not verify_recaptcha(recaptcha_response):
        return jsonify({
            "error": "reCAPTCHA verification failed. Please try again.",
            "details": "Invalid reCAPTCHA response"
        })

    url = request.form["url"]
    quality = request.form["quality"]

    try:
        # Create a unique download directory
        download_dir = tempfile.mkdtemp(dir=DOWNLOAD_FOLDER)
        print(f"Download directory: {download_dir}")

        # Get video info first
        try:
            video_info = get_video_info(url)
            if not video_info:
                raise Exception("Could not get video information")
            
            # Add a small delay
            time.sleep(2)
            
        except Exception as e:
            print(f"Error getting video info: {e}")
            raise Exception("Failed to get video information. Please try again.")

        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if quality != "audio" else 'bestaudio[ext=m4a]/best',
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'http_headers': get_browser_like_headers(),
            'quiet': False,
            'no_warnings': True,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'mobile'],
                    'player_skip': [],
                    'client': ['android', 'mobile'],
                    'player_params': {
                        'playback_context': {
                            'client': INNERTUBE_CONTEXT['client']
                        }
                    }
                }
            },
            'socket_timeout': 15,
            'retries': 3,
            'file_access_retries': 3,
            'fragment_retries': 3,
            'skip_download': False,
            'overwrites': True,
            'ignoreerrors': False,
            'logtostderr': True,
            'prefer_insecure': True,
            'cachedir': False
        }

        # Add format-specific options
        if quality == "audio":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            quality_formats = {
                'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'high': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
                'medium': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
                'low': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]'
            }
            ydl_opts.update({
                'format': quality_formats.get(quality, 'best'),
                'merge_output_format': 'mp4'
            })

        # Add a small delay before download
        time.sleep(2)

        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Starting download with options: {ydl_opts}")
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("Failed to extract video information")

            # Get the output file path
            video_title = info.get('title', f'video_{int(time.time())}')
            video_title = re.sub(r'[<>:"/\\|?*]', '', video_title).strip()[:200]
            ext = 'mp3' if quality == "audio" else 'mp4'
            output_file = os.path.join(download_dir, f"{video_title}.{ext}")

            # Verify the file exists and has content
            if not os.path.exists(output_file):
                # Try to find any file in the directory
                files = os.listdir(download_dir)
                if files:
                    output_file = os.path.join(download_dir, files[0])
                else:
                    raise Exception("Download failed - file not found")

            if os.path.getsize(output_file) == 0:
                raise Exception("Download failed - empty file")

            print(f"File downloaded successfully: {output_file}")

            # Add a small delay before sending
            time.sleep(1)

            # Send the file
            try:
                response = send_file(
                    output_file,
                    as_attachment=True,
                    download_name=os.path.basename(output_file),
                    mimetype='audio/mpeg' if quality == "audio" else 'video/mp4'
                )

                # Clean up after sending
                @response.call_on_close
                def cleanup():
                    try:
                        if os.path.exists(output_file):
                            os.remove(output_file)
                        if os.path.exists(download_dir):
                            os.rmdir(download_dir)
                    except Exception as e:
                        print(f"Cleanup error: {e}")

                return response

            except Exception as e:
                print(f"Error sending file: {e}")
                raise

    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg:
            error_msg = "YouTube is detecting automated access. Please try again with a different video or quality setting."
        elif "not available on this app" in error_msg:
            error_msg = "This video is not available for download. Please try a different video."
        print(f"Download error: {error_msg}")
        
        # Clean up on error
        try:
            if os.path.exists(download_dir):
                import shutil
                shutil.rmtree(download_dir)
        except:
            pass
        
        return jsonify({
            "error": error_msg,
            "details": "Try a different video or quality setting"
        })

@app.route("/get_file/<filename>")
def get_file(filename):
    return "File download method changed", 410

if __name__ == "__main__":
    app.run(debug=True)         