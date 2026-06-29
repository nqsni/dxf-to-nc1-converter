"""
NC1 Converter Web App
Flask server untuk konversi DXF -> NC1 (DSTV)
Jalankan: python app.py
Akses   : http://localhost:5000  (atau http://IP-SERVER:5000 dari komputer lain)
"""

import os
import uuid
import zipfile
from pathlib import Path
from flask import (Flask, render_template, request,
                   send_file, jsonify, after_this_request, url_for)
from converter import parse_dxf, build_nc1

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # max 64MB (banyak file)

UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
OUTPUT_FOLDER = Path(__file__).parent / 'outputs'
STATIC_FOLDER = Path(__file__).parent / 'static'
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)
STATIC_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXT = {'.dxf'}


def allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXT


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    files = request.files.getlist('dxf_files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'Tidak ada file yang dipilih.'}), 400

    # Validasi parameter global
    try:
        thickness = float(request.form.get('thickness', 0))
        if thickness <= 0:
            raise ValueError
    except ValueError:
        return jsonify({'error': 'Ketebalan harus angka positif (mm).'}), 400

    grade   = request.form.get('grade', 'SS400').strip() or 'SS400'
    qty     = max(1, int(request.form.get('qty', 1) or 1))

    uid = uuid.uuid4().hex[:8]
    results = []
    nc1_paths = []

    for file in files:
        if not file.filename or not allowed_file(file.filename):
            results.append({
                'filename': file.filename or '(kosong)',
                'error': 'Bukan file .dxf, dilewati.'
            })
            continue

        stem     = Path(file.filename).stem
        dxf_path = UPLOAD_FOLDER / f"{uid}_{stem}.dxf"
        nc1_name = f"{uid}_{stem}.nc1"
        nc1_path = OUTPUT_FOLDER / nc1_name
        file.save(str(dxf_path))

        try:
            outline_pts, holes = parse_dxf(str(dxf_path))
            xs = [p[0] for p in outline_pts]
            ys = [p[1] for p in outline_pts]
            length = max(xs) - min(xs)
            width  = max(ys) - min(ys)

            piece_mark = stem
            content = build_nc1(
                outline_pts=outline_pts,
                holes=holes,
                mark=piece_mark,
                thickness=thickness,
                grade=grade,
                qty=qty,
                drawing_no=piece_mark,
            )

            with open(nc1_path, 'w', encoding='utf-8') as f:
                f.write(content)

            nc1_paths.append((nc1_path, f"{stem}.nc1"))
            results.append({
                'success'   : True,
                'original'  : file.filename,
                'filename'  : f"{stem}.nc1",
                'download'  : url_for('download', filename=nc1_name),
                'mark'      : piece_mark,
                'length'    : round(length, 2),
                'width'     : round(width, 2),
                'thickness' : thickness,
                'grade'     : grade,
                'holes'     : len(holes),
                'preview'   : content,
            })

        except Exception as e:
            results.append({
                'original': file.filename,
                'filename': file.filename,
                'error': str(e)
            })
        finally:
            try:
                dxf_path.unlink(missing_ok=True)
            except Exception:
                pass

    # Jika lebih dari 1 file sukses, sediakan juga endpoint zip
    success_count = sum(1 for r in results if r.get('success'))
    zip_download = None
    if success_count > 1:
        zip_name = f"{uid}_all_nc1.zip"
        zip_path = OUTPUT_FOLDER / zip_name
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for nc1_path, display_name in nc1_paths:
                if nc1_path.exists():
                    zf.write(nc1_path, display_name)
        zip_download = url_for('download', filename=zip_name)

    return jsonify({
        'results'      : results,
        'total'        : len(results),
        'success_count': success_count,
        'zip_download' : zip_download,
    })


@app.route('/download/<filename>')
def download(filename):
    path = OUTPUT_FOLDER / filename
    if not path.exists():
        return 'File tidak ditemukan.', 404

    # Nama yang ditampilkan ke user (hilangkan prefix uid)
    parts = filename.split('_', 1)
    display = parts[1] if len(parts) > 1 else filename

    @after_this_request
    def cleanup(response):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return response

    mimetype = 'application/zip' if filename.endswith('.zip') else 'text/plain'
    return send_file(str(path), as_attachment=True,
                     download_name=display, mimetype=mimetype)


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("  NC1 Converter Web App")
    print("  Akses lokal   : http://localhost:5000")
    print("  Akses jaringan: http://<IP-komputer>:5000")
    print("=" * 50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)