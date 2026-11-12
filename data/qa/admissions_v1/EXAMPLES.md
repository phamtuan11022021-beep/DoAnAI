# Ví dụ hỏi–đáp UniConnect AI

Đây là trích mẫu. Xem `review.csv` để duyệt đầy đủ; số liệu lấy từ dữ liệu nội bộ, chưa xác minh lại website.

## qa-0001 — history

**Hỏi:** Điểm chuẩn ngành Ngôn ngữ Anh (mã 7220201) của Trường ĐH Tây Đô năm 2024 là bao nhiêu?

**Đáp:** Theo dữ liệu nội bộ, ngành Ngôn ngữ Anh (mã 7220201) của Trường ĐH Tây Đô năm 2024 có điểm chuẩn 15. Khi nộp hồ sơ, bạn cần đối chiếu thông báo tuyển sinh của trường.

**Tập dữ liệu:** `train`

## qa-0002 — history

**Hỏi:** Điểm chuẩn ngành Ngôn ngữ Anh (mã 7220201) của Trường ĐH Tây Đô năm 2026 là bao nhiêu?

**Đáp:** Theo dữ liệu nội bộ, ngành Ngôn ngữ Anh (mã 7220201) của Trường ĐH Tây Đô năm 2026 có điểm chuẩn 15. Khi nộp hồ sơ, bạn cần đối chiếu thông báo tuyển sinh của trường.

**Tập dữ liệu:** `train`

## qa-0003 — comparison

**Hỏi:** Điểm ngành Ngôn ngữ Anh, mã 7220201, ở Trường ĐH Tây Đô thay đổi thế nào từ 2024 đến 2026?

**Đáp:** Trong dữ liệu được cung cấp, điểm từ 15 năm 2024 thành 15 năm 2026, không đổi, chênh lệch 0 điểm. Đây là chênh lệch hai mốc, chưa đủ để kết luận xu hướng các năm tiếp theo.

**Tập dữ liệu:** `train`

## qa-0004 — combination

**Hỏi:** Ngành Ngôn ngữ Anh mã 7220201 ở Trường ĐH Tây Đô dùng tổ hợp nào năm 2026?

**Đáp:** Bản ghi năm 2026 của ngành Ngôn ngữ Anh tại Trường ĐH Tây Đô ghi nhận các tổ hợp: D01, D14, D15, D66, X78. Danh sách này không tự động áp dụng cho năm khác; cần kiểm tra thông báo của năm bạn xét tuyển.

**Tập dữ liệu:** `train`

## qa-0005 — prediction

**Hỏi:** Dự đoán điểm chuẩn 2027 của ngành Ngôn ngữ Anh mã 7220201 tại Trường ĐH Tây Đô?

**Đáp:** Mô hình dự đoán 15 điểm cho ngành Ngôn ngữ Anh tại Trường ĐH Tây Đô năm 2027. Lịch sử gần nhất dùng cho dự đoán là năm 2026. Đây là dự đoán tham khảo, không phải điểm chuẩn chính thức hay cam kết trúng tuyển.

**Tập dữ liệu:** `train`

## qa-0006 — multi_turn_history

**Người dùng trước đó:** Mình đang tìm hiểu ngành Ngôn ngữ Anh mã 7220201 của Trường ĐH Tây Đô.

**Trợ lý trước đó:** Bạn muốn tra điểm lịch sử hay dự đoán của ngành Ngôn ngữ Anh tại Trường ĐH Tây Đô?

**Hỏi:** Ngành đó năm 2026 lấy bao nhiêu?

**Đáp:** Ngành Ngôn ngữ Anh (mã 7220201) tại Trường ĐH Tây Đô năm 2026 có điểm chuẩn 15 theo dữ liệu nội bộ.

**Tập dữ liệu:** `train`

## qa-0007 — no_guarantee

**Hỏi:** Em có 15 điểm, bằng dự đoán 2027 ngành Ngôn ngữ Anh ở Trường ĐH Tây Đô, vậy chắc chắn đỗ chứ?

**Đáp:** Chưa thể khẳng định. 15 là điểm dự đoán 2027, không phải ngưỡng trúng tuyển chính thức. Bạn cần đối chiếu tổ hợp, điều kiện xét tuyển và thông báo của trường; bằng mức dự đoán không bảo đảm đỗ.

**Tập dữ liệu:** `train`

## qa-0211 — sparse_city_coverage

**Hỏi:** 28 điểm CNTT ở Đà Nẵng mà chỉ có một trường thôi sao?

