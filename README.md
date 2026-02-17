# 🖼️ Media Server (Homelab)

A self-hosted image storage server — like a mini Cloudinary. Built with **FastAPI**.

## How it works

```
Frontend  ──(image)──►  Media Server  ──(stores on disk)
          ◄──(url)────
Frontend  ──(url)──►  Backend  ──(saves url in DB)
```

1. **Frontend uploads an image** via `POST /upload`
2. **Media server stores it** on disk and returns a public URL
3. **Frontend sends the URL** to the backend, which saves it in the database
4. **Anyone with the URL** can view the image via `GET /media/{filename}`

## Setup

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server runs at `http://localhost:8000`. Images are stored in the `media/` folder.

## API Endpoints

### Upload an image
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/your/image.png"
```
**Response:**
```json
{
  "url": "http://localhost:8000/media/a1b2c3d4.png",
  "filename": "a1b2c3d4.png"
}
```

### Get an image
```
GET http://localhost:8000/media/{filename}
```
Returns the image file directly — use the URL in `<img>` tags.

### List all images
```
GET http://localhost:8000/media
```

### Delete an image
```bash
curl -X DELETE http://localhost:8000/media/{filename}
```

### Health check
```
GET http://localhost:8000/
```

## Exposing to the internet

To make this accessible from your deployed frontend/backend, you can:

- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8000`
- **ngrok**: `ngrok http 8000`
- **Reverse proxy (Nginx/Caddy)**: point a domain to this server

## Frontend usage example (JavaScript)

```javascript
// Upload an image
const formData = new FormData();
formData.append("file", fileInput.files[0]);

const res = await fetch("http://your-media-server:8000/upload", {
  method: "POST",
  body: formData,
});

const { url } = await res.json();

// Now send `url` to your backend to store in the database
await fetch("http://your-backend/api/menu-item", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ name: "Burger", imageUrl: url }),
});
```