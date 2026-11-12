from __future__ import annotations

import io
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import pandas as pd
import requests
import pymupdf
from bs4 import BeautifulSoup


# ============================================================================
# CẤU HÌNH CHUNG
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
DATASET_DIR = PROJECT_ROOT / "data" / "dataset"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

HTML_VERIFIED_FILE = RAW_DIR / "admission_scores_2025_html_verified.csv"
DOCUMENT_SOURCES_FILE = RAW_DIR / "document_sources_2025_verified.csv"
PDF_ANALYSIS_FILE = RAW_DIR / "pdf_source_analysis_2025.csv"
THUYLOI_VERIFIED_FILE = RAW_DIR / "admission_scores_2025_pdf_thuyloi_verified.csv"
THUYLOI_RAW_FILE = RAW_DIR / "admission_scores_2025_pdf_thuyloi_raw.csv"

AUTO_FILE = PROCESSED_DIR / "admission_scores_2025_auto.csv"
REVIEW_FILE = PROCESSED_DIR / "admission_scores_2025_review.csv"
FINAL_FILE = PROCESSED_DIR / "admission_scores_2025_final.csv"
ML_READY_FILE = PROCESSED_DIR / "admission_scores_2025_ml_ready.csv"
ML_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2025_ml_excluded.csv"
# V6: một cache duy nhất để khóa các fallback TS247 đã pass validation,
# tránh việc chạy lại live web làm mất trường do nội dung/encoding thay đổi giữa các request.
FALLBACK_CACHE_FILE = RAW_DIR / "admission_scores_2025_fallback_cache.csv"


YEAR = 2025
PIPELINE_VERSION = "2025-V6.1-FINALIZE-2025-ADD-DAU-20260907"

CANONICAL_COLUMNS = [
    "university_name",
    "major_code",
    "major_name",
    "year",
    "admission_method_codes",
    "combination",
    "cutoff_score",
    "admission_note",
    "source_url",
]

REVIEW_COLUMNS = [
    "university_name",
    "source_type",
    "status",
    "reason",
    "detected_method",
    "candidate_rows",
    "page_url",
    "source_url",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    )
}

# Nguồn dự phòng có cấu trúc rõ theo từng phương thức.
# Chỉ dùng khi nguồn chính thức hiện tại không tự parse được.
TS247_INDEX_URL = "https://diemthi.tuyensinh247.com/diem-chuan.html"
TS247_BASE = "https://diemthi.tuyensinh247.com"
TS247_SKIP_SCHOOLS = {
    "đại học huế",       # nguồn umbrella, không phải một trường đơn lẻ
    "đại học thái nguyên",  # nguồn umbrella, gồm nhiều trường thành viên
}

# V3: khóa mã trường cho các tên rất dễ fuzzy-match nhầm.
# Hai trường "Vinh" và "Vĩnh Long" là lỗi thật đã phát hiện ở V2.
# Dùng MÃ TRƯỜNG thay vì hard-code toàn bộ URL để vẫn tương thích khi slug đổi.
TS247_EXACT_SCHOOL_CODES = {
    # Hai trường từng bị match nhầm ở V2.
    "trường đh sư phạm kỹ thuật vinh": "SKV",
    "trường đh sư phạm kỹ thuật vĩnh long": "VLU",

    # V4: các tên trong source map 2025 đã đối chiếu với mã trường trên
    # Tuyensinh247. Khóa bằng code để không phụ thuộc fuzzy-name/slug.
    "hv y dược học cổ truyền vn": "HYD",
    "trường đh dầu khí vn": "PVU",
    "trường đh hải phòng": "THP",
    "trường đh kh sức khỏe - đhqghcm": "QSY",
    "trường đh khánh hòa": "UKH",
    "trường đh kinh tế - đhqghn": "QHE",
    "trường đh kiến trúc hn": "KTA",
    "trường đh kỹ thuật y dược đà nẵng": "YDN",
    "trường đh luật tphcm": "LPS",
    "trường đh sp kỹ thuật nam định": "SKN",
    "trường đh tiền giang": "TTG",
    "trường đh tài chính - kế toán": "UFA",
    "trường đh xây dựng hà nội": "XDA",
}


# V5: với các trường còn REVIEW ở V4, URL score/info được khóa theo đúng mã trường.
# Mục đích là không phụ thuộc slug/link-discovery thay đổi của TS247.
TS247_EXACT_SOURCE_URLS = {
    "trường đh khánh hòa": {
        "code": "UKH",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-khanh-hoa-UKH.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-khanh-hoa-UKH.html",
    },
    "trường đh kinh tế - đhqghn": {
        "code": "QHE",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-kinh-te-ha-noi-QHE.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-kinh-te-dai-hoc-quoc-gia-ha-noi-QHE.html",
    },
    "trường đh hải phòng": {
        "code": "THP",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-hai-phong-THP.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-hai-phong-THP.html",
    },
    "trường đh sp kỹ thuật nam định": {
        "code": "SKN",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-su-pham-ky-thuat-nam-dinh-SKN.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-su-pham-ky-thuat-nam-dinh-SKN.html",
    },
    "trường đh tiền giang": {
        "code": "TTG",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-tien-giang-TTG.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-tien-giang-TTG.html",
    },
    "trường đh tài chính - kế toán": {
        "code": "UFA",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-tai-chinh-ke-toan-UFA.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-tai-chinh-ke-toan-UFA.html",
    },
    "trường đh xây dựng hà nội": {
        "code": "XDA",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-xay-dung-ha-noi-XDA.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-xay-dung-ha-noi-XDA.html",
    },
    # V6: khóa URL Sài Gòn để retry/caching không phụ thuộc fuzzy slug.
    "trường đh sài gòn": {
        "code": "SGD",
        "score_url": "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-sai-gon-SGD.html",
        "info_url": "https://diemthi.tuyensinh247.com/thong-tin-dai-hoc-sai-gon-SGD.html",
    },
}

# V5: catalog 2025 cố định cho hai trường mà catalog 2026 đã đổi tên/chia nhóm,
# khiến fuzzy-map từ bảng điểm 2025 sang mã ngành bị sai hoặc xung đột.
# Các mapping dưới đây chỉ dùng cho đúng YEAR=2025 và đúng mã trường đã khóa.
TS247_2025_NAME_CODE_MAPS = {
    "THP": {
        "giáo dục mầm non": ["7140201_01"],
        "giáo dục tiểu học": ["7140202_01"],
        "giáo dục thể chất": ["7140206_01"],
        "sư phạm toán học": ["7140209_01"],
        "sư phạm ngữ văn": ["7140217_01"],
        "sư phạm tiếng anh": ["7140231_01"],
        "ngôn ngữ anh": ["7220201_01"],
        "ngôn ngữ trung quốc": ["7220204_01"],
        "kinh tế ngoại thương": ["7310101_02"],
        "quản lý kinh tế": ["7310101_03"],
        "logistics và vận tải đa phương thức": ["7310101_04"],
        "logistics và vận tải đa phương thức (clc)": ["7310101_20"],
        "quản trị kinh doanh": ["7340101_01"],
        "quản trị tài chính kế toán": ["7340101_02"],
        "kinh doanh số và đổi mới sáng tạo (clc)": ["7340101_20"],
        "marketing số": ["7340115_01"],
        "thương mại điện tử": ["7340122_01"],
        "tài chính doanh nghiệp": ["7340201_02"],
        "kế toán doanh nghiệp": ["7340301_02"],
        "kế toán - kiểm toán": ["7340301_03"],
        "kế toán doanh nghiệp theo định hướng acca (clc)": ["7340301_20"],
        "luật": ["7380101_01"],
        "công nghệ thông tin": ["7480201_01"],
        "trí tuệ nhân tạo và khoa học dữ liệu": ["7480201_02"],
        "thiết kế game và multimedia (clc)": ["7480201_20"],
        "xây dựng dân dụng và công nghiệp": ["7510103_02"],
        "công nghệ chế tạo máy": ["7510202_01"],
        "công nghệ kỹ thuật cơ điện tử": ["7510203_01"],
        "điện công nghiệp và dân dụng": ["7510301_02"],
        "công nghệ điện tử, vi mạch và bán dẫn (clc)": ["7510301_20"],
        "điện tự động công nghiệp": ["7510303_02"],
        "kiến trúc": ["7580101_01"],
        "công tác xã hội": ["7760101_01"],
        "quản trị dịch vụ du lịch và lữ hành": ["7810103_01"],
        "quản trị lữ hành, khách sạn": ["7810103_02"],
        "hướng dẫn du lịch": ["7810103_03"],
    },
    "UKH": {
        "giáo dục tiểu học": ["7140202"],
        "sư phạm toán học": ["7140209"],
        "sư phạm vật lý": ["7140211"],
        "sư phạm ngữ văn": ["7140217"],
        "sư phạm tiếng anh": ["7140231"],
        "sư phạm lịch sử - địa lý": ["7140249"],
        "sư phạm lịch sử - địa lí": ["7140249"],
        "ngôn ngữ anh": ["7220201"],
        "ngôn ngữ anh (tiếng anh du lịch)": ["7220201"],
        "ngôn ngữ anh - ngôn ngữ anh - ngôn ngữ anh (tiếng anh du lịch)": ["7220201"],
        "ngôn ngữ học (tiếng trung quốc)": ["7229020"],
        "văn học (báo chí - truyền thông)": ["7229030"],
        "văn học (báo chí-truyền thông)": ["7229030"],
        "văn hóa học (văn hóa - truyền thông)": ["7229040"],
        "văn hoá học (văn hóa - truyền thông)": ["7229040"],
        "việt nam học (văn hóa du lịch)": ["7310630"],
        "việt nam học (văn hoá du lịch)": ["7310630"],
        "quản trị kinh doanh": ["7340101"],
        "quản trị kinh doanh - quản trị kinh doanh - quản trị kinh doanh (quản lý bán lẻ) - quản trị kinh doanh (marketing) - quản trị kinh doanh (nhà hàng và dịch vụ ăn uống)": ["7340101"],
        "sinh học ứng dụng (dược liệu)": ["7420203"],
        "hóa học (hóa dược - sản phẩm thiên nhiên)": ["7440112"],
        "hoá học (hóa dược - sản phẩm thiên nhiên)": ["7440112"],
        "du lịch": ["7810101"],
        "quản trị dịch vụ du lịch và lữ hành": ["7810103"],
        "quản trị khách sạn": ["7810201"],
    },
    "QHE": {
        "kinh tế": ["7310101"],
        "kinh tế phát triển": ["7310105"],
        "kinh tế quốc tế": ["7310106"],
        "quản trị kinh doanh": ["7340101"],
        "tài chính - ngân hàng": ["7340201"],
        "tài chính – ngân hàng": ["7340201"],
        "kế toán": ["7340301"],
    },
    "SKN": {
        "quản trị kinh doanh": ["7340101"],
        "quản trị kinh doanh (chuyên ngành logistics)": ["7340101_1"],
        "quản trị kinh doanh - chuyên ngành logistics": ["7340101_1"],
        "kế toán": ["7340301"],
        "khoa học máy tính": ["7480101"],
        "công nghệ thông tin": ["7480201"],
        "công nghệ thông tin (chuyên ngành đồ họa máy tính)": ["7480201_1"],
        "công nghệ thông tin - chuyên ngành đồ họa máy tính": ["7480201_1"],
        "công nghệ kỹ thuật cơ khí": ["7510201"],
        "công nghệ kỹ thuật cơ khí (chuyên ngành công nghệ khuôn mẫu)": ["7510201_1"],
        "công nghệ kỹ thuật cơ khí - chuyên ngành công nghệ khuôn mẫu": ["7510201_1"],
        "công nghệ kỹ thuật khuôn mẫu": ["7510201_1"],
        "công nghệ chế tạo máy": ["7510202"],
        "công nghệ kỹ thuật cơ điện tử": ["7510203"],
        "công nghệ kỹ thuật ô tô": ["7510205"],
        "công nghệ kỹ thuật điện, điện tử": ["7510301"],
        "công nghệ kỹ thuật điện, điện tử (chuyên ngành công nghệ kỹ thuật điện)": ["7510301_1"],
        "công nghệ kỹ thuật điện, điện tử - chuyên ngành công nghệ kỹ thuật điện": ["7510301_1"],
        "công nghệ kỹ thuật điện, điện tử (chuyên ngành hệ thống điện)": ["7510301_2"],
        "công nghệ kỹ thuật điện, điện tử - chuyên ngành hệ thống điện": ["7510301_2"],
        "công nghệ kỹ thuật điện, điện tử (chuyên ngành công nghệ điện lạnh và điều hòa không khí)": ["7510301_3"],
        "công nghệ kỹ thuật điện, điện tử - chuyên ngành công nghệ điện lạnh và điều hòa không khí": ["7510301_3"],
        "công nghệ kỹ thuật điều khiển và tự động hóa": ["7510303"],
    },
    "TTG": {
        "văn hóa học": ["7229040"],
        "văn hoá học": ["7229040"],
        "kinh tế": ["7310101"],
        "quản trị kinh doanh": ["7340101"],
        "tài chính - ngân hàng": ["7340201"],
        "tài chính – ngân hàng": ["7340201"],
        "kế toán": ["7340301"],
        "luật": ["7380101"],
        "công nghệ sinh học": ["7420201"],
        "công nghệ thông tin": ["7480201"],
        "công nghệ kỹ thuật xây dựng": ["7510103"],
        "công nghệ kỹ thuật cơ khí": ["7510201"],
        "công nghệ kỹ thuật cơ điện tử": ["7510203"],
        "công nghệ kỹ thuật ô tô": ["7510205"],
        "công nghệ kỹ thuật điều khiển và tự động hóa": ["7510303"],
        "công nghệ thực phẩm": ["7540101"],
        "bảo vệ thực vật": ["7620112"],
        "nuôi trồng thủy sản": ["7620301"],
        "thú y": ["7640101"],
        "du lịch": ["7810101"],
    },
    "UFA": {
        "quản trị kinh doanh": ["7340101"],
        "kinh doanh quốc tế": ["7340120"],
        "tài chính - ngân hàng": ["7340201"],
        "tài chính – ngân hàng": ["7340201"],
        "kế toán": ["7340301"],
        "luật kinh tế": ["7380107"],
    },
    "XDA": {
        "mỹ thuật đô thị": ["7210110"],
        "ctđt nghệ thuật và thiết kế": ["72104_NT1", "72104_NT2", "72104_NT3"],
        "quản lý dự án": ["7340409"],
        "khoa học dữ liệu": ["7460108"],
        "công nghệ thông tin": ["7480201"],
        "công nghệ thông tin/ công nghệ đa phương tiện": ["7480201_01"],
        "công nghệ thông tin/ an toàn thông tin": ["7480201_02"],
        "công nghệ kỹ thuật xây dựng": ["7510103"],
        "công nghệ kỹ thuật vật liệu xây dựng": ["7510105"],
        "logistics và quản lý chuỗi cung ứng": ["7510605"],
        "logistics và quản lý chuỗi cung ứng/ logistics đô thị": ["7510605_01"],
        "logistics và quản lý chuỗi cung ứng/ logistics công nghiệp": ["7510605_02"],
        "kỹ thuật cơ khí": ["7520103"],
        "kỹ thuật cơ khí/ máy xây dựng": ["7520103_01"],
        "kỹ thuật cơ khí/ kỹ thuật cơ điện": ["7520103_03"],
        "kỹ thuật cơ khí/ kỹ thuật ô tô": ["7520103_04"],
        "kỹ thuật điện": ["7520201"],
        "kỹ thuật điều khiển và tự động hóa": ["7520216"],
        "kỹ thuật vật liệu": ["7520309"],
        "kỹ thuật môi trường": ["7520320"],
        "kiến trúc": ["7580101"],
        "kiến trúc/kiến trúc công nghệ": ["7580101_02"],
        "kiến trúc cảnh quan": ["7580102"],
        "kiến trúc nội thất": ["7580103"],
        "quy hoạch vùng và đô thị": ["7580105"],
        "kỹ thuật xây dựng/ xây dựng dân dụng và công nghiệp": ["7580201_01"],
        "kỹ thuật xây dựng/ hệ thống kỹ thuật trong công trình": ["7580201_02"],
        "kỹ thuật xây dựng/ tin học xây dựng": ["7580201_03"],
        "kỹ thuật xây dựng/ kỹ thuật công trình thủy": ["7580201_04"],
        "kỹ thuật xây dựng/ kỹ thuật công trình biển": ["7580201_05"],
        "kỹ thuật xây dựng công trình giao thông/ xây dựng cầu đường": ["7580205_01"],
        "kỹ thuật xây dựng công trình giao thông/ đường sắt tốc độ cao và đường sắt đô thị": ["7580205_02"],
        "kỹ thuật cấp thoát nước/ kỹ thuật nước - môi trường nước": ["7580213_01"],
        "kinh tế xây dựng": ["7580301"],
        "quản lý xây dựng/ kinh tế và quản lý đô thị": ["7580302_01"],
        "quản lý xây dựng/ kinh tế và quản lý bất động sản": ["7580302_02"],
        "quản lý xây dựng/ quản lý hạ tầng, đất đai đô thị": ["7580302_03"],
        "quản lý xây dựng/ kiểm toán đầu tư xây dựng": ["7580302_04"],
    },
}

