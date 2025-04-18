# YouTube Downloader

A Flask web application that allows users to download YouTube videos as MP4 or audio as MP3.

## Features

- Download YouTube videos in MP4 format
- Extract audio in MP3 format
- Clean and modern web interface
- Automatic file cleanup
- Rate limiting and bot detection avoidance
- Error handling and logging

## Prerequisites

- Python 3.8 or higher
- FFmpeg (for audio extraction)
- Chrome browser (for cookie handling)

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd youtube-downloader
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install FFmpeg:
- Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

## Configuration

1. Create a `.env` file in the root directory:
```env
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
```

2. Set up logging directory:
```bash
mkdir logs
```

## Running the Application

### Development
```bash
flask run --debug
```

### Production
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Usage

1. Open your browser and navigate to the application URL
2. Enter a YouTube URL
3. Select quality (Video or Audio Only)
4. Click Download
5. Wait for the download to complete

## Security Notes

- The application implements rate limiting
- Files are automatically cleaned up after 1 hour
- Secure headers are implemented
- Cookie handling is done securely

## Maintenance

- Logs are stored in the `logs` directory
- Downloaded files are temporarily stored in the configured download folder
- Old files are automatically cleaned up

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request 