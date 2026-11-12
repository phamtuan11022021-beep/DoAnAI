# Nhập và duyệt dữ liệu tuyển sinh

Đăng nhập tài khoản quản trị như bình thường, mở **Dữ liệu tuyển sinh**.
Đây là quản lý các đợt dữ liệu có nguồn, tách khỏi quản lý bài viết/thành viên.

Hướng dẫn này gồm hai luồng: nhập từng đợt qua admin và cập nhật tập dữ liệu
ngoại tuyến. Công bố dữ liệu từ admin không tự chạy lại crawler hoặc huấn luyện.

## Quy trình sử dụng

1. Bấm **Xem trường còn thiếu dữ liệu**, chọn năm cần bổ sung. Bảng thể hiện
   khoảng trống của tập THPT sạch, không khẳng định trường không tuyển sinh.
2. Mở **Tải danh mục tên và khóa trường** để lấy đúng danh tính trường.
3. Chọn **Thêm đợt dữ liệu tuyển sinh**, tải tệp mẫu, điền điểm đã kiểm tra và
   chọn tệp CSV UTF-8. Mỗi đợt tối đa 1.000 dòng, 1 MB.
4. Đặt tên đợt dễ nhớ và bấm **Lưu**. Tệp được kiểm tra trước khi nhận. Dữ liệu
   lúc này ở trạng thái **Chờ đối chiếu**, chưa xuất hiện khi tra cứu.
5. Mở đợt đã lưu, xem thông tin và mở **Đối chiếu nguồn**. Kiểm tra đúng năm,
   ngành, mã, phương thức, thang điểm và điều kiện. Không nhập điểm sàn thành
   điểm chuẩn hoặc lấy điểm học bạ thay THPT. Phần xem trước tối đa 100 dòng;
   với tệp lớn hơn phải kiểm tra toàn bộ tệp nguồn trước khi duyệt.
6. Đánh dấu xác nhận rồi bấm **Công bố dữ liệu đã kiểm tra**. Người duyệt cần
   quyền công bố; quyền xem/nhập chưa đủ để tự công bố.
7. Nếu phát hiện sai, mở đợt đang hiển thị và chọn **Thu hồi đợt dữ liệu này**.
   Các dòng của đợt đó ngừng phục vụ tra cứu. CSV gốc và các đợt khác được giữ.

Nội dung của đợt đã lưu không được sửa trực tiếp. Muốn sửa bản đã công bố,
thu hồi bản sai rồi nhập đợt mới. Bản đã thu hồi và người xử lý vẫn được giữ
làm lịch sử; không có nút xóa vĩnh viễn trong giao diện này.

## Các cột trong tệp

| Cột | Ý nghĩa |
|---|---|
| university_key | Khóa trường lấy nguyên từ danh mục tải xuống |
| university_name | Tên trường khớp với khóa trong danh mục |
| major_code | Mã ngành/chương trình do trường công bố; để trống nếu chưa xác minh |
| major_name | Tên ngành/chương trình chính xác |
| year | Năm tuyển sinh; từ 2023 đến năm hiện tại |
| cutoff_score | Điểm trường công bố, số hữu hạn lớn hơn 0; không tự quy đổi |
| admission_method | Ghi rõ phương thức, thang điểm và điều kiện quan trọng |
| source_url | Đường dẫn HTTPS trên tên miền chính thức `.edu.vn` |

Hệ thống không tải URL do người nhập cung cấp. Kiểm tra định dạng và tên miền
không thay thế việc người duyệt mở nguồn để xác nhận. Trường chưa có trong
danh mục cần được xác minh danh tính trước, không tự tạo khóa tương tự.

## Dữ liệu được dùng ở đâu?

Điểm đã công bố được lưu trong MySQL và đọc cùng danh sách điểm công bố riêng
khi tra cứu lịch sử hoặc xem chi tiết trường. Chúng có `comparable_thpt=false`:
chưa tự dùng để huấn luyện, dự đoán hoặc gán mức An toàn/Phù hợp. Muốn đưa vào
tập huấn luyện vẫn cần quy trình kiểm tra bằng chứng, tổ hợp và khả năng so sánh.

