import json
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

TEMPLATE_FILE = 'exam_template.json'

def _to_number(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(',', '')
        if text == '':
            return default
        return float(text)
    except Exception:
        return default

def _format_currency(value):
    return f"{_to_number(value):,.0f}"

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
        default = get_default_template()
        return {
            'template': default.get('default', {}),
            'placeholders': default.get('placeholders', {})
        }

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
            "drugs_section": "## Thuốc\n\n| # | Tên thuốc | SL | Ghi chú |\n|---|----------|----|---------|\n{drug_rows}\n\n",
            "drug_row_template": "| {index} | {name} | {quantity} | {note} |",
            "services_section": "## Dịch vụ\n\n| # | Tên dịch vụ | SL | Giá | Thanh toán trước |\n|---|-------------|----|-----|------------------|\n{service_rows}\n\n",
            "service_row_template": "| {index} | {name} | {quantity} | {price} | {prepaid_status} |",
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

def build_drug_rows_markdown(drugs, row_template=None):
    """Build drug rows for markdown table"""
    if not drugs:
        return "| - | Không có thuốc | - | - |"

    if not row_template:
        # Default fallback (classic behavior)
        row_template = "| {index} | {name} | {quantity} | {note} |"

    rows = []
    for idx, drug in enumerate(drugs, 1):
        try:
            rows.append(row_template.format(
                index=idx,
                name=drug.get('name', ''),
                quantity=drug.get('quantity', ''),
                note=drug.get('note', ''),
            ))
        except Exception:
            # If formatting fails, fall back to simple row
            rows.append(f"| {idx} | {drug.get('name', '')} | {drug.get('quantity', '')} | {drug.get('note', '')} |")
    return "\n".join(rows)

def build_service_rows_markdown(services, row_template=None):
    """Build service rows for markdown table using a template"""
    if not services:
        return "| - | Không có dịch vụ | - |"

    if not row_template:
        # Default fallback (classic behavior)
        row_template = "| {index} | {name} | {quantity} | {price} | {prepaid_status} |"

    rows = []
    for idx, service in enumerate(services, 1):
        price_text = f"{_format_currency(service.get('price', 0))} VND"
        try:
            rows.append(row_template.format(
                index=idx,
                name=service.get('name', ''),
                quantity=service.get('quantity', ''),
                price=price_text,
                prepaid_status=service.get('prepaid_status', ''),
            ))
        except Exception:
            # If formatting fails, fall back to simple row
            rows.append(f"| {idx} | {service.get('name', '')} | {service.get('quantity', '')} | {price_text} | {service.get('prepaid_status', '')} |")
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
        price_text = f"{_format_currency(service.get('price', 0))} VND"
        
        rows += f"<tr><td>{idx}</td>"
        if show_quantities:
            rows += f"<td>{quantity}</td>"
        rows += f"<td>{service['name']}</td>"
        rows += f'<td class="text-right">{price_text}</td>'
        if show_prepaid and prepaid_status:
            rows += f"<td>{prepaid_status}</td>"
        rows += "</tr>"
    
    return rows

def calculate_footer_code(exam_data, doctor_name=None):
    """Calculate the footer code for the exam"""
    total_value = int(round(_to_number(exam_data.get('total_money', 0), default=0.0)))
    total_short = int((Decimal(total_value) / Decimal(1000)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    if doctor_name is None:
        doctor_name = exam_data.get('created_by_name') or exam_data.get('doctor_name') or exam_data.get('created_by') or ''
    doctor_name = str(doctor_name).strip()
    doctor_initial = doctor_name[:1].upper() if doctor_name else 'Q'

    submit_time = exam_data.get('submit_time')
    if not submit_time:
        submit_time = datetime.now().strftime('%y%m%d%H%M%S')

    return f"{submit_time}{doctor_initial}{total_short}"

def render_exam_markdown(patient, exam_data, doctor_name=None, custom_template=None, department=None):
    """Render exam data as markdown for Discord"""
    if custom_template:
        template_data = {'template': custom_template, 'placeholders': get_default_template()['placeholders']}
    else:
        template_data = load_exam_template(department)
    
    template = template_data['template']

    # Prepare data
    drug_row_template = template.get('drug_row_template')
    service_row_template = template.get('service_row_template')

    drug_rows = build_drug_rows_markdown(exam_data.get('drugs', []), row_template=drug_row_template)
    service_rows = build_service_rows_markdown(exam_data.get('services', []), row_template=service_row_template)
    doctor_name = doctor_name or "BS. Quang"
    footer_code = calculate_footer_code(exam_data, doctor_name=doctor_name)

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
        'total_money': _format_currency(exam_data.get('total_money', 0)),
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


def markdown_to_html(markdown_text: str) -> str:
    """Convert a small subset of Markdown into HTML."""
    import re

    def escape_html(text: str) -> str:
        return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

    lines = markdown_text.splitlines()
    html_parts = []
    in_table = False
    table_lines = []

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return ''

        header = [cell.strip() for cell in table_lines[0].strip().strip('|').split('|')]
        rows = [
            [cell.strip() for cell in line.strip().strip('|').split('|')]
            for line in table_lines[2:]
        ]

        thead = '<thead><tr>' + ''.join(f'<th>{escape_html(c)}</th>' for c in header) + '</tr></thead>'
        tbody = '<tbody>' + ''.join(
            '<tr>' + ''.join(f'<td>{escape_html(c)}</td>' for c in row) + '</tr>' for row in rows
        ) + '</tbody>'

        table_lines = []
        return f'<table>{thead}{tbody}</table>'

    for line in lines:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            in_table = True
            table_lines.append(line)
            continue

        if in_table:
            html_parts.append(flush_table())
            in_table = False

        if line.startswith('### '):
            html_parts.append(f'<h3>{escape_html(line[4:])}</h3>')
            continue
        if line.startswith('## '):
            html_parts.append(f'<h2>{escape_html(line[3:])}</h2>')
            continue
        if line.startswith('# '):
            html_parts.append(f'<h1>{escape_html(line[2:])}</h1>')
            continue

        escaped = escape_html(line)
        escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"`([^`]*)`", r"<code>\1</code>", escaped)

        if escaped.strip() == '':
            html_parts.append('<p></p>')
        else:
            html_parts.append(f'<p>{escaped}</p>')

    if in_table:
        html_parts.append(flush_table())

    return ''.join(html_parts)


def render_exam_html(patient, exam_data, doctor_name=None, custom_template=None, department=None):
    """Render exam data as HTML for PDF"""
    markdown = render_exam_markdown(patient, exam_data, doctor_name, custom_template, department)
    html_body = markdown_to_html(markdown)

    return f"""
    <html>
      <head>
        <meta charset=\"utf-8\" />
        <meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\" />
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
        {html_body}
      </body>
    </html>
    """

    # Prepare data
    drug_rows = build_drug_rows_html(exam_data.get('drugs', []))
    service_rows = build_service_rows_html(exam_data.get('services', []), show_quantities=True, show_prepaid=True)
    doctor_name = doctor_name or "BS. Quang"
    footer_code = calculate_footer_code(exam_data, doctor_name=doctor_name)
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

        <h3>Thuốc</h3>
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

        {"<h3>Dịch vụ</h3><table><thead><tr><th>#</th><th>Tên dịch vụ</th><th>SL</th><th>Giá</th><th>Trạng thái</th></tr></thead><tbody>" + service_rows + "</tbody></table>" if exam_data.get('services') else ""}

        <div class="footer">
          <p>{signature_text}</p>
          <span style="white-space:nowrap;">{footer_code}</span>
        </div>
      </body>
    </html>
    """
    return html