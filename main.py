import os
import uuid
import hmac
import hashlib
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024

# ---------------------------------------------------------------------------
# Auth – HMAC signed tokens (shared secret between Django & media server)
# ---------------------------------------------------------------------------
# Set the same secret in your Django backend to generate upload tokens.
SHARED_SECRET = os.environ.get("MEDIA_SERVER_SECRET", "")
if not SHARED_SECRET:
    raise RuntimeError(
        "MEDIA_SERVER_SECRET env variable is required. "
        "Set the same value in your Django backend to sign upload tokens."
    )

TOKEN_EXPIRY_SECONDS = int(os.environ.get("TOKEN_EXPIRY_SECONDS", "900"))  # 15 min


def verify_upload_token(token: str):
    """
    Verify an HMAC-signed upload token.

    Token format:  <timestamp>.<hex-signature>

    Your Django backend generates it like this:

        import hmac, hashlib, time
        SHARED_SECRET = "same-secret-as-media-server"

        def generate_upload_token():
            ts = str(int(time.time()))
            sig = hmac.new(
                SHARED_SECRET.encode(), ts.encode(), hashlib.sha256
            ).hexdigest()
            return f"{ts}.{sig}"
    """
    if not token:
        raise HTTPException(status_code=401, detail="Upload token is required.")

    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Malformed token.")

    timestamp_str, signature = parts

    # 1. Check expiry
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed token.")

    if time.time() - timestamp > TOKEN_EXPIRY_SECONDS:
        raise HTTPException(status_code=401, detail="Token has expired.")

    # 2. Verify HMAC signature
    expected_sig = hmac.new(
        SHARED_SECRET.encode(), timestamp_str.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid token.")


app = FastAPI(title="Media Server", version="1.0.0")

# ---------------------------------------------------------------------------
# CORS – allow your frontend & backend to talk to this server
# In production, replace "*" with your actual frontend/backend origins.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# POST /upload  –  (protected by signed token)
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    token: str = Query(..., description="HMAC-signed upload token from your backend"),
):
    verify_upload_token(token)

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
    image_url = f"{request.base_url}media/{unique_name}"

    return {"url": image_url, "filename": unique_name}


# ---------------------------------------------------------------------------
# GET /media/{filename}  –  Serve a stored image (public)
# ---------------------------------------------------------------------------
@app.get("/media/{filename}")
async def get_image(filename: str):
    file_path = MEDIA_DIR / filename

    if not file_path.resolve().is_relative_to(MEDIA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")

    return FileResponse(file_path)


# ---------------------------------------------------------------------------
# DELETE /media/{filename}  –  (protected by signed token)
# ---------------------------------------------------------------------------
@app.delete("/media/{filename}")
async def delete_image(
    filename: str,
    token: str = Query(..., description="HMAC-signed upload token from your backend"),
):
    verify_upload_token(token)

    file_path = MEDIA_DIR / filename

    if not file_path.resolve().is_relative_to(MEDIA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")

    os.remove(file_path)
    return {"detail": f"Deleted {filename}"}


# ---------------------------------------------------------------------------
# GET /media  –  List all stored images (public, handy for debugging)
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