# Rà soát trước khi nộp bài — 08/11/2026

## Kết luận

**Về phần mềm, có thể chốt bản hiện tại để nộp đồ án và demo theo phạm vi chức năng đã xây dựng.** Các kiểm tra chạy trong đợt này đều đạt; không phát hiện lỗi chặn trong các luồng đã kiểm tra. Chưa có đề cương/rubric nghiệm thu của giảng viên để kết luận đủ mọi tiêu chí chấm điểm. Không cần thêm nhiều chức năng trước khi nộp; nên tập trung báo cáo, slide và tập dượt demo.

Đánh giá này dựa trên cấu trúc mã nguồn frontend/backend/AI/crawler, cấu hình, migrations, tài liệu, dữ liệu, kiểm thử và luồng trình duyệt bên dưới. Không phải cam kết mọi đường đi của ứng dụng đã được thử hoặc hệ thống đã nghiệm thu vận hành công khai.

## Bằng chứng kiểm tra thực tế

| Phần | Kết quả mới nhất |
|---|---|
| Backend | 83 kiểm thử đạt với database kiểm thử, gồm tài khoản, cộng đồng, AI, giới hạn yêu cầu, vận hành và admin dữ liệu. Có truyền nhãn connections/career nhưng hai app này chưa có bộ kiểm thử riêng. |
| Frontend | `npm.cmd run build` đạt, tạo bản Vite build. |
| Trình duyệt | `social.ui_checks`: 1 kịch bản tích hợp đạt; tư vấn trường, cập nhật ảnh hồ sơ, đăng/sửa/xóa bài có ảnh và bình chọn, gửi tin nhắn; kiểm tra màn hình 1440px và 390px, không phát hiện lỗi JavaScript hay cuộn ngang ngoài màn hình điện thoại trong kịch bản. |
| MySQL | Kết nối thật thành công, 27 bảng; không có migration chưa áp dụng và không có thay đổi model thiếu migration. |
| API đọc | Health, danh sách trường, câu hỏi hướng nghiệp và gợi ý kết nối đều trả HTTP 200 qua Django test client với cấu hình/database hiện tại. |
| Bộ cào | 20 kiểm thử đạt, gồm kiểm tra nguồn, năm, mã ngành, phương thức, cột điểm và thang điểm. |
| QA | 250 bản ghi qua kiểm tra nguồn, bằng chứng, phép tính và phân chia tập. Đây là kiểm tra tính nhất quán, không phải 250 câu hội thoại Gemini đã được chấm. |
| AI tra điểm | 4/4 trường hợp tra cứu có mục tiêu đạt: Tân Tạo CNTT, UET Vật lý kỹ thuật, UET Cơ kỹ thuật, CMC CNTT. Chạy chế độ backend, không gọi Gemini trong đợt rà soát này. |
| Khóa API trong mã | Quét mẫu định dạng khóa Google/OpenAI trong mã nguồn và tài liệu hoạt động không phát hiện khóa; không đọc/chép giá trị `.env` vào báo cáo. Đây không phải kiểm toán bảo mật toàn diện. |

