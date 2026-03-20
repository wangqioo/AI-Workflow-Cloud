"""Text-to-Speech service.

Ported from v0.7.5 tts_server.py (port 8088).
Cloud mode: uses cloud TTS API (edge-tts as default, extensible to AWS Polly / Azure / Google).
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

VOICES = {
    "xiaoxiao": {"id": "zh-CN-XiaoxiaoNeural", "lang": "zh", "gender": "female"},
    "yunxi": {"id": "zh-CN-YunxiNeural", "lang": "zh", "gender": "male"},
    "xiaoyi": {"id": "zh-CN-XiaoyiNeural", "lang": "zh", "gender": "female"},
    "yunjian": {"id": "zh-CN-YunjianNeural", "lang": "zh", "gender": "male"},
    "jenny": {"id": "en-US-JennyNeural", "lang": "en", "gender": "female"},
    "guy": {"id": "en-US-GuyNeural", "lang": "en", "gender": "male"},
    "aria": {"id": "en-US-AriaNeural", "lang": "en", "gender": "female"},
    "nanami": {"id": "ja-JP-NanamiNeural", "lang": "ja", "gender": "female"},
}


def list_voices() -> list[dict]:
    return [{"name": k, **v} for k, v in VOICES.items()]


async def synthesize(text: str, voice: str = "xiaoxiao") -> dict:
    """Synthesize speech. Returns path to audio file."""
    voice_info = VOICES.get(voice, VOICES["xiaoxiao"])
    voice_id = voice_info["id"]

    try:
        import edge_tts

        outfile = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        outfile.close()

        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(outfile.name)

        return {
            "voice": voice,
            "voice_id": voice_id,
            "audio_path": outfile.name,
            "format": "mp3",
            "text_length": len(text),
        }
    except ImportError:
        return {"error": "edge-tts not installed. Install with: pip install edge-tts"}
    except Exception as e:
        return {"error": str(e)}
