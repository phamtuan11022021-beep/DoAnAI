# Sử dụng trang quản trị UniConnect AI

Đã bổ sung mục **Dữ liệu tuyển sinh**: nhập CSV, xem trước, đối chiếu nguồn,
công bố và thu hồi từng đợt. Hướng dẫn tại [Quản lý dữ liệu tuyển sinh](QUAN_LY_DU_LIEU_TUYEN_SINH.md).

Giao diện cập nhật ngày 06/11/2026, tập trung vào công việc thường dùng.
Đăng nhập qua form của trang chính bằng tài khoản có quyền quản trị để vào Admin.

## Các mục chính

| Mục | Dùng khi nào? | Cách thực hiện |
|---|---|---|
| Tổng quan | Xem hoạt động chung | Xem tổng số, số mới trong 7 ngày hoặc chọn một lối tắt công việc. |
| Thành viên | Tìm tài khoản, đổi thông tin hoặc trạng thái hoạt động | Tìm bằng tên/email, mở thành viên, cập nhật thông tin rồi bấm Lưu. Bỏ chọn Đang hoạt động để khóa tài khoản. |
| Hồ sơ & mentor | Kiểm tra mục tiêu học tập, đổi vai trò mentor | Tìm thành viên, mở hồ sơ, đổi Vai trò hoặc mục tiêu học tập và bấm Lưu. |
| Bài viết | Kiểm duyệt nội dung cộng đồng | Tìm theo nội dung, tác giả hoặc hashtag; dùng bộ lọc; mở bài để xem ảnh, chỉnh nội dung/chuyên mục. |
| Bình luận | Kiểm tra bình luận | Tìm nội dung hoặc người viết, mở để xem bài liên quan và chỉnh sửa nếu có quyền. |
| Tư vấn AI | Đọc lại trao đổi với trợ lý | Tìm và mở cuộc tư vấn; nội dung hiển thị theo người hỏi và trợ lý, ở chế độ chỉ xem. |
| Hướng nghiệp | Xem kết quả trắc nghiệm | Mở kết quả để xem nhóm tính cách, điểm từng nhóm và ngành gợi ý. |

Trang chỉ hiển thị các mục tài khoản có quyền truy cập. Mentor không tự động
trở thành quản trị viên; vai trò mentor và quyền vào trang quản trị là hai việc riêng.

## Xóa bài hoặc bình luận

Mở nội dung cần xóa, bấm Xóa và kiểm tra màn hình xác nhận trước khi thực hiện.
Khi xử lý nhiều mục, đánh dấu các dòng, chọn **Xóa các mục đã chọn**, rồi thực
hiện bước xác nhận. Xóa bài có thể xóa các bình luận và tương tác liên quan;
ảnh đính kèm được dọn sau khi thao tác xóa bài thành công.

## Phân quyền và tài khoản quản trị

Mở **Cài đặt nâng cao → Phân quyền** để xem các nhóm. Quyền quản trị của từng
thành viên nằm trong phần **Quyền quản trị · Nâng cao** ở trang chi tiết tài khoản,
dành cho superuser. Hai nhóm có sẵn là Kiểm duyệt cộng đồng và Theo dõi tư vấn.
Người được giao quản lý thành viên thông thường không được tự cấp thêm quyền
quản trị hoặc sửa tài khoản quản trị cấp cao.

Tạo hoặc khôi phục hai nhóm quyền bằng `manage.py setup_admin_roles`; lệnh không
tự gán người dùng vào nhóm. Tạo quản trị mới bằng `manage.py createsuperuser`;
nếu cần đổi mật khẩu từ terminal, dùng `manage.py changepassword TEN_DANG_NHAP`.
Chạy các lệnh qua `.venv/Scripts/python.exe backend/manage.py` từ gốc dự án.
Không có mật khẩu quản trị cố định trong mã nguồn.

## Trên điện thoại

Bấm **Menu quản trị** ở đầu trang để chuyển mục. Danh sách nhiều cột có thể
cuộn ngang trong vùng bảng. Bấm biểu tượng tài khoản ở góc trên để đổi mật khẩu
hoặc đăng xuất; bấm Xem trang web để trở lại giao diện chính.

Các bảng lượt thích, bài đã lưu, phiếu bình chọn, trường đã lưu và dữ liệu kỹ
thuật vẫn tồn tại trong database nhưng được đưa khỏi menu chính. Báo cáo độ
phủ dữ liệu và JSON không còn xuất hiện trên trang tổng quan.