# Các tên bị TS247 rút gọn làm mất phần mô tả chương trình.
# Dùng chính score 2025 + tên để phân biệt mã xét tuyển, không suy đoán theo thứ tự dòng.
TS247_2025_NAME_SCORE_CODE_MAPS = {
    "XDA": {
        ("khoa học máy tính", 25.50): ["7480101"],
        ("khoa học máy tính", 22.70): ["7480101_QT"],
        ("kỹ thuật xây dựng", 23.85): ["7580201"],
        ("kỹ thuật xây dựng", 21.00): ["7580201_CLC"],
        ("kỹ thuật xây dựng", 22.00): ["7580201_QT"],
    },
}

# Ngưỡng V3 cho fuzzy matching trường. Nếu không đủ rõ thì REVIEW, không đoán.
TS247_MATCH_MIN_SCORE = 0.72
TS247_MATCH_MIN_MARGIN = 0.055
TS247_MATCH_MIN_SOURCE_COVERAGE = 0.80
TS247_MATCH_MIN_CANDIDATE_COVERAGE = 0.72

# Fingerprint giống nhau gần như toàn bộ giữa hai trường là dấu hiệu cross-school contamination.
FALLBACK_FINGERPRINT_MIN_ROWS = 8
FALLBACK_FINGERPRINT_OVERLAP = 0.95

# V4: một số trang TS247 đặt các dòng "kết hợp" hoặc thang có hệ số ngay trong
# khu vực hiển thị Điểm thi THPT. Các dòng này KHÔNG cùng thang 30 với input AI.
TS247_UNSAFE_ROW_NOTE_MARKERS = (
    "nhân 2",
    "nhan 2",
    "thang 40",
    "thang điểm 40",
    "xét 2 môn thi tn và ccnnqt",
    "xet 2 mon thi tn va ccnnqt",
    "ccnnqt",
    "chứng chỉ",
    "chung chi",
)

# Trường này đã xác minh có cấu trúc THPT nhiều môn nhân hệ số/thang 40.
# Không nhận fallback tự động vào dataset thang 30 dù một số giá trị tình cờ <=30.
TS247_FORCE_REVIEW_SCHOOLS = {
    "trường đh tôn đức thắng",
    # "Trường ĐH Ngoại thương" trong source map không ghi cơ sở Bắc/Nam,
    # trong khi TS247 tách NTH/NTS và điểm khác nhau => không được tự chọn một cơ sở.
    "trường đh ngoại thương",
}

# Chỉ retry verify=False cho host đã biết có lỗi chứng chỉ trong batch trước.
SSL_RETRY_HOSTS = {
    "gateway.ulsa.edu.vn",
}

# Các PDF đã kiểm tra thủ công và biết rằng text/font/cấu trúc không đủ an toàn
# để tự động nhận vào dataset THPT.
FORCE_REVIEW_SCHOOLS = {
    "trường đh luật hà nội",
    "trường đh quảng nam",
    "trường đh thái bình",
    "trường đh tài chính - qtkd",
    "trường đh y khoa vinh",
    # Tôn Đức Thắng dùng bảng rất phức tạp, nhiều thang điểm/môn nhân hệ số.
    "trường đh tôn đức thắng",
    # Đại học Huế có cột 'Điểm thi tốt nghiệp THPT/Kết hợp' => chưa xem là THPT thuần.
    "đại học huế",
}

# V6 final: 4 nguồn được giữ REVIEW có chủ đích vì không thể đưa thẳng vào
# dataset THPT-30 mà không làm sai nghĩa dữ liệu hoặc gộp sai trường thành viên.
INTENTIONAL_REVIEW_SCHOOLS = {
    "trường đh ngoại thương",
    "trường đh tôn đức thắng",
    "đại học huế",
    "đại học thái nguyên",
}

MOJIBAKE_MARKERS = (
    "�",
    "\x7f",
    "trüng",
    "tuyén",
    "näm",
    "dgi hoc",
    "h9c",
    "phü",
    "luät",
    "thöng",
)

THPT_POSITIVE_MARKERS = (
    "thi tốt nghiệp thpt",
    "kết quả thi tốt nghiệp thpt",
    "điểm thi tốt nghiệp thpt",
    "xét tuyển kết quả thi tốt nghiệp thpt",
    "xét tuyển theo kết quả thi tốt nghiệp thpt",
    "thi thpt",
)

THPT_NEGATIVE_MARKERS = (
    "học bạ",
    "học tập thpt",
    "đánh giá năng lực",
    "đgnl",
    "đánh giá tư duy",
    "vsat",
    "v-sat",
    "sat",
    "tuyển thẳng",
)

MAJOR_CODE_PATTERNS = [
    re.compile(r"^[A-Z]{1,4}\d{3,10}[A-Z]{0,2}$", re.I),
    re.compile(r"^\d{7,8}$"),
]


# ============================================================================
# KIỂU KẾT QUẢ
# ============================================================================

@dataclass
class ParseResult:
    rows: list[dict]
    method_code: str = ""
    reason: str = ""
    context_text: str = ""


# ============================================================================
# TEXT / NORMALIZE
# ============================================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    if text.lower() in {"nan", "none", "<na>"}:
        return ""

    return text


def norm_lower(value) -> str:
    return clean_text(value).lower()


def normalize_school(value) -> str:
    text = norm_lower(value)
    text = text.replace("đại học", "đh")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def looks_garbled(text: str) -> bool:
    low = norm_lower(text)
    if not low:
        return False
    return any(marker in low for marker in MOJIBAKE_MARKERS)


def parse_number(value) -> Optional[float]:
    text = clean_text(value)
    if not text:
        return None

    text = text.replace(",", ".")
    text = text.replace(" ", "")

    if not re.fullmatch(r"\d{1,4}(?:\.\d{1,4})?", text):
        return None

    try:
        return float(text)
    except ValueError:
        return None


def parse_thpt_score(value) -> Optional[float]:
    number = parse_number(value)
    if number is None:
        return None

    # Chỉ dùng để phát hiện candidate THPT.
    # >40 thường là ĐGNL/V-SAT/SAT hoặc thang khác => không nhận tự động.
    if 0 < number <= 40:
        return number
    return None


def is_major_code(value) -> bool:
    text = clean_text(value).replace(" ", "")
    if not text:
        return False
    return any(pattern.fullmatch(text) for pattern in MAJOR_CODE_PATTERNS)


def normalize_major_code(value) -> str:
    return clean_text(value).replace(" ", "").upper()


def contains_thpt_positive(text: str) -> bool:
    low = norm_lower(text)
    return any(marker in low for marker in THPT_POSITIVE_MARKERS)


def contains_negative_method(text: str) -> bool:
    low = norm_lower(text)
    return any(marker in low for marker in THPT_NEGATIVE_MARKERS)


# ============================================================================
# METHOD DETECTION
# ============================================================================

def detect_thpt_method_code(text: str) -> str:
    """
    Chỉ trả code khi tài liệu tự mô tả rõ phương thức đó là kết quả thi TN THPT.
    Nếu không có code nhưng có THPT rõ ràng => 'THPT'.
    """
    raw = clean_text(text)
    low = raw.lower()

    # PT100 / PT1 / PT4 ... nằm gần cụm thi tốt nghiệp THPT.
    patterns = [
        r"\b(pt\s*\d{1,3})\b[^\n\.]{0,120}?(?:xét tuyển[^\n\.]{0,60}?)?(?:kết quả\s+)?thi\s+tốt\s+nghiệp\s+thpt",
        r"\b(pt\s*\d{1,3})\b[^\n\.]{0,120}?tốt\s+nghiệp\s+thpt",
        r"phương\s*thức\s*(\d{1,3})[^\n\.]{0,120}?(?:kết quả\s+)?thi\s+tốt\s+nghiệp\s+thpt",
        r"phương\s*thức\s*(\d{1,3})[^\n\.]{0,120}?tốt\s+nghiệp\s+thpt",
    ]

    for pattern in patterns:
        match = re.search(pattern, low, flags=re.I)
        if not match:
            continue
        code = match.group(1).upper().replace(" ", "")
        if code.isdigit():
            code = f"PT{code}"
        return code

    if contains_thpt_positive(raw):
        return "THPT"

    return ""


def document_has_unsafe_scale(text: str) -> bool:
    low = norm_lower(text)

    # Tôn Đức Thắng và các bảng tương tự: PT THPT nhưng thang 40 / môn nhân hệ số.
    if "thang 40" in low or "thang điểm 40" in low:
        return True

    # Huế: cột gộp THPT/Kết hợp, không xác nhận được THPT thuần.
    if re.search(r"tốt\s+nghiệp\s+thpt\s*/\s*kết\s+hợp", low):
        return True

    return False


# ============================================================================
# NETWORK
# ============================================================================

def get_url(url: str, timeout: int = 45) -> requests.Response:
    url = clean_text(url)
    if not url:
        raise ValueError("URL rỗng")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
            verify=True,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError:
        host = urlparse(url).netloc.lower()
        if host not in SSL_RETRY_HOSTS:
            raise

        # Chỉ retry có kiểm soát cho host đã biết bị lỗi certificate.
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
            verify=False,
        )
        response.raise_for_status()
        return response


def resolve_google_viewer_url(url: str) -> str:
    parsed = urlparse(url)
    if "docs.google.com" in parsed.netloc.lower() and "viewer" in parsed.path.lower():
        query = parse_qs(parsed.query)
        if query.get("url"):
            return unquote(query["url"][0])
    return url


