"""
AWS 청구서 PDF 텍스트 추출 에이전트
- PDF에서 AWS 서비스별, 리전별, 상세 사용량 정보를 계층적 형식으로 추출
- CSV 파일로 저장 기능 지원
"""

import re
import csv
import io
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field

import pdfplumber


@dataclass
class UsageItem:
    """사용량 항목"""
    description: str
    usage_quantity: str = ""
    amount: str = ""


@dataclass
class RegionSection:
    """리전별 섹션"""
    region_name: str
    region_total: str = ""
    sub_services: dict = field(default_factory=dict)  # sub_service_name -> list of UsageItem
    items: list = field(default_factory=list)  # UsageItem list (sub_service가 없는 경우)


@dataclass
class ServiceSection:
    """서비스별 섹션"""
    service_name: str
    service_total: str = ""
    regions: dict = field(default_factory=dict)  # region_name -> RegionSection


class AWSBillingExtractor:
    """AWS 청구서 PDF에서 구조화된 텍스트를 추출하는 에이전트"""

    # AWS 서비스 이름 패턴
    SERVICE_NAMES = [
        "Elastic Container Service",
        "Simple Storage Service",
        "Elastic Compute Cloud",
        "Relational Database Service",
        "Glue",
        "DynamoDB",
        "Virtual Private Cloud",
        "Data Transfer",
        "Athena",
        "Lambda",
        "Elastic Load Balancing",
        "Kinesis",
        "CloudWatch",
        "EC2 Container Registry",
        "Key Management Service",
        "Elastic File System",
        "S3 Glacier Deep Archive",
        "Secrets Manager",
        "Route 53",
        "Cost Explorer",
        "Simple Email Service",
        "Simple Queue Service",
        "Certificate Manager",
        "Simple Notification Service",
        "CloudFront",
        "CodeBuild",
        "CodePipeline",
        "Step Functions",
        "API Gateway",
        "Cognito",
        "EventBridge",
        "Backup",
        "Config",
        "GuardDuty",
        "Inspector",
        "Security Hub",
        "WAF",
        "Shield",
        "Savings Plans",
        "Support",
    ]

    # 리전 이름 패턴
    REGION_PATTERNS = [
        "Asia Pacific (Seoul)",
        "Asia Pacific (Tokyo)",
        "Asia Pacific (Singapore)",
        "Asia Pacific (Sydney)",
        "Asia Pacific (Mumbai)",
        "Asia Pacific (Hong Kong)",
        "Asia Pacific (Osaka)",
        "Asia Pacific (Jakarta)",
        "US East (N. Virginia)",
        "US East (Ohio)",
        "US West (Oregon)",
        "US West (N. California)",
        "EU (Ireland)",
        "EU (Frankfurt)",
        "EU (London)",
        "EU (Paris)",
        "EU (Stockholm)",
        "EU (Milan)",
        "South America (Sao Paulo)",
        "Canada (Central)",
        "Middle East (Bahrain)",
        "Africa (Cape Town)",
        "Any",
        "Global",
    ]

    def __init__(self):
        self.services: dict = {}  # service_name -> ServiceSection

    def extract_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 AWS 청구서 정보를 추출하여 구조화된 텍스트로 반환"""

        if not Path(pdf_path).exists():
            return f"오류: 파일을 찾을 수 없습니다 - {pdf_path}"

        # PDF에서 전체 텍스트 추출
        all_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)

        full_text = "\n".join(all_text)

        # 청구서 정보 파싱
        return self._parse_billing_text(full_text)

    def _parse_billing_text(self, text: str) -> str:
        """청구서 텍스트를 파싱하여 구조화된 형식으로 변환"""

        lines = text.split('\n')
        result = []

        current_service = None
        current_region = None
        current_sub_service = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 서비스 헤더 감지 (예: "Elastic Container Service USD 234.79")
            service_match = self._match_service_header(line)
            if service_match:
                service_name, service_total = service_match

                # 이전 서비스 출력
                if current_service:
                    result.append(self._format_service(current_service))

                current_service = ServiceSection(
                    service_name=service_name,
                    service_total=service_total
                )
                current_region = None
                current_sub_service = None
                i += 1
                continue

            # 리전 헤더 감지 (예: "Asia Pacific (Seoul) USD 234.79")
            region_match = self._match_region_header(line)
            if region_match and current_service:
                region_name, region_total = region_match
                current_region = RegionSection(
                    region_name=region_name,
                    region_total=region_total
                )
                current_service.regions[region_name] = current_region
                current_sub_service = None
                i += 1
                continue

            # 서브서비스 헤더 감지 (예: "Amazon Elastic Container Service APN2-Fargate-GB-Hours USD 59.90")
            sub_service_match = self._match_sub_service_header(line)
            if sub_service_match and current_region:
                sub_service_name, sub_total = sub_service_match
                current_sub_service = sub_service_name
                if current_sub_service not in current_region.sub_services:
                    current_region.sub_services[current_sub_service] = []
                # 서브서비스 자체도 항목으로 추가 (총액 표시용)
                current_region.sub_services[current_sub_service].append(
                    UsageItem(description=sub_service_name, amount=sub_total)
                )
                i += 1
                continue

            # 사용량 상세 항목 감지 (예: "$0.059 per GB Data Processed... 2,023.848 GB USD 119.41")
            usage_match = self._match_usage_line(line)
            if usage_match and current_region:
                desc, qty, amt = usage_match
                item = UsageItem(description=desc, usage_quantity=qty, amount=amt)

                if current_sub_service and current_sub_service in current_region.sub_services:
                    current_region.sub_services[current_sub_service].append(item)
                else:
                    current_region.items.append(item)
                i += 1
                continue

            i += 1

        # 마지막 서비스 출력
        if current_service:
            result.append(self._format_service(current_service))

        return "\n".join(result)

    def _match_service_header(self, line: str) -> Optional[tuple]:
        """서비스 헤더 매칭"""
        for service_name in self.SERVICE_NAMES:
            # "Elastic Container Service USD 234.79" 패턴
            pattern = rf"^{re.escape(service_name)}\s+(USD\s*[\d,]+\.?\d*)"
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                return service_name, match.group(1)

            # "Elastic Container Service" 만 있는 경우 (다음 줄에 금액)
            if line == service_name:
                return service_name, ""

        return None

    def _match_region_header(self, line: str) -> Optional[tuple]:
        """리전 헤더 매칭"""
        for region_name in self.REGION_PATTERNS:
            # "Asia Pacific (Seoul) USD 234.79" 패턴
            pattern = rf"^{re.escape(region_name)}\s*(USD\s*[\d,]+\.?\d*)?"
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                total = match.group(1) if match.group(1) else ""
                return region_name, total

        return None

    def _match_sub_service_header(self, line: str) -> Optional[tuple]:
        """서브서비스 헤더 매칭 (Amazon XXX Service YYY USD ZZZ)"""
        # "Amazon Elastic Container Service APN2-Fargate-GB-Hours USD 59.90"
        pattern = r"^(Amazon\s+[\w\s]+(?:Service|Cloud|System)?[\w\-\s]*?)\s+(USD\s*[\d,]+\.?\d*)$"
        match = re.match(pattern, line)
        if match:
            return match.group(1).strip(), match.group(2)

        # "AWS XXX USD YYY"
        pattern2 = r"^(AWS\s+[\w\s\-]+?)\s+(USD\s*[\d,]+\.?\d*)$"
        match2 = re.match(pattern2, line)
        if match2:
            return match2.group(1).strip(), match2.group(2)

        # "EBS USD 0.73" 같은 짧은 형식
        pattern3 = r"^(EBS|Bandwidth)\s+(USD\s*[\d,]+\.?\d*)$"
        match3 = re.match(pattern3, line)
        if match3:
            return match3.group(1), match3.group(2)

        # "Elastic Load Balancing - Application USD 16.74" 같은 형식
        pattern4 = r"^([\w\s]+ - [\w\s]+)\s+(USD\s*[\d,]+\.?\d*)$"
        match4 = re.match(pattern4, line)
        if match4:
            return match4.group(1).strip(), match4.group(2)

        return None

    def _match_usage_line(self, line: str) -> Optional[tuple]:
        """사용량 상세 라인 매칭"""
        # "$0.059 per GB Data Processed by NAT Gateways 2,023.848 GB USD 119.41"
        # 가격 설명 + 사용량 + 금액 패턴
        pattern = r"^(\$[\d.,]+\s+per\s+.+?)\s+([\d,]+\.?\d*\s*[\w\-]+)\s+(USD\s*[\d,]+\.?\d*)$"
        match = re.match(pattern, line)
        if match:
            return match.group(1), match.group(2), match.group(3)

        # "AWS Fargate - Memory - Asia Pacific (Seoul) 11,722.678 hours USD 59.90"
        pattern2 = r"^([\w\s\-\(\)]+?)\s+([\d,]+\.?\d*\s*[\w\-]+)\s+(USD\s*[\d,]+\.?\d*)$"
        match2 = re.match(pattern2, line)
        if match2:
            return match2.group(1).strip(), match2.group(2), match2.group(3)

        # 사용량 없이 금액만 있는 경우
        pattern3 = r"^(.+?)\s+(USD\s*[\d,]+\.?\d*)$"
        match3 = re.match(pattern3, line)
        if match3 and not any(region in line for region in self.REGION_PATTERNS):
            return match3.group(1).strip(), "", match3.group(2)

        return None

    def _format_service(self, service: ServiceSection) -> str:
        """서비스 섹션을 지정된 형식으로 포맷팅"""
        lines = []

        # 서비스 헤더
        lines.append(f"[{service.service_name}]")
        lines.append("\t사용량 (숫자)\t\t금액 (USD)")
        lines.append(f"합계\t\t\t{service.service_total}")

        # 리전별 정보
        for region_name, region in service.regions.items():
            lines.append(region_name)

            # 서브서비스별 항목
            for sub_service_name, items in region.sub_services.items():
                for item in items:
                    if item.usage_quantity:
                        lines.append(f"{item.description}\t{item.usage_quantity}\t\t{item.amount}")
                    else:
                        lines.append(f"{item.description}\t\t\t{item.amount}")

            # 서브서비스 없는 항목
            for item in region.items:
                if item.usage_quantity:
                    lines.append(f"{item.description}\t{item.usage_quantity}\t\t{item.amount}")
                else:
                    lines.append(f"{item.description}\t\t\t{item.amount}")

        lines.append("")  # 빈 줄 추가
        return "\n".join(lines)


class AWSBillingExtractorV2:
    """개선된 AWS 청구서 추출기 - pdfplumber 테이블 추출 활용"""

    # 서비스명 목록
    SERVICE_KEYWORDS = [
        "Elastic Container Service", "Simple Storage Service", "Elastic Compute Cloud",
        "Relational Database Service", "Glue", "DynamoDB", "Virtual Private Cloud",
        "Data Transfer", "Athena", "Lambda", "Elastic Load Balancing", "Kinesis",
        "CloudWatch", "EC2 Container Registry", "Key Management Service",
        "Elastic File System", "S3 Glacier Deep Archive", "Secrets Manager",
        "Route 53", "Cost Explorer", "Simple Email Service", "Simple Queue Service",
        "Certificate Manager", "Simple Notification Service", "CloudFront",
        "Savings Plans", "Tax", "Support"
    ]

    # 리전명 목록
    REGION_KEYWORDS = [
        "Asia Pacific (Seoul)", "Asia Pacific (Tokyo)", "Asia Pacific (Singapore)",
        "Asia Pacific (Mumbai)", "Asia Pacific (Hong Kong)", "Asia Pacific (Osaka)",
        "Asia Pacific (Sydney)", "Asia Pacific (Jakarta)",
        "US East (N. Virginia)", "US East (Ohio)", "US West (Oregon)",
        "US West (N. California)", "EU (Ireland)", "EU (Frankfurt)", "EU (London)",
        "EU (Paris)", "EU (Stockholm)", "EU (Milan)", "South America (Sao Paulo)",
        "Canada (Central)", "Middle East (Bahrain)", "Africa (Cape Town)",
        "Any", "Global"
    ]

    def __init__(self):
        pass

    def extract_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 AWS 청구서를 구조화된 형식으로 추출"""

        if not Path(pdf_path).exists():
            return f"오류: 파일을 찾을 수 없습니다 - {pdf_path}"

        all_lines = self._read_pdf_lines(pdf_path)
        return self._parse_lines(all_lines)

    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """PDF 바이트에서 AWS 청구서를 구조화된 형식으로 추출"""
        all_lines = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        all_lines.append(line.strip())
        return self._parse_lines(all_lines)

    def _read_pdf_lines(self, pdf_path: str) -> List[str]:
        """PDF 파일에서 라인 목록 추출"""
        all_lines = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        all_lines.append(line.strip())
        return all_lines

    def extract_to_csv_data(self, pdf_path: str = None, pdf_bytes: bytes = None) -> List[Dict]:
        """PDF에서 AWS 청구서를 CSV용 딕셔너리 리스트로 추출"""
        if pdf_bytes:
            all_lines = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        for line in text.split('\n'):
                            all_lines.append(line.strip())
        elif pdf_path:
            if not Path(pdf_path).exists():
                return []
            all_lines = self._read_pdf_lines(pdf_path)
        else:
            return []

        return self._parse_lines_to_csv_data(all_lines)

    def _parse_lines_to_csv_data(self, lines: List[str]) -> List[Dict]:
        """라인을 파싱하여 CSV용 딕셔너리 리스트로 변환"""
        csv_data = []
        current_service = None
        current_service_total = ""
        current_region = None
        current_sub_service = None

        def is_service_header(line):
            for svc in self.SERVICE_KEYWORDS:
                if line.startswith(svc) and "USD" in line:
                    parts = line.split("USD")
                    if len(parts) >= 2:
                        return svc, "USD" + parts[-1].strip()
            return None, None

        def is_region_header(line):
            for region in self.REGION_KEYWORDS:
                if line.startswith(region):
                    if "USD" in line:
                        parts = line.split("USD")
                        return region, "USD" + parts[-1].strip()
                    return region, ""
            return None, None

        def parse_amount(amount_str):
            """USD 금액 문자열에서 숫자 추출"""
            if not amount_str:
                return 0.0
            match = re.search(r'[\d,]+\.?\d*', amount_str.replace(',', ''))
            if match:
                return float(match.group().replace(',', ''))
            return 0.0

        i = 0
        while i < len(lines):
            line = lines[i]

            if not line:
                i += 1
                continue

            if "Charges by service" in line:
                i += 1
                continue

            # 서비스 헤더 체크
            svc_name, svc_total = is_service_header(line)
            if svc_name:
                current_service = svc_name
                current_service_total = svc_total
                current_region = None
                current_sub_service = None
                i += 1
                continue

            if current_service:
                # 리전 헤더 체크
                region_name, region_total = is_region_header(line)
                if region_name:
                    current_region = region_name
                    current_sub_service = None
                    i += 1
                    continue

                # 서브서비스 헤더
                if (line.startswith("Amazon ") or line.startswith("AWS ") or
                    line.startswith("EBS ") or line.startswith("Bandwidth ") or
                    "Elastic Load Balancing -" in line):
                    if "USD" in line:
                        parts = line.rsplit("USD", 1)
                        current_sub_service = parts[0].strip()
                    i += 1
                    continue

                # 사용량 라인
                if "USD" in line:
                    parts = line.rsplit("USD", 1)
                    left_part = parts[0].strip()
                    amount = "USD" + parts[1].strip() if len(parts) > 1 else ""

                    # 사용량 추출
                    qty_match = re.search(r'([\d,]+\.?\d*)\s*([\w\-\/]+)$', left_part)
                    if qty_match:
                        qty = qty_match.group(1)
                        unit = qty_match.group(2)
                        desc = left_part[:qty_match.start()].strip()
                    else:
                        qty = ""
                        unit = ""
                        desc = left_part

                    if desc and amount:
                        csv_data.append({
                            'Service': current_service,
                            'Region': current_region or '',
                            'Description': desc,
                            'Usage_Quantity': qty,
                            'Usage_Unit': unit,
                            'Amount': parse_amount(amount),
                            'Amount_Unit': 'USD'
                        })

            i += 1

        return csv_data

    def to_csv_string(self, csv_data: List[Dict]) -> str:
        """CSV 데이터를 문자열로 변환"""
        if not csv_data:
            return ""

        output = io.StringIO()
        fieldnames = ['Service', 'Region', 'Description', 'Usage_Quantity', 'Usage_Unit', 'Amount', 'Amount_Unit']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
        return output.getvalue()

    def save_to_csv(self, pdf_path: str, output_path: str) -> bool:
        """PDF에서 추출한 데이터를 CSV 파일로 저장"""
        csv_data = self.extract_to_csv_data(pdf_path=pdf_path)
        if not csv_data:
            return False

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = ['Service', 'Region', 'Description', 'Usage_Quantity', 'Usage_Unit', 'Amount', 'Amount_Unit']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
        return True

    def _parse_lines(self, lines: list) -> str:
        """라인 단위로 파싱하여 구조화된 출력 생성"""

        result = []
        current_service = None
        current_service_total = ""
        current_region = None
        current_sub_service = None
        service_lines = []

        # 서비스명 목록
        service_keywords = [
            "Elastic Container Service", "Simple Storage Service", "Elastic Compute Cloud",
            "Relational Database Service", "Glue", "DynamoDB", "Virtual Private Cloud",
            "Data Transfer", "Athena", "Lambda", "Elastic Load Balancing", "Kinesis",
            "CloudWatch", "EC2 Container Registry", "Key Management Service",
            "Elastic File System", "S3 Glacier Deep Archive", "Secrets Manager",
            "Route 53", "Cost Explorer", "Simple Email Service", "Simple Queue Service",
            "Certificate Manager", "Simple Notification Service", "CloudFront",
            "Savings Plans", "Tax", "Support"
        ]

        # 리전명 목록
        region_keywords = [
            "Asia Pacific (Seoul)", "Asia Pacific (Tokyo)", "Asia Pacific (Singapore)",
            "Asia Pacific (Mumbai)", "Asia Pacific (Hong Kong)", "Asia Pacific (Osaka)",
            "Asia Pacific (Sydney)", "Asia Pacific (Jakarta)",
            "US East (N. Virginia)", "US East (Ohio)", "US West (Oregon)",
            "US West (N. California)", "EU (Ireland)", "EU (Frankfurt)", "EU (London)",
            "EU (Paris)", "EU (Stockholm)", "EU (Milan)", "South America (Sao Paulo)",
            "Canada (Central)", "Middle East (Bahrain)", "Africa (Cape Town)",
            "Any", "Global"
        ]

        def is_service_header(line):
            """서비스 헤더인지 확인"""
            for svc in service_keywords:
                if line.startswith(svc) and "USD" in line:
                    # "Elastic Container Service USD 234.79" 형태
                    parts = line.split("USD")
                    if len(parts) >= 2:
                        return svc, "USD" + parts[-1].strip()
            return None, None

        def is_region_header(line):
            """리전 헤더인지 확인"""
            for region in region_keywords:
                if line.startswith(region):
                    if "USD" in line:
                        parts = line.split("USD")
                        return region, "USD" + parts[-1].strip()
                    return region, ""
            return None, None

        def format_service_block(service_name, service_total, lines_data):
            """서비스 블록을 포맷팅"""
            output = []
            output.append(f"[{service_name}]")
            output.append("\t\t\t사용량 (숫자)\t\t금액 (USD)")
            output.append(f"합계\t\t\t\t\t{service_total}")

            current_region = None
            for line_info in lines_data:
                line_type, content = line_info

                if line_type == "region":
                    region_name, region_total = content
                    output.append(region_name + ("\t\t\t\t\t" + region_total if region_total else ""))
                elif line_type == "sub_service":
                    sub_name, sub_total = content
                    output.append(sub_name + ("\t\t\t\t\t" + sub_total if sub_total else ""))
                elif line_type == "item":
                    desc, qty, amt = content
                    if qty:
                        output.append(f"{desc}\t{qty}\t\t{amt}")
                    else:
                        output.append(f"{desc}\t\t\t{amt}")

            output.append("")
            return "\n".join(output)

        i = 0
        while i < len(lines):
            line = lines[i]

            # 빈 줄 스킵
            if not line:
                i += 1
                continue

            # Charges by service 이전 내용은 스킵
            if "Charges by service" in line:
                i += 1
                continue

            # 서비스 헤더 체크
            svc_name, svc_total = is_service_header(line)
            if svc_name:
                # 이전 서비스 출력
                if current_service and service_lines:
                    result.append(format_service_block(current_service, current_service_total, service_lines))

                current_service = svc_name
                current_service_total = svc_total
                service_lines = []
                i += 1
                continue

            # 현재 서비스가 있을 때만 처리
            if current_service:
                # 리전 헤더 체크
                region_name, region_total = is_region_header(line)
                if region_name:
                    service_lines.append(("region", (region_name, region_total)))
                    i += 1
                    continue

                # 서브서비스 헤더 (Amazon XXX, AWS XXX, EBS, Bandwidth 등)
                if (line.startswith("Amazon ") or line.startswith("AWS ") or
                    line.startswith("EBS ") or line.startswith("Bandwidth ") or
                    "Elastic Load Balancing -" in line):
                    if "USD" in line:
                        parts = line.rsplit("USD", 1)
                        sub_name = parts[0].strip()
                        sub_total = "USD" + parts[1].strip()
                        service_lines.append(("sub_service", (sub_name, sub_total)))
                    i += 1
                    continue

                # 사용량 라인 ($X per ... 또는 일반 항목)
                if "USD" in line:
                    # USD로 분리
                    parts = line.rsplit("USD", 1)
                    left_part = parts[0].strip()
                    amount = "USD" + parts[1].strip() if len(parts) > 1 else ""

                    # 사용량 추출 시도
                    qty_match = re.search(r'([\d,]+\.?\d*)\s*([\w\-\/]+)$', left_part)
                    if qty_match:
                        qty = qty_match.group(1) + " " + qty_match.group(2)
                        desc = left_part[:qty_match.start()].strip()
                    else:
                        qty = ""
                        desc = left_part

                    if desc and amount:
                        service_lines.append(("item", (desc, qty, amount)))

            i += 1

        # 마지막 서비스 출력
        if current_service and service_lines:
            result.append(format_service_block(current_service, current_service_total, service_lines))

        return "\n".join(result)


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='AWS 청구서 PDF 텍스트 추출 에이전트')
    parser.add_argument('pdf_path', help='AWS 청구서 PDF 파일 경로')
    parser.add_argument('-o', '--output', help='출력 파일 경로 (지정하지 않으면 터미널 출력)')
    parser.add_argument('-v', '--version', type=int, default=2, choices=[1, 2],
                        help='추출기 버전 (1: 기본, 2: 개선된 버전)')

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"AWS 청구서 PDF 텍스트 추출")
    print(f"파일: {args.pdf_path}")
    print(f"{'='*60}\n")

    if args.version == 1:
        extractor = AWSBillingExtractor()
    else:
        extractor = AWSBillingExtractorV2()

    result = extractor.extract_from_pdf(args.pdf_path)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"결과가 저장되었습니다: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
