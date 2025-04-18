from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform

app = Flask(__name__)

# Configure download folder based on environment and platform
if os.environ.get('FLASK_ENV') == 'production':
    # For production (Docker/cloud) - use /app/downloads with proper permissions
    DOWNLOAD_FOLDER = '/app/downloads'
else:
    # For local development - use platform-appropriate downloads folder
    if platform.system() == 'Windows':
        DOWNLOAD_FOLDER = os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads')
    else:
        DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')

# Ensure the download folder exists and has correct permissions
try:
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    # Make folder writable in production
    if os.environ.get('FLASK_ENV') == 'production':
        os.chmod(DOWNLOAD_FOLDER, 0o777)
except Exception as e:
    print(f"Warning: Could not create or set permissions for download folder: {e}")

# Updated Quality options for better compatibility
QUALITY_OPTIONS = {
    "low": "worst[ext=mp4][height>=360]",
    "medium": "best[ext=mp4][height<=480]",
    "high": "best[ext=mp4][height<=720]",
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "audio": "bestaudio"  # Simplified audio format
}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        format_string = QUALITY_OPTIONS.get(quality, "best")
        output_template = os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s")

        options = {
            "format": format_string,
            "outtmpl": output_template,
            "cookiefile": "cookies.txt",
            "verbose": True,
            "no_warnings": False,  # Show warnings for better debugging
            "extract_flat": False
        }

        # Special case for audio-only download in mp3 format
        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
            options["format"] = "bestaudio/best"  # Ensure we get the best audio

        with yt_dlp.YoutubeDL(options) as ydl:
            print(f"Downloading to folder: {DOWNLOAD_FOLDER}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Download folder exists: {os.path.exists(DOWNLOAD_FOLDER)}")
            print(f"Download folder writable: {os.access(DOWNLOAD_FOLDER, os.W_OK)}")
            
            # Extract info first
            info = ydl.extract_info(url, download=False)
            print(f"Available formats: {[f['format'] for f in info['formats']]}")
            
            # Download the file
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "downloaded")
            if quality == "audio":
                filename = f"{title}.mp3"
            else:
                filename = f"{title}.mp4"

            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            print(f"Expected file path: {filepath}")
            print(f"File exists: {os.path.exists(filepath)}")

            if os.path.exists(filepath):
                return jsonify({"filename": filename})
            else:
                return jsonify({
                    "error": f"File not found at {filepath}",
                    "download_folder": DOWNLOAD_FOLDER,
                    "writable": os.access(DOWNLOAD_FOLDER, os.W_OK),
                    "available_formats": [f['format'] for f in info['formats']]
                })

    except Exception as e:
        print(f"Download error: {str(e)}")
        return jsonify({
            "error": str(e),
            "download_folder": DOWNLOAD_FOLDER,
            "folder_exists": os.path.exists(DOWNLOAD_FOLDER),
            "folder_writable": os.access(DOWNLOAD_FOLDER, os.W_OK) if os.path.exists(DOWNLOAD_FOLDER) else False
        })

@app.route("/get_file/<filename>")
def get_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True)         