def extract_google_id(url: str) -> str:
    patterns = [
        r"/document/d/([^/]+)",
        r"/file/d/([^/]+)",
        r"[?&]id=([^&]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


# ============================================================================
# TABLE UTILITIES
# ============================================================================

def dataframe_to_grid(df: pd.DataFrame) -> list[list[str]]:
    grid: list[list[str]] = []

    # Giữ cả tên cột vì PyMuPDF thường đưa một phần header lên DataFrame columns.
    grid.append([clean_text(col) for col in df.columns])

    for _, row in df.iterrows():
        grid.append([clean_text(v) for v in row.tolist()])

    width = max((len(row) for row in grid), default=0)
    for row in grid:
        row.extend([""] * (width - len(row)))

    return grid


def html_tables_to_grids(html_text: str) -> list[list[list[str]]]:
    try:
        tables = pd.read_html(
            io.StringIO(html_text),
            header=None,
            thousands=None,
            decimal=",",
        )
    except Exception:
        return []

    grids: list[list[list[str]]] = []
    for df in tables:
        if df.empty:
            continue
        grid = [[clean_text(v) for v in row] for row in df.astype(object).values.tolist()]
        width = max((len(row) for row in grid), default=0)
        for row in grid:
            row.extend([""] * (width - len(row)))
        grids.append(grid)
    return grids


def build_column_context(grid: list[list[str]], max_header_rows: int = 6) -> list[str]:
    if not grid:
        return []
    width = max(len(row) for row in grid)
    contexts = []
    for col in range(width):
        parts = []
        for row in grid[:max_header_rows]:
            if col < len(row) and clean_text(row[col]):
                parts.append(clean_text(row[col]))
        contexts.append(" ".join(parts))
    return contexts


def detect_data_start(grid: list[list[str]]) -> int:
    for i, row in enumerate(grid):
        if any(is_major_code(cell) for cell in row):
            return i
    return len(grid)


def infer_code_column(grid: list[list[str]], data_start: int, contexts: list[str]) -> Optional[int]:
    for idx, context in enumerate(contexts):
        low = norm_lower(context)
        if "mã ngành" in low or "mã tuyển sinh" in low or "mã tuyển" in low:
            return idx

    width = len(contexts)
    best_idx = None
    best_count = 0
    for col in range(width):
        count = 0
        for row in grid[data_start : data_start + 60]:
            if col < len(row) and is_major_code(row[col]):
                count += 1
        if count > best_count:
            best_count = count
            best_idx = col
    return best_idx


def infer_name_column(contexts: list[str]) -> Optional[int]:
    priorities = (
        "tên ngành/chương trình",
        "tên ngành",
        "ngành đào tạo",
        "ngành/chương trình",
    )
    for marker in priorities:
        for idx, context in enumerate(contexts):
            if marker in norm_lower(context):
                return idx
    return None


def infer_combination_column(contexts: list[str]) -> Optional[int]:
    for idx, context in enumerate(contexts):
        low = norm_lower(context)
        if "tổ hợp" in low and "điểm" not in low:
            return idx
    return None


def infer_note_column(contexts: list[str]) -> Optional[int]:
    for idx, context in enumerate(contexts):
        low = norm_lower(context)
        if "tiêu chí" in low or "ghi chú" in low:
            return idx
    return None


def infer_thpt_column(
    contexts: list[str],
    method_code: str,
) -> Optional[int]:
    method_low = norm_lower(method_code)

    # 1) Nếu đã xác minh PT100/PT1/... thì ưu tiên đúng code đó ở header.
    if method_low and method_low != "thpt":
        for idx, context in enumerate(contexts):
            low = norm_lower(context).replace(" ", "")
            if method_low.replace(" ", "") in low:
                return idx

    # 2) Header mô tả trực tiếp thi THPT.
    best_idx = None
    best_score = -999
    for idx, context in enumerate(contexts):
        low = norm_lower(context)
        score = 0

        if "thi tốt nghiệp thpt" in low:
            score += 100
        elif "tốt nghiệp thpt" in low:
            score += 80
        elif "thi thpt" in low:
            score += 70

        if "điểm thi" in low:
            score += 20
        if "thi" in low:
            score += 10

        if any(marker in low for marker in THPT_NEGATIVE_MARKERS):
            score -= 120

        if score > best_score:
            best_score = score
            best_idx = idx

    if best_score >= 70:
        return best_idx

    return None


def find_code_in_row(row: list[str], preferred_col: Optional[int]) -> tuple[Optional[int], str]:
    if preferred_col is not None:
        for idx in range(max(0, preferred_col - 2), min(len(row), preferred_col + 3)):
            if is_major_code(row[idx]):
                return idx, normalize_major_code(row[idx])

    for idx, cell in enumerate(row):
        if is_major_code(cell):
            return idx, normalize_major_code(cell)

    return None, ""


def nearest_score_in_row(
    row: list[str],
    thpt_col: int,
    code_idx: Optional[int],
) -> tuple[Optional[int], Optional[float]]:
    """
    PyMuPDF có thể đặt label PT1 ở cột 8 nhưng giá trị thực nằm cột 7/8/9.
    Chỉ tìm quanh cột THPT, không lấy 'số đầu tiên của cả dòng' một cách mù quáng.
    """
    candidates: list[tuple[int, int, float]] = []

    for distance in range(0, 4):
        for idx in {thpt_col - distance, thpt_col + distance}:
            if idx < 0 or idx >= len(row):
                continue
            if code_idx is not None and idx == code_idx:
                continue
            score = parse_thpt_score(row[idx])
            if score is None:
                continue
            candidates.append((distance, idx, score))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: (x[0], x[1]))
    _, idx, score = candidates[0]
    return idx, score


def extract_name_fragment(
    row: list[str],
    name_col: Optional[int],
    code_idx: Optional[int],
    score_idx: Optional[int],
    combination_col: Optional[int],
    note_col: Optional[int],
) -> str:
    def acceptable(text: str) -> bool:
        low = norm_lower(text)
        if not text:
            return False
        if is_major_code(text):
            return False
        if parse_number(text) is not None:
            return False
        if low in {"pt1", "pt2", "pt3", "pt4", "pt5", "thpt"}:
            return False
        if "điểm chuẩn" in low or "điểm trúng tuyển" in low:
            return False
        if "tiêu chí" in low or "ttnv" in low:
            return False
        return True

    if name_col is not None and 0 <= name_col < len(row):
        text = clean_text(row[name_col])
        if acceptable(text):
            return text

    start = (code_idx + 1) if code_idx is not None else 0
    end = score_idx if score_idx is not None else len(row)
    if end <= start:
        end = len(row)

    parts = []
    for idx in range(start, end):
        if idx == combination_col or idx == note_col:
            continue
        text = clean_text(row[idx])
        if acceptable(text):
            parts.append(text)

    return " ".join(parts).strip()


def extract_from_grid(
    grid: list[list[str]],
    university_name: str,
    source_url: str,
    method_code: str,
) -> ParseResult:
    if not grid:
        return ParseResult([], method_code, "table rỗng")

    contexts = build_column_context(grid)
    data_start = detect_data_start(grid)
    if data_start >= len(grid):
        return ParseResult([], method_code, "không tìm thấy mã ngành trong bảng")

    code_col = infer_code_column(grid, data_start, contexts)
    name_col = infer_name_column(contexts)
    if name_col is None:
        return ParseResult([], method_code, "không xác định chắc chắn cột tên ngành")

    combination_col = infer_combination_column(contexts)
    note_col = infer_note_column(contexts)
    thpt_col = infer_thpt_column(contexts, method_code)

    if thpt_col is None:
        return ParseResult([], method_code, "không xác định được cột điểm THPT")

    records: list[dict] = []
    current: Optional[dict] = None

    def flush_current():
        nonlocal current
        if current is None:
            return
        major_name = re.sub(r"\s+", " ", " ".join(current["name_parts"])).strip()
        if current.get("major_code") and major_name and current.get("cutoff_score") is not None:
            records.append(
                {
                    "university_name": university_name,
                    "major_code": current["major_code"],
                    "major_name": major_name,
                    "year": YEAR,
                    "admission_method_codes": method_code or "THPT",
                    "combination": clean_text(current.get("combination")) or None,
                    "cutoff_score": float(current["cutoff_score"]),
                    "admission_note": clean_text(current.get("note")) or None,
                    "source_url": source_url,
                }
            )
        current = None

    for row in grid[data_start:]:
        code_idx, code = find_code_in_row(row, code_col)

        if code:
            flush_current()
            score_idx, score = nearest_score_in_row(row, thpt_col, code_idx)
            name = extract_name_fragment(
                row,
                name_col=name_col,
                code_idx=code_idx,
                score_idx=score_idx,
                combination_col=combination_col,
                note_col=note_col,
            )

            current = {
                "major_code": code,
                "name_parts": [name] if name else [],
                "cutoff_score": score,
                "combination": (
                    clean_text(row[combination_col])
                    if combination_col is not None and combination_col < len(row)
                    else ""
                ),
                "note": (
                    clean_text(row[note_col])
                    if note_col is not None and note_col < len(row)
                    else ""
                ),
            }
            continue

        if current is None:
            continue

        # continuation row: bổ sung score nếu start row bị merge cell.
        if current.get("cutoff_score") is None:
            _, score = nearest_score_in_row(row, thpt_col, None)
            if score is not None:
                current["cutoff_score"] = score

        fragment = extract_name_fragment(
            row,
            name_col=name_col,
            code_idx=None,
            score_idx=None,
            combination_col=combination_col,
            note_col=note_col,
        )
        if fragment:
            current["name_parts"].append(fragment)

        if not current.get("combination") and combination_col is not None and combination_col < len(row):
            current["combination"] = clean_text(row[combination_col])

        if not current.get("note") and note_col is not None and note_col < len(row):
            current["note"] = clean_text(row[note_col])

    flush_current()

    return ParseResult(records, method_code, "")


# ============================================================================
# PDF PARSER
# ============================================================================

