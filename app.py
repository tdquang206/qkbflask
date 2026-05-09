from flask import Flask
from flask_wtf.csrf import CSRFProtect
import os

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Determine debug mode once and reuse it for configuration decisions.
is_debug = os.getenv('FLASK_DEBUG', '0') == '1'

secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    if is_debug:
        # In debug mode, allow an ephemeral per-process secret key.
        secret_key = os.urandom(32).hex()
    else:
        # In non-debug environments, require an explicit SECRET_KEY.
        raise RuntimeError("SECRET_KEY environment variable must be set in non-debug environments.")
app.secret_key = secret_key

# CSRF protection for all POST/PUT/PATCH/DELETE requests
csrf = CSRFProtect(app)

# Security hardening: only enable debug when explicitly requested.
app.config['DEBUG'] = is_debug

# include blueprint
from routes.core import core_bp
app.register_blueprint(core_bp)

from routes.mua_thuoc import mua_thuoc_bp
app.register_blueprint(mua_thuoc_bp)

from routes.route_all_exams_page import exams_list_bp
app.register_blueprint(exams_list_bp)

from routes.exam import exam_bp
app.register_blueprint(exam_bp)

from routes.settings import settings_bp
app.register_blueprint(settings_bp)

from routes.drugs import drugs_bp
app.register_blueprint(drugs_bp)

from routes.patients import patients_bp
app.register_blueprint(patients_bp)

from routes.reports import reports_bp
app.register_blueprint(reports_bp)

from flask_login import LoginManager
from routes.auth import auth_bp, setup_default_admin, User
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

import threading
import webbrowser
from pystray import Icon, Menu, MenuItem
from PIL import Image
import waitress

# Setup default admin on startup
setup_default_admin()

# Comment out for waitress
# if __name__ == '__main__':
#     app.run(debug=True)

def run_server():
    # Run the Flask app with Waitress on localhost:5000
    waitress.serve(app, host='127.0.0.1', port=5000)

def open_browser(icon, item):
    webbrowser.open('http://127.0.0.1:5000')

def exit_app(icon, item):
    icon.stop()
    # Stop the server thread if needed (Waitress handles shutdown on exit)

if __name__ == '__main__':
    # Start the server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Load icon (assuming app_icon.ico exists in the same directory)
    icon_image = Image.open('app_icon.ico')

    # Create tray icon menu
    menu = Menu(
        MenuItem('Open in Browser', open_browser),
        MenuItem('Exit', exit_app)
    )

    # Create and run the tray icon
    icon = Icon('QKBFlask', icon_image, 'QKBFlask App', menu)
    icon.run()