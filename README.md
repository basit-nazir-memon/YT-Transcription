# YouTube Transcription Server

This FastAPI server downloads YouTube videos (audio only) using provided cookies, transcribes them using AssemblyAI, and returns the transcript.

## Features
- Accepts a YouTube URL (POST /transcribe)
- Uses cookies from `cookies.txt` to bypass bot detection
- Downloads audio using yt-dlp
- Transcribes audio with AssemblyAI
- Returns transcript as JSON

## Setup

1. **Clone the repo and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add your AssemblyAI API key:**
   - Edit `main.py` and set `ASSEMBLYAI_API_KEY` to your API key, or use an environment variable.

3. **Add your YouTube cookies:**
   - Save your cookies in a file named `cookies.txt` in the project root. (Export from browser using an extension like "Get cookies.txt")

## Running Locally

```bash
uvicorn main:app --reload
```

## Testing with Postman
- Method: POST
- URL: `http://localhost:8000/transcribe`
- Body (JSON):
  ```json
  {
    "youtube_url": "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
  }
  ```
- Response: `{ "transcript": "..." }`

## Deploying on Render
- Create a new Web Service on Render
- Use this repo as the source
- Set the start command to:
  ```
  uvicorn main:app --host 0.0.0.0 --port 10000
  ```
- Add your `cookies.txt` and set your AssemblyAI API key

## Notes
- For now, cookies are read from `cookies.txt`. In the future, the API will accept cookies in the request body.
- Make sure `yt-dlp` is available in the Render environment (add to requirements.txt). #   Y T - T r a n s c r i p t i o n  
 