import re
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
}

THPT_EXAM_KEYWORDS = [
    "kết quả thi tốt nghiệp thpt",
    "kết quả kỳ thi tốt nghiệp thpt",
    "kỳ thi tốt nghiệp thpt",
    "thi tốt nghiệp thpt",
    "xét điểm thi tốt nghiệp thpt",
    "xét tuyển theo kết quả thi tốt nghiệp thpt",
    "xét tuyển dựa trên điểm thi tốt nghiệp thpt",
    "kq thi tn thpt",
    "kết quả thi tn thpt",
    "thi tn thpt",
    "xét điểm thi tn thpt",
    "điểm thi thpt",
    "theo điểm thi thpt",
    "xét điểm thi thpt",
]

NON_THPT_KEYWORDS = [
    "học bạ",
    "kết quả học tập",
    "đánh giá năng lực",
    "đgnl",
    "đánh giá tư duy",
    "đgtd",
    "v-sat",
    "vsat",
    "hsa",
    "tsa",
    "đánh giá đầu vào",
    "tuyển thẳng",
]

COMBINED_KEYWORDS = [
    "xét tuyển kết hợp",
    "xét kết hợp",
    "kết hợp kết quả",
    "kết hợp điểm thi",
    "điểm thi thpt và học bạ",
    "điểm thi tốt nghiệp thpt và học bạ",
    "học bạ và điểm thi",
    "học bạ và kết quả thi",
]


