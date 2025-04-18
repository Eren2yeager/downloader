from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile
import random

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

# Quality options for different resolutions
QUALITY_OPTIONS = {
    "low": "18",  # 360p
    "medium": "22",  # 720p
    "high": "137+140/22",  # 1080p+audio / fallback 720p
    "best": "137+140/22/18",  # 1080p+audio / 720p / 360p
    "audio": "140/bestaudio"  # m4a audio / fallback best audio
}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        download_dir = tempfile.mkdtemp(dir=DOWNLOAD_FOLDER)
        print(f"Created download directory: {download_dir}")

        format_string = QUALITY_OPTIONS.get(quality, "best")
        output_template = os.path.join(download_dir, "%(title)s.%(ext)s")

        # Enhanced options to avoid bot detection
        options = {
            "format": format_string,
            "outtmpl": output_template,
            "verbose": True,
            "no_warnings": False,
            # Add headers to appear more like a browser
            "http_headers": {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Sec-Fetch-Mode": "navigate",
                "Connection": "keep-alive"
            },
            # Additional options to bypass restrictions
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": False,
            "no_warnings": True,
            "extract_flat": False,
            # Cookie handling
            "cookiesfrombrowser": ("chrome",),  # Try to use Chrome cookies
        }

        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
            options["format"] = "bestaudio/best"

        print(f"Download options: {options}")

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                # First try without download to check availability
                info = ydl.extract_info(url, download=False)
                print(f"Video info extracted: {info.get('title')}")
                
                # Then proceed with download
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "downloaded")
                
                if quality == "audio":
                    filename = f"{title}.mp3"
                else:
                    filename = f"{title}.mp4"

                filepath = os.path.join(download_dir, filename)
                print(f"Looking for file at: {filepath}")

                # List directory contents
                print("Files in download directory:")
                for file in os.listdir(download_dir):
                    print(f"- {file}")

                if os.path.exists(filepath):
                    response = send_file(filepath, as_attachment=True)
                    # Clean up
                    try:
                        os.remove(filepath)
                        os.rmdir(download_dir)
                    except Exception as e:
                        print(f"Cleanup error: {e}")
                    return response
                else:
                    return jsonify({
                        "error": "File not found after download",
                        "expected_path": filepath,
                        "available_files": os.listdir(download_dir),
                        "download_dir": download_dir
                    })

            except Exception as e:
                print(f"Download error: {str(e)}")
                return jsonify({
                    "error": str(e),
                    "details": "YouTube might be blocking this request. Try again later."
                })

    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({
            "error": str(e),
            "download_folder": DOWNLOAD_FOLDER,
            "folder_exists": os.path.exists(DOWNLOAD_FOLDER)
        })

@app.route("/get_file/<filename>")
def get_file(filename):
    return "File download method changed", 410

if __name__ == "__main__":
    app.run(debug=True)         