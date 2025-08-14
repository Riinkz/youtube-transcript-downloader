from __future__ import annotations

import io
import logging
import os
import zipfile
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import LanguageInfo, TranscriptRequest, TranscriptResponse
from .services import (
    fetch_transcript,
    fetch_video_title,
    get_available_transcripts,
    parse_video_id,
    expand_inputs_to_video_ids,
    sanitize_filename,
    unique_name,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("YT API key loaded? %s", bool(os.getenv("YOUTUBE_API_KEY") or os.getenv("YT_API_KEY")))


def create_app() -> FastAPI:
    app = FastAPI(title="YouTube Transcript Service", version="1.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"

    @app.post("/api/transcript", response_model=TranscriptResponse)
    async def transcript_endpoint(request: TranscriptRequest) -> TranscriptResponse:
        try:
            video_id = parse_video_id(str(request.url))
        except ValueError as ex:
            logger.error(f"Invalid URL provided: {request.url}")
            raise HTTPException(status_code=400, detail=str(ex))

        languages_raw = get_available_transcripts(video_id)
        languages = [LanguageInfo(**lang) for lang in languages_raw]

        try:
            transcript_text, used_language = fetch_transcript(
                video_id,
                language_code=request.language,
                include_timestamps=bool(request.include_timestamps),
            )
        except ValueError as ex:
            logger.error(f"Error while fetching transcript: {ex}")
            raise HTTPException(status_code=404, detail=str(ex))

        title = fetch_video_title(video_id)

        return TranscriptResponse(
            transcript=transcript_text,
            language_used=used_language,
            available_languages=languages,
            video_title=title,
        )

    @app.post("/api/bulk-transcripts")
    async def bulk_transcripts_endpoint(payload: dict):
        """Bulk transcript download endpoint. Returns ZIP file."""
        logger.info(f"Bulk request payload: {payload}")
        
        urls: List[str] = payload.get("urls") or []
        playlist_url: Optional[str] = payload.get("playlist_url")
        channel_url: Optional[str] = payload.get("channel_url")
        limit: int = int(payload.get("limit") or 50)
        language: Optional[str] = payload.get("language")
        include_timestamps: bool = bool(payload.get("include_timestamps") or False)

        logger.info(f"Processing: {len(urls)} URLs, playlist={playlist_url}, channel={channel_url}, limit={limit}")
        
        video_ids, expansion_errors = expand_inputs_to_video_ids(
            urls=urls, playlist_url=playlist_url, channel_url=channel_url, limit=limit
        )

        logger.info(f"Expansion result: {len(video_ids)} videos, {len(expansion_errors)} errors")
        if expansion_errors:
            logger.warning(f"Expansion errors: {expansion_errors}")

        if not video_ids:
            msg = "No videos to process. Provide valid video URLs or set YOUTUBE_API_KEY for playlist/channel expansion."
            logger.error(f"No videos found. Expansion errors: {expansion_errors}")
            return JSONResponse(status_code=400, content={"detail": msg, "expansion_errors": expansion_errors})

        buffer = io.BytesIO()
        used_names: dict[str, int] = {}
        errors: List[str] = []

        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for vid in video_ids:
                try:
                    text, used_lang = fetch_transcript(
                        vid, language_code=language, include_timestamps=include_timestamps
                    )
                    title = fetch_video_title(vid) or vid
                    base = sanitize_filename(title)
                    unique = unique_name(base, used_names)
                    filename = f"{unique}.txt"
                    zf.writestr(filename, text)
                except Exception as ex:
                    errors.append(f"{vid}: {ex}")

            if expansion_errors:
                errors.extend([f"[expand] {e}" for e in expansion_errors])

            if errors:
                zf.writestr("errors_report.txt", "\n".join(errors))

        buffer.seek(0)
        headers = {"Content-Disposition": 'attachment; filename="transcripts.zip"'}
        return StreamingResponse(buffer, media_type="application/zip", headers=headers)
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir), html=False), name="static")

        @app.get("/", include_in_schema=False)
        def spa_index():
            return FileResponse(frontend_dir / "index.html")

        logger.info(f"Serving static files from {frontend_dir}")
    else:
        logger.warning(
            f"Frontend directory {frontend_dir} does not exist; only API will be served"
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