Tập huấn luyện, dự đoán tính sẵn và dữ liệu nền hiện vẫn nằm trong CSV. Việc
thu hồi một đợt nhập admin không xóa điểm nền cùng trường/ngành nếu nó đã được
xác minh độc lập từ trước. Hệ thống từ chối công bố đợt chứa bản ghi trùng
trường, mã ngành (hoặc tên khi thiếu mã), năm và phương thức đang hiển thị.

## Phân quyền

Nhóm **Biên tập dữ liệu tuyển sinh** có quyền xem, nhập, duyệt và thu hồi đợt.
Lệnh chuẩn bị nhóm không tự gán quyền cho bất kỳ thành viên nào:

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py setup_admin_roles
```

Superuser chủ động gán nhóm và quyền staff cho người được giao trách nhiệm.
Người chỉ cần theo dõi có thể được cấp riêng quyền xem đợt dữ liệu.

## Cào dữ liệu và tái tạo tập phục vụ

Chạy từ gốc dự án, trong môi trường đã cài `requirements-training.txt`.
Các bước này có thể tải nguồn và ghi lại CSV/mô hình; chỉ chạy chủ động sau khi
lưu bản sao, không chạy cùng một tiến trình cào khác đang ghi vào tập supplement.

```powershell
# Ví dụ cào bổ sung có giới hạn, cần kết nối mạng:
.venv/Scripts/python.exe -X utf8 scraper/scrape_missing_2025_2026.py --years 2025 2026 --limit 20
# Chuẩn hóa và kiểm tra nguồn trước khi huấn luyện:
.venv/Scripts/python.exe -X utf8 ai/prepare_dataset_4years_FINAL.py
.venv/Scripts/python.exe -X utf8 scraper/audit_recovery.py
.venv/Scripts/python.exe -X utf8 ai/train_cutoff_models.py
.venv/Scripts/python.exe -X utf8 ai/audit_data.py
.venv/Scripts/python.exe -X utf8 ai/build_qa_dataset.py
.venv/Scripts/python.exe -X utf8 ai/build_qa_dataset.py --check
```

`--limit 0` xử lý toàn bộ danh sách; `--refresh` thử lại dữ liệu đã có báo cáo.
Chế độ `--api-only --include-index --years 2023 2024 2025 2026` hỗ trợ lấy lịch sử
từ nguồn tổng hợp công khai, có thể thêm `--workers 3 --delay 0.6`. Đây là nguồn
thứ cấp, cần giữ URL và đối chiếu danh tính, năm, phương thức, công thức và thang
điểm; không tự gọi là thông báo chính thức của trường. Dùng `--help` của công cụ
để xem đủ tùy chọn. Không thực hiện quy đổi thang hoặc lấy trung bình điểm xung đột.

Nguồn tải và báo cáo nằm ở `data/raw/`; tập đang phục vụ ở `data/dataset/`.
`coverage_summary.json`, `coverage_by_school_year.csv`,
`recovery_inventory_coverage.csv` và `recovery_school_year_gaps.csv` giúp xác định
độ phủ và phần thiếu. Không suy ra đã đủ toàn quốc chỉ từ danh sách của một nguồn.
Một số tệp `.md` ở nhánh OCR là dữ liệu đọc từ thông báo, bộ cào còn sử dụng
`combined.md`; không xóa chúng như tài liệu ghi chú.

Các công cụ `fetch_official_gaps.py`, `import_official_gaps.py`,
`fetch_completion_sources.py`, `import_completion_ttu.py`, `import_verified_ai2.py`
và `import_recovery_nov08.py` giữ khả năng kiểm tra lại những đợt bổ sung đã có.
Xem trợ giúp hoặc mã công cụ trước khi dùng tùy chọn ghi dữ liệu; các báo cáo
nguồn và JSON kiểm tra vẫn được giữ dù nhật ký Markdown cũ đã được dọn.

Huấn luyện ở đây là hồi quy điểm, không phải fine-tune mô hình hội thoại.
Bộ QA là tập kiểm tra có nguồn và phép tính. Sau khi đổi dataset/metadata,
khởi động lại backend để xóa cache trong tiến trình, rồi kiểm tra tra cứu và tư vấn.
