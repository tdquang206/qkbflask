import os

# generate filename for pdf and jpeg on server
def generate_exam_file_name(phone, exam_date, exam_id):
    # phone_date_hex[:8]
    random_part = str(exam_id)[:8].replace('-','')
    date = str(exam_date).replace('-', '')
    
    return f"{phone}_{date}_{random_part}"

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
        <title>Phiếu Khám</title>
        <style>
          @page {{ size: A5 portrait; margin: 1cm; }}
          body {{ font-family: sans-serif; font-size: 11pt; }}
          h2 {{ text-align: center; margin-bottom: 1em; }}
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

        filename = generate_exam_file_name(phone, date, short_exam_id)
        pdf_dir = f"files/pdf"
        jpeg_dir = f"files/jpeg"
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
            'no-outline': None,
        }
        
        pdfkit.from_string(html_content, pdf_path, options=options)
        print(f"✅ PDF generated: {pdf_path}")

        # PDF → JPEG
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
            if images:
                images[0].save(jpeg_path, 'JPEG', quality=85)
                print(f"✅ JPEG generated: {jpeg_path}")
        except ImportError:
            print("⚠️ pdf2image not installed - JPEG skipped")
            jpeg_path = None
        except Exception as e:
            print(f"⚠️ Error converting to JPEG: {e}")
            jpeg_path = None
        
        return {
            'success': True,
            'exam_id': short_exam_id,
            'filename': filename,
            'pdf_path': pdf_path,
            'jpeg_path': jpeg_path
        }
    
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def delete_exam_files(phone, exam_date, short_exam_id):
    """
    Delete PDF and JPEG files for an exam
    """
    import shutil
    
    filename = generate_exam_file_name(phone, exam_date, short_exam_id)
    
    pdf_path = os.path.join("files/pdf", f"{filename}.pdf")
    jpeg_path = os.path.join("files/jpeg", f"{filename}.jpg")
    
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