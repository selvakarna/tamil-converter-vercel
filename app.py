from flask import Flask, render_template, request, jsonify, send_file
import os
from google.cloud import vision
from googletrans import Translator
from gtts import gTTS
import tempfile
import uuid
from werkzeug.middleware.proxy_fix import ProxyFix
import io

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Initialize Google Cloud Vision client
# NOTE: GOOGLE_APPLICATION_CREDENTIALS env var is auto-loaded by the client
client = vision.ImageAnnotatorClient()

# Initialize translator
translator = Translator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})

    # Save uploaded file
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.jpg")
    file.save(temp_path)

    # OCR: Extract text using Google Cloud Vision
    try:
        with io.open(temp_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        detected_text = texts[0].description if texts else ""
    except Exception as e:
        os.remove(temp_path)
        return jsonify({'error': f'OCR failed: {str(e)}'})

    if not detected_text:
        os.remove(temp_path)
        return jsonify({'error': 'No text detected in image'})

    # Translate to Tamil
    try:
        translation = translator.translate(detected_text, src='auto', dest='ta')
        tamil_text = translation.text
    except Exception as e:
        os.remove(temp_path)
        return jsonify({'error': f'Translation failed: {str(e)}'})

    # Generate audio
    try:
        tts = gTTS(text=tamil_text, lang='ta', slow=False)
        audio_path = os.path.join(temp_dir, f"{uuid.uuid4()}.mp3")
        tts.save(audio_path)
    except Exception as e:
        os.remove(temp_path)
        return jsonify({'error': f'Audio generation failed: {str(e)}'})

    # Clean up temp image
    os.remove(temp_path)

    return jsonify({
        'original_text': detected_text,
        'tamil_text': tamil_text,
        'audio_path': audio_path
    })

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
