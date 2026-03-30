from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
import json
import os
import uuid
from tinydb import Query
from flask_login import login_required, current_user
from utils.template_renderer import load_exam_template, save_exam_template, get_default_template

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

@settings_bp.route('/settings', methods=['GET'])
@login_required
def index():
    return redirect(url_for('settings.discord_settings'))


@settings_bp.route('/settings/discord', methods=['GET', 'POST'])
@login_required
def discord_settings():
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

        if save_settings(settings):
            flash("Đã lưu cài đặt thành công", "success")
        else:
            flash("Lỗi khi lưu cài đặt", "error")

        return redirect(url_for('settings.discord_settings'))

    return render_template('settings_discord.html', settings=settings)


@settings_bp.route('/settings/departments', methods=['GET', 'POST'])
@login_required
def departments_settings():
    settings = load_settings()

    from shared_db import users_table
    users = users_table.all()

    if request.method == 'POST':
        if current_user.role != 'admin':
            flash("Bạn không có quyền chỉnh sửa danh sách khoa/phòng khám.", "error")
            return redirect(url_for('settings.departments_settings'))

        departments_raw = request.form.get('departments', '')
        old_departments = set(settings.get('departments', []))
        new_departments_list = [line.strip() for line in departments_raw.split('\n') if line.strip()]
        new_departments = set(new_departments_list)

        settings['departments'] = new_departments_list
        removed_departments = old_departments - new_departments

        if save_settings(settings):
            flash("Đã lưu danh sách khoa/phòng khám", "success")

            if removed_departments:
                UserQuery = Query()
                users_to_update = users_table.search(UserQuery.department.one_of(list(removed_departments)))
                count = 0
                for user in users_to_update:
                    users_table.update({'department': 'Chưa có PK'}, doc_ids=[user.doc_id])
                    count += 1

                if count > 0:
                    flash(f"Đã cập nhật {count} người dùng về trạng thái 'Chưa có PK' do xóa phòng khám.", "warning")
        else:
            flash("Lỗi khi lưu cài đặt", "error")

        return redirect(url_for('settings.departments_settings'))

    departments = settings.get('departments', [])
    doctors_by_department = {}
    for department in departments:
        doctors_by_department[department] = [
            user for user in users
            if user.get('department') == department and user.get('role') in ('doctor', 'admin')
        ]

    unassigned_users = [
        user for user in users
        if user.get('department') not in departments
    ]

    return render_template(
        'settings_departments.html',
        settings=settings,
        doctors_by_department=doctors_by_department,
        unassigned_users=unassigned_users,
        is_admin=(current_user.role == 'admin')
    )

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

# ============================================================================
# Services Management Routes (Khoa / Dịch vụ)
# ============================================================================

@settings_bp.route('/settings/services', methods=['GET'])
def services_management():
    """Display services management page"""
    settings = load_settings()
    departments = settings.get('departments', [])
    
    from shared_db import services_table
    all_services = services_table.all()
    
    # Group services by department
    services_by_dept = {}
    for dept in departments:
        services_by_dept[dept] = [s for s in all_services if s.get('department') == dept]
    
    return render_template('services.html', 
                         departments=departments,
                         services_by_dept=services_by_dept)


@settings_bp.route('/api/services', methods=['GET', 'POST'])
def api_services():
    """API endpoint for managing services"""
    from shared_db import services_table
    
    if request.method == 'GET':
        # Get all services, optionally filtered by department
        department = request.args.get('department')
        
        if department:
            ServiceQuery = Query()
            services = services_table.search(ServiceQuery.department == department)
        else:
            services = services_table.all()
        
        # Convert to list with id field
        return jsonify([{**s, 'id': s.doc_id} for s in services])
    
    elif request.method == 'POST':
        # Add new service
        data = request.get_json()
        
        service = {
            'id': str(uuid.uuid4()),
            'department': data.get('department'),
            'name': data.get('name'),
            'price': float(data.get('price', 0))
        }
        
        if not service['name'] or not service['department']:
            return jsonify({'error': 'Name and department are required'}), 400
        
        services_table.insert(service)
        service['id'] = service['id']  # Keep uuid id
        
        return jsonify(service), 201


