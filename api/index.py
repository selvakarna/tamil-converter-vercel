"""
Tamil Text → Speech converter (Google Cloud TTS) — Vercel-ready Flask app.
"""

import io
import json
import os

from flask import Flask, jsonify, render_template_string, request, send_file
from google.cloud import texttospeech
from google.oauth2 import service_account

# ---------------------------------------------------------------------------
# 1. Google credentials — works BOTH on Vercel and locally
# ---------------------------------------------------------------------------
_raw_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

credentials = None
if _raw_creds.startswith("{"):
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(_raw_creds),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

tts_client = (
    texttospeech.TextToSpeechClient(credentials=credentials)
    if credentials
    else texttospeech.TextToSpeechClient()
)

app = Flask(__name__)

MAX_BYTES = 4800  # Google TTS limit is ~5000 bytes per request

# ---------------------------------------------------------------------------
# 2. Minimal frontend
# ---------------------------------------------------------------------------
PAGE = """
<!doctype html>
<html lang="ta">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>தமிழ் Text → Speech</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, "Noto Sans Tamil", sans-serif; background:#0f172a;
         color:#e2e8f0; min-height:100vh; display:flex; align-items:center;
         justify-content:center; margin:0; padding:24px; }
  .card { background:#1e293b; width:100%; max-width:560px; border-radius:16px;
          padding:28px; box-shadow:0 10px 40px rgba(0,0,0,.4); }
  h1 { margin:0 0 6px; font-size:22px; }
  p.sub { margin:0 0 20px; color:#94a3b8; font-size:14px; }
  textarea { width:100%; min-height:130px; background:#0f172a; color:#e2e8f0;
             border:1px solid #334155; border-radius:10px; padding:12px;
             font-size:16px; resize:vertical; }
  .row { display:flex; gap:10px; margin:12px 0 16px; }
  select, input[type=number] { flex:1; background:#0f172a; color:#e2e8f0;
             border:1px solid #334155; border-radius:10px; padding:10px; font-size:14px; }
  button { width:100%; background:#22c55e; border:0; color:#052e16; font-weight:700;
           font-size:16px; padding:13px; border-radius:10px; cursor:pointer; }
  button:disabled { opacity:.6; cursor:wait; }
  .status { min-height:20px; font-size:14px; color:#f87171; margin-top:10px; }
  audio, a.dl { width:100%; margin-top:14px; }
  a.dl { display:none; text-align:center; background:#334155; color:#e2e8f0;
         padding:10px; border-radius:10px; text-decoration:none; }
</style>
</head>
<body>
  <div class="card">
    <h1>தமிழ் Text → Speech 🔊</h1>
    <p class="sub">Google Cloud TTS • ta-IN</p>
    <textarea id="text" placeholder="தமிழ் உரையை இங்கே தட்டச்சு செய்யவும்…">வணக்கம்! இது ஒரு சோதனை.</textarea>
    <div class="row">
      <select id="voice">
        <option value="ta-IN-Standard-A">Voice A</option>
        <option value="ta-IN-Standard-B">Voice B</option>
        <option value="ta-IN-Standard-C">Voice C</option>
        <option value="ta-IN-Standard-D">Voice D</option>
      </select>
      <input id="rate" type="number" step="0.05" min="0.25" max="4" value="1" title="Speaking rate">
    </div>
    <button id="go" onclick="convert()">Convert &amp; Play ▶</button>
    <div class="status" id="status"></div>
    <audio id="player" controls style="display:none"></audio>
    <a class="dl" id="dl" download="tamil-speech.mp3">⬇ Download MP3</a>
  </div>
<script>
async function convert() {
  var btn = document.getElementById('go'),
      status = document.getElementById('status'),
      player = document.getElementById('player'),
      dl = document.getElementById('dl');
  btn.disabled = true; status.textContent = '⏳ Generating audio…';
  try {
    var res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text:  document.getElementById('text').value,
        voice: document.getElementById('voice').value,
        rate:  parseFloat(document.getElementById('rate').value) || 1
      })
    });
    if (!res.ok) {
      var e = await res.json().catch(function () { return {}; });
      throw new Error(e.error || res.statusText);
    }
    var blob = await res.blob();
    var url = URL.createObjectURL(blob);
    player.src = url; player.style.display = 'block'; player.play();
    dl.href = url; dl.style.display = 'block';
    status.textContent = '';
  } catch (err) {
    status.textContent = '❌ ' + err.message;
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE)


# ---------------------------------------------------------------------------
# 3. API — POST /api/tts
# ---------------------------------------------------------------------------
@app.route("/api/tts", methods=["POST"])
def synthesize():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify(error="Please enter some Tamil text."), 400
    if len(text.encode("utf-8")) > MAX_BYTES:
        return jsonify(error="Text too long (max ~4800 bytes per request)."), 400

    voice_name = data.get("voice") or "ta-IN-Standard-A"
    try:
        speaking_rate = float(data.get("rate", 1.0))
    except (TypeError, ValueError):
        speaking_rate = 1.0
    speaking_rate = min(max(speaking_rate, 0.25), 4.0)

    try:
        response = tts_client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(
                language_code="ta-IN",
                name=voice_name,
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speaking_rate,
            ),
        )
    except Exception as exc:
        return jsonify(error="TTS failed: {}".format(exc)), 500

    return send_file(
        io.BytesIO(response.audio_content),
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="tamil-speech.mp3",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
