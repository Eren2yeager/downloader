def download():
    url = request.form["url"]
    quality = request.form["quality"]

    try:
        format_string = QUALITY_OPTIONS.get(quality, "best")  # Default to best
        outtmpl = os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s")

        # Default yt_dlp options
        options = {
            "format": format_string,
            "outtmpl": outtmpl,
            "cookiefile": "cookies.txt"
        }

        # Special handling for audio download
        if quality == "audio":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
            options["outtmpl"] = outtmpl.replace(".%(ext)s", ".mp3")
        else:
            options["merge_output_format"] = "mp4"
            options["postprocessors"] = [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }]

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if quality == "audio":
                filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
            else:
                filename = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".m4a", ".mp4")

        return jsonify({"filename": os.path.basename(filename)})

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