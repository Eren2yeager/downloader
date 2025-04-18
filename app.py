from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import platform
import tempfile
import random
import re
import requests

app = Flask(__name__)

# Free proxy list (update these periodically)
PROXY_LIST = [
    'socks5://51.79.52.80:3080',
    'socks5://72.195.34.35:27360',
    'socks5://72.217.216.239:4145',
    'socks5://184.170.245.148:4145'
]

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

def get_working_proxy():
    for proxy in PROXY_LIST:
        try:
            response = requests.get('https://www.youtube.com', 
                                 proxies={'http': proxy, 'https': proxy}, 
                                 timeout=5)
            if response.status_code == 200:
                return proxy
        except:
            continue
    return None

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

        # Get working proxy
        proxy = get_working_proxy()
        print(f"Using proxy: {proxy}")

        # Basic options
        options = {
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "format": "best" if quality != "audio" else "bestaudio",
            "verbose": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "no_check_certificates": True,
            "quiet": False
        }

        # Add proxy if available
        if proxy:
            options["proxy"] = proxy

        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]

        print("Starting download with options:", options)

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                # Extract info
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
                
                # Download
                print(f"Downloading to: {options['outtmpl']}")
                ydl.download([url])
                
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
                print(f"Download error: {str(e)}")
                return jsonify({
                    "error": str(e),
                    "details": "Try again with a different quality setting"
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