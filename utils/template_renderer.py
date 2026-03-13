import json
import os
from datetime import datetime

TEMPLATE_FILE = 'exam_template.json'

def load_exam_template(department=None):
    """Load the exam template from file, optionally for a specific department"""
    if not os.path.exists(TEMPLATE_FILE):
        return get_default_template()
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # If department is specified and exists, return department template
        if department and department in data.get('departments', {}):
            return {
                'template': data['departments'][department],
                'placeholders': data.get('placeholders', {})
            }

        # Otherwise return default template
        return {
            'template': data.get('default', {}),
            'placeholders': data.get('placeholders', {})
        }
    except Exception as e:
        print(f"Error loading template: {e}")
        return get_default_template()

def save_exam_template(template_data, department=None):
    """Save the exam template to file, optionally for a specific department"""
    try:
        # Load existing data
        if os.path.exists(TEMPLATE_FILE):
            with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = get_default_template()

        # Ensure structure exists
        if 'departments' not in data:
            data['departments'] = {}
        if 'placeholders' not in data:
            data['placeholders'] = get_default_template()['placeholders']

        if department:
            # Save department-specific template
            data['departments'][department] = template_data['template']
        else:
            # Save default template
            data['default'] = template_data['template']

        with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving template: {e}")
        return False

def get_default_template():
    """Get the default template structure"""
    return {
        "default": {
            "header": "# Phiếu Khám Bệnh - {exam_date}\n\n**Bé:** {kid_name} ({kid_birthday}) - {weight}kg {height}cm\n**Phụ huynh:** {parent_name}\n**SĐT:** {phone}\n**Địa chỉ:** {address}\n\n**Ghi chú / Khám bệnh:** {history}\n**Hẹn tái khám:** {expected_date}\n\n",
            "drugs_section": "## 💊 Thuốc\n\n| # | Tên thuốc | SL | Ghi chú |\n|---|----------|----|---------|\n{drug_rows}\n\n",
            "services_section": "## 🛎️ Dịch vụ\n\n| # | Tên dịch vụ | Giá |\n|---|-------------|-----|\n{service_rows}\n\n",
            "footer": "**Tổng tiền:** {total_money} VND\n\n*Bác sĩ khám: {doctor_name}*\n\n`{footer_code}`"
        },
        "departments": {},
        "placeholders": {
            "exam_date": "Ngày khám",
            "kid_name": "Tên bé",
            "kid_birthday": "Ngày sinh bé",
            "weight": "Cân nặng",
            "height": "Chiều cao",
            "parent_name": "Tên phụ huynh",
            "phone": "Số điện thoại",
            "address": "Địa chỉ",
            "history": "Ghi chú khám bệnh",
            "expected_date": "Ngày hẹn tái khám",
            "drug_rows": "Danh sách thuốc (bảng)",
            "service_rows": "Danh sách dịch vụ (bảng)",
            "total_money": "Tổng tiền",
            "doctor_name": "Tên bác sĩ",
            "footer_code": "Mã footer"
        }
    }

def build_drug_rows_markdown(drugs):
    """Build drug rows for markdown table"""
    if not drugs:
        return "| - | Không có thuốc | - | - |"

    rows = []
    for idx, drug in enumerate(drugs, 1):
        name = drug.get('name', '')
        qty = str(drug.get('quantity', ''))
        note = drug.get('note', '')
        rows.append(f"| {idx} | {name} | {qty} | {note} |")
    return "\n".join(rows)

def build_service_rows_markdown(services, show_quantities=False, show_prepaid=False):
    """Build service rows for markdown table with optional quantities and prepaid status"""
    if not services:
        headers = ["#", "Tên dịch vụ", "Giá"]
        if show_quantities:
            headers.insert(2, "SL")
        if show_prepaid:
            headers.append("Trạng thái")
        header_row = " | ".join(headers)
        sep_row = "|".join(["-" * len(h) for h in headers])
        return f"| {header_row} |\n| {sep_row} |\n| {' | '.join(['-'] * len(headers))} |"

    rows = []
    for idx, service in enumerate(services, 1):
        name = service.get('name', '')
        price = f"{service.get('price', 0):,.0f} VND"
        quantity = service.get('quantity', 1)
        prepaid_status = service.get('prepaid_status', '')
        
        row_data = [str(idx), name]
        if show_quantities:
            row_data.insert(2, str(quantity))
        row_data.append(price)
        if show_prepaid and prepaid_status:
            row_data.append(prepaid_status)
        
        rows.append(" | ".join(row_data))
    
    return "\n".join(rows)

def build_drug_rows_html(drugs):
    """Build drug rows for HTML table"""
    if not drugs:
        return '<tr><td colspan="3">Không có thuốc</td></tr>'

    rows = ""
    for idx, drug in enumerate(drugs, 1):
        rows += f"""
        <tr>
          <td>{idx}</td>
          <td>{drug['name']}</td>
          <td>{drug['quantity']}</td>
        </tr>
        <tr>
          <td></td>
          <td colspan="2" style="font-style:italic;">{drug['note']}</td>
        </tr>
        """
    return rows

def build_service_rows_html(services, show_quantities=False, show_prepaid=False):
    """Build service rows for HTML table with optional quantities and prepaid status"""
    if not services:
        colspan = 3
        if show_quantities:
            colspan += 1
        if show_prepaid:
            colspan += 1
        return f'<tr><td colspan="{colspan}">Không có dịch vụ</td></tr>'

    rows = ""
    for idx, service in enumerate(services, 1):
        quantity = service.get('quantity', 1)
        prepaid_status = service.get('prepaid_status', '')
        
        rows += f"<tr><td>{idx}</td>"
        if show_quantities:
            rows += f"<td>{quantity}</td>"
        rows += f"<td>{service['name']}</td>"
        rows += f'<td class="text-right">{"{:,.0f}".format(service["price"])} VND</td>'
        if show_prepaid and prepaid_status:
            rows += f"<td>{prepaid_status}</td>"
        rows += "</tr>"
    
    return rows