def clean_text(value):
    if value is None:
        return ""

    value = str(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def contains_thpt_exam(text):
    text = clean_text(text)
    return any(keyword in text for keyword in THPT_EXAM_KEYWORDS)


def contains_combined_method(text):
    text = clean_text(text)
    return any(keyword in text for keyword in COMBINED_KEYWORDS)


def contains_non_thpt(text):
    text = clean_text(text)
    return any(keyword in text for keyword in NON_THPT_KEYWORDS)


def extract_method_codes(text):
    """
    Nhận:
      PT3
      PT 3
      Phương thức 3
      Phương thức 2A
    """
    text = clean_text(text)
    codes = set()

    for pattern in [
        r"\bpt\s*([0-9]+[a-z]?)\b",
        r"\bphương\s*thức(?:\s+xét\s+tuyển)?\s*([0-9]+[a-z]?)\b",
    ]:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            codes.add("PT" + match.group(1).upper())

    return sorted(codes)


def extract_thpt_method_codes(html):
    """
    Chỉ phát hiện mã phương thức khi mã đó xuất hiện gần cụm mô tả
    điểm thi tốt nghiệp THPT.
    """
    soup = BeautifulSoup(html, "lxml")
    text = clean_text(soup.get_text(" ", strip=True))

    detected_codes = set()

    thpt_phrase = (
        r"(?:"
        r"kết\s+quả\s+(?:kỳ\s+)?thi\s+tốt\s+nghiệp\s+thpt"
        r"|kỳ\s+thi\s+tốt\s+nghiệp\s+thpt"
        r"|thi\s+tốt\s+nghiệp\s+thpt"
        r"|xét\s+(?:tuyển\s+)?(?:dựa\s+trên\s+|theo\s+)?"
        r"(?:kết\s+quả\s+)?điểm\s+thi\s+(?:tốt\s+nghiệp\s+)?thpt"
        r")"
    )

    patterns = [
        (
            rf"\bpt\s*([0-9]+[a-z]?)\b"
            rf"\s*[-:–—]?\s*[^.;]{{0,220}}?{thpt_phrase}"
        ),
        (
            rf"\bphương\s*thức(?:\s+xét\s+tuyển)?\s*"
            rf"([0-9]+[a-z]?)\b[^.;]{{0,220}}?{thpt_phrase}"
        ),
        (
            rf"{thpt_phrase}[^.;]{{0,220}}?"
            rf"\(\s*pt\s*([0-9]+[a-z]?)\s*\)"
        ),
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            # thpt_phrase contains no capturing groups, so group(1) is method code.
            detected_codes.add("PT" + match.group(1).upper())

    return sorted(detected_codes)


def find_table_context(table_tag):
    """
    Lấy đoạn mô tả gần nhất trước bảng.
    """
    signals = [
        "phương thức",
        "pt1", "pt2", "pt3", "pt4", "pt5",
        "thi tốt nghiệp",
        "thi tn thpt",
        "điểm thi thpt",
        "xét điểm thi",
        "học bạ",
        "kết quả học tập",
        "đánh giá năng lực",
        "đánh giá tư duy",
        "xét tuyển kết hợp",
        "v-sat",
        "hsa",
        "tsa",
    ]

    previous_tags = table_tag.find_all_previous(
        ["p", "h1", "h2", "h3", "h4", "h5", "strong", "b", "div"],
        limit=80,
    )

    for tag in previous_tags:
        text = clean_text(tag.get_text(" ", strip=True))

        if not text or len(text) > 1000:
            continue

        if any(signal in text for signal in signals):
            return text

    return ""


def classify_table_context(context, thpt_method_codes=None):
    """
    THPT:
        phương thức điểm thi THPT thuần.
    THPT_COMBINED:
        điểm thi THPT được kết hợp học bạ/chứng chỉ/tiêu chí khác.
        Có thể giữ RAW nhưng KHÔNG nên đưa thẳng vào ML THPT-30.
    NON_THPT:
        học bạ, ĐGNL, ĐGTD... không có evidence THPT.
    NEUTRAL:
        chưa đủ bằng chứng.
    """
    context = clean_text(context)

    if not context:
        return "NEUTRAL"

    context_codes = set(extract_method_codes(context))
    thpt_codes = set(thpt_method_codes or [])

    has_thpt = contains_thpt_exam(context)
    has_combined = contains_combined_method(context)

    if has_thpt and has_combined:
        return "THPT_COMBINED"

    if context_codes and thpt_codes and context_codes.intersection(thpt_codes):
        if has_combined:
            return "THPT_COMBINED"
        return "THPT"

    if has_thpt:
        return "THPT"

    if contains_non_thpt(context):
        return "NON_THPT"

    if has_combined:
        # "kết hợp" nhưng không chứng minh có điểm thi THPT.
        return "NON_THPT"

    if (
        context_codes
        and thpt_codes
        and not context_codes.intersection(thpt_codes)
    ):
        return "NON_THPT"

    return "NEUTRAL"


def flatten_column(column):
    if isinstance(column, tuple):
        parts = []

        for item in column:
            text = str(item).strip()

            if (
                not text
                or text.lower() == "nan"
                or text.lower().startswith("unnamed:")
            ):
                continue

            if text not in parts:
                parts.append(text)

        return " | ".join(parts)

    return str(column).strip()


def is_note_header(column_name):
    name = clean_text(column_name)

    return (
        "nguyện vọng" in name
        or "tiêu chí phụ" in name
        or "điều kiện bổ sung" in name
        or "ghi chú" in name
    )


def is_combined_major_header(column_name):
    name = clean_text(column_name)

    return (
        (
            "mã xét tuyển" in name
            or "mã ngành" in name
            or "mã chương trình" in name
        )
        and (
            "tên ngành" in name
            or "ngành, chương trình" in name
            or "chương trình đào tạo" in name
            or "tên chương trình" in name
        )
    )


def is_major_code_header(column_name):
    name = clean_text(column_name)

    if is_combined_major_header(column_name):
        return False

    return (
        name == "mã"
        or name == "mã ngành"
        or name == "mã xét tuyển"
        or name == "mã ctđt"
        or "mã ngành" in name
        or "mã ngành tuyển sinh" in name
        or "mã xét tuyển" in name
        or "mã chương trình đào tạo" in name
        or "mã chương trình" in name
        or "mã ctđt" in name
    )


def is_major_name_header(column_name):
    name = clean_text(column_name)

    if is_combined_major_header(column_name):
        return False

    if is_major_code_header(column_name):
        return False

    return (
        name == "ngành"
        or name == "chuyên ngành"
        or "tên ngành" in name
        or "ngành đào tạo" in name
        or "ngành tuyển sinh" in name
        or "ngành/ctđt" in name
        or "ngành / ctđt" in name
        or "chương trình đào tạo" in name
        or "tên chương trình" in name
        or "tên ngành/chuyên ngành" in name
        or "tên ngành/chương trình" in name
        or "tên mã xét tuyển" in name
        or "chuyên ngành" in name
    )


def is_combination_header(column_name):
    name = clean_text(column_name)

    if (
        "điểm chuẩn" in name
        or "điểm trúng tuyển" in name
        or "ngưỡng điểm" in name
    ):
        return False

    return (
        name == "tổ hợp"
        or name == "tổ hợp gốc"
        or name == "tổ hợp xét tuyển"
        or "tổ hợp xét tuyển" in name
        or "các tổ hợp xét tuyển" in name
    )


def is_score_header(column_name):
    name = clean_text(column_name)

    if is_note_header(column_name):
        return False

    # Không coi "điểm sàn/ngưỡng đầu vào" là cutoff.
    if (
        "điểm sàn" in name
        or "ngưỡng đầu vào" in name
        or "ngưỡng đảm bảo" in name
        or "ngưỡng bảo đảm" in name
    ):
        return False

    return (
        "điểm chuẩn" in name
        or "điểm trúng tuyển" in name
        or "mức điểm trúng tuyển" in name
    )


def is_method_header(column_name):
    name = clean_text(column_name)

    if is_score_header(column_name):
        return False

    return (
        "phương thức" in name
        or "ptxt" in name
        or "phương thức tuyển sinh" in name
    )


def score_priority(column_name, thpt_method_codes=None):
    if not is_score_header(column_name):
        return -1000

    name = clean_text(column_name)
    score = 10

    for method_code in thpt_method_codes or []:
        method_text = clean_text(method_code)

        if re.search(
            rf"\b{re.escape(method_text)}\b",
            name,
        ):
            score += 200

    if (
        "điểm chuẩn thpt" in name
        or "điểm trúng tuyển thpt" in name
    ):
        score += 150

    if contains_thpt_exam(name):
        score += 100

    non_thpt_header_keywords = [
        "học bạ",
        "điểm chuẩn hb",
        "kết quả học tập",
        "đgnl",
        "đgtd",
        "đánh giá năng lực",
        "đánh giá tư duy",
        "điểm chuẩn tsa",
        "điểm chuẩn hsa",
        "điểm chuẩn spt",
        "v-sat",
        "vsat",
        "tsa",
        "hsa",
    ]

    if any(keyword in name for keyword in non_thpt_header_keywords):
        score -= 150

    return score


def select_score_column(columns, thpt_method_codes=None):
    candidates = []

    for column in columns:
        if is_score_header(column):
            candidates.append(
                (
                    column,
                    score_priority(
                        column,
                        thpt_method_codes,
                    ),
                )
            )

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0][0]

    best = max(
        candidates,
        key=lambda item: item[1],
    )

    # Khi có nhiều cột điểm chỉ chọn cột đủ evidence THPT.
    if best[1] >= 50:
        return best[0]

    return None


def headers_are_generic(columns):
    for column in columns:
        name = clean_text(
            flatten_column(column)
        )

        if re.fullmatch(r"\d+", name):
            continue

        if not name or name.startswith("unnamed:"):
            continue

        return False

    return True


def build_header_from_rows(table, number_of_rows):
    headers = []

    for column_index in range(len(table.columns)):
        parts = []

        for row_index in range(number_of_rows):
            value = table.iloc[
                row_index,
                column_index,
            ]

            if pd.isna(value):
                continue

            text = str(value).strip()

            if not text or text.lower() == "nan":
                continue

            if text not in parts:
                parts.append(text)

        headers.append(
            " | ".join(parts)
            if parts
            else f"column_{column_index}"
        )

    result = table.iloc[number_of_rows:].copy()
    result.columns = headers
    return result.reset_index(drop=True)


def create_table_candidates(table):
    candidates = []

    if not headers_are_generic(table.columns):
        result = table.copy()
        result.columns = [
            flatten_column(column)
            for column in table.columns
        ]
        candidates.append(result)
        return candidates

    max_header_rows = min(
        3,
        len(table) - 1,
    )

    for number_of_rows in range(
        1,
        max_header_rows + 1,
    ):
        candidates.append(
            build_header_from_rows(
                table,
                number_of_rows,
            )
        )

    return candidates


def table_has_explicit_thpt_score(
    table,
    thpt_method_codes=None,
):
    candidates = create_table_candidates(table)
    thpt_codes = [
        clean_text(code)
        for code in (thpt_method_codes or [])
    ]

    for candidate in candidates:
        for column in candidate.columns:
            if not is_score_header(column):
                continue

            name = clean_text(column)

            explicit_thpt = (
                contains_thpt_exam(name)
                or (
                    "thpt" in name
                    and not contains_non_thpt(name)
                )
            )

            if explicit_thpt:
                return True

            for code in thpt_codes:
                if re.search(
                    rf"\b{re.escape(code)}\b",
                    name,
                ):
                    return True

    return False


def select_combination_column(
    columns,
    score_column,
):
    combinations = [
        column
        for column in columns
        if is_combination_header(column)
    ]

    if not combinations:
        return None

    if len(combinations) == 1:
        return combinations[0]

    score_prefix = clean_text(
        score_column
    ).split("|")[0].strip()

    for column in combinations:
        combination_prefix = clean_text(
            column
        ).split("|")[0].strip()

        if combination_prefix == score_prefix:
            return column

    return combinations[0]


def normalize_score(value):
    if pd.isna(value):
        return None

    text = str(value).strip()

    if text in {"", "-", "--", "nan", "None"}:
        return None

    text = (
        text.replace(",", ".")
        .replace(" ", "")
    )

    try:
        return float(text)
    except ValueError:
        match = re.search(
            r"-?\d+(?:\.\d+)?",
            text,
        )

        if match:
            try:
                return float(
                    match.group()
                )
            except ValueError:
                return None

    return None


def is_valid_major_code(value):
    """
    Chặt hơn bản cũ:
    - Không cho STT '1', '2', '3' lọt thành major_code.
    - Vẫn cho mã chuẩn 7480201, 7420201A...
    - Vẫn cho mã chương trình QHT01, D101, EP12, UTHGIT01V...
    """
    if pd.isna(value):
        return False

    text = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
    )

    if not text or len(text) > 30:
        return False

    if text.isdigit():
        return 6 <= len(text) <= 8

    patterns = [
        r"[A-Z]{1,12}\d{1,12}[A-Z0-9]{0,12}",
        r"\d{5,8}[A-Z][A-Z0-9]{0,12}",
        r"[A-Z0-9]{2,16}[_./-][A-Z0-9_.\-/]{1,16}",
    ]

    return any(
        re.fullmatch(pattern, text)
        for pattern in patterns
    )


