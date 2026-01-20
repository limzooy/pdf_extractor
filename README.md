# AWS 청구서 PDF 텍스트 추출기

AWS 청구서 PDF 파일에서 텍스트를 추출하여 CSV 파일로 변환하는 에이전트입니다.

## 기능

- PDF 파일에서 AWS 서비스별, 리전별, 상세 사용량 정보 추출
- CSV 파일로 저장
- 웹 인터페이스를 통한 PDF 업로드 및 CSV 다운로드
- 여러 PDF 파일 일괄 처리 지원

## 설치

```bash
pip install -r requirements.txt
```

## 사용 방법

### 1. 웹 서버 실행

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

### 2. 커맨드라인 사용

```bash
# 텍스트 형식으로 추출
python aws_billing_extractor.py billing.pdf -o output.txt

# CSV로 저장 (Python 코드)
python -c "from aws_billing_extractor import AWSBillingExtractorV2; e = AWSBillingExtractorV2(); e.save_to_csv('billing.pdf', 'output.csv')"
```

### 3. Python 코드에서 사용

```python
from aws_billing_extractor import AWSBillingExtractorV2

extractor = AWSBillingExtractorV2()

# CSV 파일로 저장
extractor.save_to_csv("billing.pdf", "output.csv")

# 데이터만 추출
csv_data = extractor.extract_to_csv_data(pdf_path="billing.pdf")

# 텍스트 형식으로 추출
text = extractor.extract_from_pdf("billing.pdf")
```

## CSV 출력 형식

| 컬럼 | 설명 |
|------|------|
| Service | AWS 서비스명 (예: Elastic Compute Cloud) |
| Region | 리전 (예: Asia Pacific (Seoul)) |
| Sub_Service | 서브서비스명 |
| Description | 상세 설명 |
| Usage_Quantity | 사용량 숫자 |
| Unit | 사용량 단위 |
| Amount_USD | 금액 (숫자) |
| Amount_String | 금액 (문자열) |

## 파일 구조

```
pdf_extractor/
├── app.py                    # Flask 웹 서버
├── aws_billing_extractor.py  # AWS 청구서 추출 에이전트
├── pdf_extractor.py          # 일반 PDF 텍스트 추출기
├── example.py                # 사용 예제
├── requirements.txt          # 필요 패키지
└── templates/
    └── index.html            # 웹 업로드 페이지
```

## 요구사항

- Python 3.8+
- pdfplumber
- Flask
