"""
Entry point mô tả phạm vi scraper của đồ án.

Không chạy lại các pipeline đã LOCK từ đây.
Mỗi năm vẫn có một production pipeline riêng để tránh vô tình sửa dữ liệu cũ.
"""

PROJECT_YEARS = (
    2023,
    2024,
    2025,
    2026,
)

LOCKED_YEARS = (
    2023,
    2024,
    2025,
)

ACTIVE_YEAR = 2026


def main():
    print("UniConnect AI - Admission score scraper")
    print("Phạm vi dữ liệu :", PROJECT_YEARS)
    print("Đã khóa        :", LOCKED_YEARS)
    print("Đang xử lý     :", ACTIVE_YEAR)
    print()
    print(
        "Chạy pipeline năm hiện tại bằng:"
    )
    print(
        "  python .\\scraper\\run_2026_pipeline.py"
    )


if __name__ == "__main__":
    main()