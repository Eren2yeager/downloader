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

# Quality options using format IDs
QUALITY_OPTIONS = {
    "low": "18/135+140",  # 360p
    "medium": "22/136+140",  # 720p
    "high": "22/137+140",  # 1080p if available, else 720p
    "best": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # Best quality up to 1080p
    "audio": "140/bestaudio[ext=m4a]/bestaudio"  # m4a audio / fallback best audio
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

        # Enhanced options without cookie dependency
        options = {
            "format": format_string,
            "outtmpl": output_template,
            "verbose": True,
            "no_warnings": True,
            "http_headers": {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Sec-Fetch-Mode": "navigate"
            },
            "nocheckcertificate": True,
            "extract_flat": "in_playlist",
            "extractor_retries": 3,
            "file_access_retries": 3,
            "fragment_retries": 3,
            "skip_download": False,
            "rm_cachedir": True,
            "legacy_server_connect": True,
            "no_check_certificates": True
        }

        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]

        print(f"Starting download with options: {options}")

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                print(f"Video info extracted: {info.get('title')}")
                
                # Proceed with download
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
                    # Try to find the actual file if filename doesn't match exactly
                    files = os.listdir(download_dir)
                    if files:  # If there are any files in the directory
                        actual_file = files[0]  # Take the first file
                        actual_filepath = os.path.join(download_dir, actual_file)
                        response = send_file(actual_filepath, as_attachment=True)
                        # Clean up
                        try:
                            os.remove(actual_filepath)
                            os.rmdir(download_dir)
                        except Exception as e:
                            print(f"Cleanup error: {e}")
                        return response
                    
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
                    "details": "Failed to download. Please try a different quality or video."
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