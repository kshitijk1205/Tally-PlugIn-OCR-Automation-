from flask import Flask, request, render_template_string, session
import license_guard
import webbrowser
import threading
import os

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cardioflow-admin")

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CardioFlow Admin Login</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #101010; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background-color: #18181b; padding: 40px; border-radius: 15px; width: 350px; text-align: center; border: 1px solid #333; }
        h2 { color: #3b8ed0; margin-bottom: 30px; }
        input { width: 90%; padding: 15px; margin-bottom: 20px; background: #27272a; border: 1px solid #3f3f46; color: white; font-size: 16px; border-radius: 8px; text-align: center; }
        input:focus { border-color: #3b8ed0; }
        button { width: 100%; padding: 15px; background: #3b8ed0; border: none; color: white; font-weight: bold; font-size: 18px; border-radius: 8px; cursor: pointer; }
        .error { color: #ef4444; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🔐 ADMIN LOGIN</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="Enter Admin Password" required>
            <button type="submit">LOGIN</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
    </div>
</body>
</html>
"""

GENERATOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CardioFlow Admin Panel</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #101010; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background-color: #18181b; padding: 40px; border-radius: 15px; width: 400px; text-align: center; border: 1px solid #333; }
        h2 { color: #3b8ed0; margin-bottom: 30px; letter-spacing: 1px; }
        input { width: 90%; padding: 15px; margin-bottom: 20px; background: #27272a; border: 1px solid #3f3f46; color: white; font-size: 16px; border-radius: 8px; text-align: center; outline: none; }
        input:focus { border-color: #3b8ed0; }
        button { width: 100%; padding: 15px; background: #10b981; border: none; color: black; font-weight: bold; font-size: 18px; border-radius: 8px; cursor: pointer; transition: 0.2s; }
        button:hover { background: #059669; }
        .result { margin-top: 30px; padding: 20px; background: #27272a; border-radius: 8px; border: 1px solid #3b8ed0; }
        .key-text { font-size: 24px; font-family: monospace; color: #facc15; font-weight: bold; letter-spacing: 2px; }
        .copy-hint { font-size: 12px; color: gray; margin-top: 10px; }
        .logout { margin-top: 20px; display: inline-block; color: #6b7280; text-decoration: none; font-size: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🔐 LICENSE GENERATOR</h2>
        <form method="POST">
            <input type="text" name="hw_id" placeholder="Paste Client Hardware ID" required autocomplete="off">
            <button type="submit">GENERATE KEY</button>
        </form>

        {% if key %}
        <div class="result">
            <div class="key-text">{{ key }}</div>
            <div class="copy-hint">Double-click to copy</div>
        </div>
        {% endif %}
        <a class="logout" href="/logout">Logout</a>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    if not session.get('authenticated'):
        error = None
        if request.method == 'POST':
            if request.form.get('password', '') == ADMIN_PASSWORD:
                session['authenticated'] = True
            else:
                error = "Invalid password"
        return render_template_string(LOGIN_HTML, error=error)

    generated_key = None
    if request.method == 'POST':
        hw_id = request.form.get('hw_id', '').strip()
        if hw_id:
            generated_key = license_guard.generate_key_for_machine(hw_id)
    return render_template_string(GENERATOR_HTML, key=generated_key)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return '<meta http-equiv="refresh" content="0;url=/"><h2>Logged out</h2>'

if __name__ == '__main__':
    url = "http://127.0.0.1:8888"
    threading.Timer(1, lambda: webbrowser.open(url)).start()
    app.run(port=8888)