def split_combined_major(value):
    if pd.isna(value):
        return None, None

    text = str(value).strip()

    patterns = [
        r"mã\s*xét\s*tuyển\s*:\s*([A-Za-z0-9._/-]+)",
        r"mã\s*ngành\s*:\s*([A-Za-z0-9._/-]+)",
        r"mã\s*ctđt\s*:\s*([A-Za-z0-9._/-]+)",
        r"mã\s*chương\s*trình(?:\s*đào\s*tạo)?\s*:\s*([A-Za-z0-9._/-]+)",
    ]

    code_match = None

    for pattern in patterns:
        code_match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        if code_match:
            break

    if not code_match:
        return text, None

    major_code = code_match.group(1).strip()

    major_name = re.sub(
        r"\s*mã\s*(?:xét\s*tuyển|ngành|ctđt|chương\s*trình(?:\s*đào\s*tạo)?)"
        r"\s*:.*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ,-")

    return major_name, major_code


def find_first_column(columns, detector):
    for column in columns:
        if detector(column):
            return column

    return None


def derive_method_from_score_header(score_column):
    name = clean_text(score_column)

    match = re.search(
        r"\bpt\s*([0-9]+[a-z]?)\b",
        name,
        flags=re.IGNORECASE,
    )

    if match:
        return "PT" + match.group(1).upper()

    if (
        "điểm chuẩn thpt" in name
        or "điểm trúng tuyển thpt" in name
        or contains_thpt_exam(name)
    ):
        return "THPT"

    return None


