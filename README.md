# YouTube Transcript Viewer

A tiny, production-ready, open source web app to fetch and read YouTube video transcripts. Paste a YouTube URL, pick a language (if available), optionally include timestamps, copy the text, or download it as `.txt` (named after the video title when possible).

## Features

- Single-page UI, clean + modern, keyboard-friendly
- Handles manual and auto-generated captions
- Language selection (populated from available tracks)
- Optional `[MM:SS]` timestamps
- Copy & Download (`.txt` named after the video title)
- Graceful errors (private/unavailable videos, no captions)
- No frontend framework; FastAPI backend

## Tech

- **Backend:** Python 3.11+ / FastAPI / `youtube-transcript-api`
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **Optional:** Video title via YouTube Data API v3 (if an API key is set), otherwise oEmbed fallback

## YouTube API Key (Optional)

**When you need it:**
- Bulk downloads from playlists or channels
- Better video title lookup

**When you don't need it:**
- Single video transcript downloads
- Basic functionality works fine without it

**How to get one:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select an existing one
3. Enable the "YouTube Data API v3"
4. Create credentials → API Key
5. Copy your API key

**How to use it:**
1. Copy `.env.example` to `.env`
2. Add your key: `YT_API_KEY=your_api_key_here`

## Quickstart

### Windows (PowerShell)

```powershell
# 1) Clone and navigate to the project
git clone https://github.com/your-username/youtube-transcript-app.git
cd youtube-transcript-app

# 2) Create & activate virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4) Run the server
python -m uvicorn backend.main:app --reload --port 8000

# 5) Visit http://127.0.0.1:8000/
```

### Linux/macOS (Bash)

```bash
# 1) Clone and navigate to the project
git clone https://github.com/your-username/youtube-transcript-app.git
cd youtube-transcript-app

# 2) Create & activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4) Run the server
python -m uvicorn backend.main:app --reload --port 8000

# 5) Visit http://127.0.0.1:8000/
```

## Credits
See [CREDITS.md](./CREDITS.md) and [NOTICE](./NOTICE).  
- 2025 Riinkz
- README.md written by Gemini, because I'm lazy.
