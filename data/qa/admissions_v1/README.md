# Bộ hỏi–đáp UniConnect AI v1

Bộ mẫu dành cho **hỏi đáp tuyển sinh từ dữ liệu dự án**, không phải hỏi đáp về mã
nguồn. Mục tiêu là dạy trợ lý đọc kết quả tra cứu, trả lời tiếng Việt, giữ ngữ cảnh
và nói rõ khi chưa đủ thông tin. Model không cần học thuộc điểm chuẩn.

## Nội dung

Có **250 mẫu**, trong đó 210 mẫu dựa trên dữ liệu của **30 trường**, 35 tình huống
hành vi và 5 hội thoại thay đổi hồ sơ. Mỗi dòng JSONL là một mẫu hội thoại hoàn chỉnh;
mẫu nhiều lượt không bị tách thành các tập khác nhau.

| Nội dung | Số mẫu |
|---|---:|
| Tra điểm lịch sử | 60 |
| So sánh hai mốc điểm của một ngành | 30 |
| Tra tổ hợp và giới hạn xác minh tổ hợp | 30 |
| Dự đoán điểm 2027 | 30 |
| Hỏi tiếp về trường/ngành vừa nhắc | 30 |
| Không cam kết đỗ từ điểm dự đoán | 30 |
| Thiếu hồ sơ, sai thang điểm, thiếu dữ liệu, thông tin ngoài phạm vi… | 35 |
| Đổi điểm, ngành, tổ hợp, khu vực trong hội thoại | 5 |

## Các file

| File | Mục đích |
|---|---|
| `review.csv` | Mở bằng Excel để duyệt câu hỏi, đáp án, bằng chứng và nguồn; UTF-8 BOM |
| `EXAMPLES.md` | Đọc nhanh một số mẫu, có cả hội thoại nhiều lượt |
| `all_records.jsonl` | Bản đầy đủ: mã mẫu, nhóm, tập, nguồn, evidence và messages |
| `train.jsonl` | 196 mẫu huấn luyện, mỗi dòng chỉ chứa trường `messages` |
| `validation.jsonl` | 24 mẫu chọn cấu hình/so sánh phiên bản trong quá trình phát triển |
| `test.jsonl` | 30 mẫu kiểm tra cuối cùng, không đưa vào huấn luyện |
| `report.json` | Thống kê, kết quả kiểm tra và SHA-256 của CSV nguồn |

Phân chia theo **trường** đối với mẫu có số liệu: toàn bộ câu hỏi về một trường
nằm trong cùng một tập. Mẫu hành vi chia theo tình huống; cả 5 mẫu sửa hồ sơ được
giữ chung một nhóm ở tập test. Tỷ lệ gần 80/10/10 vì chia theo nhóm, không theo dòng.
Các tập vẫn dùng chung một số khuôn câu; đây chưa phải benchmark độc lập về mọi
cách diễn đạt ngoài thực tế.

## Định dạng đầu vào

```json
{"messages":[{"role":"system","content":"Chỉ dùng số liệu trong EVIDENCE..."},{"role":"user","content":"Câu hỏi của người dùng\nEVIDENCE:\n{...kết quả tra cứu...}"},{"role":"assistant","content":"Câu trả lời mẫu"}]}
```

`EVIDENCE` do backend cung cấp; người dùng không phải tự nhập phần này. Dạng này
tương ứng với bước sinh câu trả lời hiện có trong `backend/ai_chat/service.py`.
Đây là dữ liệu cho **bước trả lời**, chưa phải bộ huấn luyện bước chọn intent/trích
xuất hồ sơ JSON. Schema evidence ở đây gọn hơn schema cards của backend; trước khi
huấn luyện thực tế nên đánh giá thêm trên payload backend thật.

Khi đánh giá, lấy `messages` trừ tin nhắn assistant cuối cùng làm đầu vào;
tin nhắn cuối là đáp án tham chiếu. Không gửi đáp án tham chiếu cho model rồi chấm.
Chấm theo dữ kiện và ý nghĩa, không bắt buộc câu trả lời phải giống từng chữ.

## Nguồn và mức độ kiểm tra

- Lịch sử: `data/dataset/admission_scores_2023_2026_program_year.csv`.
- Dự đoán: `data/dataset/predicted_cutoff_2027.csv`.
- Không đọc các file `ambiguous` hoặc `quarantine` để tạo câu trả lời.
- Loại dòng có ghi chú OCR, tên ngành ngoài danh sách tên đã chọn, danh sách tổ hợp
  quá rộng (>10) và điểm ngoài 10–30. Mỗi chương trình phải có ít nhất hai dòng đạt
  bộ lọc. Vì vậy đây là mẫu có chọn lọc, không đại diện đầy đủ mọi ngành/trường.
- `sources.csv_record` là số thứ tự bản ghi CSV, bắt đầu từ 1 sau header; không phải
  số dòng vật lý nếu một trường CSV chứa xuống dòng.
- Nguồn lịch sử có URL gốc trong bằng chứng. Nguồn dự đoán là file mô hình sinh ra;
  không được xem đó là thông báo điểm chuẩn chính thức.

Đã kiểm tra tự động số liệu so với CSV, phép trừ điểm, trùng mẫu, JSON, vai trò hội
thoại và nhóm giữa các tập. **Chưa xác minh lại website nguồn hoặc có chuyên gia
tuyển sinh duyệt từng mẫu.** Trạng thái `source_checked_not_human_reviewed` thể hiện
điều này; chưa gọi đây là bộ gold đã được chuyên gia xác nhận. Một CSV đã làm sạch
vẫn có thể chứa lỗi nghiệp vụ, nên số liệu cần được duyệt trước khi dùng chính thức.

## Tạo lại và kiểm tra

Từ thư mục gốc dự án:

```powershell
.\.venv\Scripts\python.exe -X utf8 ai/build_qa_dataset.py --check
# Chỉ chạy dòng dưới khi muốn tạo lại và ghi đè các file sinh tự động:
.\.venv\Scripts\python.exe -X utf8 ai/build_qa_dataset.py
```

Script dùng thư viện chuẩn Python, không gọi Ollama, không cần GPU hoặc Internet.
Chỉnh câu mẫu và bộ lọc trong `ai/build_qa_dataset.py` rồi tạo lại. Sửa trực tiếp
`review.csv` không tự cập nhật JSONL và sẽ bị ghi đè khi tạo lại.

## Cách duyệt trước khi huấn luyện

1. Kiểm tra trường, mã ngành, năm, phương thức và điểm theo nguồn; loại mẫu mâu thuẫn.
2. Kiểm tra đáp án không biến dự đoán thành sự thật, không tự xác nhận tổ hợp chưa rõ
   hoặc cam kết trúng tuyển.
3. Kiểm tra câu hỏi thiếu dữ liệu có yêu cầu bổ sung đúng thông tin còn thiếu.
4. Bổ sung câu hỏi thực tế đã ẩn danh, cách viết tắt/sai chính tả và kết quả tư vấn
   từ Recommendation Engine; giữ các biến thể của cùng tình huống trong một nhóm.
5. Giữ test riêng và kiểm tra khả năng trả lời từ evidence mới, không chỉ nhớ đáp án.

Bộ v1 là điểm khởi đầu có thể kiểm tra được, chưa đủ để khẳng định fine-tune sẽ tốt
hơn model gốc. Chưa chạy huấn luyện và chưa thay đổi model đang phục vụ chatbot.
