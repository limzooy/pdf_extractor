"""
PDF 텍스트 추출 AI 에이전트
- 일반 PDF: PyPDF2, pdfplumber 사용
- 스캔된 PDF (이미지 기반): OCR (pytesseract) 사용
"""

import os
from pathlib import Path
from typing import Optional

# PDF 텍스트 추출 라이브러리
import PyPDF2
import pdfplumber


class PDFTextExtractor:
    """PDF 파일에서 텍스트를 추출하는 에이전트"""

    def __init__(self, use_ocr: bool = False):
        """
        Args:
            use_ocr: OCR 사용 여부 (스캔된 PDF용)
        """
        self.use_ocr = use_ocr

    def extract_with_pypdf2(self, pdf_path: str) -> str:
        """PyPDF2를 사용하여 텍스트 추출"""
        text_content = []

        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)

            print(f"[PyPDF2] 총 {total_pages}페이지 처리 중...")

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- 페이지 {page_num} ---\n{text}")

        return "\n\n".join(text_content)

    def extract_with_pdfplumber(self, pdf_path: str) -> str:
        """pdfplumber를 사용하여 텍스트 추출 (테이블 포함)"""
        text_content = []

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"[pdfplumber] 총 {total_pages}페이지 처리 중...")

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- 페이지 {page_num} ---\n{text}")

                # 테이블 추출
                tables = page.extract_tables()
                if tables:
                    for table_idx, table in enumerate(tables, 1):
                        table_text = f"\n[테이블 {table_idx}]\n"
                        for row in table:
                            row_text = " | ".join([str(cell) if cell else "" for cell in row])
                            table_text += row_text + "\n"
                        text_content.append(table_text)

        return "\n\n".join(text_content)

    def extract_with_ocr(self, pdf_path: str) -> str:
        """OCR을 사용하여 스캔된 PDF에서 텍스트 추출"""
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError:
            return "OCR 라이브러리가 설치되지 않았습니다. pip install pytesseract pdf2image 를 실행하세요."

        text_content = []

        print("[OCR] PDF를 이미지로 변환 중...")
        images = convert_from_path(pdf_path)

        print(f"[OCR] 총 {len(images)}페이지 OCR 처리 중...")
        for page_num, image in enumerate(images, 1):
            # 한국어+영어 OCR
            text = pytesseract.image_to_string(image, lang='kor+eng')
            if text.strip():
                text_content.append(f"--- 페이지 {page_num} ---\n{text}")

        return "\n\n".join(text_content)

    def extract(self, pdf_path: str, method: str = "auto") -> dict:
        """
        PDF에서 텍스트 추출

        Args:
            pdf_path: PDF 파일 경로
            method: 추출 방법 ("pypdf2", "pdfplumber", "ocr", "auto")

        Returns:
            dict: 추출 결과 (text, method, pages, success)
        """
        # 파일 존재 확인
        if not os.path.exists(pdf_path):
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {pdf_path}",
                "text": "",
                "method": None
            }

        print(f"\n{'='*50}")
        print(f"PDF 텍스트 추출 시작: {Path(pdf_path).name}")
        print(f"{'='*50}\n")

        result = {
            "success": True,
            "text": "",
            "method": method,
            "file": pdf_path
        }

        try:
            if method == "auto":
                # pdfplumber로 먼저 시도 (테이블 지원)
                text = self.extract_with_pdfplumber(pdf_path)
                result["method"] = "pdfplumber"

                # 텍스트가 거의 없으면 OCR 시도
                if len(text.strip()) < 100 and self.use_ocr:
                    print("\n텍스트가 적습니다. OCR로 재시도...")
                    text = self.extract_with_ocr(pdf_path)
                    result["method"] = "ocr"

            elif method == "pypdf2":
                text = self.extract_with_pypdf2(pdf_path)
            elif method == "pdfplumber":
                text = self.extract_with_pdfplumber(pdf_path)
            elif method == "ocr":
                text = self.extract_with_ocr(pdf_path)
            else:
                return {
                    "success": False,
                    "error": f"알 수 없는 방법: {method}",
                    "text": "",
                    "method": None
                }

            result["text"] = text
            result["char_count"] = len(text)

            print(f"\n✓ 추출 완료! (방법: {result['method']}, 문자 수: {result['char_count']})")

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            print(f"\n✗ 오류 발생: {e}")

        return result

    def save_to_file(self, text: str, output_path: str) -> bool:
        """추출된 텍스트를 파일로 저장"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"✓ 텍스트가 저장되었습니다: {output_path}")
            return True
        except Exception as e:
            print(f"✗ 저장 실패: {e}")
            return False


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='PDF 텍스트 추출 에이전트')
    parser.add_argument('pdf_path', help='PDF 파일 경로')
    parser.add_argument('-m', '--method',
                        choices=['auto', 'pypdf2', 'pdfplumber', 'ocr'],
                        default='auto',
                        help='추출 방법 (기본: auto)')
    parser.add_argument('-o', '--output', help='출력 파일 경로')
    parser.add_argument('--ocr', action='store_true',
                        help='OCR 사용 (스캔된 PDF용)')

    args = parser.parse_args()

    # 에이전트 생성 및 실행
    extractor = PDFTextExtractor(use_ocr=args.ocr)
    result = extractor.extract(args.pdf_path, method=args.method)

    if result["success"]:
        # 출력 파일 지정시 저장
        if args.output:
            extractor.save_to_file(result["text"], args.output)
        else:
            # 터미널에 출력
            print("\n" + "="*50)
            print("추출된 텍스트:")
            print("="*50)
            print(result["text"])
    else:
        print(f"오류: {result.get('error', '알 수 없는 오류')}")


if __name__ == "__main__":
    main()
