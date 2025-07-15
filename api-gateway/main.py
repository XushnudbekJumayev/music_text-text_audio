from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import uuid
import os
from typing import Optional
import aiofiles
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MUSIC audio converter gateway", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
MEDIA_PROCESSOR_URL = os.getenv("MEDIA_PROCESSOR_URL", "http://media-processor:8001")
TEXT_TO_SPEECH_URL = os.getenv("TEXT_TO_SPEECH_URL", "http://text-to-speech:8002")
TEMP_FILES_DIR = "/app/temp_files"

# Ensure temp directory exists
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

# Request models
class TextToAudioRequest(BaseModel):
    text: str
    voice_type: str = "male"  # male or female
    filename: Optional[str] = None

class MediaToTextResponse(BaseModel):
    id: str
    filename: str
    file_upload: str
    status: str
    created_at: str

class TextToAudioResponse(BaseModel):
    id: str
    filename: str
    audio_url: str
    voice_type: str
    status: str

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Media to text endpoint
@app.post("/api/v1/media-to-text", response_model=MediaToTextResponse)
async def media_to_text(file: UploadFile = File(...)):
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())

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

        # Generate filename if not provided
        filename = file.filename or f"audio_{job_id[:8]}.mp3"

        # Save file temporarily
        temp_file_path = os.path.join(TEMP_FILES_DIR, f"{job_id}_{filename}")

        async with aiofiles.open(temp_file_path, "wb") as f:
            await f.write(content)

        # Send to media processor
        async with httpx.AsyncClient() as client:
            with open(temp_file_path, "rb") as f:
                files = {"file": (filename, f, file.content_type)}
                data = {"job_id": job_id, "filename": filename}

                response = await client.post(
                    f"{MEDIA_PROCESSOR_URL}/process-media",
                    files=files,
                    data=data,
                    timeout=300.0
                )

        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Media processing failed"
            )

        result = response.json()

        return MediaToTextResponse(
            id=job_id,
            filename=filename,
            file_upload=temp_file_path,
            status="completed",
            created_at=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error in media_to_text: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Text to audio endpoint
@app.post("/api/v1/text-to-audio", response_model=TextToAudioResponse)
async def text_to_audio(request: TextToAudioRequest):
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Validate voice type
        if request.voice_type not in ["male", "female"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice type must be 'male' or 'female'"
            )

        # Generate filename if not provided
        if not request.filename:
            # Generate random filename with 10 characters
            import random
            import string
            random_name = ''.join(random.choices(string.ascii_lowercase, k=10))
            filename = f"{random_name}.mp3"
        else:
            filename = request.filename if request.filename.endswith('.mp3') else f"{request.filename}.mp3"

        # Send to text-to-speech service
        async with httpx.AsyncClient() as client:
            payload = {
                "job_id": job_id,
                "text": request.text,
                "voice_type": request.voice_type,
                "filename": filename
            }

            response = await client.post(
                f"{TEXT_TO_SPEECH_URL}/generate-speech",
                json=payload,
                timeout=300.0
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Text-to-speech generation failed"
            )

        result = response.json()

        return TextToAudioResponse(
            id=job_id,
            filename=filename,
            audio_url=f"/api/v1/download/{job_id}",
            voice_type=request.voice_type,
            status="completed"
        )

    except Exception as e:
        logger.error(f"Error in text_to_audio: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Download endpoint
@app.get("/api/v1/download/{job_id}")
async def download_file(job_id: str):
    try:
        # This would typically fetch from MinIO storage
        # For now, we'll implement a simple file serving mechanism

        # In a production environment, you would:
        # 1. Query database for job_id and file location
        # 2. Generate signed URL from MinIO
        # 3. Return file or redirect to signed URL

        # Placeholder implementation
        file_path = os.path.join(TEMP_FILES_DIR, f"{job_id}.mp3")

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        return FileResponse(
            file_path,
            media_type="audio/mpeg",
            filename=f"{job_id}.mp3"
        )

    except Exception as e:
        logger.error(f"Error in download_file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Get job status endpoint
@app.get("/api/v1/status/{job_id}")
async def get_job_status(job_id: str):
    try:
        # This would query the database for job status
        # Placeholder implementation
        return {
            "id": job_id,
            "status": "completed",
            "created_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in get_job_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
