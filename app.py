from flask import Flask, render_template, request, redirect, url_for, jsonify, Blueprint
from tinydb import Query, where
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid
# from rapidfuzz import fuzz # Moved to routes/drugs.py

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = b'quang0902915519'

from shared_db import db, patients_table as patients, drugs_table as drugs, exams_table as exams

# include blueprint
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

# weekly backup
from utils.db_logger import weekly_backup_all, log_action
@app.after_request
def auto_log_and_backup(response):
    if request.method in ['POST', 'PUT', 'DELETE']:
        weekly_backup_all()

        log_action("auto", {
            "endpoint": request.endpoint,
            "method": request.method,
            "path": request.path,
            "form": request.form.to_dict(),
            "args": request.args.to_dict()
        })
    return response

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/exams')
def all_exams():
    return render_template('exams.html', exams=exams.all(), patients=patients)



if __name__ == '__main__':
    app.run(debug=True)