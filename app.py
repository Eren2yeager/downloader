from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile
import random
import re
import requests
import json
from datetime import datetime

app = Flask(__name__)

# YouTube consent cookie (helps bypass some restrictions)
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

try:
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
except Exception as e:
    print(f"Error setting up download folder: {e}")
    DOWNLOAD_FOLDER = tempfile.mkdtemp()

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/122.0.2365.66',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ]
    return random.choice(user_agents)

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
    cookie_data = [
        {
            "name": "CONSENT",
            "value": YOUTUBE_CONSENT,
            "domain": ".youtube.com",
            "path": "/"
        },
        {
            "name": "CONSENT",
            "value": YOUTUBE_CONSENT,
            "domain": "youtube.com",
            "path": "/"
        }
    ]
    
    cookie_file = os.path.join(tempfile.gettempdir(), 'youtube_cookies.txt')
    with open(cookie_file, 'w') as f:
        json.dump(cookie_data, f)
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
        download_dir = tempfile.mkdtemp(dir=DOWNLOAD_FOLDER)
        print(f"Download directory: {download_dir}")

        # Create cookie file
        cookie_file = create_cookie_file()

        # Basic options with necessary settings
        options = {
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "cookiefile": cookie_file,
            "cookiesfrombrowser": None,  # Disable browser cookies
            "quiet": False,
            "no_warnings": True,
            "extract_flat": False,
            "http_headers": {
                "User-Agent": get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive"
            }
        }

        # Set format based on quality
        if quality == "audio":
            options.update({
                "format": "bestaudio",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }]
            })
        else:
            if quality == "best":
                options["format"] = "best"
            elif quality == "high":
                options["format"] = "best[height<=720]"
            elif quality == "medium":
                options["format"] = "best[height<=480]"
            elif quality == "low":
                options["format"] = "best[height<=360]"

        print("Starting download with options:", options)

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                # Extract info first
                print(f"Extracting info for URL: {url}")
                meta = ydl.extract_info(url, download=False)
                if not meta:
                    raise Exception("Could not extract video metadata")

                # Clean title
                title = re.sub(r'[<>:"/\\|?*]', '', meta.get('title', 'video'))[:200]
                
                # Set filename
                if quality == "audio":
                    filename = f"{title}.mp3"
                else:
                    filename = f"{title}.mp4"
                
                options["outtmpl"] = os.path.join(download_dir, filename)
                
                # Download with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        print(f"Download attempt {attempt + 1}/{max_retries}")
                        ydl.download([url])
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        print(f"Attempt {attempt + 1} failed: {str(e)}")
                        import time
                        time.sleep(3)
                
                filepath = os.path.join(download_dir, filename)
                if os.path.exists(filepath):
                    print(f"File downloaded successfully: {filepath}")
                    response = send_file(filepath, as_attachment=True)
                    try:
                        os.remove(filepath)
                        os.rmdir(download_dir)
                        os.remove(cookie_file)  # Clean up cookie file
                    except Exception as e:
                        print(f"Cleanup error: {e}")
                    return response
                
                # Fallback: look for any downloaded file
                files = os.listdir(download_dir)
                if files:
                    actual_file = files[0]
                    actual_filepath = os.path.join(download_dir, actual_file)
                    print(f"Using fallback file: {actual_filepath}")
                    response = send_file(actual_filepath, as_attachment=True)
                    try:
                        os.remove(actual_filepath)
                        os.rmdir(download_dir)
                        os.remove(cookie_file)  # Clean up cookie file
                    except Exception as e:
                        print(f"Cleanup error: {e}")
                    return response

                raise Exception("No file found after download")

            except Exception as e:
                try:
                    os.remove(cookie_file)  # Clean up cookie file on error
                except:
                    pass
                    
                error_msg = str(e)
                if "Sign in to confirm you're not a bot" in error_msg:
                    error_msg = "This video requires age verification. Please try a different video."
                print(f"Download error: {error_msg}")
                return jsonify({
                    "error": error_msg,
                    "details": "Try a different video or quality setting"
                })

    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({
            "error": str(e),
            "details": "An unexpected error occurred"
        })

@app.route("/get_file/<filename>")
def get_file(filename):
    return "File download method changed", 410

if __name__ == "__main__":
    app.run(debug=True)         