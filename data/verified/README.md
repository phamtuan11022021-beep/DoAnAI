# Metadata đã đối chiếu ngày 29/10/2026

`program_metadata.csv` chỉ sửa tên ngành do OCR và bổ sung tổ hợp còn thiếu; không chứa và không thay đổi điểm chuẩn. Khóa sửa là tên trường + năm + mã chương trình. Không áp dụng tổ hợp năm 2026 cho năm khác hoặc cho mã chương trình khác.

Đã đọc trực tiếp ảnh bảng tổ hợp 2026 cập nhật 01/07 trên trang chính thức: https://tuyensinh.dut.udn.vn/xet-kq-thi-tot-nghiep-thpt . Bản ảnh lưu ở `data/raw/verified_udn/dut_combinations_2026_1.jpg`. Tám dòng đầu được đối chiếu đầy đủ; dòng thứ chín bị cắt trong ảnh nên chưa dùng. Mã 7480201TN không có trong phần bảng đã đọc, vẫn giữ tình trạng chưa xác minh tổ hợp.

Nguồn điểm chuẩn 2026 hiện có được giữ nguyên. PDF tại thông báo https://tuyensinh.dut.udn.vn/bai-viet-tuyen-sinh/26 bị chủ sở hữu Google Drive chặn tải; phản hồi HTML được giữ với đuôi `.download_denied.html`, không coi là PDF và không dùng làm bằng chứng điểm.

Địa điểm bổ sung trong `data/dataset/university_locations.csv`: Duy Tân theo https://duytan.edu.vn/ContactUs ; cơ sở chính Đông Á theo https://donga.edu.vn/gioi-thieu . Trường có phân hiệu khác không được coi là cùng địa điểm cho mọi chương trình; cần tiếp tục kiểm chứng campus khi thêm dữ liệu.

Lượt cào mở rộng bổ sung địa điểm các đơn vị thành viên ĐH Đà Nẵng theo https://www.udn.vn/ , ghi riêng trong `danang_locations.csv`. Quy tắc `data/dataset/program_location_rules.csv` đưa mã chương trình Đông Á hậu tố DL về Đắk Lắk, ghi đè metadata trụ sở chính. Đã đối chiếu nhóm mã ở https://donga.edu.vn/tin-tuc/ttsk-chi-tiet/Dai-hoc-Dong-A-thong-bao-tuyen-sinh-bac-dai-hoc-chinh-quy-nam-2026-42971 và thông báo 2024 tại https://daklak.donga.edu.vn/chi-tiet/Thong-bao-tuyen-sinh-Dai-hoc-chinh-quy-nam-2024-36136 .
