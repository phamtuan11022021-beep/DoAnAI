from io import StringIO
from urllib.parse import urljoin

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


def clean_text(value):
    if value is None:
        return ""

    value = str(value).replace("\xa0", " ")
    return " ".join(
        value.split()
    ).strip().lower()


def table_signals(table):
    """
    Trả về tín hiệu thay vì bắt buộc phải có major_code.

    Lý do:
    một số bảng điểm chuẩn thật có:
      Tên ngành | Điểm trúng tuyển
    nhưng không công bố mã ngay trong bảng.
    Pipeline final có thể map mã bằng same-school cross-year sau.
    """
    column_text = " ".join(
        clean_text(column)
        for column in table.columns
    )

    row_text = " ".join(
        clean_text(value)
        for value in table.head(
            12
        ).values.flatten()
    )

    full_text = (
        column_text
        + " "
        + row_text
    )

    has_major_code = any(
        marker in full_text
        for marker in (
            "mã ngành",
            "mã xét tuyển",
            "mã ctđt",
            "mã chương trình",
            "mã chương trình đào tạo",
        )
    )

    has_major_name = any(
        marker in full_text
        for marker in (
            "tên ngành",
            "ngành đào tạo",
            "tên ngành/ctđt",
            "chương trình đào tạo",
            "chuyên ngành",
            "tên mã xét tuyển",
            "ngành",
        )
    )

    has_score = any(
        marker in full_text
        for marker in (
            "điểm chuẩn",
            "điểm trúng tuyển",
            "mức điểm trúng tuyển",
        )
    )

    has_floor_only = (
        "điểm sàn" in full_text
        or "ngưỡng đầu vào" in full_text
        or "ngưỡng đảm bảo" in full_text
        or "ngưỡng bảo đảm" in full_text
    )

    return {
        "has_major_code": has_major_code,
        "has_major_name": has_major_name,
        "has_score": has_score,
        "has_floor_only": has_floor_only,
        "is_candidate": (
            has_major_name
            and has_score
            and not has_floor_only
        ),
    }


def is_admission_table(table):
    return table_signals(
        table
    )["is_candidate"]


def find_article_images(
    soup,
    page_url,
):
    article_images = []

    h1 = soup.find("h1")

    if h1 is None:
        # Fallback: vẫn xét img nhưng filter rất chặt.
        elements = soup.find_all(
            "img"
        )
    else:
        elements = h1.find_all_next()

    for element in elements:
        if element.name in [
            "h2",
            "h3",
            "h4",
            "div",
            "p",
        ]:
            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                text == "tin cùng chuyên mục"
                or text.startswith(
                    "tin cùng chuyên mục"
                )
            ):
                break

        if element.name != "img":
            continue

        raw_values = [
            element.get("src"),
            element.get("data-src"),
            element.get("data-original"),
            element.get("data-lazy-src"),
        ]

        srcset = element.get(
            "srcset"
        )

        if srcset:
            for part in srcset.split(","):
                raw_values.append(
                    part.strip().split(" ")[0]
                )

        for src in raw_values:
            if not src:
                continue

            src = src.strip()

            if src.startswith(
                "data:"
            ):
                continue

            image_url = urljoin(
                page_url,
                src,
            )
            low = image_url.lower()

            ignored_keywords = [
                "logo",
                "icon",
                "banner",
                "avatar",
                "facebook",
                "youtube",
                "loading",
                "blank",
                "ads",
                "advert",
                "google",
                "tracking",
                "pixel",
                "sprite",
            ]

            if any(
                keyword in low
                for keyword in ignored_keywords
            ):
                continue

            valid_image = (
                ".jpg" in low
                or ".jpeg" in low
                or ".png" in low
                or ".webp" in low
                or "/upload/" in low
            )

            if (
                valid_image
                and image_url
                not in article_images
            ):
                article_images.append(
                    image_url
                )

    return article_images


def classify_source(url):
    """
    Phân loại nguồn primary.

    source_type có thể là:
      HTML_TABLE
      PDF
      IMAGE
      EXTERNAL_DOCUMENT
      UNKNOWN
      ERROR

    Điểm khác bản cũ:
    - nhận direct PDF bằng Content-Type / magic bytes;
    - nhận direct image;
    - bảng không bắt buộc có major_code mới được coi là candidate;
    - hỗ trợ mã CTĐT / mã chương trình 2026.
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=25,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return {
            "source_type": "ERROR",
            "detail": str(error),
        }

    content_type = clean_text(
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if (
        "application/pdf"
        in content_type
        or response.content[:5]
        == b"%PDF-"
    ):
        return {
            "source_type": "PDF",
            "detail": [
                response.url
            ],
        }

    if content_type.startswith(
        "image/"
    ):
        return {
            "source_type": "IMAGE",
            "detail": [
                response.url
            ],
        }

    html = response.text
    soup = BeautifulSoup(
        html,
        "lxml",
    )

    try:
        tables = pd.read_html(
            StringIO(html),
            header=None,
            thousands=None,
        )
    except ValueError:
        tables = []
    except Exception:
        tables = []

    admission_tables = []

    for index, table in enumerate(
        tables
    ):
        signals = table_signals(
            table
        )

        if signals[
            "is_candidate"
        ]:
            admission_tables.append(
                {
                    "index": index,
                    "has_major_code":
                        signals[
                            "has_major_code"
                        ],
                }
            )

    if admission_tables:
        return {
            "source_type":
                "HTML_TABLE",
            "detail": (
                "Bảng candidate: "
                + str(
                    admission_tables
                )
            ),
        }

    pdf_links = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = urljoin(
            response.url,
            anchor["href"],
        )
        low = href.lower()

        if (
            low.endswith(".pdf")
            or ".pdf?" in low
        ):
            if href not in pdf_links:
                pdf_links.append(
                    href
                )

    if pdf_links:
        return {
            "source_type": "PDF",
            "detail": pdf_links,
        }

    external_documents = []

    for tag in soup.find_all(
        ["a", "iframe", "embed", "object"]
    ):
        raw = (
            tag.get("href")
            or tag.get("src")
            or tag.get("data")
        )

        if not raw:
            continue

        href = urljoin(
            response.url,
            raw,
        )
        low = href.lower()

        if (
            "drive.google.com"
            in low
            or "docs.google.com"
            in low
        ):
            if (
                href
                not in external_documents
            ):
                external_documents.append(
                    href
                )

    if external_documents:
        return {
            "source_type":
                "EXTERNAL_DOCUMENT",
            "detail":
                external_documents,
        }

    article_images = find_article_images(
        soup,
        response.url,
    )

    if article_images:
        return {
            "source_type": "IMAGE",
            "detail": article_images,
        }

    return {
        "source_type": "UNKNOWN",
        "detail": (
            "Không phát hiện bảng điểm chuẩn candidate, "
            "PDF, Google Drive/Docs hoặc ảnh bài viết."
        ),
    }