def derive_method_from_context(
    table_context,
    thpt_method_codes=None,
):
    codes = extract_method_codes(
        table_context
    )
    thpt_codes = set(
        thpt_method_codes or []
    )

    for code in codes:
        if code in thpt_codes:
            return code

    if contains_thpt_exam(
        table_context
    ):
        if len(codes) == 1:
            return codes[0]

        if len(thpt_codes) == 1:
            return next(
                iter(thpt_codes)
            )

        return "THPT"

    return None


def row_method_type(
    value,
    thpt_method_codes=None,
):
    text = clean_text(value)

    if not text:
        return "NEUTRAL"

    codes = set(
        extract_method_codes(text)
    )
    thpt_codes = set(
        thpt_method_codes or []
    )

    has_thpt = contains_thpt_exam(text)
    has_combined = contains_combined_method(text)

    if has_thpt and has_combined:
        return "THPT_COMBINED"

    if has_thpt:
        return "THPT"

    if codes and thpt_codes and codes.intersection(thpt_codes):
        return "THPT_COMBINED" if has_combined else "THPT"

    if contains_non_thpt(text) or has_combined:
        return "NON_THPT"

    if (
        codes
        and thpt_codes
        and not codes.intersection(thpt_codes)
    ):
        return "NON_THPT"

    # Rất nhiều bảng 2026 ghi ngắn "Xét điểm thi THPT".
    if "thpt" in text:
        return "THPT_COMBINED" if has_combined else "THPT"

    return "NEUTRAL"


