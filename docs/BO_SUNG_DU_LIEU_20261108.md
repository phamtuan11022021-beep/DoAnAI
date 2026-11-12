# Bổ sung dữ liệu tuyển sinh ngày 08/11/2026

Đã nhập thêm **8 bản ghi ngành–năm THPT**, tăng dữ liệu sạch từ **18.738 lên 18.746**. Đã bổ sung **148 dòng điểm theo phương thức từ nguồn chính thức**, tăng tập tra cứu riêng từ **259 lên 407**. Hai con số này thuộc hai tập dữ liệu khác nhau, không cộng lại thành số ngành mới.

## Nguồn và kết quả

| Nguồn | Dữ liệu đã xác minh | Cách sử dụng |
|---|---|---|
| [Vinh 2026, quyết định 706](https://vuted.edu.vn/tin-tuc-17/cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026-dot-3753) | 14 ngành × 3 phương thức = 42 dòng | Đọc đúng cột PT100 ở giữa bảng. 6 ngành đã có, bổ sung 8 ngành THPT còn thiếu. Lưu riêng học bạ và ĐGNL. |
| [Vinh 2025, quyết định 726](https://vuted.edu.vn/Resources/Document/2025/8/2025-qd-diem-tt-dh-d1.pdf) | 14 ngành × 3 phương thức = 42 dòng | Cột PT100 nằm đầu nhóm điểm, khác thứ tự năm 2026. Lưu vào bảng tra cứu theo phương thức. |
| [TUEBA 2025](https://tuyensinh.tueba.edu.vn/bai-viet/Thong-Bao-Diem-Trung-Tuyen-Dai-Hoc-Chinh-Quy-Nam-2025-Dot-1-111.html) | 21 mã xét tuyển | Điểm quy đổi, gồm điểm cộng/ưu tiên theo chú thích. Chỉ tra cứu, không đưa vào huấn luyện THPT thuần. Giữ mã có hậu tố tiếng Anh, Hà Giang. |
| [TUEBA 2026](https://tuyensinh.tueba.edu.vn/bai-viet/Thong-Bao-Diem-Chuan-Trung-Tuyen-Dai-Hoc-Chinh-Quy-Dot-1-Nam-2026-151.html) | 29 mã xét tuyển | Điểm quy đổi chung giữa phương thức và tổ hợp. Chỉ tra cứu, giữ riêng các chương trình và phân hiệu. |
| [UIT 2025](https://tuyensinh.uit.edu.vn/node/4147) | 14 ngành THPT | Bổ sung nguồn tra cứu chính thức; không tính là 14 ngành mới trong dữ liệu huấn luyện. Mã Thiết kế vi mạch giữ đúng `75202A1` trên ảnh thông báo. |

Quyết định Vinh 2026 ghi rõ việc đổi tên từ **Đại học Sư phạm Kỹ thuật Vinh** thành **Đại học Công nghệ Kỹ thuật Vinh**. Dữ liệu bổ sung dùng danh tính trường đã có để nối lịch sử; không tạo thêm một trường riêng vì đổi tên.

Đã bổ sung địa chỉ trường Vinh từ chân trang thông báo chính thức: **117 - Nguyễn Viết Xuân - Phường Trường Vinh – Tỉnh Nghệ An**. Tập vị trí tăng từ 49 lên **50** dòng, giúp AI lọc trường này theo Nghệ An.

## Tám ngành THPT được bổ sung năm 2026

| Mã ngành | Ngành | Điểm |
|---|---|---:|
| 7140246 | Sư phạm công nghệ | 20,00 |
| 7510201 | Công nghệ kỹ thuật cơ khí | 18,20 |
| 7510202 | Công nghệ chế tạo máy | 16,20 |
| 7510203 | Công nghệ kỹ thuật cơ điện tử | 19,20 |
| 7510205 | Công nghệ kỹ thuật ô tô | 20,00 |
| 7510206 | Công nghệ kỹ thuật nhiệt | 17,00 |
| 7510301 | Công nghệ kỹ thuật điện, điện tử | 21,50 |
| 7510303 | Công nghệ kỹ thuật điều khiển và tự động hóa | 22,50 |

Tổ hợp được lấy từ phụ lục theo nhóm ngành. Điểm học bạ/ĐGNL không được chép sang cột THPT. Không tự chia điểm quy đổi để tạo điểm THPT.

## Lưu nguồn và kiểm tra

- Bản nguồn: `data/raw/recovery_20261108/`, kèm `manifest.json`, URL, trạng thái tải và SHA-256.
- Trình nhập: `scraper/import_recovery_nov08.py`. Chạy không có `--apply` để xem trước; `--apply` sao lưu trước khi nhập. PDF/ảnh đã đọc trực quan được khóa bằng SHA-256; nguồn thay đổi phải kiểm tra lại.
- Kiểm tra tự động: `scraper/test_recovery_nov08.py`, gồm thứ tự cột, điểm/mã/năm/tổ hợp bị sửa, tệp nguồn bị thay đổi và phân biệt phân hiệu/phương thức.
- Đối chiếu trước–sau: `docs/DATA_RECOVERY_CHECK_20261108.json`. Không mất bản ghi cũ, không đổi điểm của bản ghi cũ.
- Sao lưu trước nhập: `backups/recovery_20261108T012533Z/`.

Kết quả kiểm tra sau nhập:

- 5 kiểm thử bộ nhập mới, 5 kiểm thử bộ đọc nguồn cũ và 4 kiểm thử catalog đều đạt.
- Kiểm toán toàn bộ bằng chứng API lưu trên máy: **0 lỗi**; các dòng THPT mới được kiểm tra riêng bằng bộ đọc nguồn khóa SHA-256.
- Bộ QA 250 câu đã tạo lại và kiểm tra nguồn, phép tính, phân chia tập, tệp xuất; đây là kiểm tra tính nhất quán dữ liệu, không phải đánh giá 250 câu trả lời thực tế của Gemini.
- Đã huấn luyện lại và tạo dự đoán 2027 cho **7.517 chương trình**. Tập kiểm định 2026 có **3.776** mẫu; phương pháp được chọn để phục vụ vẫn là `Baseline_LastScore`, MAE khoảng **1,2280 điểm**. Không coi thay đổi chỉ số trên tập kiểm định mở rộng là bằng chứng mô hình tốt hơn.
- Kiểm tra trực tiếp dịch vụ tư vấn với mã `7510303`, tổ hợp `A00`, khu vực `Nghệ An`: ngành mới của Vinh xuất hiện trong kết quả chính, tổ hợp đã xác minh. Chi tiết: `docs/RECOVERY_API_CHECK_20261108.json`.

## Phần chưa thể coi là hoàn chỉnh

Đây là một đợt bổ sung có kiểm chứng, chưa phải dữ liệu đầy đủ toàn quốc. Danh sách `data/dataset/recovery_school_year_gaps.csv` dựa trên tên trường trong danh mục nguồn; tên viết tắt/đổi tên có thể tạo khoảng trống giả, nên không lấy số dòng thiếu làm số trường thực sự chưa có dữ liệu.

UFBA 2025 chưa tải thành công tệp quyết định; không suy đoán điểm. Vinh 2023 chưa tìm được nguồn chính thức đủ điều kiện trong đợt này. Những trường chỉ có phương thức tổng hợp, thang 40/90/100 hoặc thông báo điểm sàn cần được xử lý riêng.

Bảng lịch sử UIT và dữ liệu cũ có một số cách ghi mã khác nhau (ví dụ Khoa học dữ liệu, Việt–Nhật, Thiết kế vi mạch). Đã lưu bảng lịch sử để đối chiếu; chưa tự gộp hoặc sửa mã các năm cũ chỉ vì tên ngành giống nhau.
