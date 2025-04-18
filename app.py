from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile

app = Flask(__name__)

# Configure download folder based on environment
if os.environ.get('FLASK_ENV') == 'production':
    DOWNLOAD_FOLDER = '/tmp/downloads'  # Use /tmp for Railway
else:
    if platform.system() == 'Windows':
        DOWNLOAD_FOLDER = os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads')
    else:
        DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')

# Create temporary download directory with proper permissions
try:
    if os.environ.get('FLASK_ENV') == 'production':
        DOWNLOAD_FOLDER = tempfile.mkdtemp()  # Create a unique temporary directory
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    print(f"Using download folder: {DOWNLOAD_FOLDER}")
except Exception as e:
    print(f"Error setting up download folder: {e}")
    # Fallback to /tmp if main directory creation fails
    DOWNLOAD_FOLDER = tempfile.mkdtemp()

# Quality options for different resolutions
QUALITY_OPTIONS = {
    "low": "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]",
    "medium": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
    "high": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
    "audio": "bestaudio/best"
}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        # Create a unique subdirectory for this download
        download_dir = tempfile.mkdtemp(dir=DOWNLOAD_FOLDER)
        print(f"Created download directory: {download_dir}")

        format_string = QUALITY_OPTIONS.get(quality, "best")
        output_template = os.path.join(download_dir, "%(title)s.%(ext)s")

        options = {
            "format": format_string,
            "outtmpl": output_template,
            "verbose": True,
            "no_warnings": False
        }

        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
            options["format"] = "bestaudio/best"

        print(f"Download options: {options}")
        print(f"Download directory exists: {os.path.exists(download_dir)}")
        print(f"Download directory writable: {os.access(download_dir, os.W_OK)}")

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "downloaded")
            
            if quality == "audio":
                filename = f"{title}.mp3"
            else:
                filename = f"{title}.mp4"

            filepath = os.path.join(download_dir, filename)
            print(f"Looking for file at: {filepath}")

            # List all files in download directory
            print("Files in download directory:")
            for file in os.listdir(download_dir):
                print(f"- {file}")

            if os.path.exists(filepath):
                response = send_file(filepath, as_attachment=True)
                # Clean up the temporary directory after sending
                try:
                    os.remove(filepath)
                    os.rmdir(download_dir)
                except Exception as e:
                    print(f"Cleanup error: {e}")
                return response
            else:
                available_files = os.listdir(download_dir)
                return jsonify({
                    "error": "File not found after download",
                    "expected_path": filepath,
                    "available_files": available_files,
                    "download_dir": download_dir
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
    # This route is now deprecated as we send files directly in the download route
    return "File download method changed", 410

if __name__ == "__main__":
    app.run(debug=True)         