Lệnh chính đã chạy:

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py test accounts social connections career ai_api ai_chat config catalog --noinput
.venv/Scripts/python.exe -X utf8 backend/manage.py test social.ui_checks --noinput
.venv/Scripts/python.exe -X utf8 -m unittest discover -s scraper -p test_*.py
.venv/Scripts/python.exe -X utf8 backend/manage.py check
.venv/Scripts/python.exe -X utf8 backend/manage.py migrate --check
.venv/Scripts/python.exe -X utf8 backend/manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe -X utf8 ai/build_qa_dataset.py --check
.venv/Scripts/python.exe -X utf8 backend/manage.py evaluate_admissions
# Chạy trong frontend:
npm.cmd run build
```

Ảnh kiểm thử hiện tại nằm ở `docs/ui_review_campus/`. Dữ liệu người dùng/bài viết/ảnh của kịch bản trình duyệt được tạo trong database kiểm thử và thư mục tạm, không thêm vào MySQL nghiệp vụ đang dùng.

## Phạm vi có thể trình bày khi bảo vệ

- Đăng ký/đăng nhập, hồ sơ; tài khoản quản trị dùng chung form đăng nhập và được phân luồng theo quyền.
- Tra trường/ngành/điểm theo năm; lưu trường, so sánh trường, trắc nghiệm định hướng RIASEC.
- Tư vấn theo điểm, tổ hợp, ngành và khu vực có dữ liệu xác minh; hội thoại kết hợp truy xuất bằng chứng và Gemini, có chế độ tra cứu khi nhà cung cấp lỗi.
- Cộng đồng, ảnh, bình luận, bình chọn, theo dõi, thông báo và tin nhắn; phân quyền phía backend.
- Admin đã tùy biến; nhập CSV tuyển sinh, xem trước, duyệt, công bố và thu hồi dữ liệu.
- Pipeline cào/chuẩn hóa/cách ly xung đột; mô hình dự đoán, đánh giá theo thời gian và quản lý nguồn.

Kiến trúc dữ liệu cần giải thích đúng: **MySQL lưu tài khoản và nghiệp vụ; điểm tuyển sinh chuẩn hóa và dự đoán được phục vụ từ CSV**. Dữ liệu nhập từ admin lưu ở MySQL và được ghép vào phần tra cứu chính thức. Không mô tả toàn bộ điểm đã chuyển hết vào bảng MySQL.

## Những giới hạn cần nói rõ

1. **Dữ liệu chưa đầy đủ toàn quốc:** 18.746 bản ghi ngành–năm, 266 khóa trường, 7.517 chương trình; 2.406 chương trình đủ bốn năm. Metadata địa điểm có 50 dòng, vì vậy lọc theo khu vực chưa bao phủ mọi trường. 407 dòng điểm theo phương thức là tập tra cứu riêng, không cộng vào số bản ghi ngành–năm sạch.
2. **AI dự đoán có sai số:** phương pháp phục vụ được chọn là `Baseline_LastScore`; MAE khoảng 1,2280 điểm trên 3.776 mẫu năm 2026. RandomForest được huấn luyện nhưng chưa tốt hơn baseline về chỉ số này. Điểm 2027 là dự đoán; các mức tư vấn không phải xác suất đỗ.
3. **Hội thoại phụ thuộc dịch vụ:** chưa đánh giá lại Gemini trực tiếp trong đợt này. Quota, mạng hoặc nhà cung cấp có thể làm chế độ tra cứu được dùng thay thế. Không gọi đây là chatbot đã fine-tune chỉ vì có bộ QA 250 mẫu.
4. **Email:** chức năng quên mật khẩu có sẵn, nhưng gửi thư thật cần SMTP. Chưa có bằng chứng gửi/nhận thư thật trong đợt rà soát này.
5. **Triển khai:** `check --deploy` trên cấu hình phát triển hiện tại báo 6 cảnh báo về DEBUG, secret và HTTPS/cookie/HSTS. Đã có module `config.production` và hướng dẫn triển khai; chưa kiểm tra một hosting/tên miền HTTPS đang vận hành. Không đổi cấu hình localhost sang HTTPS chỉ để xóa cảnh báo.
6. **Hồ sơ nộp:** chưa tìm thấy báo cáo Word/PDF hoặc slide PowerPoint trong cây tài liệu/mã nguồn hoạt động đã kiểm tra. Có thể bạn đang lưu ngoài dự án; cần đối chiếu quy định của khoa và giảng viên.

## Kịch bản demo khoảng 8–10 phút

1. Khởi động MySQL, backend và frontend theo README; xác nhận trang chính tải được.
2. Đăng nhập thành viên, cập nhật hồ sơ; tìm trường/ngành và xem điểm theo năm cùng nguồn.
3. Thử hồ sơ có bằng chứng mới: 23 điểm, A00, mã `7510303`, Nghệ An; xem ngành Điều khiển và tự động hóa của trường Vinh, phân biệt điểm 2026 với dự đoán 2027.
4. So sánh/lưu trường; làm trắc nghiệm hướng nghiệp và mở lại kết quả.
5. Đăng bài, bình luận hoặc bình chọn; dùng hai tài khoản để minh họa kết nối/tin nhắn.
6. Đăng nhập quản trị qua form chung; xem thành viên, kiểm duyệt bài và trình bày quy trình duyệt dữ liệu CSV.
7. Hỏi AI một câu có nguồn đã kiểm tra; trình bày kết quả tra cứu và nguồn, giải thích trạng thái khi dịch vụ AI không sẵn sàng.
8. Kết thúc bằng kiến trúc, thống kê dữ liệu, cách chia tập theo thời gian, sai số và hướng phát triển.

## Chuẩn bị bản nộp

- Chốt báo cáo, slide, sơ đồ kiến trúc và ERD; tài liệu bảng MySQL ở `GIAI_THICH_CAC_BANG_MYSQL.md` có thể dùng để dựng ERD.
- Kèm README, mã nguồn, migrations, `package-lock.json`, requirements, `.env.example`, dữ liệu phục vụ trong `data/dataset/`, mô hình và tài liệu cần thiết.
- Nếu cần tái lập crawler/kiểm thử bằng chứng, kèm dữ liệu nguồn tương ứng trong `data/raw/` và `data/processed/` hoặc bàn giao bằng gói dữ liệu riêng. Không xóa bằng chứng nguồn chỉ để giảm kích thước.
- Không đưa `.env`, `.venv`, `frontend/node_modules`, cache Python, bản sao lưu có người dùng hoặc database cá nhân vào gói mã nguồn nộp/chia sẻ. Máy chấm tự cài dependency; MySQL khởi tạo bằng migrations và `createsuperuser`.
- `frontend/dist` là đầu ra build có thể tạo lại; đã giữ bản build mới tại máy để chạy kiểm tra. `archive/` là mã/dữ liệu lịch sử, `backups/` là bản phục hồi; hai thư mục này không cần nằm trong gói mã nguồn thông thường.
- Xác nhận thầy/cô yêu cầu dump SQL, video demo hay triển khai online. Chỉ thêm các mục đó theo yêu cầu thực tế.

## Dọn dự án

Đã phân loại các thư mục lớn trước khi xử lý. Chỉ dọn cache Python có thể tạo lại trong `ai/`, `backend/`, `scraper/`; nhật ký tên tệp/số lượng/dung lượng nằm ở `CLEANUP_20261108.json`. Bổ sung quy tắc bỏ qua output build, cache và tệp hệ điều hành trong `.gitignore`.

Các bản sao lưu, dữ liệu nguồn, CSV, mô hình, migrations, media, môi trường chạy và database SQLite cũ được giữ vì không có đủ căn cứ xem chúng là tệp rác. Database SQLite vẫn là đường chạy dự phòng được mã cấu hình hỗ trợ.

Các báo cáo ngày trước mô tả trạng thái tại thời điểm viết; bản rà soát này là mốc đánh giá mới nhất cho lần nộp hiện tại.