def append_note(old_value, marker):
    old = (
        str(old_value).strip()
        if pd.notna(old_value)
        else ""
    )

    if not old:
        return marker

    if marker.lower() in old.lower():
        return old

    return f"{old}; {marker}"


def parse_candidate_table(
    table,
    thpt_method_codes=None,
    table_context="",
):
    columns = list(
        table.columns
    )

    combined_major_column = find_first_column(
        columns,
        is_combined_major_header,
    )
    major_code_column = find_first_column(
        columns,
        is_major_code_header,
    )
    major_name_column = find_first_column(
        columns,
        is_major_name_header,
    )
    score_column = select_score_column(
        columns,
        thpt_method_codes,
    )

    if score_column is None:
        return None

    if combined_major_column is None:
        if (
            major_code_column is None
            or major_name_column is None
        ):
            return None

    result = pd.DataFrame(
        index=table.index
    )

    if combined_major_column is not None:
        parsed = table[
            combined_major_column
        ].apply(
            split_combined_major
        )

        result["major_name"] = parsed.apply(
            lambda item: item[0]
        )
        result["major_code"] = parsed.apply(
            lambda item: item[1]
        )
    else:
        result["major_code"] = table[
            major_code_column
        ]
        result["major_name"] = table[
            major_name_column
        ]

    result["cutoff_score"] = table[
        score_column
    ].apply(
        normalize_score
    )

    method_column = find_first_column(
        columns,
        is_method_header,
    )

    if method_column is not None:
        result["admission_method_codes"] = table[
            method_column
        ]
        result["_row_method_type"] = table[
            method_column
        ].apply(
            lambda value: row_method_type(
                value,
                thpt_method_codes,
            )
        )
    else:
        inferred_method = derive_method_from_score_header(
            score_column
        )

        if inferred_method is None:
            inferred_method = derive_method_from_context(
                table_context,
                thpt_method_codes,
            )

        result[
            "admission_method_codes"
        ] = inferred_method
        result["_row_method_type"] = "NEUTRAL"

    combination_column = select_combination_column(
        columns,
        score_column,
    )

    if combination_column is not None:
        result["combination"] = table[
            combination_column
        ]
    else:
        result["combination"] = None

    note_column = find_first_column(
        columns,
        is_note_header,
    )

    if note_column is not None:
        result["admission_note"] = table[
            note_column
        ]
    else:
        result["admission_note"] = None

    context_type = classify_table_context(
        table_context,
        thpt_method_codes,
    )

    # 2026 thường có cột phương thức theo từng dòng.
    # Nếu trong bảng có ít nhất một dòng xác định rõ THPT,
    # chỉ giữ THPT/THPT_COMBINED, không trộn học bạ/ĐGNL.
    if method_column is not None:
        explicit_mask = result[
            "_row_method_type"
        ].isin(
            ["THPT", "THPT_COMBINED"]
        )

        if explicit_mask.any():
            result = result[
                explicit_mask
            ].copy()
        elif context_type in {
            "THPT",
            "THPT_COMBINED",
        }:
            # Bảng đã có context THPT nhưng cell phương thức chỉ ghi mã/ngắn.
            result = result[
                result["_row_method_type"]
                != "NON_THPT"
            ].copy()
        else:
            return None

    # Mark combined rows/table so ML pipeline can exclude them later.
    combined_mask = (
        result["_row_method_type"]
        == "THPT_COMBINED"
    )

    if context_type == "THPT_COMBINED":
        combined_mask = pd.Series(
            True,
            index=result.index,
        )

    if combined_mask.any():
        result.loc[
            combined_mask,
            "admission_note",
        ] = result.loc[
            combined_mask,
            "admission_note",
        ].apply(
            lambda value: append_note(
                value,
                "thpt_combined",
            )
        )

    valid_mask = result[
        "major_code"
    ].apply(
        is_valid_major_code
    )

    result = result[
        valid_mask
    ].copy()

    result = result.dropna(
        subset=[
            "major_code",
            "major_name",
            "cutoff_score",
        ]
    ).reset_index(
        drop=True
    )

    result = result.drop(
        columns=["_row_method_type"],
        errors="ignore",
    )

    if result.empty:
        return None

    return result


def parse_html_table(
    table,
    thpt_method_codes=None,
    table_context="",
):
    candidates = create_table_candidates(
        table
    )
    best_result = None

    for candidate in candidates:
        result = parse_candidate_table(
            candidate,
            thpt_method_codes,
            table_context,
        )

        if (
            result is not None
            and len(result) > 0
        ):
            if (
                best_result is None
                or len(result)
                > len(best_result)
            ):
                best_result = result

    return best_result


