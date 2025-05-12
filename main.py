import random
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.params import Form
from fastapi.middleware.cors import CORSMiddleware
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

# Get port from environment variable or default to 8000
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")

app = FastAPI(
    title="YouTube Audio Transcription API",
    description="API to download YouTube videos and transcribe them using AssemblyAI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

ASSEMBLYAI_API_KEY = 'b22ca2f6671b4976b7109b6b48f18fc7'  # Replace with your key or use env var

TOKEN = 'NjU1OTRwWG95ZHFpdmhib3Rnam1uZ3AzYXkzcTJ1bWRia3RqeGNyYnE1cmFlb2xzYjRzajVfMjc3NDA5YmM1MGQ5YTkzNDJhNGQxMDlmY2IxMzFjMGQ'

@app.get("/")
async def root():
    return {
        "message": "YouTube Audio Transcription API",
        "endpoints": {
            "transcribe": "/transcribe (POST) - Send YouTube URL and cookies to get transcription"
        }
    }




# pass youtube url as a query parameter
@app.post('/transcribe')
async def transcribe(
        youtube_url: str = Query(...)
    ):    

    global TOKEN
    # Create a unique working directory for this request
    work_dir = Path(f"temp_{uuid.uuid4()}") # make sure it is unique
    work_dir.mkdir(exist_ok=True)
    audio_filename = work_dir / "audio.mp3"

    try:
        logger.info("Starting download process...")

        # Step 1: Initialize
        init_url = "https://d.ummn.nu/api/v1/init"
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,ur;q=0.8,sd;q=0.7',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Host': 'd.ummn.nu',
            'Origin': 'https://ytmp3.la',
            'Pragma': 'no-cache',
            'Referer': 'https://ytmp3.la/',
            'Sec-Ch-Ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?1',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36'
        }

        params = {
            'a': TOKEN
        }

        convert_url = None

        triesLeft = 3
        # Step 1: Call /init repeatedly until success
        while triesLeft > 0:
            _value = str(random.random())
            params['_'] = _value

            try:
                response = requests.get(init_url, headers=headers, params=params)
                logger.info(f"[INIT] Status: {response.status_code} | _={_value}")

                if response.status_code == 403:
                    # send request 
                    token_response = requests.get("https://mp3convertortokengenerator.onrender.com/api/get-token")
                    if token_response.status_code == 200:
                        token_data = token_response.json()
                        TOKEN = token_data.get("token")
                        params['a'] = TOKEN
                        logger.info(f"[GET TOKEN] Status: {token_response.status_code}")
                    else:
                        logger.error(f"[GET TOKEN] Status: {token_response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    convert_url = data.get("convertURL")
                    # logger.info(f"[INIT] Got convertURL: {convert_url}")
                    break
                

                time.sleep(1)

            except requests.exceptions.RequestException as e:
                logger.error(f"[INIT] Request failed: {e}")
                break

            triesLeft -= 1

        # Step 2: Send GET request to convertURL
        if convert_url:
            # take out the sig query from convert_url
            sig = convert_url.split("sig=")[1]

            params = {
                "sig": sig,
                "v": "k4715CJ0Ii8",
                "f": "mp3",
                "_": str(random.random())
            }

            try:
                response = requests.get(convert_url, headers=headers, params=params)
                logger.info(f"[CONVERT] Status: {response.status_code}")

                redirect_url = None

                if response.status_code == 200:
                    convert_data = response.json()

                    if convert_data.get("redirect") == 1:
                        redirect_url = convert_data.get("redirectURL")
                        # logger.info(f"[REDIRECT] Found redirectURL: {redirect_url}")
                    else:
                        logger.info("[CONVERT] No redirect found.")

                else:
                    logger.error(f"[CONVERT] Unexpected status code: {response.status_code}")


                final_response = None
                # make the payload for the final request consisting of sig, v, f, and _ must be uniqly generated
                if redirect_url:
                    final_response = requests.get(redirect_url, headers=headers)
                    logger.info(f"[CONVERT] Status: {final_response.status_code}")

                    if final_response.status_code == 200:
                        convert_data = final_response.json()
                        # logger.info(f"[CONVERT] Response: {convert_data}")
                        if convert_data.get("redirect") == 0:
                            downloadURL = convert_data.get("downloadURL")
                            dividedPart = downloadURL.split("?")[1]
                            downloadURL = "https://uuuu.ummn.nu/api/v1/download?" + dividedPart

                            # logger.info(f"[REDIRECT] Found downloadURL: {downloadURL}")
                        else:
                            logger.info("[CONVERT] No downloadURL found.")

                else:
                    logger.error(f"[CONVERT] Unexpected status code: {final_response.status_code}")

            except requests.exceptions.RequestException as e:
                logger.error(f"[CONVERT] Request failed: {e}")

        if downloadURL:
            try:
                # Add retry mechanism for download
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        logger.info(f"Attempting to download from URL (attempt {retry_count + 1}/{max_retries})")
                        response = requests.get(downloadURL, timeout=30)
                        response.raise_for_status()
                        
                        with open(audio_filename, 'wb') as f:
                            f.write(response.content)
                        logger.info("Download completed successfully")
                        break
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count == max_retries:
                            raise HTTPException(status_code=500, detail=f"Failed to download audio after {max_retries} attempts: {str(e)}")
                        logger.warning(f"Download attempt {retry_count} failed: {str(e)}")
                        time.sleep(2)  # Wait before retrying
            except Exception as e:
                logger.error(f"Error downloading audio: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error downloading audio: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail="No download URL was obtained from the conversion process")

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

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT) 