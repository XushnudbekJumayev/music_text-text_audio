from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
import whisper
import os
import tempfile
import logging
from datetime import datetime
import subprocess
import json
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Media Processor Service", version="1.0.0")

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
MINIO_URL = os.getenv("MINIO_URL")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
TEMP_FILES_DIR = "/app/temp_files"

# Ensure temp directory exists
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

# Load Whisper model
logger.info("Loading Whisper model...")
model = whisper.load_model("base")
logger.info("Whisper model loaded successfully")

def extract_audio_info(file_path: str) -> dict:
    """Extract audio information using ffprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"ffprobe failed: {result.stderr}")
            return {}

        info = json.loads(result.stdout)
        return info
    except Exception as e:
        logger.error(f"Error extracting audio info: {str(e)}")
        return {}

def convert_to_audio(input_path: str, output_path: str) -> bool:
    """Convert video to audio using ffmpeg"""
    try:
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vn',  # No video
            '-acodec', 'mp3',
            '-ab', '192k',  # Audio bitrate
            '-ar', '44100',  # Sample rate
            '-y',  # Overwrite output file
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr}")
            return False

        return True
    except Exception as e:
        logger.error(f"Error converting to audio: {str(e)}")
        return False

def transcribe_audio(file_path: str) -> dict:
    """Transcribe audio using Whisper"""
    try:
        logger.info(f"Starting transcription for: {file_path}")
        result = model.transcribe(file_path)

        transcription = {
            "text": result["text"],
            "language": result["language"],
            "segments": result["segments"]
        }

        logger.info(f"Transcription completed. Language: {result['language']}")
        return transcription
    except Exception as e:
        logger.error(f"Error during transcription: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "media-processor", "timestamp": datetime.now().isoformat()}

@app.post("/process-media")
async def process_media(
    file: UploadFile = File(...),
    job_id: str = Form(...),
    filename: str = Form(...)
):
    """Process media file and extract text"""
    temp_input_path = None
    temp_audio_path = None

    try:
        logger.info(f"Processing media file: {filename} (Job ID: {job_id})")

        # Validate file size (150MB max)
        file_size = 0
        await file.seek(0)
        content = await file.read()
        file_size = len(content)

        if file_size > 150 * 1024 * 1024:  # 150MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 150MB limit"
            )

        # Save uploaded file temporarily
        temp_input_path = os.path.join(TEMP_FILES_DIR, f"{job_id}_{filename}")

        with open(temp_input_path, "wb") as f:
            f.write(content)

        # Extract file info
        file_info = extract_audio_info(temp_input_path)

        # Determine if we need to convert the file
        audio_path = temp_input_path
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''

        # If it's a video file, convert to audio
        if file_extension in ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm']:
            temp_audio_path = os.path.join(TEMP_FILES_DIR, f"{job_id}_audio.mp3")

            if not convert_to_audio(temp_input_path, temp_audio_path):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to convert video to audio"
                )

            audio_path = temp_audio_path

        # Transcribe audio
        transcription = transcribe_audio(audio_path)

        # Here you would typically save the result to database and MinIO
        # For now, we'll return the result directly

        result = {
            "job_id": job_id,
            "filename": filename,
            "file_size": file_size,
            "file_info": file_info,
            "transcription": transcription,
            "status": "completed",
            "processed_at": datetime.now().isoformat()
        }

        logger.info(f"Media processing completed for job: {job_id}")
        return result

    except Exception as e:
        logger.error(f"Error processing media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Media processing failed: {str(e)}"
        )

    finally:
        # Clean up temporary files
        if temp_input_path and os.path.exists(temp_input_path):
            os.remove(temp_input_path)
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

@app.get("/supported-formats")
async def get_supported_formats():
    """Get list of supported audio/video formats"""
    return {
        "audio_formats": [
            "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a"
        ],
        "video_formats": [
            "mp4", "avi", "mov", "mkv", "flv", "wmv", "webm"
        ],
        "max_file_size": "150MB"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
