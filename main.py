import os
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Where images are saved on disk
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

# Allowed image extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}

# Max file size in bytes (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

app = FastAPI(title="Media Server", version="1.0.0")

# ---------------------------------------------------------------------------
# CORS – allow your frontend & backend to talk to this server
# In production, replace "*" with your actual frontend/backend origins.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # e.g. ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# POST /upload  –  Frontend sends an image, gets back a URL
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    # 1. Validate the file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. Read the file and check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024*1024)} MB.",
        )

    # 3. Generate a unique filename so nothing gets overwritten
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = MEDIA_DIR / unique_name

    # 4. Write to disk
    with open(save_path, "wb") as f:
        f.write(contents)

    # 5. Build the public URL for this image
    #    request.base_url gives us e.g. "http://localhost:8000/"
    image_url = f"{request.base_url}media/{unique_name}"

    return {"url": image_url, "filename": unique_name}


# ---------------------------------------------------------------------------
# GET /media/{filename}  –  Serve a stored image by its filename
# ---------------------------------------------------------------------------
@app.get("/media/{filename}")
async def get_image(filename: str):
    file_path = MEDIA_DIR / filename

    # Prevent directory traversal attacks
    if not file_path.resolve().is_relative_to(MEDIA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")

    return FileResponse(file_path)


# ---------------------------------------------------------------------------
# DELETE /media/{filename}  –  Delete a stored image
# ---------------------------------------------------------------------------
@app.delete("/media/{filename}")
async def delete_image(filename: str):
    file_path = MEDIA_DIR / filename

    if not file_path.resolve().is_relative_to(MEDIA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")

    os.remove(file_path)
    return {"detail": f"Deleted {filename}"}


# ---------------------------------------------------------------------------
# GET /media  –  List all stored images (handy for debugging)
# ---------------------------------------------------------------------------
@app.get("/media")
async def list_images(request: Request):
    files = [f.name for f in MEDIA_DIR.iterdir() if f.is_file()]
    images = [
        {"filename": name, "url": f"{request.base_url}media/{name}"}
        for name in files
    ]
    return {"count": len(images), "images": images}


# ---------------------------------------------------------------------------
# GET /  –  Health check
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok", "service": "Media Server"}