def read_tables_with_context(html):
    soup = BeautifulSoup(
        html,
        "lxml",
    )
    table_tags = soup.find_all(
        "table"
    )
    entries = []

    for table_index, table_tag in enumerate(
        table_tags
    ):
        context = find_table_context(
            table_tag
        )

        try:
            parsed_tables = pd.read_html(
                StringIO(
                    str(table_tag)
                ),
                header=None,
                thousands=None,
            )
        except Exception:
            continue

        for parsed_table in parsed_tables:
            entries.append(
                {
                    "index": table_index,
                    "table": parsed_table,
                    "context": context,
                }
            )

    if not entries:
        try:
            fallback_tables = pd.read_html(
                StringIO(html),
                header=None,
                thousands=None,
            )

            for index, table in enumerate(
                fallback_tables
            ):
                entries.append(
                    {
                        "index": index,
                        "table": table,
                        "context": "",
                    }
                )
        except Exception:
            pass

    return entries


def scrape_school(
    university_name,
    url,
    year,
):
    """
    Generic HTML scraper cho 2023-2026.

    year bắt buộc truyền rõ để tránh lỗi vô tình gán 2025 cho dữ liệu 2026.
    """
    if year not in {
        2023,
        2024,
        2025,
        2026,
    }:
        raise ValueError(
            "year phải thuộc phạm vi đồ án 2023-2026"
        )

    print()
    print("=" * 80)
    print(
        f"ĐANG CÀO {year}:",
        university_name,
    )
    print("URL:", url)
    print("=" * 80)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=25,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(
            "❌ Không tải được trang:",
            error,
        )
        return None

    content_type = clean_text(
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if (
        "application/pdf" in content_type
        or response.content[:5] == b"%PDF-"
    ):
        print(
            "ℹ Nguồn là PDF trực tiếp. "
            "school_scraper chỉ xử lý HTML; "
            "hãy chuyển PDF sang pipeline document/OCR."
        )
        return None

    thpt_method_codes = extract_thpt_method_codes(
        response.text
    )

    if thpt_method_codes:
        print(
            "✅ Phương thức THPT phát hiện:",
            thpt_method_codes,
        )
    else:
        print(
            "ℹ Không phát hiện mã PT THPT cụ thể."
        )

    table_entries = read_tables_with_context(
        response.text
    )

    if not table_entries:
        print(
            "❌ Trang không có bảng HTML đọc được."
        )
        return None

    print(
        "Số bảng HTML:",
        len(table_entries),
    )

    extracted_tables = []

    for entry in table_entries:
        table_index = entry["index"]
        table = entry["table"]
        table_context = entry["context"]

        context_type = classify_table_context(
            table_context,
            thpt_method_codes,
        )

        table_has_thpt = table_has_explicit_thpt_score(
            table,
            thpt_method_codes,
        )

        if (
            context_type == "NON_THPT"
            and not table_has_thpt
        ):
            print(
                f"⏭ Table {table_index}: NON_THPT"
            )
            continue

        parsed = parse_html_table(
            table,
            thpt_method_codes,
            table_context,
        )

        if (
            parsed is not None
            and len(parsed) > 0
        ):
            print(
                f"✅ Table {table_index}: "
                f"{len(parsed)} dòng | "
                f"context={context_type}"
            )
            extracted_tables.append(
                parsed
            )

    if not extracted_tables:
        print(
            "⚠ Không có bảng điểm THPT đủ điều kiện."
        )
        return None

    admission_table = pd.concat(
        extracted_tables,
        ignore_index=True,
    )

    text_columns = [
        "major_code",
        "major_name",
        "admission_method_codes",
        "combination",
        "admission_note",
    ]

    for column in text_columns:
        admission_table[column] = admission_table[
            column
        ].apply(
            lambda value:
                str(value).strip()
                if pd.notna(value)
                else None
        )

    admission_table = (
        admission_table
        .drop_duplicates(
            subset=[
                "major_code",
                "major_name",
                "admission_method_codes",
                "combination",
                "cutoff_score",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    admission_table[
        "university_name"
    ] = university_name
    admission_table["year"] = year
    admission_table[
        "source_url"
    ] = url

    admission_table = admission_table[
        [
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
    ]

    print(
        f"✅ Thành công: "
        f"{len(admission_table)} dòng"
    )

    return admission_table
