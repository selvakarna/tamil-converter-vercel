document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const cameraBtn = document.getElementById('camera-btn');
    const captureBtn = document.getElementById('capture-btn');
    const retakeBtn = document.getElementById('retake-btn');
    const previewImg = document.getElementById('preview-img');
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const processingDiv = document.getElementById('processing');
    const resultsDiv = document.getElementById('results');
    const originalText = document.getElementById('original-text');
    const tamilText = document.getElementById('tamil-text');
    const audioPlayer = document.getElementById('audio-player');
    const newConversionBtn = document.getElementById('new-conversion');
    const copyTamilBtn = document.getElementById('copy-tamil');
    const downloadAudioBtn = document.getElementById('download-audio');

    let currentAudioPath = '';

    // Upload button
    uploadBtn.addEventListener('click', function() {
        fileInput.click();
    });

    // File input change
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(event) {
                previewImg.src = event.target.result;
                previewImg.style.display = 'block';
                captureBtn.style.display = 'none';
                retakeBtn.style.display = 'none';
                uploadBtn.style.display = 'none';
                cameraBtn.style.display = 'inline-block';
                processImage(file);
            };
            reader.readAsDataURL(file);
        }
    });

    // Camera button
    cameraBtn.addEventListener('click', async function() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            video.srcObject = stream;
            video.style.display = 'block';
            previewImg.style.display = 'none';
            uploadBtn.style.display = 'none';
            cameraBtn.style.display = 'none';
            captureBtn.style.display = 'inline-block';
            retakeBtn.style.display = 'inline-block';
        } catch (err) {
            alert('Error accessing camera: ' + err.message);
        }
    });

    // Capture button
    captureBtn.addEventListener('click', function() {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        previewImg.src = canvas.toDataURL('image/jpeg');
        previewImg.style.display = 'block';
        video.style.display = 'none';
        captureBtn.style.display = 'none';

        // Stop camera stream
        const stream = video.srcObject;
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }

        // Convert canvas to blob and process
        canvas.toBlob(function(blob) {
            processImage(blob);
        }, 'image/jpeg');
    });

    // Retake button
    retakeBtn.addEventListener('click', function() {
        previewImg.style.display = 'none';
        video.style.display = 'block';
        captureBtn.style.display = 'inline-block';
        uploadBtn.style.display = 'inline-block';
        cameraBtn.style.display = 'inline-block';
        retakeBtn.style.display = 'none';
    });

    // Process image
    function processImage(file) {
        processingDiv.style.display = 'block';
        resultsDiv.style.display = 'none';

        const formData = new FormData();
        formData.append('file', file);

        fetch('/process', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            processingDiv.style.display = 'none';

            if (data.error) {
                alert('Error: ' + data.error);
                resetUI();
                return;
            }

            // Display results
            originalText.textContent = data.original_text;
            tamilText.textContent = data.tamil_text;

            // Play audio
            audioPlayer.src = '/' + data.audio_path;
            currentAudioPath = data.audio_path;

            resultsDiv.style.display = 'block';
        })
        .catch(error => {
            processingDiv.style.display = 'none';
            alert('Error: ' + error.message);
            resetUI();
        });
    }

    // Copy Tamil text
    copyTamilBtn.addEventListener('click', function() {
        navigator.clipboard.writeText(tamilText.textContent)
            .then(() => alert('Tamil text copied to clipboard!'))
            .catch(err => alert('Failed to copy: ' + err));
    });

    // Download audio
    downloadAudioBtn.addEventListener('click', function() {
        if (currentAudioPath) {
            window.location.href = '/download/' + currentAudioPath;
        }
    });

    // New conversion
    newConversionBtn.addEventListener('click', function() {
        resetUI();
    });

    function resetUI() {
        previewImg.style.display = 'none';
        video.style.display = 'none';
        captureBtn.style.display = 'none';
        retakeBtn.style.display = 'none';
        uploadBtn.style.display = 'inline-block';
        cameraBtn.style.display = 'inline-block';
        processingDiv.style.display = 'none';
        resultsDiv.style.display = 'none';
        originalText.textContent = '';
        tamilText.textContent = '';
        audioPlayer.src = '';
        currentAudioPath = '';

        // Stop any active camera stream
        const stream = video.srcObject;
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
    }
});
