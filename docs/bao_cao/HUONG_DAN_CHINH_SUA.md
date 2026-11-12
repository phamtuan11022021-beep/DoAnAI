# Sử dụng bản báo cáo chỉnh sửa

Bản hiện tại là **BAO_CAO_UNICONNECT_AI_BAN_CHINH_SUA.docx**. Bản PDF cùng tên dùng để xem và in. Báo cáo có **39 trang, 7 chương, 8 hình và 9 bảng**, khổ A4 dọc thống nhất. Có 7 sơ đồ trọng tâm và 1 ảnh giao diện; phần phân tích bằng chữ được mở rộng theo mã nguồn dự án.

## Những điểm đã thay đổi

- Giảm từ 26 hình xuống 8 hình; bỏ các sơ đồ lặp hoặc quá chi tiết khỏi phần chính.
- Giữ BFD, kiến trúc, luồng hoạt động, ERD, SQL, quy trình cào dữ liệu và chia tập huấn luyện.
- Viết rõ quan hệ giữa MySQL và CSV, trách nhiệm frontend/backend, xử lý ngữ cảnh AI, dữ liệu thiếu, lỗi Gemini và quy trình duyệt dữ liệu.
- Bỏ các lần đổi trang ngang; thống nhất phông chữ, lề, giãn dòng và chú thích. Giữ các bảng ngắn liền trang, mục lục và danh mục hình/bảng được cập nhật bằng Word.
- Danh mục đủ 27 bảng được giữ trong phụ lục; DDL và Mermaid đầy đủ vẫn nằm ở so_do/schema_mysql.sql và so_do/erd_mysql_day_du.mmd.

## Trước khi nộp

1. Điền trường, khoa, học phần, họ tên, MSSV, lớp, giảng viên và địa điểm ở bìa.
2. Đối chiếu mẫu riêng của khoa về bìa, lời cam đoan, cảm ơn, nhận xét và tài liệu tham khảo. Không tự điền chữ ký hoặc nhận xét của giảng viên.
3. Sau khi sửa Word, nhấn Ctrl+A rồi F9 để cập nhật mục lục và số trang, xuất lại PDF và kiểm tra ngắt trang. Số trang có thể thay đổi trên máy khác.
4. Dùng đúng tên **BAN_CHINH_SUA**. Các bản báo cáo cũ và thư mục lịch sử đã được dọn ngày 09/11/2026; nhật ký nằm ở docs/CLEANUP_20261109.json.

## Chỉnh nội dung và tái tạo

Nội dung nguồn nằm trong BAO_CAO_UNICONNECT_AI_BAN_CHINH_SUA.md. Chạy build_report.py để tạo lại Word; công cụ này dùng build_report_compact.py, report_diagrams_compact.py và diagram_canvas.py. Tạo lại sẽ ghi đè chỉnh sửa trực tiếp trong Word, vì vậy hãy lưu bản riêng trước khi chạy. Những công cụ chuyển đổi một lần từ bản cũ đã được bỏ, không ảnh hưởng việc dựng lại từ Markdown hiện tại. verify_report.py kiểm tra cấu trúc Word, PDF và sự nhất quán của tài liệu.

render_report.vbs dùng Microsoft Word để cập nhật mục lục và xuất PDF, nhận lần lượt đường dẫn DOCX và PDF tuyệt đối. Bản đã kiểm tra dùng phương án này vì môi trường không có LibreOffice. Ảnh trang tạm dùng kiểm tra đã được dọn; kết quả kiểm tra được giữ trong KIEM_TRA_BAO_CAO_BAN_CHINH_SUA.json.

Số liệu dữ liệu, mô hình và kiểm thử phản ánh mốc 08/11/2026; cấu trúc MySQL được đối chiếu 09/11/2026. Lần chỉnh báo cáo này không chạy lại toàn bộ kiểm thử ứng dụng, cào dữ liệu hay huấn luyện. Không gọi điểm 2027 là điểm chính thức, bộ QA là chatbot đã fine-tune hoặc trạng thái localhost là nghiệm thu hosting công khai.
