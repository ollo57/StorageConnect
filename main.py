import os
import json
import threading
import urllib.request
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename

# Determine the absolute path of the directory containing this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'))

# --- CONFIGURATION ---
BASE_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
FRIEND_KEY = ''
MAX_FILE_SIZE_MB = 2000 # Increased for 4K Videos and large backups
APPROVED_DEVICES_FILE = os.path.join(BASE_DIR, 'approved_devices.json')
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
# ---------------------

app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

# Load persistent upload folder if it exists
settings = load_settings()
if settings.get('upload_folder'):
    BASE_UPLOAD_FOLDER = settings['upload_folder']

if not os.path.exists(BASE_UPLOAD_FOLDER):
    os.makedirs(BASE_UPLOAD_FOLDER)

def load_approved_devices():
    if os.path.exists(APPROVED_DEVICES_FILE):
        try:
            with open(APPROVED_DEVICES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_approved_devices(devices):
    with open(APPROVED_DEVICES_FILE, 'w') as f:
        json.dump(devices, f, indent=4)

def is_device_approved(device_id):
    devices = load_approved_devices()
    return devices.get(device_id, False)

def manual_approval_cli():
    """Background thread to handle interactive commands via terminal."""
    global BASE_UPLOAD_FOLDER
    while True:
        try:
            print("\n[ADMIN] Available commands: 'pending', 'approve <ID>', 'setdir <path>', 'q' to quit")
            cmd_input = input("[ADMIN] > ").strip().split(maxsplit=1)

            if not cmd_input:
                continue

            cmd = cmd_input[0].lower()

            if cmd == 'q':
                break

            if cmd == 'pending':
                devices = load_approved_devices()
                pending = [uid for uid, approved in devices.items() if not approved]
                if pending:
                    print("\n--- PENDING DEVICES ---")
                    for uid in pending:
                        print(f" > {uid}")
                    print("-----------------------")
                else:
                    print("\n--- No pending devices ---")

            elif cmd == 'approve':
                if len(cmd_input) < 2:
                    print("Usage: approve <Device ID>")
                    continue
                device_id = cmd_input[1]
                devices = load_approved_devices()
                if device_id in devices:
                    confirm = input(f"Approve device {device_id}? (y/n): ").strip().lower()
                    if confirm == 'y':
                        devices[device_id] = True
                        save_approved_devices(devices)
                        print(f"--- Device {device_id} APPROVED ---")
                    else:
                        print("--- Approval cancelled ---")
                else:
                    print(f"!!! Device ID {device_id} not found in pending list !!!")

            elif cmd == 'setdir':
                if len(cmd_input) < 2:
                    print("Usage: setdir <absolute_path>")
                    continue
                new_path = cmd_input[1].strip('"')
                if os.path.isabs(new_path):
                    if not os.path.exists(new_path):
                        try:
                            os.makedirs(new_path)
                        except Exception as e:
                            print(f"Error creating directory: {e}")
                            continue
                    BASE_UPLOAD_FOLDER = new_path
                    # Save to settings
                    settings = load_settings()
                    settings['upload_folder'] = BASE_UPLOAD_FOLDER
                    save_settings(settings)
                    print(f"--- STORAGE DIRECTORY CHANGED TO: {BASE_UPLOAD_FOLDER} ---")
                    print(f"--- (Setting saved and will persist after restart) ---")
                else:
                    print("Error: Please provide an ABSOLUTE path.")

        except EOFError:
            break

@app.before_request
def verify_access():
    # Whitelist paths that don't need authentication (like the app installer or web dashboard)
    path = request.path.rstrip('/')

    # Debug info to help you see what's happening in your terminal
    print(f"[LOG] Request: {request.method} {path}")

    # Serve the web dashboard itself without a key initially (login is handled by JS)
    if path == '':
        return

    if path in ['/ping'] or path.startswith('/approve'):
        return

    # Check for Friend-Key in headers OR as a query parameter (for browser downloads/previews)
    client_key = request.headers.get('Friend-Key') or request.args.get('key')

    if client_key != FRIEND_KEY:
        if path == '/install':
            return # Blocked below anyway
        print(f"!!! Unauthorized: Key mismatch for {path}. Received: '{client_key}'")
        return jsonify({"error": "Invalid Friend-Key"}), 401

    # Skip device-id check for the install link
    if path == '/install':
        return

    # Check for Device-Id in headers OR as a query parameter (for browsers)
    device_id = request.headers.get('Device-Id') or request.args.get('device')

    if not device_id:
        return jsonify({"error": "Device-Id missing"}), 400

    if not is_device_approved(device_id):
        devices = load_approved_devices()
        if device_id not in devices:
            devices[device_id] = False
            save_approved_devices(devices)
            print(f"\n[ALERT] New Web/iPhone request from: {device_id}")
            print(f"Type 'approve {device_id}' to allow them.")

        return jsonify({"error": "Device not approved by admin"}), 403

@app.route('/')
def index():
    """Serves the web dashboard for iPhone users."""
    try:
        return render_template('index.html')
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        # Add some directory info to help debug
        try:
            cwd = os.getcwd()
            files_in_cwd = os.listdir(cwd)
            base_dir_files = os.listdir(BASE_DIR) if os.path.exists(BASE_DIR) else "BASE_DIR does not exist"
            template_path = os.path.join(BASE_DIR, 'templates')
            template_exists = os.path.exists(template_path)
            template_files = os.listdir(template_path) if template_exists else "Template folder not found"
        except:
            cwd = "error"
            files_in_cwd = []
            base_dir_files = []
            template_files = []

        debug_info = f"CWD: {cwd}\nFiles in CWD: {files_in_cwd}\nBASE_DIR: {BASE_DIR}\nFiles in BASE_DIR: {base_dir_files}\nTemplate Folder: {template_path} (Exists: {template_exists})\nFiles in Template Folder: {template_files}"

        return f"<h1>Internal Server Error</h1><p>{str(e)}</p><pre>{error_details}\n\n{debug_info}</pre>", 500

@app.route('/approve/<device_id>', methods=['POST'])
def approve_device(device_id):
    devices = load_approved_devices()
    if device_id in devices:
        devices[device_id] = True
        save_approved_devices(devices)
        return jsonify({"message": f"Device {device_id} approved"}), 200
    return jsonify({"error": "Device ID not found"}), 404

@app.route('/files', methods=['GET'])
def list_files():
    device_id = request.headers.get('Device-Id') or request.args.get('device')
    if not device_id:
        return jsonify({"error": "Device-Id missing"}), 400

    user_folder = os.path.join(BASE_UPLOAD_FOLDER, device_id)

    if not os.path.exists(user_folder):
        return jsonify([]), 200

    files = []
    for filename in os.listdir(user_folder):
        path = os.path.join(user_folder, filename)
        if os.path.isfile(path):
            if "_" in filename and "." in filename:
                base_name = filename.rsplit("_", 1)[0]
                ext = filename.rsplit(".", 1)[1]
                original_name = f"{base_name}.{ext}"
            elif "_" in filename:
                original_name = filename.rsplit("_", 1)[0]
            else:
                original_name = filename

            files.append({
                "name": filename,
                "size": os.path.getsize(path),
                "original_name": original_name,
                "url": f"/download/{filename}"
            })
    return jsonify(files), 200

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    device_id = request.headers.get('Device-Id') or request.args.get('device')
    if not device_id:
        return jsonify({"error": "Device-Id missing"}), 400

    user_folder = os.path.join(BASE_UPLOAD_FOLDER, device_id)
    return send_from_directory(user_folder, filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    device_id = request.headers.get('Device-Id') or request.args.get('device')
    if not device_id:
        return jsonify({"error": "Device-Id missing"}), 400

    user_folder = os.path.join(BASE_UPLOAD_FOLDER, device_id)

    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        original_filename = secure_filename(file.filename)

        if "." in original_filename:
            name_without_ext = original_filename.rsplit(".", 1)[0]
            extension = original_filename.rsplit(".", 1)[1].lower()
        else:
            name_without_ext = original_filename
            extension = ""

        final_filename = original_filename
        counter = 1

        # Improved uniqueness logic: name_1.ext, name_2.ext
        while os.path.exists(os.path.join(user_folder, final_filename)):
            if extension:
                final_filename = f"{name_without_ext}_{counter}.{extension}"
            else:
                final_filename = f"{name_without_ext}_{counter}"
            counter += 1

        save_path = os.path.join(user_folder, final_filename)
        file.save(save_path)
        print(f"[SUCCESS] Saved: {final_filename} for {device_id}")
        return jsonify({"message": f"Uploaded as {final_filename}"}), 200

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok", "message": "StorageConnect Multi-User Server Running"}), 200

@app.route('/verify', methods=['GET'])
def verify_login():
    """Checks if the provided Key and Device ID are valid and approved."""
    return jsonify({"status": "success", "message": "Authorized"}), 200

@app.route('/install', methods=['GET'])
def download_app():
    """Serves the APK file for friends to download the app."""
    for filename in os.listdir('.'):
        if filename.endswith('.apk'):
            return send_from_directory('.', filename, as_attachment=True)
    return "<h1>No APK found</h1><p>Please place your <b>.apk</b> file in the same folder as server.py</p>", 404

if __name__ == '__main__':
    # Start the CLI approval thread
    threading.Thread(target=manual_approval_cli, daemon=True).start()

    print(f"\n" + "="*50)
    print(f"STORAGE CONNECT SERVER STARTING...")
    print(f"="*50)

    try:
        public_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
        print(f"[PUBLIC]  Worldwide Link: http://{public_ip}:5000")
        print(f"[CHECK]   Verify Port 5000 is open at: https://canyouseeme.org/")
    except Exception as e:
        print(f"[PUBLIC]  Could not detect Public IP. Make sure you are online.")

    print(f"[LOCAL]   Home Network Link: http://0.0.0.0:5000")
    print(f"[ADMIN]   To approve friends, type their Device ID below when prompted.")
    print(f"="*50 + "\n")

    app.run(host='0.0.0.0', port=5000)
