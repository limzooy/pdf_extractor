"""
AWS 청구서 PDF 텍스트 추출 웹 애플리케이션
- localhost에서 PDF 파일을 업로드하면 CSV로 변환하여 다운로드
"""

import os
import io
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
from werkzeug.utils import secure_filename

from aws_billing_extractor import AWSBillingExtractorV2

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 최대 50MB
app.config['UPLOAD_FOLDER'] = 'uploads'

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 허용된 확장자
ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """PDF 파일 업로드 및 CSV 변환"""

    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': '파일이 선택되지 않았습니다'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'PDF 파일만 업로드 가능합니다'}), 400

    try:
        # PDF 바이트 읽기
        pdf_bytes = file.read()

        # PDF에서 데이터 추출
        extractor = AWSBillingExtractorV2()
        csv_data = extractor.extract_to_csv_data(pdf_bytes=pdf_bytes)

        if not csv_data:
            return jsonify({'error': 'PDF에서 청구서 데이터를 추출할 수 없습니다'}), 400

        # CSV 문자열 생성
        csv_string = extractor.to_csv_string(csv_data)

        # 파일명 생성
        original_name = secure_filename(file.filename)
        base_name = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"{base_name}_{timestamp}.csv"

        # CSV 파일을 메모리에서 직접 전송
        csv_bytes = csv_string.encode('utf-8-sig')
        return send_file(
            io.BytesIO(csv_bytes),
            mimetype='text/csv',
            as_attachment=True,
            download_name=csv_filename
        )

    except Exception as e:
        return jsonify({'error': f'처리 중 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/upload-multiple', methods=['POST'])
def upload_multiple_files():
    """여러 PDF 파일 업로드 및 CSV 변환"""

    if 'files' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400

    files = request.files.getlist('files')

    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': '파일이 선택되지 않았습니다'}), 400

    results = []
    extractor = AWSBillingExtractorV2()

    for file in files:
        if file.filename == '' or not allowed_file(file.filename):
            continue

        try:
            pdf_bytes = file.read()
            csv_data = extractor.extract_to_csv_data(pdf_bytes=pdf_bytes)

            if csv_data:
                results.extend(csv_data)

        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
            continue

    if not results:
        return jsonify({'error': 'PDF에서 데이터를 추출할 수 없습니다'}), 400

    # 합쳐진 CSV 생성
    csv_string = extractor.to_csv_string(results)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"aws_billing_merged_{timestamp}.csv"

    csv_bytes = csv_string.encode('utf-8-sig')
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype='text/csv',
        as_attachment=True,
        download_name=csv_filename
    )


@app.route('/preview', methods=['POST'])
def preview_data():
    """CSV 데이터 미리보기 (JSON 반환)"""

    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400

    file = request.files['file']

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'PDF 파일만 업로드 가능합니다'}), 400

    try:
        pdf_bytes = file.read()
        extractor = AWSBillingExtractorV2()
        csv_data = extractor.extract_to_csv_data(pdf_bytes=pdf_bytes)

        if not csv_data:
            return jsonify({'error': 'PDF에서 데이터를 추출할 수 없습니다'}), 400

        # 서비스별 요약
        service_summary = {}
        for row in csv_data:
            service = row['Service']
            if service not in service_summary:
                service_summary[service] = {'count': 0, 'total': 0.0}
            service_summary[service]['count'] += 1
            service_summary[service]['total'] += row['Amount_USD']

        return jsonify({
            'success': True,
            'total_rows': len(csv_data),
            'service_summary': service_summary,
            'preview': csv_data[:20]  # 처음 20개 항목만 미리보기
        })

    except Exception as e:
        return jsonify({'error': f'처리 중 오류: {str(e)}'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("AWS 청구서 PDF 추출 웹 서버")
    print("=" * 60)
    print("\n브라우저에서 http://localhost:5000 접속하세요\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
