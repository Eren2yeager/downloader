from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform

app = Flask(__name__)

# Configure download folder based on environment and platform
if os.environ.get('FLASK_ENV') == 'production':
    # For production (Docker/cloud)
    DOWNLOAD_FOLDER = os.path.join(os.path.sep, 'app', 'downloads')
else:
    # For local development - use platform-appropriate downloads folder
    if platform.system() == 'Windows':
        DOWNLOAD_FOLDER = os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads')
    else:
        DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')

# Create download folder if it doesn't exist
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Quality options for different resolutions
QUALITY_OPTIONS = {
    "low": "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]",
    "medium": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
    "high": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
    "best": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",  # Highest quality
    "audio": "bestaudio[ext=m4a]/bestaudio",  # Best audio-only
}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        format_string = QUALITY_OPTIONS.get(quality, "best")  # Default to best
        output_template = os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s")

        options = {
            "format": format_string,
            "outtmpl": output_template,
            "cookiefile": "cookies.txt"
        }

        # Special case for audio-only download in mp3 format
        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
            # Ensure output ends in .mp3
            options["outtmpl"] = os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s")
        else:
            options["merge_output_format"] = "mp4"
            options["postprocessors"] = [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4"
            }]

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "downloaded")
            if quality == "audio":
                filename = f"{title}.mp3"
            else:
                filename = f"{title}.mp4"

        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            return jsonify({"filename": filename})  # Return JSON with the filename
        else:
            return jsonify({"error": "Could not download or convert the file."})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/get_file/<filename>")
def get_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True)         