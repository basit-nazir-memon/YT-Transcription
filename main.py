from fastapi import FastAPI, HTTPException, Request
from fastapi.params import Form
from pydantic import BaseModel
import subprocess
import os
import requests
import time
import uuid
import shutil
from pathlib import Path
import logging
import tempfile


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Audio Transcription API",
    description="API to download YouTube videos and transcribe them using AssemblyAI",
    version="1.0.0"
)

ASSEMBLYAI_API_KEY = 'b22ca2f6671b4976b7109b6b48f18fc7'  # Replace with your key or use env var

class TranscribeRequest(BaseModel):
    youtube_url: str
    cookies: str  # This will be the cookies.txt content

@app.get("/")
async def root():
    return {
        "message": "YouTube Audio Transcription API",
        "endpoints": {
            "transcribe": "/transcribe (POST) - Send YouTube URL and cookies to get transcription"
        }
    }

@app.post('/transcribe')
async def transcribe(
        youtube_url: str = Form(...),
        cookies: str = Form(...)
    ):    
    # Create a unique working directory for this request
    work_dir = Path(f"temp_{uuid.uuid4()}")
    work_dir.mkdir(exist_ok=True)
    audio_filename = work_dir / "audio.mp3"
    
    # Create a temporary cookies file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_cookies:
        temp_cookies.write(cookies)
        temp_cookies_path = temp_cookies.name

    try:
        logger.info("Starting download process...")
        # Download audio using yt-dlp and cookies
        cmd = [
            'yt-dlp',
            '--cookies', temp_cookies_path,
            '-f', 'bestaudio/best',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--no-keep-video',
            '--no-warnings',
            '--quiet',
            '--no-check-certificate',
            '--prefer-insecure',
            '--geo-bypass',
            '--add-header', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '-o', str(audio_filename),
            youtube_url
        ]
        
        logger.info(f"Attempting to download: {youtube_url}")
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"First download attempt failed: {process.stderr}")
            # Try alternative format if first attempt fails
            cmd[4] = 'best'  # Change format to just 'best'
            logger.info("Retrying with alternative format...")
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"Second download attempt failed: {process.stderr}")
                # Try one last time with minimal options
                minimal_cmd = [
                    'yt-dlp',
                    '--cookies', temp_cookies_path,
                    '-f', 'best',
                    '--extract-audio',
                    '--audio-format', 'mp3',
                    '-o', str(audio_filename),
                    youtube_url
                ]
                logger.info("Retrying with minimal options...")
                process = subprocess.run(minimal_cmd, capture_output=True, text=True)
                if process.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"All download attempts failed. Last error: {process.stderr}")
        
        logger.info("Download completed, checking file...")
        if not audio_filename.exists():
            raise HTTPException(status_code=500, detail="Audio file not found after download")

        logger.info("Uploading to AssemblyAI...")
        # Upload audio to AssemblyAI
        headers = {'authorization': ASSEMBLYAI_API_KEY}
        with open(audio_filename, 'rb') as f:
            response = requests.post('https://api.assemblyai.com/v2/upload', headers=headers, files={'file': f})
        response.raise_for_status()
        audio_url = response.json()['upload_url']
        logger.info("Upload successful")

        logger.info("Requesting transcription...")
        # Request transcription
        transcript_response = requests.post(
            'https://api.assemblyai.com/v2/transcript',
            headers=headers,
            json={'audio_url': audio_url}
        )
        transcript_response.raise_for_status()
        transcript_id = transcript_response.json()['id']
        logger.info(f"Transcription started with ID: {transcript_id}")

        # Poll for completion
        while True:
            poll = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}', headers=headers)
            poll.raise_for_status()
            status = poll.json()['status']
            logger.info(f"Transcription status: {status}")
            
            if status == 'completed':
                result = {'transcript': poll.json()['text']}
                logger.info("Transcription completed successfully")
                return result
            elif status == 'failed':
                raise HTTPException(status_code=500, detail='Transcription failed')
            time.sleep(5)

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the working directory and temporary cookies file
        if work_dir.exists():
            shutil.rmtree(work_dir)
            logger.info("Cleaned up temporary files")
        if os.path.exists(temp_cookies_path):
            os.unlink(temp_cookies_path)
            logger.info("Cleaned up temporary cookies file") 