"""Unified router for utility services.

Consolidates: translate, crawler, TTS, email (from v0.7.5 ports 8088-8093).
"""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..auth.dependencies import get_current_user
from ..models.user import User
from . import crawler, email_svc, files, system_monitor, translate, tts

router = APIRouter(tags=["services"])


# ---- Translation ----

class TranslateRequest(BaseModel):
    text: str
    source: str = "auto"
    target: str = "en"


class DetectRequest(BaseModel):
    text: str


@router.post("/api/translate")
async def translate_text(
    body: TranslateRequest,
    user: User = Depends(get_current_user),
):
    return await translate.translate_text(body.text, body.source, body.target)


@router.get("/api/translate/languages")
async def list_languages():
    return {"languages": translate.SUPPORTED_LANGUAGES}


@router.post("/api/translate/detect")
async def detect_language(body: DetectRequest):
    lang = translate.detect_language(body.text)
    return {"language": lang, "name": translate.SUPPORTED_LANGUAGES.get(lang, lang)}


# ---- Crawler ----

class CrawlRequest(BaseModel):
    url: str
    max_chars: int = 8000


class RssRequest(BaseModel):
    url: str


@router.post("/api/crawl")
async def crawl_page(
    body: CrawlRequest,
    user: User = Depends(get_current_user),
):
    return await crawler.crawl_page(body.url, body.max_chars)


@router.post("/api/rss")
async def parse_rss(
    body: RssRequest,
    user: User = Depends(get_current_user),
):
    return await crawler.parse_rss(body.url)


# ---- TTS ----

class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "xiaoxiao"


@router.get("/api/tts/voices")
async def list_voices():
    return {"voices": tts.list_voices()}


@router.post("/api/tts/synthesize")
async def synthesize_speech(
    body: SynthesizeRequest,
    user: User = Depends(get_current_user),
):
    result = await tts.synthesize(body.text, body.voice)
    if "error" in result:
        return result
    # Return audio file
    return FileResponse(
        result["audio_path"],
        media_type="audio/mpeg",
        filename=f"tts_{body.voice}.mp3",
    )


# ---- Email ----

class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    html: bool = False


@router.get("/api/email/inbox")
async def get_inbox(
    limit: int = 20,
    user: User = Depends(get_current_user),
):
    emails = await email_svc.get_inbox(limit)
    return {"emails": emails, "count": len(emails)}


@router.get("/api/email/{email_id}")
async def get_email(
    email_id: str,
    user: User = Depends(get_current_user),
):
    email = await email_svc.get_email(email_id)
    if not email:
        return {"error": "Email not found"}
    return email


@router.post("/api/email/send")
async def send_email(
    body: SendEmailRequest,
    user: User = Depends(get_current_user),
):
    return await email_svc.send_email(body.to, body.subject, body.body, body.html)


@router.post("/api/email/{email_id}/summarize")
async def summarize_email(
    email_id: str,
    user: User = Depends(get_current_user),
):
    return await email_svc.summarize_email(email_id)


# ---- File Transfer ----

@router.post("/api/files/upload")
async def upload_file_endpoint(
    file: UploadFile = File(...),
    category: str = "general",
    user: User = Depends(get_current_user),
):
    content = await file.read()
    return await files.upload_file(
        user.id, file.filename or "untitled", content, category
    )


@router.get("/api/files")
async def list_files(
    category: str | None = None,
    user: User = Depends(get_current_user),
):
    file_list = await files.list_files(user.id, category)
    return {"files": file_list, "count": len(file_list)}


@router.get("/api/files/stats")
async def file_stats(user: User = Depends(get_current_user)):
    return await files.get_stats(user.id)


@router.get("/api/files/{file_id}")
async def download_file(
    file_id: str,
    user: User = Depends(get_current_user),
):
    result = await files.download_file(user.id, file_id)
    if not result:
        return {"error": "File not found"}
    content, filename, mime_type = result
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    user: User = Depends(get_current_user),
):
    ok = await files.delete_file(user.id, file_id)
    if not ok:
        return {"error": "File not found"}
    return {"status": "deleted"}


# ---- System Monitor ----

@router.get("/api/system/status")
async def system_status(user: User = Depends(get_current_user)):
    return await system_monitor.get_system_status()


@router.get("/api/system/quick")
async def system_quick(user: User = Depends(get_current_user)):
    return await system_monitor.get_quick_stats()