@settings_bp.route('/api/services/<service_id>', methods=['PUT', 'DELETE'])
def api_service_detail(service_id):
    """API endpoint for individual service operations"""
    from shared_db import services_table
    
    ServiceQuery = Query()
    
    if request.method == 'PUT':
        # Update service
        data = request.get_json()
        
        service_doc = None
        for doc in services_table.all():
            if doc.get('id') == service_id:
                service_doc = doc
                break
        
        if not service_doc:
            return jsonify({'error': 'Service not found'}), 404
        
        updated = {
            'id': service_id,
            'department': data.get('department', service_doc.get('department')),
            'name': data.get('name', service_doc.get('name')),
            'price': float(data.get('price', service_doc.get('price', 0)))
        }
        
        services_table.update(updated, doc_ids=[service_doc.doc_id])
        return jsonify(updated), 200
    
    elif request.method == 'DELETE':
        # Delete service
        service_doc = None
        for doc in services_table.all():
            if doc.get('id') == service_id:
                service_doc = doc
                break
        
        if not service_doc:
            return jsonify({'error': 'Service not found'}), 404
        
        services_table.remove(doc_ids=[service_doc.doc_id])
        return '', 204


# Template Management Routes
@settings_bp.route('/template', methods=['GET', 'POST'])
def manage_template():
    """Manage exam template"""
    department = request.args.get('department', None)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save':
            template_data = {
                'template': {
                    'header': request.form.get('header_template', ''),
                    'drugs_section': request.form.get('drugs_template', ''),
                    'drug_row_template': request.form.get('drug_row_template', ''),
                    'services_section': request.form.get('services_template', ''),
                    'service_row_template': request.form.get('service_row_template', ''),
                    'footer': request.form.get('footer_template', '')
                },
                'placeholders': get_default_template()['placeholders']
            }
            
            if save_exam_template(template_data, department):
                flash(f'Template saved successfully for {"department: " + department if department else "default"}!', 'success')
            else:
                flash('Error saving template', 'error')
                
        elif action == 'reset':
            default_template = get_default_template()
            if save_exam_template(default_template, department):
                flash(f'Template reset to default for {"department: " + department if department else "default"}!', 'success')
            else:
                flash('Error resetting template', 'error')
        
        return redirect(url_for('settings.manage_template', department=department))
    
    # GET request - show template editor
    template_data = load_exam_template(department)
    
    # Get list of departments for the dropdown
    settings = load_settings()
    departments = settings.get('departments', [])
    
    return render_template('template_editor.html', 
                         template=template_data['template'],
                         placeholders=template_data['placeholders'],
                         current_department=department,
                         departments=departments)


@settings_bp.route('/api/template/preview', methods=['POST'])
def preview_template():
    """API endpoint to preview template with sample data"""
    from utils.template_renderer import render_exam_markdown, render_exam_html
    
    data = request.get_json()
    custom_template = data.get('template')
    department = data.get('department')
    
    # Sample data for preview
    sample_patient = {
        'kid_name': 'Bé A',
        'kid_birthday': '2020-01-01',
        'name': 'Nguyễn Văn A',
        'phone': '0987654321',
        'address': '123 Đường ABC, Quận XYZ'
    }
    
    sample_exam = {
        'exam_date': '2025-01-15',
        'weight': '15',
        'height': '100',
        'history': 'Sốt nhẹ, ho',
        'expected_date': '2025-01-22',
        'total_money': 150000,
        'drugs': [
            {'name': 'Paracetamol', 'quantity': '10 viên', 'note': 'Uống 1 viên/lần, 3 lần/ngày'},
            {'name': 'Amoxicillin', 'quantity': '20 viên', 'note': 'Uống 1 viên/lần, 2 lần/ngày'}
        ],
        'services': [
            {'name': 'Khám tổng quát', 'price': 100000},
            {'name': 'Xét nghiệm máu', 'price': 50000}
        ]
    }
    
    format_type = data.get('format', 'markdown')
    
    if format_type == 'html':
        content = render_exam_html(sample_patient, sample_exam, 'BS. Quang', custom_template, department)
    else:
        content = render_exam_markdown(sample_patient, sample_exam, 'BS. Quang', custom_template, department)
    
    return jsonify({'content': content})


@settings_bp.route('/api/template/departments', methods=['GET'])
def get_department_templates():
    """Get list of departments that have custom templates"""
    try:
        if os.path.exists('exam_template.json'):
            with open('exam_template.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            departments_with_templates = list(data.get('departments', {}).keys())
        else:
            departments_with_templates = []
        
        return jsonify({'departments': departments_with_templates})
    except Exception as e:
        return jsonify({'error': str(e)}), 500