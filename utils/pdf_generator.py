import os
from datetime import datetime

# generate filename for pdf and jpeg on server
def generate_exam_file_name(phone, exam_date, exam_id):
    # phone_date_hex[:8]
    random_part = str(exam_id)[:8].replace('-', '')
    date_str = str(exam_date).replace('-', '')  # ✅ Renamed for clarity
    
    return f"{phone}_{date_str}_{random_part}"

def build_exam_html(patient, exam_data):
    # reuse pdf template in print
    # Build drug rows
    drug_rows = ""
    for idx, drug in enumerate(exam_data.get('drugs', []), 1):
        drug_rows += f"""
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
    
    # Your existing HTML template
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
          table {{ width: 100%; border-collapse: collapse; margin-top: 1em; }}
          th, td {{ border: none; padding: 6px 4px; }}
          th {{ font-weight: bold; text-align: left; }}
          tbody tr {{ margin-bottom: 5px; display: table-row;}}
          tbody td {{ padding-top: 5px; padding-bottom: 10px }}
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
            {drug_rows or '<tr><td colspan="3">Toa không thuốc</td></tr>'}
          </tbody>
        </table>
        <div class="footer">
          <span style="white-space:nowrap;">{datetime.now().strftime('%H:%M')}</span>
        </div>
      </body>
    </html>
    """
    return html

def generate_pdf_and_jpeg(html_content, phone, exam_date, short_exam_id):
    """
    Generate PDF and JPEG from HTML

    Args:
      html_content: HTML string (must be UTF-8)
      phone: Patient phone (e.g., '0988014887')
      exam_date: Exam date (e.g., '2025-11-29')
      short_exam_id: Short exam ID (e.g., '99dcb620')
    
    Returns:
        dict: {
            'success': bool,
            'exam_id': str (short ID like 20251129_99dcb620),
            'filename': str (phone_exam_date_randompart),
            'pdf_path': str,
            'jpeg_path': str
        }
    """
    try:
        import pdfkit
        from pdf2image import convert_from_path

        filename = generate_exam_file_name(phone, exam_date, short_exam_id)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # for bin inside flask app
        wkhtml_path = os.path.join(base_dir, "wkhtmltopdf_bin", "wkhtmltopdf.exe")
        poppler_path = os.path.join(base_dir, "poppler_bin", "bin")

        pdf_dir = os.path.join(base_dir, "files", "pdf")
        jpeg_dir = os.path.join(base_dir, "files", "jpeg")
        os.makedirs(pdf_dir, exist_ok=True)
        os.makedirs(jpeg_dir, exist_ok=True)

        pdf_path = os.path.join(pdf_dir, f"{filename}.pdf")
        jpeg_path = os.path.join(jpeg_dir, f"{filename}.jpg")

        # HTML to PDF
        options = {
            'page-size': 'A5',
            'margin-top': '1cm',
            'margin-bottom': '1cm',
            'margin-left': '1cm',
            'margin-right': '1cm',
            'encoding': 'UTF-8',
            'no-outline': None,
            # 'enable-local-file-access': None # Uncomment if you use local images/css
            'quiet': '',  # Suppress wkhtmltopdf warnings
        }

        # Write HTML to temp file with UTF-8 encoding
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html_path = f.name

        try:
            # ✅ Create config with wkhtmltopdf path
            config = pdfkit.configuration(wkhtmltopdf=wkhtml_path)
            # ✅ Pass config to pdfkit.from_file()
            pdfkit.from_file(temp_html_path, pdf_path, options=options, configuration=config)
            print(f"✅ PDF generated: {pdf_path}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)
        # PDF → JPEG
        jpeg_result = None
        try:
            images = convert_from_path(pdf_path, poppler_path=poppler_path, dpi=150, first_page=1, last_page=1)
            if images:
                images[0].save(jpeg_path, 'JPEG', quality=85)
                jpeg_result = jpeg_path
                print(f"✅ JPEG generated: {jpeg_path}")

        except Exception as e:
            print(f"⚠️ Error converting to JPEG: {e}")

        return {
            'success': True,
            'exam_id': short_exam_id,
            'filename': filename,
            'pdf_path': pdf_path,
            'jpeg_path': jpeg_result
        }
    
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def delete_exam_files(phone, exam_date, short_exam_id):
    """
    Delete PDF and JPEG files for an exam
    """
    filename = generate_exam_file_name(phone, exam_date, short_exam_id)
    
    # Calculate absolute paths (same as above)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(base_dir, "files", "pdf", f"{filename}.pdf")
    jpeg_path = os.path.join(base_dir, "files", "jpeg", f"{filename}.jpg")
    
    deleted = []
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        deleted.append(f"PDF: {pdf_path}")
        print(f"✅ Deleted: {pdf_path}")
    
    if os.path.exists(jpeg_path):
        os.remove(jpeg_path)
        deleted.append(f"JPEG: {jpeg_path}")
        print(f"✅ Deleted: {jpeg_path}")
    
    return deleted