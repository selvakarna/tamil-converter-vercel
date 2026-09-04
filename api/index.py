"""
Tamil Text & Audio Converter — Vercel-ready Flask backend.

Pipeline:  Image (upload/camera)  ->  Google Vision OCR  ->  Translate v3 (-> ta)
           ->  Google Cloud TTS (MP3)  ->  returned as base64 in JSON

Structure:
  project/
  ├── api/
  │   ├── index.py            <- this file
  │   ├── templates/index.html
  │   └── static/{script.js, style.css}
  ├── requirements.txt
  └── vercel.json

Why no files on disk?
  Vercel serverless functions have an EPHEMERAL filesystem. Audio is returned
  as base64 inside the JSON response; the browser plays/downloads it directly.
"""

import base64
import json
import os

from flask import Flask, jsonify, render_template, request
from google.cloud import texttospeech, translate, vision
from google.oauth2 import service_account

# ---------------------------------------------------------------------------
# 1. Credentials — reads the JSON *itself* from the env var (Vercel style),
#    or falls back to a file path (local dev: GOOGLE_APPLICATION_CREDENTIALS=...json)
# ---------------------------------------------------------------------------
_raw_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

credentials = None
project_id = None
if _raw_creds.startswith("{"):
    _creds_info = json.loads(_raw_creds)
    project_id = _creds_info.get("project_id")  # needed for Translate v3
    credentials = service_account.Credentials.from_service_account_info(
        _creds_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

_vision = (
    vision.ImageAnnotatorClient(credentials=credentials)
    if credentials else vision.ImageAnnotatorClient()
)
_translator = (
    translate.TranslationServiceClient(credentials=credentials)
    if credentials else translate.TranslationServiceClient()
)
_tts = (
    texttospeech.TextToSpeechClient(credentials=credentials)
    if credentials else texttospeech.TextToSpeechClient()
)

# Translate v3 needs: projects/<project_id>/locations/global
PARENT = f"projects/{project_id}/locations/global" if project_id else None

app = Flask(__name__)  # auto-finds api/templates/ and api/static/

MAX_IMAGE_BYTES = 4 * 1024 * 1024   # Vercel request body limit is ~4.5 MB
TTS_CHUNK_BYTES = 4500              # TTS limit is ~5000 bytes per request


# ---------------------------------------------------------------------------
# Helper: split long OCR text into TTS-safe chunks (sentence/line aware)
# ---------------------------------------------------------------------------
def _split_for_tts(text: str, max_bytes: int = TTS_CHUNK_BYTES):
    chunks, current = [], ""
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        while len(line.encode("utf-8")) > max_bytes:
            part = ""
            for word in line.split(" "):
                if part and len((part + " " + word).encode("utf-8")) > max_bytes:
                    break
                part = (part + " " + word).strip()
            chunks.append(part)
            line = line[len(part):].strip()
        if not line:
            continue
        combined = (current + "\n" + line) if current else line
        if len(combined.encode("utf-8")) > max_bytes:
            chunks.append(current)
            current = line
        else:
            current = combined
    if current:
        chunks.append(current)
    return chunks


def _synthesize_tamil(tamil_text: str) -> bytes:
    """Synthesize Tamil speech, chunking long text. Returns MP3 bytes."""
    audio_parts = []
    for chunk in _split_for_tts(tamil_text):
        try:
            voice = texttospeech.VoiceSelectionParams(
                language_code="ta-IN", name="ta-IN-Standard-A"
            )
            resp = _tts.synthesize_speech(
                input=texttospeech.SynthesisInput(text=chunk),
                voice=voice,
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                ),
            )
        except Exception:
            # Fallback: let Google pick any available ta-IN voice
            resp = _tts.synthesize_speech(
                input=texttospeech.SynthesisInput(text=chunk),
                voice=texttospeech.VoiceSelectionParams(language_code="ta-IN"),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                ),
            )
        audio_parts.append(resp.audio_content)
    return b"".join(audio_parts)


# ---------------------------------------------------------------------------
# 2. Frontend
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# 3. POST /process  (multipart: file=<image>)
#    Returns JSON: { original_text, tamil_text, audio_base64 }
# ---------------------------------------------------------------------------
@app.route("/process", methods=["POST"])
def process():
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify(error="No image uploaded."), 400

    image_bytes = uploaded.read()
    if not image_bytes:
        return jsonify(error="Empty file."), 400
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return jsonify(error="Image too large (max 4 MB)."), 400

    # -- 1) OCR — Vision auto-detects the script (en, te, hi, kn, ml, ...)
    try:
        ocr = _vision.document_text_detection(
            image=vision.Image(content=image_bytes)
        )
    except Exception as exc:
        return jsonify(error="OCR failed: {}".format(exc)), 500
    if ocr.error and ocr.error.message:
        return jsonify(error="OCR failed: " + ocr.error.message), 500

    original_text = (
        ocr.full_text_annotation.text.strip()
        if ocr.full_text_annotation and ocr.full_text_annotation.text else ""
    )
    if not original_text:
        return jsonify(error="No text found in the image."), 400

    # -- 2) Translate -> Tamil (source language auto-detected)
    if not PARENT:
        return jsonify(error="Missing project_id in service-account JSON."), 500
    try:
        result = _translator.translate_text(
            request={
                "parent": PARENT,
                "contents": [original_text],
                "mime_type": "text/plain",
                "target_language_code": "ta",
            }
        )
        tamil_text = (
            result.translations[0].translated_text if result.translations else ""
        )
    except Exception as exc:
        return jsonify(error="Translation failed: {}".format(exc)), 500
    if not tamil_text:
        return jsonify(error="Translation returned empty text."), 500

    # -- 3) Text-to-Speech -> MP3 (returned as base64, no files!)
    try:
        audio_bytes = _synthesize_tamil(tamil_text)
    except Exception as exc:
        return jsonify(error="TTS failed: {}".format(exc)), 500

    return jsonify(
        original_text=original_text,
        tamil_text=tamil_text,
        audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
    )


# Optional health check — handy for quick browser tests
@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="ok", project=project_id or "unknown")


if __name__ == "__main__":
    # Local dev only:  python api/index.py
    app.run(debug=True, port=5000)
