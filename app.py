from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile
import random
import re
import requests
from datetime import datetime

app = Flask(__name__)

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

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        download_dir = tempfile.mkdtemp(dir=DOWNLOAD_FOLDER)
        print(f"Download directory: {download_dir}")

        # Enhanced options with anti-bot detection measures
        options = {
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "format": "best" if quality != "audio" else "bestaudio",
            "verbose": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "no_check_certificates": True,
            "quiet": False,
            "extractor_retries": 5,
            "file_access_retries": 5,
            "fragment_retries": 5,
            "retry_sleep_functions": {"http": lambda n: 5 * (n + 1)},
            "socket_timeout": 30,
            "http_headers": {
                "User-Agent": get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "DNT": "1"
            },
            "cookiesfrombrowser": ["chrome"],  # Try to use Chrome cookies if available
            "sleep_interval_requests": 1,  # Add delay between requests
            "sleep_interval": 5,  # Add delay between downloads
            "max_sleep_interval": 10,
            "sleep_interval_subtitles": 0
        }

        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]

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
                        # Wait before retry
                        import time
                        time.sleep(5 * (attempt + 1))
                
                filepath = os.path.join(download_dir, filename)
                if os.path.exists(filepath):
                    print(f"File downloaded successfully: {filepath}")
                    response = send_file(filepath, as_attachment=True)
                    try:
                        os.remove(filepath)
                        os.rmdir(download_dir)
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
                    except Exception as e:
                        print(f"Cleanup error: {e}")
                    return response

                raise Exception("No file found after download")

            except Exception as e:
                error_msg = str(e)
                if "Sign in to confirm you're not a bot" in error_msg:
                    error_msg = "YouTube is requesting verification. Please try again in a few minutes or try a different video."
                print(f"Download error: {error_msg}")
                return jsonify({
                    "error": error_msg,
                    "details": "Try again with a different quality setting or video"
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