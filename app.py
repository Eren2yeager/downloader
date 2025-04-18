from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile
import random
import re

app = Flask(__name__)

# Configure download folder based on environment
if os.environ.get('FLASK_ENV') == 'production':
    DOWNLOAD_FOLDER = '/tmp/downloads'
else:
    if platform.system() == 'Windows':
        DOWNLOAD_FOLDER = os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads')
    else:
        DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')

# Create temporary download directory
try:
    if os.environ.get('FLASK_ENV') == 'production':
        DOWNLOAD_FOLDER = tempfile.mkdtemp()
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    print(f"Using download folder: {DOWNLOAD_FOLDER}")
except Exception as e:
    print(f"Error setting up download folder: {e}")
    DOWNLOAD_FOLDER = tempfile.mkdtemp()

# Common User Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
]

def clean_filename(title):
    # Remove invalid characters
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    # Limit length
    return title[:200]

def get_video_id(url):
    # Extract video ID from URL
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        video_id = get_video_id(url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL"})

        download_dir = tempfile.mkdtemp(dir=DOWNLOAD_FOLDER)
        print(f"Created download directory: {download_dir}")

        # Base options
        options = {
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "verbose": True,
            "no_warnings": True,
            "http_headers": {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
            },
            "nocheckcertificate": True,
            "no_check_certificates": True,
            "prefer_insecure": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
            "socket_timeout": 30,
            "retries": 10,
            "quiet": False,
            "no_color": True,
            "extract_flat": True,
            "force_generic_extractor": False,
            "youtube_include_dash_manifest": False,
            "youtube_include_hls_manifest": False
        }

        # Format selection based on quality
        if quality == "audio":
            options["format"] = "bestaudio"
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        else:
            if quality == "low":
                options["format"] = "18/134+140/worst[ext=mp4]"
            elif quality == "medium":
                options["format"] = "22/135+140/18"
            elif quality == "high":
                options["format"] = "22/136+140/18"
            else:  # best
                options["format"] = "22/137+140/18"

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                # First try to extract info
                meta = ydl.extract_info(url, download=False)
                if not meta:
                    raise Exception("Could not extract video metadata")

                title = clean_filename(meta.get('title', 'video'))
                print(f"Extracted title: {title}")

                # Update options with confirmed title
                if quality == "audio":
                    filename = f"{title}.mp3"
                else:
                    filename = f"{title}.mp4"

                options["outtmpl"] = os.path.join(download_dir, filename)
                
                # Attempt download
                info = ydl.download([url])
                
                filepath = os.path.join(download_dir, filename)
                if os.path.exists(filepath):
                    response = send_file(filepath, as_attachment=True)
                    try:
                        os.remove(filepath)
                        os.rmdir(download_dir)
                    except Exception as e:
                        print(f"Cleanup error: {e}")
                    return response
                else:
                    # Try to find any downloaded file
                    files = os.listdir(download_dir)
                    if files:
                        actual_file = files[0]
                        actual_filepath = os.path.join(download_dir, actual_file)
                        response = send_file(actual_filepath, as_attachment=True)
                        try:
                            os.remove(actual_filepath)
                            os.rmdir(download_dir)
                        except Exception as e:
                            print(f"Cleanup error: {e}")
                        return response

                    return jsonify({
                        "error": "Download failed",
                        "details": "File not found after download"
                    })

            except Exception as e:
                print(f"Download error: {str(e)}")
                return jsonify({
                    "error": str(e),
                    "details": "Failed to download. Please try a different quality or video."
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