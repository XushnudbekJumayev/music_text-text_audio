from fastapi import FastAPI, HTTPException, status, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import tempfile
import logging
from datetime import datetime
from gtts import gTTS
import pyttsx3
from typing import Optional
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import traceback
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Text-to-Speech Service", version="1.0.0")

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
MINIO_URL = os.getenv("MINIO_URL")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
TEMP_FILES_DIR = "/app/temp_files"

# Ensure temp directory exists
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

# Thread pool for TTS processing
executor = ThreadPoolExecutor(max_workers=4)

class TTSRequest(BaseModel):
    job_id: str
    text: str
    voice_type: str = "male"  # male or female
    filename: Optional[str] = None
    language: str = "en"
    download_path: Optional[str] = None  # User specified download path

class TTSResponse(BaseModel):
    job_id: str
    filename: str
    file_path: str
    status: str
    processed_at: str
    download_url: str  # URL to download the file

def get_default_download_path():
    """Get default download path (Downloads folder)"""
    home = Path.home()
    downloads_path = home / "Downloads"

    # Create Downloads folder if it doesn't exist
    downloads_path.mkdir(exist_ok=True)
    return str(downloads_path)

def copy_file_to_destination(source_path: str, destination_folder: str, filename: str) -> str:
    """Copy file from temp location to destination folder"""
    try:
        # Ensure destination folder exists
        Path(destination_folder).mkdir(parents=True, exist_ok=True)

        destination_path = os.path.join(destination_folder, filename)
        shutil.copy2(source_path, destination_path)

        logger.info(f"File copied to: {destination_path}")
        return destination_path

    except Exception as e:
        logger.error(f"Error copying file to destination: {str(e)}")
        raise

def generate_gtts_speech(text: str, language: str = "en", slow: bool = False) -> bytes:
    """Generate speech using gTTS"""
    try:
        tts = gTTS(text=text, lang=language, slow=slow)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tts.save(tmp_file.name)

            # Read the file content
            with open(tmp_file.name, "rb") as f:
                audio_data = f.read()

            # Clean up
            os.unlink(tmp_file.name)

            return audio_data
    except Exception as e:
        logger.error(f"Error generating gTTS speech: {str(e)}")
        traceback.print_exc()
        raise

def generate_pyttsx3_speech(text: str, voice_type: str = "male") -> bytes:
    """Generate speech using pyttsx3"""
    try:
        engine = pyttsx3.init()

        # Configure voice
        voices = engine.getProperty('voices')
        if voices:
            # Try to select voice based on type
            selected_voice = None
            for voice in voices:
                voice_name = voice.name.lower()
                if voice_type == "female" and any(word in voice_name for word in ["female", "woman", "zira", "susan", "anna"]):
                    selected_voice = voice.id
                    break
                elif voice_type == "male" and any(word in voice_name for word in ["male", "man", "david", "mark", "james"]):
                    selected_voice = voice.id
                    break

            if selected_voice:
                engine.setProperty('voice', selected_voice)
            elif voices:
                # Fallback to first available voice
                engine.setProperty('voice', voices[0].id)

        # Configure speech rate and volume
        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 0.9)  # Volume level (0.0 to 1.0)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            engine.save_to_file(text, tmp_file.name)
            engine.runAndWait()

            # Read the file content
            with open(tmp_file.name, "rb") as f:
                audio_data = f.read()

            # Clean up
            os.unlink(tmp_file.name)

            return audio_data
    except Exception as e:
        logger.error(f"Error generating pyttsx3 speech: {str(e)}")
        raise

def run_tts_generation(text: str, voice_type: str, language: str = "en", use_gtts: bool = True) -> bytes:
    """Run TTS generation in thread"""
    try:
        if use_gtts:
            return generate_gtts_speech(text, language)
        else:
            return generate_pyttsx3_speech(text, voice_type)
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "text-to-speech", "timestamp": datetime.now().isoformat()}

@app.post("/generate-speech", response_model=TTSResponse)
async def generate_speech(request: TTSRequest):
    """Generate speech from text"""
    try:
        logger.info(f"Generating speech for job: {request.job_id}")

        # Validate voice type
        if request.voice_type not in ["male", "female"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice type must be 'male' or 'female'"
            )

        if len(request.text) > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text is too long (max 5000 characters)"
            )

        if not request.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text cannot be empty"
            )

        filename = request.filename or f"{request.job_id}.mp3"
        if not filename.endswith('.mp3'):
            filename += '.mp3'

        loop = asyncio.get_event_loop()

        try:
            # Try generating speech with gTTS (online)
            audio_data = await loop.run_in_executor(
                executor,
                run_tts_generation,
                request.text,
                request.voice_type,
                request.language,
                True  # use_gtts = True
            )
        except Exception as e:
            logger.warning(f"gTTS failed for job {request.job_id}. Falling back to pyttsx3... Error: {e}")
            # Fallback to pyttsx3 (offline)
            filename = filename.replace(".mp3", ".wav")  # Change file extension
            audio_data = await loop.run_in_executor(
                executor,
                run_tts_generation,
                request.text,
                request.voice_type,
                request.language,
                False  # use_gtts = False
            )

        # Save file to temp directory first
        temp_output_path = os.path.join(TEMP_FILES_DIR, filename)
        with open(temp_output_path, "wb") as f:
            f.write(audio_data)

        # Determine download path
        if request.download_path:
            download_folder = request.download_path
        else:
            download_folder = get_default_download_path()

        # Copy file to destination
        final_output_path = copy_file_to_destination(
            temp_output_path,
            download_folder,
            filename
        )

        result = TTSResponse(
            job_id=request.job_id,
            filename=filename,
            file_path=final_output_path,
            status="completed",
            processed_at=datetime.now().isoformat(),
            download_url=f"/download/{request.job_id}/{filename}"
        )

        logger.info(f"Speech generation completed for job: {request.job_id}")
        return result

    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech generation failed: {str(e)}"
        )

@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Download generated audio file"""
    try:
        file_path = os.path.join(TEMP_FILES_DIR, filename)

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Determine media type based on file extension
        media_type = "audio/mpeg" if filename.endswith('.mp3') else "audio/wav"

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )

@app.get("/supported-languages")
async def get_supported_languages():
    """Get list of supported languages for TTS"""
    return {
        "languages": {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
            "ar": "Arabic",
            "hi": "Hindi",
            "tr": "Turkish",
            "pl": "Polish",
            "nl": "Dutch",
            "sv": "Swedish",
            "da": "Danish",
            "no": "Norwegian",
            "fi": "Finnish"
        },
        "voice_types": ["male", "female"],
        "max_text_length": 5000
    }

@app.get("/files/{job_id}")
async def get_file_info(job_id: str):
    """Get information about generated files for a job"""
    try:
        files = []
        for filename in os.listdir(TEMP_FILES_DIR):
            if filename.startswith(job_id):
                file_path = os.path.join(TEMP_FILES_DIR, filename)
                file_stats = os.stat(file_path)
                files.append({
                    "filename": filename,
                    "size": file_stats.st_size,
                    "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    "download_url": f"/download/{job_id}/{filename}"
                })

        return {"job_id": job_id, "files": files}

    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file info: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