def extract_pdf_text(doc: pymupdf.Document) -> str:
    parts = []
    for page in doc:
        try:
            parts.append(page.get_text("text", sort=True) or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def parse_pdf_document(
    university_name: str,
    source_url: str,
    local_file: str = "",
    content: Optional[bytes] = None,
) -> ParseResult:
    if local_file and Path(local_file).exists():
        doc = pymupdf.open(local_file)
    elif content:
        if not content.startswith(b"%PDF"):
            return ParseResult([], "", "nội dung không phải PDF thật")
        doc = pymupdf.open(stream=content, filetype="pdf")
    else:
        return ParseResult([], "", "không có PDF để đọc")

    try:
        full_text = extract_pdf_text(doc)
        method_code = detect_thpt_method_code(full_text)

        if len(full_text.strip()) < 100:
            return ParseResult([], method_code, "PDF scan/ảnh: không có text", full_text)

        if looks_garbled(full_text):
            return ParseResult([], method_code, "text PDF lỗi font/encoding", full_text)

        if document_has_unsafe_scale(full_text):
            return ParseResult([], method_code, "thang điểm/cột THPT không tương thích tự động", full_text)

        if not method_code:
            return ParseResult([], "", "không xác minh được phương thức thi THPT", full_text)

        all_rows: list[dict] = []
        table_errors = []

        for page in doc:
            try:
                finder = page.find_tables()
            except Exception as exc:
                table_errors.append(str(exc))
                continue

            for table in finder.tables:
                try:
                    df = table.to_pandas()
                except Exception as exc:
                    table_errors.append(str(exc))
                    continue

                grid = dataframe_to_grid(df)
                parsed = extract_from_grid(
                    grid,
                    university_name=university_name,
                    source_url=source_url,
                    method_code=method_code,
                )
                all_rows.extend(parsed.rows)

        if not all_rows:
            reason = "không trích được bảng điểm THPT chắc chắn"
            if table_errors:
                reason += f"; table errors: {table_errors[0][:120]}"
            return ParseResult([], method_code, reason, full_text)

        return ParseResult(all_rows, method_code, "", full_text)

    finally:
        doc.close()


# ============================================================================
# HTML / GOOGLE DOCS PARSER
# ============================================================================

def parse_html_document(
    university_name: str,
    source_url: str,
    html_text: str,
    context_text: str = "",
) -> ParseResult:
    context = f"{context_text}\n{html_text[:120000]}"
    method_code = detect_thpt_method_code(context)

    if looks_garbled(context):
        return ParseResult([], method_code, "HTML/text lỗi font/encoding", context)

    if document_has_unsafe_scale(context):
        return ParseResult([], method_code, "thang điểm/cột THPT không tương thích tự động", context)

    if not method_code:
        return ParseResult([], "", "không xác minh được phương thức thi THPT trong HTML", context)

    grids = html_tables_to_grids(html_text)
    if not grids:
        return ParseResult([], method_code, "không có bảng HTML", context)

    rows: list[dict] = []
    for grid in grids:
        parsed = extract_from_grid(
            grid,
            university_name=university_name,
            source_url=source_url,
            method_code=method_code,
        )
        rows.extend(parsed.rows)

    if not rows:
        return ParseResult([], method_code, "có bảng nhưng không trích được cột THPT chắc chắn", context)

    return ParseResult(rows, method_code, "", context)


def parse_google_doc(university_name: str, source_url: str) -> ParseResult:
    doc_id = extract_google_id(source_url)
    if not doc_id:
        return ParseResult([], "", "không lấy được Google Docs ID")

    html_url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    txt_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    try:
        html_response = get_url(html_url)
    except Exception as exc:
        return ParseResult([], "", f"Google Docs export HTML lỗi: {exc}")

    context_text = ""
    try:
        txt_response = get_url(txt_url)
        context_text = txt_response.text
    except Exception:
        pass

    return parse_html_document(
        university_name=university_name,
        source_url=source_url,
        html_text=html_response.text,
        context_text=context_text,
    )


def download_google_drive_file(source_url: str) -> bytes:
    file_id = extract_google_id(source_url)
    if not file_id:
        raise ValueError("không lấy được Google Drive file ID")

    urls = [
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
        f"https://drive.google.com/uc?export=download&id={file_id}",
    ]

    last_error = None
    for url in urls:
        try:
            response = get_url(url)
            content = response.content
            if content:
                return content
        except Exception as exc:
            last_error = exc

    raise RuntimeError(str(last_error) if last_error else "Google Drive download thất bại")


def parse_external_document(university_name: str, source_url: str) -> ParseResult:
    low = source_url.lower()

    if "docs.google.com/document/" in low:
        return parse_google_doc(university_name, source_url)

    if "drive.google.com/" in low:
        try:
            content = download_google_drive_file(source_url)
        except Exception as exc:
            return ParseResult([], "", f"Google Drive download lỗi: {exc}")

        if content.startswith(b"%PDF"):
            return parse_pdf_document(
                university_name=university_name,
                source_url=source_url,
                content=content,
            )

        # Nếu direct-download thực ra trả HTML, thử đọc như HTML.
        stripped = content.lstrip().lower()
        if stripped.startswith(b"<!doctype html") or stripped.startswith(b"<html"):
            html_text = content.decode("utf-8", errors="replace")
            return parse_html_document(
                university_name=university_name,
                source_url=source_url,
                html_text=html_text,
            )

        return ParseResult([], "", "Google Drive trả định dạng chưa hỗ trợ an toàn (không phải PDF/HTML)")

    # External URL khác: tải và tự nhận dạng.
    try:
        response = get_url(source_url)
    except Exception as exc:
        return ParseResult([], "", f"external download lỗi: {exc}")

    content = response.content
    if content.startswith(b"%PDF"):
        return parse_pdf_document(university_name, source_url, content=content)

    content_type = response.headers.get("Content-Type", "").lower()
    if "html" in content_type or content.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        return parse_html_document(
            university_name,
            source_url,
            response.text,
        )

    return ParseResult([], "", f"định dạng external chưa hỗ trợ: {content_type or 'unknown'}")


# ============================================================================
# PAGE URL FALLBACK
# ============================================================================

def parse_page_url_fallback(
    university_name: str,
    page_url: str,
    source_url: str,
) -> ParseResult:
    page_url = clean_text(page_url)
    if not page_url:
        return ParseResult([], "", "không có page_url fallback")

    try:
        response = get_url(page_url)
    except Exception as exc:
        return ParseResult([], "", f"page_url lỗi: {exc}")

    return parse_html_document(
        university_name=university_name,
        source_url=source_url or page_url,
        html_text=response.text,
    )


# ============================================================================
# TUYENSINH247 FALLBACK - STRUCTURED THPT TABLES
# ============================================================================

def strip_accents(value: str) -> str:
    text = unicodedata.normalize("NFD", clean_text(value))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


def normalize_match_name(value: str) -> str:
    text = strip_accents(value).lower()
    replacements = [
        (r"\bhv\b", "hoc vien"),
        (r"\bdh\b", "dai hoc"),
        (r"\bsp\b", "su pham"),
        (r"\bkh\b", "khoa hoc"),
        (r"\bcn\b", "cong nghe"),
        (r"\bqtkd\b", "quan tri kinh doanh"),
        (r"\bdhqghcm\b", "dai hoc quoc gia tphcm"),
        (r"\bdhqg\s*tp\s*hcm\b", "dai hoc quoc gia tphcm"),
        (r"\bdhqg hcm\b", "dai hoc quoc gia tphcm"),
        (r"\bdhqg\s*ha\s*noi\b", "dai hoc quoc gia ha noi"),
        (r"\bdhqghn\b", "dai hoc quoc gia ha noi"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    # Một vài viết tắt đặc thù trong source map cũ.
    text = re.sub(r"kinh te\s*-?\s*cong nghe\s+tn\b", "kinh te cong nghe thai nguyen", text)
    text = re.sub(r"tai nguyen va mt\b", "tai nguyen va moi truong", text)
    text = re.sub(r"tai chinh\s*-?\s*ke toan", "tai chinh ke toan", text)
    text = re.sub(r"tai chinh\s*-?\s*quan tri kinh doanh", "tai chinh quan tri kinh doanh", text)

    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def school_core_tokens(value: str) -> set[str]:
    generic = {
        "truong", "dai", "hoc", "hocvien", "vien", "the", "va",
        "tai", "co", "so", "phan", "hieu", "quoc", "gia",
    }
    tokens = set(normalize_match_name(value).split())
    return {t for t in tokens if t not in generic and len(t) > 1}


def school_match_metrics(a: str, b: str) -> dict:
    """
    V3: so khớp tên trường theo cả chuỗi và token.

    Khác V2:
    - KHÔNG thưởng chỉ vì một tên là substring của tên kia.
      Đây chính là nguyên nhân "Vinh" có thể ăn nhầm "Vĩnh Long".
    - Phạt token thừa/thiếu.
    - Trả thêm coverage để match_tuyensinh247_school có thể từ chối match mơ hồ.
    """
    na = normalize_match_name(a)
    nb = normalize_match_name(b)

    if not na or not nb:
        return {
            "score": 0.0,
            "seq": 0.0,
            "jaccard": 0.0,
            "source_coverage": 0.0,
            "candidate_coverage": 0.0,
            "extra_tokens": set(),
            "missing_tokens": set(),
        }

    if na == nb:
        tokens = school_core_tokens(a)
        return {
            "score": 1.0,
            "seq": 1.0,
            "jaccard": 1.0,
            "source_coverage": 1.0,
            "candidate_coverage": 1.0,
            "extra_tokens": set(),
            "missing_tokens": set(),
        }

    ta = school_core_tokens(a)
    tb = school_core_tokens(b)
    inter = ta & tb
    union = ta | tb

    seq = SequenceMatcher(None, na, nb).ratio()
    jacc = len(inter) / max(1, len(union))
    source_coverage = len(inter) / max(1, len(ta))
    candidate_coverage = len(inter) / max(1, len(tb))

    extra_tokens = tb - ta
    missing_tokens = ta - tb

    # Phạt rõ token thừa/thiếu thay vì thưởng substring như V2.
    extra_penalty = min(0.20, 0.07 * len(extra_tokens))
    missing_penalty = min(0.28, 0.11 * len(missing_tokens))

    score = (
        0.44 * seq
        + 0.22 * jacc
        + 0.22 * source_coverage
        + 0.12 * candidate_coverage
        - extra_penalty
        - missing_penalty
    )
    score = max(0.0, min(1.0, score))

    return {
        "score": score,
        "seq": seq,
        "jaccard": jacc,
        "source_coverage": source_coverage,
        "candidate_coverage": candidate_coverage,
        "extra_tokens": extra_tokens,
        "missing_tokens": missing_tokens,
    }


def school_similarity(a: str, b: str) -> float:
    return float(school_match_metrics(a, b)["score"])

def load_tuyensinh247_school_index() -> list[dict]:
    try:
        response = get_url(TS247_INDEX_URL, timeout=60)
    except Exception as exc:
        print(f"⚠ Không tải được index Tuyensinh247: {exc}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    seen = set()

    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        href = urljoin(TS247_BASE, clean_text(a.get("href")))

        if "/diem-chuan/" not in href:
            continue
        if not href.lower().endswith(".html"):
            continue

        match = re.match(r"^([A-Za-z0-9]+)\s*-\s*(.+)$", text)
        if match:
            code = match.group(1).upper()
            school_name = clean_text(match.group(2))
        else:
            code_match = re.search(r"-([A-Za-z0-9]+)\.html(?:\?|$)", href)
            code = code_match.group(1).upper() if code_match else ""
            school_name = text

        if not school_name:
            continue

        key = (code, href)
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "school_code": code,
            "school_name": school_name,
            "score_url": href,
        })

    return records


def _exact_school_code_for(university_name: str) -> str:
    target = normalize_school(university_name)
    for raw_name, code in TS247_EXACT_SCHOOL_CODES.items():
        if normalize_school(raw_name) == target:
            return code.upper()
    return ""



def _exact_source_for(university_name: str) -> dict:
    target = normalize_school(university_name)
    for raw_name, cfg in TS247_EXACT_SOURCE_URLS.items():
        if normalize_school(raw_name) == target:
            return dict(cfg)
    return {}


def _static_2025_codes_for(
    school_code: str,
    major_name: str,
    score: float,
) -> list[str]:
    code = clean_text(school_code).upper()
    name_key = normalize_match_name(major_name)
    rounded_score = round(float(score), 2)

    by_score = TS247_2025_NAME_SCORE_CODE_MAPS.get(code, {})
    # Keys trong cấu hình được giữ ở dạng dễ đọc (có dấu). Normalize lúc lookup
    # để không phụ thuộc dấu/case/khoảng trắng, giống mapping theo tên phía dưới.
    for (raw_name, raw_score), codes in by_score.items():
        if (
            normalize_match_name(raw_name) == name_key
            and round(float(raw_score), 2) == rounded_score
        ):
            return [normalize_major_code(x) for x in codes]

    by_name = TS247_2025_NAME_CODE_MAPS.get(code, {})
    # Normalize keys at lookup time so accents/case/punctuation differences don't matter.
    for raw_key, codes in by_name.items():
        if normalize_match_name(raw_key) == name_key:
            return [normalize_major_code(x) for x in codes]

    return []


def match_tuyensinh247_school(university_name: str, index: list[dict]) -> tuple[Optional[dict], float]:
    """
    V3 school resolver.

    Thứ tự:
    1) trường bị skip (umbrella) -> không match;
    2) nếu có mã trường khóa cứng -> chỉ nhận đúng code;
    3) còn lại dùng fuzzy nhưng phải:
       - score đủ cao,
       - coverage đủ cao,
       - top1 cách top2 đủ xa,
       - không có kiểu "tên nguồn là prefix nhưng candidate thêm token quan trọng".
    """
    if normalize_school(university_name) in {normalize_school(x) for x in TS247_SKIP_SCHOOLS}:
        return None, 0.0

    exact_source = _exact_source_for(university_name)
    if exact_source:
        item = {
            "school_code": clean_text(exact_source.get("code")).upper(),
            "school_name": university_name,
            "score_url": clean_text(exact_source.get("score_url")),
            "_match_mode": "EXACT_SOURCE_V5",
            "_match_margin": 1.0,
        }
        return item, 1.0

    exact_code = _exact_school_code_for(university_name)
    if exact_code:
        code_matches = [
            item for item in index
            if clean_text(item.get("school_code")).upper() == exact_code
        ]
        if not code_matches:
            return None, 0.0

        # Nếu index vô tình có duplicate code, chọn tên gần nhất nhưng code vẫn là hàng rào chính.
        ranked = sorted(
            code_matches,
            key=lambda item: school_similarity(university_name, item.get("school_name", "")),
            reverse=True,
        )
        item = dict(ranked[0])
        item["_match_mode"] = f"EXACT_CODE:{exact_code}"
        item["_match_margin"] = 1.0
        item["_match_source_coverage"] = 1.0
        item["_match_candidate_coverage"] = 1.0
        return item, 1.0

    ranked = []
    for item in index:
        metrics = school_match_metrics(university_name, item.get("school_name", ""))
        ranked.append((float(metrics["score"]), metrics, item))

    if not ranked:
        return None, 0.0

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best_metrics, best_item = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    margin = best_score - second_score

    exact_normalized_name = (
        normalize_match_name(university_name)
        == normalize_match_name(best_item.get("school_name", ""))
    )

    # Exact normalized name là tín hiệu mạnh nhất đối với các trường không có hard-code.
    if not exact_normalized_name:
        if best_score < TS247_MATCH_MIN_SCORE:
            return None, best_score

        if best_metrics["source_coverage"] < TS247_MATCH_MIN_SOURCE_COVERAGE:
            return None, best_score

        if best_metrics["candidate_coverage"] < TS247_MATCH_MIN_CANDIDATE_COVERAGE:
            return None, best_score

        if margin < TS247_MATCH_MIN_MARGIN:
            return None, best_score

        # Chặn cụ thể pattern từng gây lỗi ở V2:
        # source = "... Vinh", candidate = "... Vinh Long".
        source_norm = normalize_match_name(university_name)
        candidate_norm = normalize_match_name(best_item.get("school_name", ""))
        extra_tokens = set(best_metrics["extra_tokens"])
        if source_norm and candidate_norm.startswith(source_norm + " ") and extra_tokens:
            return None, best_score

    item = dict(best_item)
    item["_match_mode"] = "EXACT_NAME" if exact_normalized_name else "FUZZY_SAFE"
    item["_match_margin"] = margin
    item["_match_source_coverage"] = best_metrics["source_coverage"]
    item["_match_candidate_coverage"] = best_metrics["candidate_coverage"]
    return item, best_score


def _ts247_identity_texts(html_text: str) -> list[str]:
    """Lấy title/H1/H2 và các dòng 'Tên trường' làm tín hiệu định danh trang."""
    soup = BeautifulSoup(html_text, "html.parser")
    texts: list[str] = []

    if soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
        if title:
            texts.append(title)

    for tag in soup.find_all(["h1", "h2"], limit=8):
        value = clean_text(tag.get_text(" ", strip=True))
        if value:
            texts.append(value)

    page_text = soup.get_text("\n", strip=True)
    for line in page_text.splitlines():
        line = clean_text(line)
        if re.search(r"^\s*tên\s+trường\s*:", line, flags=re.I):
            texts.append(line)
        if len(texts) >= 14:
            break

    out = []
    seen = set()
    for value in texts:
        key = normalize_match_name(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _extract_school_label_from_identity(value: str) -> str:
    """
    Rút tên trường khỏi các title/H1 phổ biến của TS247.
    Làm bước này trước khi so token để 'Vinh' KHÔNG thể được xem là
    đồng nhất với 'Vĩnh Long'.
    """
    text = clean_text(value)
    if not text:
        return ""

    patterns = [
        r"^Điểm\s+chuẩn\s+(.+?)\s+20\d{2}(?:\s+chính\s+xác)?$",
        r"^Mã\s+trường,\s*các\s+ngành\s+(.+?)\s+20\d{2}$",
        r"^Tên\s+trường\s*:\s*(.+)$",
        r"^Điểm\s+chuẩn\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text, flags=re.I)
        if not match:
            continue
        label = clean_text(match.group(1))
        # Nếu pattern cuối bắt luôn suffix năm/chính xác thì bỏ.
        label = re.sub(r"\s+20\d{2}(?:\s+chính\s+xác)?$", "", label, flags=re.I)
        return clean_text(label)

    return ""

def _url_school_code(url: str) -> str:
    match = re.search(r"-([A-Za-z0-9]+)\.html(?:\?|$)", clean_text(url))
    return match.group(1).upper() if match else ""


def validate_ts247_page_identity(
    requested_university_name: str,
    matched_item: dict,
    html_text: str,
    url: str,
) -> tuple[bool, str]:
    """
    V3: xác minh lại trang sau khi tải.

    Điều kiện mạnh:
    - code trong URL (nếu có) phải khớp code của index;
    - title/H1 phải rút ra được tên trường;
    - tên rút ra phải khớp token với trường index, không cho token thừa kiểu
      "Vinh" -> "Vĩnh Long".
    """
    expected_name = clean_text(matched_item.get("school_name"))
    expected_code = clean_text(matched_item.get("school_code")).upper()
    url_code = _url_school_code(url)

    if expected_code and url_code and expected_code != url_code:
        return False, f"mã trường URL={url_code} khác index={expected_code}"

    hard_code = _exact_school_code_for(requested_university_name)
    if hard_code and expected_code and hard_code != expected_code:
        return False, f"mã trường khóa={hard_code} nhưng trang/index={expected_code}"

    identities = _ts247_identity_texts(html_text)
    if not identities:
        return False, "không đọc được title/H1 để xác minh danh tính trang"

    parsed_labels = []
    for value in identities:
        label = _extract_school_label_from_identity(value)
        if label:
            parsed_labels.append(label)

    if not parsed_labels:
        return False, "không rút được tên trường từ title/H1"

    expected_tokens = school_core_tokens(expected_name)

    for label in parsed_labels:
        metrics = school_match_metrics(expected_name, label)
        label_tokens = school_core_tokens(label)

        # Trường hợp tốt nhất: sau normalize là đúng cùng tên.
        if normalize_match_name(expected_name) == normalize_match_name(label):
            return True, ""

        # Cho phép khác cách viết/viết tắt nhưng KHÔNG cho thêm token địa danh
        # vào một tên vốn ngắn hơn. Ví dụ expected "... Vinh", page "... Vinh Long".
        extra = label_tokens - expected_tokens
        missing = expected_tokens - label_tokens

        if (
            metrics["score"] >= 0.86
            and metrics["source_coverage"] >= 0.95
            and metrics["candidate_coverage"] >= 0.88
            and not extra
            and not missing
        ):
            return True, ""

    preview = " | ".join(parsed_labels[:3])
    return False, f"title/H1 không khớp trường index; parsed='{preview[:180]}'"

def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        cols = []
        for col in out.columns:
            parts = [clean_text(x) for x in col if clean_text(x) and not str(x).startswith("Unnamed")]
            cols.append(" ".join(parts))
        out.columns = cols
    else:
        out.columns = [clean_text(c) for c in out.columns]
    return out


def find_column_by_markers(columns: Iterable[str], markers: Iterable[str]) -> str:
    markers_norm = [normalize_match_name(x) for x in markers]
    for col in columns:
        nc = normalize_match_name(col)
        if any(m in nc for m in markers_norm):
            return col
    return ""


def tables_under_heading(soup: BeautifulSoup, heading_pattern: str) -> list:
    target = None
    for tag in soup.find_all(["h2", "h3", "h4", "strong"]):
        text = normalize_match_name(tag.get_text(" ", strip=True))
        if re.search(heading_pattern, text):
            target = tag
            break

    if target is None:
        return []

    tables = []
    node = target
    while True:
        node = node.find_next()
        if node is None:
            break
        if node.name in {"h2", "h3"}:
            break
        if node.name == "table":
            if node not in tables:
                tables.append(node)
    return tables


def _ts247_row_note_is_unsafe(note: str) -> bool:
    low = normalize_match_name(note)
    return any(normalize_match_name(marker) in low for marker in TS247_UNSAFE_ROW_NOTE_MARKERS)


def extract_ts247_thpt_rows(score_html: str) -> list[dict]:
    """
    Đọc CHỈ section "Điểm thi THPT năm 2025".

    V4:
    - giữ major_code_hint nếu cột "Tên ngành" của TS247 thực tế chứa mã ngành;
    - bỏ từng dòng có note cho biết nhân hệ số/thang 40/kết hợp chứng chỉ;
    - không tự biến score >30 thành thang 30.
    """
    soup = BeautifulSoup(score_html, "html.parser")
    pattern = r"diem chuan theo phuong thuc diem thi thpt nam 2025"
    tables = tables_under_heading(soup, pattern)

    rows = []
    for table in tables:
        try:
            dfs = pd.read_html(io.StringIO(str(table)), thousands=None)
        except Exception:
            continue

        for df in dfs:
            if df.empty:
                continue
            df = flatten_columns(df)

            name_col = find_column_by_markers(df.columns, ["Tên ngành"])
            combo_col = find_column_by_markers(df.columns, ["Tổ hợp môn", "Tổ hợp"])
            score_col = find_column_by_markers(df.columns, ["Điểm chuẩn"])
            note_col = find_column_by_markers(df.columns, ["Ghi chú"])

            if not name_col or not score_col:
                raw = pd.read_html(io.StringIO(str(table)), header=None, thousands=None)[0]
                header_idx = None
                for i in range(min(5, len(raw))):
                    row_text = " | ".join(clean_text(v) for v in raw.iloc[i].tolist())
                    nrow = normalize_match_name(row_text)
                    if "ten nganh" in nrow and "diem chuan" in nrow:
                        header_idx = i
                        break
                if header_idx is None:
                    continue
                headers = [clean_text(v) for v in raw.iloc[header_idx].tolist()]
                df = raw.iloc[header_idx + 1:].copy()
                df.columns = headers
                df = flatten_columns(df)
                name_col = find_column_by_markers(df.columns, ["Tên ngành"])
                combo_col = find_column_by_markers(df.columns, ["Tổ hợp môn", "Tổ hợp"])
                score_col = find_column_by_markers(df.columns, ["Điểm chuẩn"])
                note_col = find_column_by_markers(df.columns, ["Ghi chú"])

            if not name_col or not score_col:
                continue

            for _, r in df.iterrows():
                raw_major = clean_text(r.get(name_col))
                if not raw_major or normalize_match_name(raw_major).startswith("tra cuu tai"):
                    continue

                score = parse_number(r.get(score_col))
                if score is None:
                    continue

                note = clean_text(r.get(note_col)) if note_col else ""
                combo = clean_text(r.get(combo_col)) if combo_col else ""

                major_code_hint = ""
                if is_catalog_major_code(raw_major):
                    major_code_hint = normalize_major_code(raw_major)

                rows.append({
                    "major_name": raw_major,
                    "major_code_hint": major_code_hint,
                    "combination": combo,
                    "cutoff_score": score,
                    "admission_note": note,
                    "row_unsafe": _ts247_row_note_is_unsafe(note),
                })

    return rows

def discover_ts247_info_url(score_url: str, score_html: str) -> list[str]:
    soup = BeautifulSoup(score_html, "html.parser")
    candidates = []

    for a in soup.find_all("a", href=True):
        href = urljoin(TS247_BASE, clean_text(a.get("href")))
        text = normalize_match_name(a.get_text(" ", strip=True))
        if "thong-tin-" in href or "ma truong" in text or "cac nganh" in text:
            if href.startswith(TS247_BASE) and href.endswith(".html"):
                candidates.append(href)

    # Fallback cấu trúc URL thông dụng.
    m = re.search(r"/diem-chuan/([^/?#]+)-([A-Za-z0-9]+)\.html", score_url)
    if m:
        slug, code = m.group(1), m.group(2)
        candidates.append(f"{TS247_BASE}/thong-tin-{slug}-{code}.html")
        candidates.append(f"{TS247_BASE}/diem-chuan-truong-{slug}-{code.lower()}.html")

    deduped = []
    seen = set()
    for url in candidates:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped[:8]


def is_catalog_major_code(value) -> bool:
    text = normalize_major_code(value)
    if not text or len(text) > 24:
        return False
    # Hỗ trợ mã chuẩn 7 số, TLA101, BF1, IU01, 7480104_TT, ...
    if not re.fullmatch(r"[A-Z0-9_-]+", text):
        return False
    if not any(ch.isdigit() for ch in text):
        return False
    # Tránh nhận STT đơn thuần như 1, 2, 15.
    if text.isdigit() and len(text) < 6:
        return False
    return True


def extract_major_catalog(info_html: str) -> list[dict]:
    entries = []

    try:
        tables = pd.read_html(io.StringIO(info_html), thousands=None)
    except Exception:
        tables = []

    for df in tables:
        if df.empty:
            continue
        df = flatten_columns(df)
        code_col = find_column_by_markers(df.columns, ["Mã ngành"])
        name_col = find_column_by_markers(df.columns, ["Tên ngành"])
        if not code_col or not name_col:
            continue

        for _, row in df.iterrows():
            code = normalize_major_code(row.get(code_col))
            name = clean_text(row.get(name_col))
            if not code or not name or not is_catalog_major_code(code):
                continue
            entries.append({"major_code": code, "major_name": name})

    # Một số trang trình bày theo list: "Mã ngành: 7220201".
    if not entries:
        soup = BeautifulSoup(info_html, "html.parser")
        text = soup.get_text("\n", strip=True)
        lines = [clean_text(x) for x in text.splitlines() if clean_text(x)]
        current_name = ""
        for line in lines:
            mname = re.match(r"^\d+\.\s*(.+)$", line)
            if mname:
                current_name = clean_text(mname.group(1))
                continue
            mcode = re.search(r"Mã ngành\s*:\s*([A-Za-z0-9_]+)", line, flags=re.I)
            if mcode and current_name:
                code = normalize_major_code(mcode.group(1))
                if is_catalog_major_code(code):
                    entries.append({"major_code": code, "major_name": current_name})

    # dedupe
    out = []
    seen = set()
    for e in entries:
        key = (e["major_code"], normalize_match_name(e["major_name"]))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def major_name_similarity(a: str, b: str) -> float:
    na, nb = normalize_match_name(a), normalize_match_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(1, len(ta | tb))
    contain = 0.12 if na in nb or nb in na else 0.0
    return min(1.0, 0.6 * seq + 0.4 * jacc + contain)


def match_major_code(major_name: str, catalog: list[dict]) -> tuple[str, float]:
    target = normalize_match_name(major_name)
    if not target:
        return "", 0.0

    exact = [e for e in catalog if normalize_match_name(e["major_name"]) == target]
    if len(exact) == 1:
        return exact[0]["major_code"], 1.0

    best_code = ""
    best_score = 0.0
    for entry in catalog:
        score = major_name_similarity(major_name, entry["major_name"])
        if score > best_score:
            best_score = score
            best_code = entry["major_code"]

    if best_score < 0.78:
        return "", best_score
    return best_code, best_score


def parse_tuyensinh247_fallback(university_name: str, index: list[dict]) -> ParseResult:
    school_norm = normalize_school(university_name)
    force_review_norms = {normalize_school(x) for x in TS247_FORCE_REVIEW_SCHOOLS}
    if school_norm in force_review_norms:
        return ParseResult(
            [],
            "THPT",
            "Tuyensinh247: trường bị khóa REVIEW vì cơ sở/thang điểm không đồng nhất với dataset THPT-30",
        )

    item, school_match_score = match_tuyensinh247_school(university_name, index)
    if item is None:
        return ParseResult(
            [],
            "THPT",
            f"Tuyensinh247: không match chắc chắn trường (score={school_match_score:.2f})",
        )

    score_url = item["score_url"]
    try:
        response = get_url(score_url, timeout=60)
    except Exception as exc:
        return ParseResult([], "THPT", f"Tuyensinh247 score page lỗi: {exc}")

    identity_ok, identity_reason = validate_ts247_page_identity(
        requested_university_name=university_name,
        matched_item=item,
        html_text=response.text,
        url=score_url,
    )
    if not identity_ok:
        return ParseResult(
            [],
            "THPT",
            f"Tuyensinh247: REJECT page identity: {identity_reason}",
            response.text[:50000],
        )

    thpt_rows = extract_ts247_thpt_rows(response.text)
    if not thpt_rows:
        return ParseResult(
            [],
            "THPT",
            "Tuyensinh247: không có section Điểm thi THPT năm 2025",
            response.text[:50000],
        )

    catalog = []
    used_info_url = ""
    exact_source = _exact_source_for(university_name)
    info_candidates = []
    if exact_source.get("info_url"):
        info_candidates.append(clean_text(exact_source["info_url"]))
    info_candidates.extend(discover_ts247_info_url(score_url, response.text))
    info_candidates = list(dict.fromkeys(url for url in info_candidates if url))

    for info_url in info_candidates:
        try:
            info_resp = get_url(info_url, timeout=45)
        except Exception:
            continue

        info_identity_ok, _ = validate_ts247_page_identity(
            requested_university_name=university_name,
            matched_item=item,
            html_text=info_resp.text,
            url=info_url,
        )
        if not info_identity_ok:
            # V5: URL info được khóa cứng theo đúng mã trường là đủ mạnh để tiếp tục,
            # ngay cả khi title/H1 đổi cách viết giữa các phiên bản trang.
            exact_cfg = _exact_source_for(university_name)
            exact_code = clean_text(exact_cfg.get("code")).upper()
            if not (
                exact_cfg
                and clean_text(info_url) == clean_text(exact_cfg.get("info_url"))
                and _url_school_code(info_url) == exact_code
            ):
                continue

        candidate_catalog = extract_major_catalog(info_resp.text)
        if candidate_catalog:
            catalog = candidate_catalog
            used_info_url = info_url
            break

    school_code = clean_text(item.get("school_code")).upper()
    has_static_2025_catalog = (
        school_code in TS247_2025_NAME_CODE_MAPS
        or school_code in TS247_2025_NAME_SCORE_CODE_MAPS
    )

    if not catalog and not has_static_2025_catalog:
        return ParseResult(
            [],
            "THPT",
            "Tuyensinh247: có điểm THPT nhưng không lấy được catalog mã ngành ĐÚNG TRƯỜNG",
            response.text[:50000],
        )

    catalog_by_code: dict[str, list[dict]] = {}
    for entry in catalog:
        catalog_by_code.setdefault(normalize_major_code(entry["major_code"]), []).append(entry)

    rows = []
    unmatched = []
    unsafe_rows = 0
    out_of_scale_rows = 0
    eligible_rows = 0
    matched_source_rows = 0

    for r in thpt_rows:
        if r.get("row_unsafe"):
            unsafe_rows += 1
            continue

        score = float(r["cutoff_score"])
        if not (10 <= score <= 30):
            out_of_scale_rows += 1
            continue

        eligible_rows += 1

        raw_name = clean_text(r["major_name"])
        code_hint = normalize_major_code(r.get("major_code_hint")) if r.get("major_code_hint") else ""

        mapped_codes: list[str] = []
        canonical_name = raw_name

        # V5 ưu tiên catalog 2025 đã khóa cho THP/XDA, vì catalog 2026 đã đổi tên/nhóm.
        static_codes = _static_2025_codes_for(
            item.get("school_code", ""),
            raw_name,
            score,
        )
        if static_codes:
            mapped_codes = static_codes

        # V4: nếu TS247 đã cho thẳng mã ngành trong cột "Tên ngành",
        # không fuzzy-match chuỗi số như thể đó là tên ngành.
        elif code_hint:
            entries = catalog_by_code.get(code_hint, [])
            distinct_names = []
            seen_names = set()
            for entry in entries:
                nm = clean_text(entry.get("major_name"))
                key = normalize_match_name(nm)
                if nm and key not in seen_names:
                    seen_names.add(key)
                    distinct_names.append(nm)

            if len(distinct_names) == 1:
                mapped_codes = [code_hint]
                canonical_name = distinct_names[0]
            else:
                unmatched.append(
                    f"mã {code_hint}: catalog có {len(distinct_names)} tên khác nhau"
                )
                continue
        else:
            code, code_score = match_major_code(raw_name, catalog)
            if not code:
                unmatched.append(f"{raw_name} ({code_score:.2f})")
                continue
            mapped_codes = [code]

            # V6 final: đôi lúc TS247 trả đúng bảng nhưng một vài tên ngành bị
            # mojibake (ví dụ "Ngôn ng�� Anh"). Nếu mã ngành đã match chắc chắn,
            # dùng lại tên sạch từ catalog của CHÍNH trường đó thay vì reject cả trường.
            if looks_garbled(raw_name):
                entries = catalog_by_code.get(normalize_major_code(code), [])
                clean_names = []
                seen_clean = set()
                for entry in entries:
                    nm = clean_text(entry.get("major_name"))
                    key = normalize_match_name(nm)
                    if nm and not looks_garbled(nm) and key not in seen_clean:
                        seen_clean.add(key)
                        clean_names.append(nm)
                if len(clean_names) == 1:
                    canonical_name = clean_names[0]
                else:
                    unmatched.append(f"{raw_name}: lỗi font và không xác định duy nhất tên sạch")
                    continue

        note_parts = []
        if r.get("admission_note"):
            note_parts.append(clean_text(r["admission_note"]))
        note_parts.append("Nguồn dự phòng Tuyensinh247 - mục Điểm thi THPT năm 2025")
        if item.get("school_code"):
            note_parts.append(f"Mã trường TS247={clean_text(item['school_code']).upper()}")

        for code in mapped_codes:
            rows.append({
                "university_name": university_name,
                "major_code": code,
                "major_name": canonical_name,
                "year": YEAR,
                "admission_method_codes": "THPT",
                "combination": r.get("combination") or None,
                "cutoff_score": score,
                "admission_note": "; ".join(note_parts),
                "source_url": score_url,
            })
        matched_source_rows += 1

    if not rows:
        reason = "Tuyensinh247: không có dòng đủ mã ngành + điểm THPT thang 30"
        if unsafe_rows:
            reason += f"; loại {unsafe_rows} dòng nhân hệ số/kết hợp"
        if out_of_scale_rows:
            reason += f"; loại {out_of_scale_rows} dòng ngoài thang 30"
        if unmatched:
            reason += f"; unmatched ví dụ: {unmatched[0]}"
        return ParseResult([], "THPT", reason, response.text[:50000])

    # Coverage chỉ tính trên các dòng còn thực sự tương thích dataset THPT-30.
    coverage = matched_source_rows / max(1, eligible_rows)
    if coverage < 0.80:
        reason = (
            f"Tuyensinh247: map mã ngành chỉ đạt {coverage:.0%} "
            f"({matched_source_rows}/{eligible_rows} dòng THPT-30 hợp lệ)"
        )
        if unmatched:
            reason += f"; ví dụ: {unmatched[0]}"
        return ParseResult([], "THPT", reason, response.text[:50000])

    context = (
        f"TS247 school={item.get('school_name','')}; "
        f"code={item.get('school_code','')}; "
        f"match={school_match_score:.3f}; "
        f"mode={item.get('_match_mode','')}; "
        f"margin={item.get('_match_margin',0):.3f}; "
        f"info={used_info_url}; "
        f"source_rows={matched_source_rows}/{eligible_rows}; "
        f"output_rows={len(rows)}; "
        f"excluded_unsafe={unsafe_rows}; excluded_scale={out_of_scale_rows}"
    )
    return ParseResult(rows, "THPT", "", context)

def validate_secondary_rows(df: pd.DataFrame) -> tuple[bool, str]:
    if df.empty:
        return False, "không có dòng fallback"
    if df["major_code"].isna().any() or df["major_name"].isna().any() or df["cutoff_score"].isna().any():
        return False, "fallback thiếu mã ngành/tên ngành/điểm"
    if df["major_name"].astype(str).apply(looks_garbled).any():
        return False, "fallback có tên ngành lỗi font"
    if (df["cutoff_score"] > 30).any() or (df["cutoff_score"] < 10).any():
        return False, "fallback có score ngoài thang THPT 10-30"

    # V4: cùng major_code có thể đại diện nhiều chương trình/track khác nhau.
    # Chỉ xem là xung đột khi cùng MÃ + cùng TÊN CHƯƠNG TRÌNH + cùng TỔ HỢP
    # nhưng lại có nhiều cutoff khác nhau.
    work = df.copy()
    work["combination_key"] = work["combination"].fillna("").astype(str).map(clean_text)
    work["major_name_key"] = work["major_name"].fillna("").astype(str).map(normalize_match_name)
    conflicts = (
        work.groupby(
            ["major_code", "major_name_key", "combination_key"],
            dropna=False,
        )["cutoff_score"]
        .nunique(dropna=True)
        .gt(1)
        .any()
    )
    if conflicts:
        return False, "fallback có cùng mã+tên chương trình+tổ hợp nhưng nhiều điểm khác nhau"
    return True, ""

# ============================================================================
# V6 - OFFICIAL QHE + STABLE FALLBACK CACHE
# ============================================================================

OFFICIAL_QHE_SOURCE_URL = (
    "https://ueb.vnu.edu.vn/Tin-Tuc/UEB/"
    "thong-bao-diem-trung-tuyen-dai-hoc-chinh-quy-nam-2025/45198"
)
OFFICIAL_QHE_COMBINATIONS = "A01;C01;C03;C04;D01;D09;D10;X01"

OFFICIAL_QHE_2025_ROWS = [
    ("7340101", "Quản trị kinh doanh", 24.93),
    ("7340201", "Tài chính - Ngân hàng", 24.25),
    ("7340301", "Kế toán", 24.20),
    ("7310106", "Kinh tế quốc tế", 25.72),
    ("7310101", "Kinh tế", 24.30),
    ("7310105", "Kinh tế phát triển", 24.20),
]


def parse_official_verified_fallback(university_name: str) -> ParseResult:
    """V6: nguồn chính thức cố định cho UEB/QHE, không phụ thuộc cấu trúc TS247."""
    if normalize_school(university_name) != normalize_school("Trường ĐH Kinh tế - ĐHQGHN"):
        return ParseResult([], "", "")

    rows = []
    for major_code, major_name, score in OFFICIAL_QHE_2025_ROWS:
        rows.append({
            "university_name": university_name,
            "major_code": major_code,
            "major_name": major_name,
            "year": YEAR,
            "admission_method_codes": "PT100",
            "combination": OFFICIAL_QHE_COMBINATIONS,
            "cutoff_score": float(score),
            "admission_note": (
                "Nguồn chính thức UEB 2025; mã PTXT 100 = kết quả thi tốt nghiệp THPT; "
                "nhà trường không quy định chênh lệch điểm giữa các tổ hợp"
            ),
            "source_url": OFFICIAL_QHE_SOURCE_URL,
        })
    return ParseResult(rows, "PT100", "", "OFFICIAL_UEB_2025")


def load_fallback_cache() -> pd.DataFrame:
    if not FALLBACK_CACHE_FILE.exists():
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    try:
        df = canonicalize_rows(pd.read_csv(FALLBACK_CACHE_FILE).to_dict("records"))
    except Exception:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    if df.empty:
        return df
    return deduplicate_final(df)


def _is_ts247_df(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    return df["source_url"].fillna("").astype(str).str.contains(
        "tuyensinh247.com", case=False, regex=False
    )


def bootstrap_fallback_cache_from_existing_auto(cache_df: pd.DataFrame) -> pd.DataFrame:
    """
    Chỉ bootstrap khi cache chưa có dữ liệu.
    Dùng AUTO của lần chạy V5 gần nhất, nhưng chỉ lấy trường TS247 mà toàn bộ
    rows của trường vẫn pass validate_secondary_rows.
    """
    if not cache_df.empty or not AUTO_FILE.exists():
        return cache_df
    try:
        auto = canonicalize_rows(pd.read_csv(AUTO_FILE).to_dict("records"))
    except Exception:
        return cache_df
    if auto.empty:
        return cache_df
    auto = auto[_is_ts247_df(auto)].copy()
    accepted = []
    for school, grp in auto.groupby("university_name", dropna=False):
        ok, _ = validate_secondary_rows(grp)
        if ok:
            accepted.extend(grp.to_dict("records"))
    if not accepted:
        return cache_df
    out = deduplicate_final(canonicalize_rows(accepted))
    FALLBACK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(FALLBACK_CACHE_FILE, index=False, encoding="utf-8-sig")
    return out


def cached_school_rows(cache_df: pd.DataFrame, university_name: str) -> pd.DataFrame:
    if cache_df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    target = normalize_school(university_name)
    mask = cache_df["university_name"].fillna("").astype(str).map(normalize_school) == target
    out = cache_df[mask].copy()
    if out.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    ok, _ = validate_secondary_rows(out)
    return out if ok else pd.DataFrame(columns=CANONICAL_COLUMNS)


def upsert_fallback_cache(cache_df: pd.DataFrame, school_df: pd.DataFrame) -> pd.DataFrame:
    if school_df.empty:
        return cache_df
    school_name = clean_text(school_df["university_name"].iloc[0])
    target = normalize_school(school_name)
    if cache_df.empty:
        out = school_df.copy()
    else:
        keep = cache_df[
            cache_df["university_name"].fillna("").astype(str).map(normalize_school) != target
        ].copy()
        out = pd.concat([keep, school_df], ignore_index=True)
    out = deduplicate_final(canonicalize_rows(out.to_dict("records")))
    FALLBACK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(FALLBACK_CACHE_FILE, index=False, encoding="utf-8-sig")
    return out


def fallback_reason_is_transient(reason: str) -> bool:
    low = norm_lower(reason)
    markers = (
        "lỗi font",
        "không có section",
        "score page lỗi",
        "không đọc được title",
        "không rút được tên trường",
        "page identity",
        "connection",
        "timeout",
    )
    return any(marker in low for marker in markers)


def get_stable_fallback(
    university_name: str,
    ts247_index: list[dict],
    cache_df: pd.DataFrame,
) -> tuple[ParseResult, pd.DataFrame, bool, str, pd.DataFrame, str]:
    """
    Trả về: result, df, ok, reason, cache_mới, mode.
    Ưu tiên: official static -> cache -> TS247 live retry tối đa 3 lần.
    """
    official = parse_official_verified_fallback(university_name)
    if official.rows:
        df = canonicalize_rows(official.rows)
        ok, reason = validate_secondary_rows(df)
        return official, df, ok, reason, cache_df, "OFFICIAL"

    cached = cached_school_rows(cache_df, university_name)
    if not cached.empty:
        return ParseResult(cached.to_dict("records"), "THPT", "", "CACHE_V6"), cached, True, "", cache_df, "CACHE"

    last_result = ParseResult([], "THPT", "TS247 index rỗng" if not ts247_index else "chưa thử")
    last_df = pd.DataFrame(columns=CANONICAL_COLUMNS)
    last_ok = False
    last_reason = last_result.reason

    if not ts247_index:
        return last_result, last_df, False, last_reason, cache_df, "LIVE"

    for attempt in range(1, 4):
        last_result = parse_tuyensinh247_fallback(university_name, ts247_index)
        last_df = canonicalize_rows(last_result.rows)
        last_ok, validation_reason = validate_secondary_rows(last_df)
        last_reason = validation_reason or last_result.reason or "fallback chưa đủ độ tin cậy"
        if last_ok:
            cache_df = upsert_fallback_cache(cache_df, last_df)
            return last_result, last_df, True, "", cache_df, f"LIVE#{attempt}"
        if not fallback_reason_is_transient(last_reason):
            break
        time.sleep(0.6 * attempt)

    return last_result, last_df, False, last_reason, cache_df, "LIVE"


# ============================================================================
# VALIDATION
# ============================================================================

def canonicalize_rows(rows: Iterable[dict]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[CANONICAL_COLUMNS].copy()

    for col in ["university_name", "major_code", "major_name", "admission_method_codes", "combination", "admission_note", "source_url"]:
        df[col] = df[col].apply(lambda x: clean_text(x) or None)

    df["major_code"] = df["major_code"].apply(lambda x: normalize_major_code(x) if x else None)
    df["year"] = YEAR
    df["cutoff_score"] = pd.to_numeric(df["cutoff_score"], errors="coerce")

    return df


def validate_school_rows(df: pd.DataFrame, context_text: str = "") -> tuple[bool, str]:
    if df.empty:
        return False, "không có dòng candidate"

    if document_has_unsafe_scale(context_text):
        return False, "tài liệu dùng thang điểm/cột kết hợp chưa an toàn"

    if df["major_code"].isna().any() or df["major_name"].isna().any() or df["cutoff_score"].isna().any():
        return False, "candidate còn thiếu mã ngành/tên ngành/điểm"

    if df["major_name"].astype(str).apply(looks_garbled).any():
        return False, "tên ngành có dấu hiệu lỗi font/encoding"

    # Không tự nhận score >30 vào dataset THPT-30 nếu không có chuẩn hoá thang điểm.
    # Điều này cố ý để tránh Tôn Đức Thắng/môn nhân hệ số lọt vào auto.
    if (df["cutoff_score"] > 30).any():
        return False, "có điểm >30; cần xác minh thang điểm trước"

    if (df["cutoff_score"] < 10).any():
        return False, "có điểm <10; cần kiểm tra thủ công"

    # Một mã ngành xuất hiện nhiều cutoff THPT khác nhau trong cùng parser => cấu trúc có thể là nhiều tổ hợp.
    # Dataset hiện tại chưa có logic quy đổi tổ hợp đủ chắc chắn, nên review thay vì tự gộp.
    dup = (
        df.groupby("major_code", dropna=False)["cutoff_score"]
        .nunique(dropna=True)
        .gt(1)
        .any()
    )
    if dup:
        return False, "một mã ngành có nhiều điểm THPT khác nhau; cần xác minh tổ hợp/quy đổi"

    method_values = set(df["admission_method_codes"].dropna().astype(str))
    if not method_values:
        return False, "thiếu method THPT"

    return True, ""


def deduplicate_final(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # V3: combination là một phần của bản ghi.
    # Hai tổ hợp khác nhau có thể cùng điểm; không được làm mất một tổ hợp khi dedupe.
    key = [
        "university_name",
        "major_code",
        "major_name",
        "year",
        "admission_method_codes",
        "combination",
        "cutoff_score",
    ]

    df = df.drop_duplicates(subset=key, keep="first").copy()
    df = df.sort_values(["university_name", "major_code", "cutoff_score"], kind="stable")
    return df.reset_index(drop=True)



# ============================================================================
# V3 CROSS-SCHOOL QUARANTINE / AUDIT
# ============================================================================

def is_ts247_fallback_row(row) -> bool:
    url = norm_lower(row.get("source_url"))
    note = norm_lower(row.get("admission_note"))
    return "diemthi.tuyensinh247.com" in url or "nguồn dự phòng tuyensinh247" in note


def fallback_fingerprint(df: pd.DataFrame) -> set[tuple]:
    """
    Fingerprint không dùng university_name/source_url.
    Nếu hai trường có gần như cùng toàn bộ mã ngành + tên + tổ hợp + điểm,
    có khả năng một trường đã ăn dữ liệu của trường kia.
    """
    signature = set()
    for _, row in df.iterrows():
        signature.add(
            (
                normalize_major_code(row.get("major_code")),
                normalize_match_name(row.get("major_name")),
                normalize_match_name(row.get("combination")),
                round(float(row.get("cutoff_score")), 4),
            )
        )
    return signature


def quarantine_cross_school_fallback(
    auto_df: pd.DataFrame,
    review_rows: list[dict],
) -> tuple[pd.DataFrame, list[dict], list[str]]:
    if auto_df.empty:
        return auto_df, review_rows, []

    work = auto_df.copy()
    fallback_mask = work.apply(is_ts247_fallback_row, axis=1)
    fallback = work[fallback_mask].copy()

    if fallback.empty:
        return auto_df, review_rows, []

    quarantine_reasons: dict[str, list[str]] = {}

    def flag(school: str, reason: str):
        quarantine_reasons.setdefault(school, [])
        if reason not in quarantine_reasons[school]:
            quarantine_reasons[school].append(reason)

    # 1) Một score_url TS247 không được đại diện cho >1 trường trong cùng run.
    for url, group in fallback.groupby("source_url", dropna=False):
        schools = sorted(set(group["university_name"].dropna().astype(str)))
        if clean_text(url) and len(schools) > 1:
            reason = (
                "V3 quarantine: cùng fallback URL được dùng cho nhiều trường: "
                + ", ".join(schools)
            )
            for school in schools:
                flag(school, reason)

    # 2) Fingerprint gần như giống hệt nhau giữa hai trường.
    school_groups = {
        school: group.copy()
        for school, group in fallback.groupby("university_name")
    }
    schools = sorted(school_groups)

    for i, school_a in enumerate(schools):
        sig_a = fallback_fingerprint(school_groups[school_a])
        if len(sig_a) < FALLBACK_FINGERPRINT_MIN_ROWS:
            continue

        for school_b in schools[i + 1:]:
            sig_b = fallback_fingerprint(school_groups[school_b])
            if len(sig_b) < FALLBACK_FINGERPRINT_MIN_ROWS:
                continue

            overlap_count = len(sig_a & sig_b)
            overlap_ratio = overlap_count / max(1, min(len(sig_a), len(sig_b)))

            if (
                overlap_count >= FALLBACK_FINGERPRINT_MIN_ROWS
                and overlap_ratio >= FALLBACK_FINGERPRINT_OVERLAP
            ):
                reason = (
                    f"V3 quarantine: fingerprint fallback giống trường khác "
                    f"{overlap_ratio:.0%} ({overlap_count} dòng trùng)"
                )
                flag(school_a, f"{reason}: {school_b}")
                flag(school_b, f"{reason}: {school_a}")

    if not quarantine_reasons:
        return auto_df, review_rows, []

    quarantined_schools = set(quarantine_reasons)

    # Batch auto có tối đa một nguồn được chấp nhận/trường trong flow hiện tại.
    # Khi một fallback trường bị nghi nhiễm chéo, loại toàn bộ batch-auto của trường đó.
    cleaned = work[
        ~work["university_name"].isin(quarantined_schools)
    ].copy()

    for school in sorted(quarantined_schools):
        group = fallback[fallback["university_name"] == school]
        source_url = clean_text(group["source_url"].iloc[0]) if not group.empty else ""
        review_rows.append(
            {
                "university_name": school,
                "source_type": "TS247_FALLBACK",
                "status": "QUARANTINE",
                "reason": " | ".join(quarantine_reasons[school]),
                "detected_method": "THPT",
                "candidate_rows": int(len(group)),
                "page_url": "",
                "source_url": source_url,
            }
        )

    events = [
        f"{school}: {' | '.join(quarantine_reasons[school])}"
        for school in sorted(quarantined_schools)
    ]
    return cleaned.reset_index(drop=True), review_rows, events


def audit_final_dataset(final_df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    if final_df.empty:
        issues.append("FINAL rỗng")
        return issues

    if final_df["major_code"].isna().any():
        issues.append(f"missing major_code={int(final_df['major_code'].isna().sum())}")
    if final_df["major_name"].isna().any():
        issues.append(f"missing major_name={int(final_df['major_name'].isna().sum())}")
    if final_df["cutoff_score"].isna().any():
        issues.append(f"missing cutoff_score={int(final_df['cutoff_score'].isna().sum())}")

    bad_year = final_df[final_df["year"] != YEAR]
    if not bad_year.empty:
        issues.append(f"sai year={len(bad_year)}")

    # Chỉ audit fallback ở đây. Verified HTML có một case 31 điểm đã được giữ có chủ đích.
    fallback = final_df[final_df.apply(is_ts247_fallback_row, axis=1)].copy()
    if not fallback.empty:
        bad_scale = fallback[
            (fallback["cutoff_score"] < 10)
            | (fallback["cutoff_score"] > 30)
        ]
        if not bad_scale.empty:
            issues.append(f"fallback score ngoài 10-30={len(bad_scale)}")

        reused = (
            fallback.groupby("source_url")["university_name"]
            .nunique()
            .gt(1)
        )
        if reused.any():
            issues.append(
                f"fallback URL dùng cho nhiều trường={int(reused.sum())}"
            )

    return issues



# ============================================================================
# INPUT HELPERS
# ============================================================================

def require_file(path: Path):
    if not path.exists():
        print(f"❌ Thiếu file bắt buộc: {path}")
        sys.exit(1)


def get_first_existing_column(df: pd.DataFrame, names: list[str]) -> str:
    for name in names:
        if name in df.columns:
            return name
    return ""


def load_pdf_analysis() -> pd.DataFrame:
    if not PDF_ANALYSIS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(PDF_ANALYSIS_FILE)


def find_local_pdf(pdf_analysis: pd.DataFrame, university_name: str, source_url: str) -> tuple[str, str]:
    if pdf_analysis.empty:
        return "", ""

    matches = pd.DataFrame()

    if "original_url" in pdf_analysis.columns and source_url:
        matches = pdf_analysis[pdf_analysis["original_url"].astype(str) == str(source_url)]

    if matches.empty and "university_name" in pdf_analysis.columns:
        target = normalize_school(university_name)
        matches = pdf_analysis[
            pdf_analysis["university_name"].apply(normalize_school) == target
        ]

    if matches.empty:
        return "", ""

    row = matches.iloc[0]
    local_file = clean_text(row.get("local_file"))
    classification = clean_text(row.get("classification"))
    return local_file, classification


# ============================================================================
# V6 FINAL - ML READY + CHECKPOINT STATUS
# ============================================================================

def build_ml_ready_2025(final_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Giữ nguyên FINAL để bảo toàn dữ liệu nguồn đã làm sạch.
    Dataset ML chỉ nhận điểm THPT tương thích thang 30 (10..30).
    Các dòng ngoài thang được tách riêng, không xóa khỏi FINAL.
    """
    if final_df.empty:
        ready = final_df.copy()
        ready["score_scale"] = pd.Series(dtype="Int64")
        ready["model_eligible"] = pd.Series(dtype="bool")
        excluded = final_df.copy()
        excluded["exclude_reason"] = pd.Series(dtype="object")
        return ready, excluded

    scores = pd.to_numeric(final_df["cutoff_score"], errors="coerce")
    eligible_mask = scores.between(10, 30, inclusive="both")

    ready = final_df[eligible_mask].copy()
    ready["score_scale"] = 30
    ready["model_eligible"] = True

    excluded = final_df[~eligible_mask].copy()
    if not excluded.empty:
        excluded["exclude_reason"] = excluded["cutoff_score"].apply(
            lambda x: "cutoff_score ngoài thang THPT-30; giữ ở FINAL nhưng không đưa vào ML"
        )

    return ready.reset_index(drop=True), excluded.reset_index(drop=True)


def checkpoint_2025_status(review_df: pd.DataFrame, audit_issues: list[str]) -> tuple[bool, str]:
    if audit_issues:
        return False, "audit còn lỗi"

    actual = set()
    if not review_df.empty:
        actual = {normalize_school(x) for x in review_df["university_name"].dropna().astype(str)}
    allowed = {normalize_school(x) for x in INTENTIONAL_REVIEW_SCHOOLS}

    unexpected = actual - allowed
    if unexpected:
        return False, "còn REVIEW ngoài danh sách có chủ đích: " + ", ".join(sorted(unexpected))

    return True, "các nguồn còn REVIEW đều là ngoại lệ có chủ đích"



# ============================================================================
# OFFICIAL EXTRA 2025 - TRƯỜNG ĐH KIẾN TRÚC ĐÀ NẴNG (KTD)
# ============================================================================

DAU_2025_SOURCE_URL = (
    "https://tuyensinh.dau.edu.vn/"
    "chinh-thuc-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2025.html"
)


def build_dau_official_2025() -> pd.DataFrame:
    """
    Nguồn chính thức Trường ĐH Kiến trúc Đà Nẵng (mã trường KTD), công bố 22/08/2025.
    Chỉ lấy cột 'Xét theo kết quả thi tốt nghiệp THPT'.
    Điểm chuẩn chính thức nằm trong khoảng 16-18.
    """
    common_combo = "A00; A01; B00; D01; X06; X07; X26; X27"
    language_combo = "D01; A01; D14; D15; X06; X07; X26; X27"

    rows = [
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7210403",
            "major_name": "Thiết kế đồ họa",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": "V00; V01; V02; V03; V04; H00",
            "cutoff_score": 18.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7580108",
            "major_name": "Thiết kế nội thất",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": "V00; V01; V02; V03; V04; A01; X06; X07; X26; X27",
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7580101",
            "major_name": "Kiến trúc",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": "V00; V01; V02; V03; V04; A01; X06; X07; X26; X27",
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7480201",
            "major_name": "Công nghệ thông tin",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7510301",
            "major_name": "Công nghệ kỹ thuật điện, điện tử",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7580201",
            "major_name": "Kỹ thuật xây dựng",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7580302",
            "major_name": "Quản lý xây dựng",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7580205",
            "major_name": "Kỹ thuật xây dựng công trình giao thông",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7340101",
            "major_name": "Quản trị kinh doanh",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7340301",
            "major_name": "Kế toán",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7510605",
            "major_name": "Logistics và quản lý chuỗi cung ứng",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7340201",
            "major_name": "Tài chính ngân hàng",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7810201",
            "major_name": "Quản trị khách sạn",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7810103",
            "major_name": "Quản trị dịch vụ du lịch và lữ hành",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": common_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7220204",
            "major_name": "Ngôn ngữ Trung Quốc",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": language_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
        {
            "university_name": "Trường ĐH Kiến trúc Đà Nẵng",
            "major_code": "7220201",
            "major_name": "Ngôn ngữ Anh",
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": language_combo,
            "cutoff_score": 16.0,
            "admission_note": "Nguồn chính thức DAU - xét kết quả thi tốt nghiệp THPT 2025",
            "source_url": DAU_2025_SOURCE_URL,
        },
    ]

    df = canonicalize_rows(rows)
    ok, reason = validate_secondary_rows(df)
    if not ok:
        raise RuntimeError(f"DAU official 2025 validation failed: {reason}")
    return deduplicate_final(df)

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 88)
    print("PIPELINE 2025 - ADMISSION SCORES / THPT ONLY")
    print(f"VERSION       : {PIPELINE_VERSION}")
    print("=" * 88)

    require_file(HTML_VERIFIED_FILE)
    require_file(DOCUMENT_SOURCES_FILE)

    html_verified = canonicalize_rows(pd.read_csv(HTML_VERIFIED_FILE).to_dict("records"))
    documents = pd.read_csv(DOCUMENT_SOURCES_FILE)
    pdf_analysis = load_pdf_analysis()
    ts247_index = load_tuyensinh247_school_index()
    fallback_cache = load_fallback_cache()
    fallback_cache = bootstrap_fallback_cache_from_existing_auto(fallback_cache)

    thuyloi_verified = pd.DataFrame(columns=CANONICAL_COLUMNS)
    thuyloi_source_file = None
    if THUYLOI_VERIFIED_FILE.exists():
        thuyloi_source_file = THUYLOI_VERIFIED_FILE
    elif THUYLOI_RAW_FILE.exists():
        # Output mới nhất đã được kiểm tra trong phiên làm việc này: 43 ngành, tên sạch, PT1 đúng.
        # Dùng làm fallback nếu người dùng chưa kịp copy sang *_verified.csv.
        thuyloi_source_file = THUYLOI_RAW_FILE

    if thuyloi_source_file is not None:
        thuyloi_verified = canonicalize_rows(
            pd.read_csv(thuyloi_source_file).to_dict("records")
        )

    source_col = get_first_existing_column(
        documents,
        ["data_source", "source_url", "original_url", "url"],
    )
    page_col = get_first_existing_column(documents, ["page_url", "page", "source_page"])
    type_col = get_first_existing_column(documents, ["source_type", "type"])

    if not source_col or not type_col or "university_name" not in documents.columns:
        print("❌ document_sources_2025_verified.csv thiếu cột cần thiết.")
        print("Các cột hiện có:", list(documents.columns))
        sys.exit(1)

    auto_rows: list[dict] = []
    review_rows: list[dict] = []
    quarantine_events: list[str] = []
    accepted_schools: set[str] = set()
    force_review_norms = {normalize_school(name) for name in FORCE_REVIEW_SCHOOLS}

    # Thủy lợi đã verify riêng => không parse lại.
    verified_school_norms = set(
        thuyloi_verified["university_name"].dropna().apply(normalize_school).tolist()
    )

    print(f"HTML VERIFIED : {len(html_verified)} rows / {html_verified['university_name'].nunique()} schools")
    print(f"DOCUMENTS     : {len(documents)} sources / {documents['university_name'].nunique()} schools")
    print(f"THUYLOI CHECK : {len(thuyloi_verified)} rows")
    print(f"TS247 INDEX    : {len(ts247_index)} schools")
    print(f"FALLBACK CACHE : {len(fallback_cache)} rows / {fallback_cache['university_name'].nunique() if not fallback_cache.empty else 0} schools")
    print()

    for idx, source in documents.iterrows():
        university_name = clean_text(source.get("university_name"))
        source_type = clean_text(source.get(type_col)).upper()
        source_url = resolve_google_viewer_url(clean_text(source.get(source_col)))
        page_url = clean_text(source.get(page_col)) if page_col else ""
        school_norm = normalize_school(university_name)

        print(f"[{idx + 1:02d}/{len(documents):02d}] {university_name} ... ", end="", flush=True)

        if school_norm in verified_school_norms:
            print("SKIP (đã verified riêng)")
            continue

        force_review = school_norm in force_review_norms
        result = ParseResult([], "", "chưa parse")

        try:
            if force_review:
                result = ParseResult([], "", "nguồn chính thức đã biết phức tạp/lỗi font; chuyển thẳng sang fallback có cấu trúc")

            elif source_type == "PDF":
                local_file, classification = find_local_pdf(
                    pdf_analysis,
                    university_name,
                    source_url,
                )

                if classification == "TEXT_PDF" and local_file:
                    result = parse_pdf_document(
                        university_name=university_name,
                        source_url=source_url,
                        local_file=local_file,
                    )

                elif classification == "SCAN_OR_IMAGE":
                    # Không OCR tự động. Chỉ thử bảng HTML ở trang nguồn.
                    result = parse_page_url_fallback(
                        university_name,
                        page_url,
                        source_url,
                    )
                    if not result.rows:
                        result.reason = f"PDF scan/ảnh; {result.reason}"

                else:
                    # FAILED/chưa có local: thử tải lại chính PDF (bao gồm SSL whitelist).
                    try:
                        response = get_url(source_url)
                        content = response.content
                        if content.startswith(b"%PDF"):
                            result = parse_pdf_document(
                                university_name=university_name,
                                source_url=source_url,
                                content=content,
                            )
                        else:
                            result = ParseResult([], "", "link PDF không trả PDF thật")
                    except Exception as exc:
                        result = ParseResult([], "", f"tải PDF lỗi: {exc}")

                    if not result.rows and page_url:
                        fallback = parse_page_url_fallback(
                            university_name,
                            page_url,
                            source_url,
                        )
                        if fallback.rows:
                            result = fallback

            elif source_type == "EXTERNAL_DOCUMENT":
                result = parse_external_document(
                    university_name,
                    source_url,
                )

                if not result.rows and page_url:
                    fallback = parse_page_url_fallback(
                        university_name,
                        page_url,
                        source_url,
                    )
                    if fallback.rows:
                        result = fallback

            else:
                # document_sources_verified hiện chủ yếu PDF/EXTERNAL_DOCUMENT.
                # Nếu có type khác thì chỉ thử page_url an toàn.
                result = parse_page_url_fallback(
                    university_name,
                    page_url,
                    source_url,
                )

        except Exception as exc:
            result = ParseResult([], "", f"exception: {type(exc).__name__}: {exc}")

        candidate_df = canonicalize_rows(result.rows)
        ok, validation_reason = validate_school_rows(candidate_df, result.context_text)

        if ok:
            auto_rows.extend(candidate_df.to_dict("records"))
            accepted_schools.add(university_name)
            print(f"AUTO ✅ {len(candidate_df)} rows | method={result.method_code}")
            continue

        # V6: official verified -> cache ổn định -> TS247 live retry.
        fallback, fallback_df, fallback_ok, fallback_reason, fallback_cache, fallback_mode = get_stable_fallback(
            university_name, ts247_index, fallback_cache
        )

        if fallback_ok:
            auto_rows.extend(fallback_df.to_dict("records"))
            accepted_schools.add(university_name)
            fallback_code = ""
            if not fallback_df.empty:
                note0 = clean_text(fallback_df["admission_note"].iloc[0])
                code_match = re.search(r"Mã trường TS247=([A-Z0-9]+)", note0)
                fallback_code = code_match.group(1) if code_match else ""
            code_label = f" | code={fallback_code}" if fallback_code else ""
            if fallback_mode == "OFFICIAL":
                print(f"OFFICIAL ✅ {len(fallback_df)} rows | UEB PT100")
            elif fallback_mode == "CACHE":
                print(f"CACHE ✅ {len(fallback_df)} rows | TS247 THPT{code_label}")
            else:
                print(f"FALLBACK ✅ {len(fallback_df)} rows | TS247 THPT{code_label} | {fallback_mode}")
            time.sleep(0.05)
            continue

        # Khi candidate rỗng, ưu tiên lý do parser thật thay vì câu generic.
        if candidate_df.empty:
            primary_reason = result.reason or validation_reason or "nguồn chính thức không có candidate"
        else:
            primary_reason = validation_reason or result.reason or "nguồn chính thức chưa đủ độ tin cậy"

        if fallback_df.empty:
            secondary_reason = fallback.reason or fallback_reason or "fallback chưa đủ độ tin cậy"
        else:
            secondary_reason = fallback_reason or fallback.reason or "fallback chưa đủ độ tin cậy"
        reason = f"PRIMARY: {primary_reason} | FALLBACK: {secondary_reason}"

        review_rows.append(
            {
                "university_name": university_name,
                "source_type": source_type,
                "status": "REVIEW",
                "reason": reason,
                "detected_method": fallback.method_code or result.method_code,
                "candidate_rows": max(len(candidate_df), len(fallback_df)),
                "page_url": page_url,
                "source_url": fallback_df["source_url"].iloc[0] if not fallback_df.empty else source_url,
            }
        )
        print(f"REVIEW ⚠ | {secondary_reason}")
        time.sleep(0.10)

    auto_df = canonicalize_rows(auto_rows)
    auto_df = deduplicate_final(auto_df)

    # V3: hậu kiểm toàn batch fallback để bắt cross-school contamination.
    auto_df, review_rows, quarantine_events = quarantine_cross_school_fallback(
        auto_df,
        review_rows,
    )
    auto_df = deduplicate_final(auto_df)

    review_df = pd.DataFrame(review_rows, columns=REVIEW_COLUMNS)
    if not review_df.empty:
        review_df = review_df.drop_duplicates(
            subset=["university_name", "source_url", "reason"],
            keep="first",
        ).reset_index(drop=True)

    # V6.1: thêm Trường ĐH Kiến trúc Đà Nẵng từ công bố chính thức 2025.
    dau_official_df = build_dau_official_2025()

    # FINAL = HTML verified + Thủy lợi verified + batch-auto + DAU official.
    final_df = pd.concat(
        [html_verified, thuyloi_verified, auto_df, dau_official_df],
        ignore_index=True,
    )
    final_df = canonicalize_rows(final_df.to_dict("records"))
    final_df = deduplicate_final(final_df)

    # Không ghi đè bất kỳ *_verified.csv nào.
    auto_df.to_csv(AUTO_FILE, index=False, encoding="utf-8-sig")
    review_df.to_csv(REVIEW_FILE, index=False, encoding="utf-8-sig")
    final_df.to_csv(FINAL_FILE, index=False, encoding="utf-8-sig")

    # V6 final: tách dataset thực sự sẵn sàng cho ML khỏi FINAL bảo toàn nguồn.
    ml_ready_df, ml_excluded_df = build_ml_ready_2025(final_df)
    ml_ready_df.to_csv(ML_READY_FILE, index=False, encoding="utf-8-sig")
    ml_excluded_df.to_csv(ML_EXCLUDED_FILE, index=False, encoding="utf-8-sig")

    print()
    print("=" * 88)
    print("KẾT QUẢ PIPELINE 2025")
    print("=" * 88)
    print(f"HTML VERIFIED        : {len(html_verified):5d} rows / {html_verified['university_name'].nunique():3d} schools")
    print(f"THỦY LỢI VERIFIED    : {len(thuyloi_verified):5d} rows / {thuyloi_verified['university_name'].nunique():3d} schools")
    print(f"DAU OFFICIAL         : {len(dau_official_df):5d} rows / {dau_official_df['university_name'].nunique():3d} schools")
    print(f"DOCUMENT AUTO        : {len(auto_df):5d} rows / {auto_df['university_name'].nunique() if not auto_df.empty else 0:3d} schools")
    print(f"NEEDS REVIEW         : {len(review_df):5d} sources / {review_df['university_name'].nunique() if not review_df.empty else 0:3d} schools")
    print(f"QUARANTINED V6       : {len(quarantine_events):5d} schools/events")
    print(f"FALLBACK CACHE FINAL : {len(fallback_cache):5d} rows / {fallback_cache['university_name'].nunique() if not fallback_cache.empty else 0:3d} schools")
    print("-" * 88)
    print(f"FINAL CLEAN 2025     : {len(final_df):5d} rows / {final_df['university_name'].nunique() if not final_df.empty else 0:3d} schools")

    if not final_df.empty:
        print(f"Score min/max        : {final_df['cutoff_score'].min()} / {final_df['cutoff_score'].max()}")
        print(f"Missing major_code   : {int(final_df['major_code'].isna().sum())}")
        print(f"Missing major_name   : {int(final_df['major_name'].isna().sum())}")
        print(f"Missing cutoff_score : {int(final_df['cutoff_score'].isna().sum())}")

    audit_issues = audit_final_dataset(final_df)
    print()
    if audit_issues:
        print("AUDIT V6             : ⚠ " + " | ".join(audit_issues))
    else:
        print("AUDIT V6             : ✅ không phát hiện lỗi cấu trúc/cross-school fallback")

    print(f"ML READY 2025        : {len(ml_ready_df):5d} rows / {ml_ready_df['university_name'].nunique() if not ml_ready_df.empty else 0:3d} schools")
    print(f"ML EXCLUDED          : {len(ml_excluded_df):5d} rows (ngoài thang THPT-30)")

    checkpoint_ok, checkpoint_reason = checkpoint_2025_status(review_df, audit_issues)
    if checkpoint_ok:
        print("2025 CHECKPOINT      : ✅ CÓ THỂ KHÓA NĂM 2025")
        print(f"                       {checkpoint_reason}")
    else:
        print("2025 CHECKPOINT      : ⚠ CHƯA KHÓA")
        print(f"                       {checkpoint_reason}")

    if quarantine_events:
        print()
        print("QUARANTINE EVENTS V6:")
        for event in quarantine_events:
            print(f"  ⛔ {event}")

    print()
    print("FILES:")
    print(" AUTO   :", AUTO_FILE)
    print(" REVIEW :", REVIEW_FILE)
    print(" FINAL  :", FINAL_FILE)
    print(" CACHE  :", FALLBACK_CACHE_FILE)
    print(" ML     :", ML_READY_FILE)
    print(" EXCLUDE:", ML_EXCLUDED_FILE)
    print("=" * 88)

    if not review_df.empty:
        print()
        print("CÁC TRƯỜNG CẦN REVIEW (không bị đưa vào FINAL):")
        for _, row in review_df.sort_values("university_name").iterrows():
            print(f"  ⚠ {row['university_name']} | {row['reason']}")


if __name__ == "__main__":
    main()
