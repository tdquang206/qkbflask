from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
import json
import os

settings_bp = Blueprint('settings', __name__)

SETTINGS_FILE = 'user_settings.json'

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "discord_webhook_url": "",
            "include_date": True,
            "include_kid_name": True,
            "include_parent_name": True,
            "include_phone": True,
            "include_address": False,
            "include_total_money": True,
            "include_table": True,
            "attach_image": True
        }
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

@settings_bp.route('/settings', methods=['GET', 'POST'])
def index():
    settings = load_settings()
    
    if request.method == 'POST':
        settings['discord_webhook_url'] = request.form.get('discord_webhook_url', '')
        settings['include_date'] = 'include_date' in request.form
        settings['include_kid_name'] = 'include_kid_name' in request.form
        settings['include_parent_name'] = 'include_parent_name' in request.form
        settings['include_phone'] = 'include_phone' in request.form
        settings['include_address'] = 'include_address' in request.form
        settings['include_total_money'] = 'include_total_money' in request.form
        settings['include_table'] = 'include_table' in request.form
        settings['attach_image'] = 'attach_image' in request.form
        
        # Handle departments (textarea, one per line)
        departments_raw = request.form.get('departments', '')
        
        # Logic to handle cascading delete/reset
        old_departments = set(settings.get('departments', []))
        new_departments_list = [line.strip() for line in departments_raw.split('\n') if line.strip()]
        new_departments = set(new_departments_list)
        
        settings['departments'] = new_departments_list

        removed_departments = old_departments - new_departments
        
        if save_settings(settings):
            flash("Đã lưu cài đặt thành công", "success")
            
            # Cascading update for removed departments
            if removed_departments:
                from shared_db import users_table
                from tinydb import Query
                UserQuery = Query()
                
                # Find users with removed departments
                users_to_update = users_table.search(UserQuery.department.one_of(list(removed_departments)))
                count = 0
                for user in users_to_update:
                    users_table.update({'department': 'Chưa có PK'}, doc_ids=[user.doc_id])
                    count += 1
                
                if count > 0:
                    flash(f"Đã cập nhật {count} người dùng về trạng thái 'Chưa có PK' do xóa phòng khám.", "warning")

        else:
            flash("Lỗi khi lưu cài đặt", "error")
            
        return redirect(url_for('settings.index'))
        
    return render_template('settings.html', settings=settings)

@settings_bp.route('/changelog')
def changelog():
    import markdown
    
    # Assuming changelog.md is in the root directory (parent of routes)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    changelog_path = os.path.join(root_dir, 'changelog.md')
    
    content = ""
    if os.path.exists(changelog_path):
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
    html_content = markdown.markdown(content)
    return render_template('changelog.html', content=html_content)
