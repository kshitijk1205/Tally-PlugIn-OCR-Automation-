from flask import Flask, request
import os
import socket
import qrcode
from PIL import Image
import threading
import logging

# CONFIG
UPLOAD_FOLDER = "mobile_uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
# Silence Flask logs to keep terminal clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# GLOBAL QUEUE (The bridge to the Main App)
file_queue_ref = None

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CardioFlow Upload</title>
    <style>
        body { font-family: sans-serif; background: #222; color: #fff; text-align: center; padding: 20px; }
        .btn-upload {
            display: block; width: 100%; padding: 20px; margin-top: 30px;
            background: #008000; color: white; border: none; border-radius: 10px;
            font-size: 20px; font-weight: bold; cursor: pointer;
        }
        input[type="file"] { display: none; }
    </style>
</head>
<body>
    <h2>📄 Scan Bill</h2>
    <p>Tap below to take a photo</p>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <label class="btn-upload">
            📷 Open Camera
            <input type="file" name="file" accept="image/*" capture="environment" onchange="this.form.submit()">
        </label>
    </form>
</body>
</html>
"""

def get_best_ip():
    """ Tries to find the actual Wi-Fi/LAN IP, ignoring VirtualBox/Simulators """
    try:
        # Connect to a public DNS (doesn't send data) to see which interface is active
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        IP = s.getsockname()[0]
        s.close()
        return IP
    except:
        return "127.0.0.1"

@app.route('/')
def index():
    return HTML

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return "No file"
    file = request.files['file']
    if file.filename == '': return "No filename"
    
    if file:
        # Save with unique name to prevent overwrites
        import time
        filename = f"scan_{int(time.time())}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # PUT IN QUEUE (Thread Safe)
        if file_queue_ref:
            file_queue_ref.put(filepath)
            
        return "<h1 style='color:lightgreen; text-align:center; font-family:sans-serif; margin-top:50px;'>✅ Uploaded!<br>Check PC Screen.</h1><script>setTimeout(function(){window.location.href='/';}, 2000);</script>"

def start_server(queue_ref):
    global file_queue_ref
    file_queue_ref = queue_ref
    
    ip = get_best_ip()
    port = 5000
    url = f"http://{ip}:{port}"
    
    # Create QR
    qr = qrcode.make(url)
    qr.save("connect_qr.png")
    
    # Run in Thread
    t = threading.Thread(target=app.run, kwargs={'host':'0.0.0.0', 'port':port})
    t.daemon = True
    t.start()
    
    return url