**Đáp:** Danh sách hiện tại chỉ phản ánh dữ liệu đã có, không phải toàn bộ trường đào tạo CNTT ở Đà Nẵng. Cần kiểm tra độ phủ trường, mã ngành, địa điểm và tổ hợp; các lựa chọn thiếu xác minh hoặc chỉ có dữ liệu cũ phải được hiển thị riêng. Bạn xét bằng tổ hợp nào?

**Tập dữ liệu:** `train`

## qa-0212 — risk_high_stays_high

**Hỏi:** Rủi ro cao có phải cùng nhóm thử sức không?

**Đáp:** Đây là hai mức khác nhau trong kết quả mô hình. Mình giữ nguyên nhãn RỦI RO CAO, không đổi thành THỬ SỨC hoặc tự chia lại bằng ngưỡng điểm cố định.

**Tập dữ liệu:** `train`

## qa-0213 — verified_vs_unverified

**Hỏi:** Cứ xem trường chưa rõ tổ hợp là đủ điều kiện nhé

**Đáp:** Chưa thể coi là đủ điều kiện khi chưa xác minh tổ hợp. Mình vẫn có thể hiển thị lựa chọn đó với nhãn cần xác minh để bạn kiểm tra thông báo tuyển sinh.

**Tập dữ liệu:** `train`

## qa-0214 — preference_order

**Hỏi:** Cứ đặt trường an toàn làm NV1 cho em

**Đáp:** Mức rủi ro và thứ tự yêu thích là hai thông tin khác nhau. Bạn muốn học trường hoặc chương trình nào nhất? Mình cần thứ tự ưu tiên của bạn trước khi đề xuất NV1/NV2/NV3, và không thể cam kết đỗ.

**Tập dữ liệu:** `train`

## qa-0215 — baseline_method

**Hỏi:** Có phải mọi điểm dự đoán đều do Random Forest đưa ra?

**Đáp:** Không. Trong bằng chứng này phương pháp đang phục vụ là Baseline_LastScore, lấy điểm gần nhất làm mốc dự đoán. Random Forest là ứng viên được đánh giá riêng; không nên gán kết quả baseline cho Random Forest.

**Tập dữ liệu:** `test`

## qa-0216 — greeting

**Hỏi:** Xin chào

**Đáp:** Chào bạn! Mình có thể tra điểm chuẩn, so sánh dữ liệu và tư vấn trường theo hồ sơ. Bạn đang quan tâm ngành nào?

**Tập dữ liệu:** `train`

## qa-0217 — capabilities

**Hỏi:** Bạn giúp được gì?

**Đáp:** Mình hỗ trợ tra dữ liệu điểm chuẩn, giải thích dự đoán và tư vấn theo điểm, tổ hợp, ngành, khu vực. Với thông tin chưa có trong dữ liệu, mình sẽ nói rõ hoặc hỏi thêm.

**Tập dữ liệu:** `validation`

## qa-0218 — missing_all

**Hỏi:** Tư vấn trường cho em với

**Đáp:** Bạn cho mình biết tổng điểm THPT, tổ hợp và ngành muốn học nhé. Bạn cũng có thể thêm tỉnh/thành mong muốn để thu hẹp kết quả.

**Tập dữ liệu:** `test`

## qa-0246 — multi_turn_profile

**Người dùng trước đó:** Em có 24 điểm A01, muốn học CNTT ở Đà Nẵng.

**Trợ lý trước đó:** Mình đã ghi nhận hồ sơ: 24 điểm, A01, Công nghệ thông tin, Đà Nẵng.

**Hỏi:** Đổi sang Hà Nội nhé

**Đáp:** Mình cập nhật khu vực thành Hà Nội, giữ 24 điểm, A01 và ngành Công nghệ thông tin. Cần chạy lại tra cứu với bộ lọc mới trước khi nêu trường phù hợp.

**Tập dữ liệu:** `test`

## qa-0247 — multi_turn_profile

**Người dùng trước đó:** Em có 24 điểm A01, muốn học CNTT ở Đà Nẵng.

**Trợ lý trước đó:** Mình đã ghi nhận hồ sơ: 24 điểm, A01, Công nghệ thông tin, Đà Nẵng.

**Hỏi:** Em sửa lại là 23,5 điểm

**Đáp:** Mình cập nhật điểm thành 23,5, giữ A01, ngành Công nghệ thông tin và Đà Nẵng. Kết quả tư vấn cần được tính lại theo điểm mới.

**Tập dữ liệu:** `test`