def calculate_footer_code(exam_data):
    """Calculate the footer code for the exam"""
    total_money = str(exam_data.get('total_money', '0'))
    total_money = ''.join(filter(str.isdigit, total_money))
    if len(total_money) > 3:
        total_short = total_money[:-3]
    else:
        total_short = "0"

    submit_time = exam_data.get('submit_time')
    if not submit_time:
        submit_time = datetime.now().strftime('%y%m%d%H%M%S')

    return f"{submit_time}H{total_short}"

def render_exam_markdown(patient, exam_data, doctor_name=None, custom_template=None, department=None):
    """Render exam data as markdown for Discord"""
    if custom_template:
        template_data = {'template': custom_template, 'placeholders': get_default_template()['placeholders']}
    else:
        template_data = load_exam_template(department)
    
    template = template_data['template']

    # Prepare data
    drug_rows = build_drug_rows_markdown(exam_data.get('drugs', []))
    service_rows = build_service_rows_markdown(exam_data.get('services', []), show_quantities=True, show_prepaid=True)
    footer_code = calculate_footer_code(exam_data)

    doctor_name = doctor_name or "BS. Quang"

    # Format data
    data = {
        'exam_date': exam_data.get('exam_date', ''),
        'kid_name': patient.get('kid_name', ''),
        'kid_birthday': patient.get('kid_birthday', ''),
        'weight': exam_data.get('weight', ''),
        'height': exam_data.get('height', ''),
        'parent_name': patient.get('name', ''),
        'phone': patient.get('phone', ''),
        'address': patient.get('address', ''),
        'history': exam_data.get('history', ''),
        'expected_date': exam_data.get('expected_date', ''),
        'drug_rows': drug_rows,
        'service_rows': service_rows,
        'total_money': f"{exam_data.get('total_money', 0):,.0f}",
        'doctor_name': doctor_name,
        'footer_code': footer_code
    }

    # Build content
    content = template['header'].format(**data)

    if exam_data.get('drugs'):
        content += template['drugs_section'].format(**data)

    if exam_data.get('services'):
        content += template['services_section'].format(**data)

    content += template['footer'].format(**data)

    return content

def render_exam_html(patient, exam_data, doctor_name=None, custom_template=None, department=None):
    """Render exam data as HTML for PDF"""
    if custom_template:
        template_data = {'template': custom_template, 'placeholders': get_default_template()['placeholders']}
    else:
        template_data = load_exam_template(department)
    
    template = template_data['template']

    # Prepare data
    drug_rows = build_drug_rows_html(exam_data.get('drugs', []))
    service_rows = build_service_rows_html(exam_data.get('services', []), show_quantities=True, show_prepaid=True)
    footer_code = calculate_footer_code(exam_data)

    doctor_name = doctor_name or "BS. Quang"
    signature_text = f"Bác sĩ khám: {doctor_name}"

    # Build HTML
    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <title>Phiếu Khám</title>
        <style>
          @page {{ size: A5 portrait; margin: 1cm; }}
          * {{ font-family: Arial, Helvetica, sans-serif; }}
          body {{ font-family: Arial, Helvetica, sans-serif; font-size: 11pt; }}
          h2 {{ text-align: center; margin: 0.5em 0; font-size: 14pt }}
          h3 {{ margin-top: 1em; margin-bottom: 0.5em; font-size: 12pt }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 1em; }}
          th, td {{ border: none; padding: 6px 4px; }}
          th {{ font-weight: bold; text-align: left; }}
          tbody tr {{ margin-bottom: 5px; display: table-row;}}
          tbody td {{ padding-top: 5px; padding-bottom: 10px }}
          .text-right {{ text-align: right; }}
          @media print {{
            th, td {{ border: none; }}
            .footer {{
              position: fixed;
              bottom: 1cm;
              width: 100%;
              text-align: left;
              font-size: 12px;
            }}
          }}
        </style>
      </head>
      <body>
        <h2>Phiếu Khám Bệnh - {exam_data.get('exam_date', '')}</h2>
        <p>{patient.get('kid_name', '')} &nbsp;&nbsp; {patient.get('kid_birthday', '')} &nbsp;&nbsp; {exam_data.get('weight', '')}kg &nbsp;&nbsp; {exam_data.get('height', '')}cm</p>
        <p>{patient.get('phone', '')} &nbsp;&nbsp; {patient.get('name', '')}</p>
        <p>{patient.get('address', '')}</p>
        <p><strong>Ghi chú / Khám bệnh:</strong> {exam_data.get('history', '')}</p>
        <p>Hẹn tái khám: {exam_data.get('expected_date', '')}</p>

        <h3>💊 Thuốc</h3>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Tên thuốc</th>
              <th>SL</th>
            </tr>
          </thead>
          <tbody>
            {drug_rows}
          </tbody>
        </table>

        {"<h3>🛎️ Dịch vụ</h3><table><thead><tr><th>#</th><th>Tên dịch vụ</th><th>SL</th><th>Giá</th><th>Trạng thái</th></tr></thead><tbody>" + service_rows + "</tbody></table>" if exam_data.get('services') else ""}

        <div class="footer">
          <p>{signature_text}</p>
          <span style="white-space:nowrap;">{footer_code}</span>
        </div>
      </body>
    </html>
    """
    return html