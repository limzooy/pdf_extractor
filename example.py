"""
PDF 텍스트 추출 에이전트 사용 예제
- 일반 PDF 텍스트 추출
- AWS 청구서 PDF 구조화된 추출
"""

from pdf_extractor import PDFTextExtractor
from aws_billing_extractor import AWSBillingExtractorV2


def example_basic():
    """기본 PDF 텍스트 추출"""
    extractor = PDFTextExtractor()
    result = extractor.extract("sample.pdf")

    if result["success"]:
        print("추출된 텍스트:")
        print(result["text"])
    else:
        print(f"오류: {result['error']}")


def example_aws_billing():
    """AWS 청구서 PDF 구조화된 추출"""
    extractor = AWSBillingExtractorV2()

    # PDF 경로
    pdf_path = "aws_billing.pdf"

    # 구조화된 형식으로 추출
    result = extractor.extract_from_pdf(pdf_path)
    print(result)

    # 파일로 저장
    with open("billing_output.txt", "w", encoding="utf-8") as f:
        f.write(result)


def example_batch_aws_billing():
    """여러 AWS 청구서 PDF 일괄 처리"""
    from pathlib import Path

    extractor = AWSBillingExtractorV2()
    pdf_folder = Path("./billing_pdfs")
    output_folder = Path("./extracted_billing")
    output_folder.mkdir(exist_ok=True)

    pdf_files = list(pdf_folder.glob("*.pdf"))
    print(f"총 {len(pdf_files)}개 청구서 PDF 발견")

    for pdf_file in pdf_files:
        print(f"\n처리 중: {pdf_file.name}")
        result = extractor.extract_from_pdf(str(pdf_file))

        output_path = output_folder / f"{pdf_file.stem}_extracted.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"저장됨: {output_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("PDF 텍스트 추출 에이전트")
    print("=" * 60)
    print("\n선택하세요:")
    print("1. 일반 PDF 텍스트 추출")
    print("2. AWS 청구서 PDF 구조화 추출")

    choice = input("\n선택 (1 또는 2): ").strip()
    pdf_path = input("PDF 파일 경로를 입력하세요: ").strip()

    if not pdf_path:
        print("PDF 경로가 입력되지 않았습니다.")
        exit()

    if choice == "1":
        # 일반 PDF 추출
        extractor = PDFTextExtractor()
        result = extractor.extract(pdf_path)

        if result["success"]:
            print("\n" + "=" * 50)
            print("추출 결과:")
            print("=" * 50)
            print(result["text"][:3000])

            if len(result["text"]) > 3000:
                print(f"\n... (총 {result['char_count']}자)")

            save = input("\n파일로 저장? (y/n): ").strip().lower()
            if save == 'y':
                output_path = pdf_path.rsplit('.', 1)[0] + "_extracted.txt"
                extractor.save_to_file(result["text"], output_path)
        else:
            print(f"오류: {result['error']}")

    elif choice == "2":
        # AWS 청구서 구조화 추출
        extractor = AWSBillingExtractorV2()
        result = extractor.extract_from_pdf(pdf_path)

        print("\n" + "=" * 50)
        print("AWS 청구서 추출 결과:")
        print("=" * 50)
        print(result[:3000])

        if len(result) > 3000:
            print(f"\n... (총 {len(result)}자)")

        save = input("\n파일로 저장? (y/n): ").strip().lower()
        if save == 'y':
            output_path = pdf_path.rsplit('.', 1)[0] + "_billing_extracted.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"저장됨: {output_path}")
    else:
        print("잘못된 선택입니다.")
