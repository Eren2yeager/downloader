from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os

app = Flask(__name__)

# Use the system's Downloads folder for storing videos
DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads")
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
        options = {
            "format": format_string,
            "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".m4a", ".mp4")

        return jsonify({"filename": filename})  # Return JSON with the filename

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
