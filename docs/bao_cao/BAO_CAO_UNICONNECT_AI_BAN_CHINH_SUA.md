# Xây dựng website tư vấn chọn trường và ngành học ứng dụng trí tuệ nhân tạo UniConnect AI

**BÁO CÁO ĐỀ TÀI**

Trường: [CẦN ĐIỀN TÊN TRƯỜNG]

Khoa hoặc bộ môn: [CẦN ĐIỀN]

Học phần: [CẦN ĐIỀN]

Sinh viên thực hiện: [CẦN ĐIỀN HỌ TÊN]

Mã số sinh viên: [CẦN ĐIỀN MSSV]

Lớp: [CẦN ĐIỀN]

Giảng viên hướng dẫn: [CẦN ĐIỀN]

Địa điểm và năm: [CẦN ĐIỀN ĐỊA ĐIỂM], 2026

## Tóm tắt đề tài

UniConnect AI là website hỗ trợ người học tìm hiểu trường đại học, ngành đào tạo và xây dựng phương án lựa chọn dựa trên điểm thi, tổ hợp môn, khu vực và sở thích. Hệ thống kết hợp danh mục điểm chuẩn có nguồn, mô hình dự đoán điểm và trợ lý hội thoại. Người dùng có thể xem lịch sử điểm, so sánh và lưu trường, thực hiện câu hỏi hướng nghiệp, trao đổi trong cộng đồng; quản trị viên quản lý tài khoản, nội dung và các đợt dữ liệu tuyển sinh.

Ứng dụng được xây dựng bằng Vue 3 và Vite ở giao diện, Django 5.2 ở máy chủ, MySQL cho dữ liệu nghiệp vụ. Dữ liệu điểm tuyển sinh đã chuẩn hóa và dự đoán được phục vụ từ các tệp CSV; đây là lớp dữ liệu phân tích riêng với cơ sở dữ liệu nghiệp vụ. Trợ lý sử dụng Gemini để hỗ trợ hội thoại và sử dụng bộ truy xuất dữ liệu nội bộ để cung cấp bằng chứng về trường, ngành và điểm.

Tại mốc rà soát ngày 08/11/2026, tập dữ liệu sạch có 18.746 bản ghi chương trình–năm thuộc 266 khóa trường và 7.517 chương trình trong giai đoạn 2023–2026. Phương pháp Baseline_LastScore đạt MAE khoảng 1,2280 điểm trên 3.776 mẫu kiểm định năm 2026 và được chọn làm phương pháp phục vụ. Kết quả kiểm thử gồm 83 kiểm thử backend, 20 kiểm thử bộ cào và một kịch bản trình duyệt tích hợp đều đạt. Hệ thống đáp ứng phạm vi demo đồ án; các giới hạn về độ phủ dữ liệu, đánh giá hội thoại và triển khai công khai được trình bày trong báo cáo.

Từ khóa: tư vấn tuyển sinh, điểm chuẩn, Vue, Django, MySQL, hồi quy, Gemini.

Dữ liệu và kết quả kiểm thử được tổng hợp tại mốc ngày 08/11/2026; cấu trúc MySQL được đối chiếu ngày 09/11/2026. Báo cáo trình bày phạm vi đã triển khai, kết quả thực nghiệm và các giới hạn còn lại của hệ thống.

# Chương 1 Tổng quan đề tài

## 1.1 Bài toán đặt ra

Thông tin tuyển sinh được công bố trên nhiều website, bảng ảnh và tệp PDF. Cùng một ngành có thể có nhiều mã chương trình, cơ sở đào tạo, tổ hợp hoặc phương thức xét tuyển. Điểm thi THPT, học bạ, ĐGNL và điểm quy đổi có thể sử dụng những thang điểm khác nhau. Nếu chỉ lấy con số mà bỏ điều kiện áp dụng, hệ thống có thể tư vấn sai dù dữ liệu nhìn có vẻ đầy đủ.

Người học cần xem thông tin theo hồ sơ của mình thay vì đọc riêng từng thông báo. Một hệ thống hữu ích phải cho biết kết quả áp dụng cho năm nào, phương thức nào, có xác minh tổ hợp hay chưa và dữ liệu có đủ để tư vấn theo khu vực hay không. Việc cung cấp nguồn và nêu rõ phần chưa biết là yêu cầu trung tâm của đề tài.

## 1.2 Mục tiêu

Mục tiêu tổng quát là xây dựng một website thống nhất việc tra cứu tuyển sinh, hỗ trợ lựa chọn trường/ngành và quản lý hoạt động tư vấn. Hệ thống hướng đến kết quả dễ hiểu và kiểm tra lại được từ nguồn.

Các mục tiêu cụ thể gồm thu thập và chuẩn hóa lịch sử điểm; xây dựng mô hình dự đoán có đối chiếu với phương pháp cơ sở; tư vấn theo điểm, ngành, tổ hợp và địa điểm; hỗ trợ hỏi đáp bằng ngôn ngữ tự nhiên; cung cấp tài khoản, cộng đồng và quản trị dữ liệu; kiểm thử những luồng sử dụng chính.

## 1.3 Đối tượng và phạm vi

Người dùng mục tiêu là học sinh hoặc người tìm hiểu tuyển sinh đại học. Mentor là vai trò hỗ trợ trao đổi trong cộng đồng. Quản trị viên quản lý hệ thống theo quyền được cấp. Vai trò mentor không tự động có quyền quản trị.

Phạm vi dữ liệu phân tích hiện tại là các bản ghi đã thu thập trong giai đoạn 2023–2026; kết quả dự đoán hướng tới năm 2027. Độ phủ này không đồng nghĩa với toàn bộ trường và phương thức xét tuyển trên cả nước. Đề tài hỗ trợ quyết định tham khảo, không thay thế thông báo tuyển sinh chính thức và không cam kết xác suất trúng tuyển.

## 1.4 Phương pháp thực hiện

Đề tài thực hiện theo chuỗi công việc: khảo sát yêu cầu; thiết kế kiến trúc và cơ sở dữ liệu; cào dữ liệu; chuẩn hóa và kiểm tra nguồn; xây dựng đặc trưng lịch sử; huấn luyện và đánh giá mô hình; tích hợp giao diện, API và hội thoại; kiểm thử và lập tài liệu. Các trường hợp dữ liệu thiếu hoặc xung đột được giữ để rà soát thay vì tự điền giá trị.

## 1.5 Bố cục báo cáo

Bảy chương lần lượt trình bày bài toán, cơ sở công nghệ, phân tích thiết kế, pipeline dữ liệu và AI, triển khai ứng dụng, kiểm thử và kết luận. Phụ lục bổ sung danh mục bảng MySQL và hướng dẫn cài đặt, tái lập kết quả. Phần phân tích tập trung vào quyết định thiết kế, cách xử lý dữ liệu và mối liên hệ giữa các chức năng của sản phẩm.

## 1.6 Đóng góp trong phạm vi đồ án

Kết quả chính là một nguyên mẫu có thể vận hành các luồng nghiệp vụ liên kết với nhau và có pipeline dữ liệu tái lập. Giá trị của đề tài nằm ở việc kết hợp dữ liệu có nguồn, điều kiện lọc rõ ràng, đánh giá mô hình theo thời gian và giao diện phục vụ người dùng. Đề tài không đề xuất một thuật toán hồi quy mới hoặc một mô hình ngôn ngữ được huấn luyện từ đầu.

## 1.7 Ý nghĩa của đề tài

Ở góc độ người sử dụng, giá trị của hệ thống nằm ở khả năng gom thông tin phân tán thành một quy trình tra cứu thống nhất. Thay vì đọc riêng thông báo từng trường rồi tự ghi chép, người học có thể cung cấp hồ sơ, xem lịch sử điểm và tiếp tục đặt câu hỏi dựa trên kết quả vừa nhận. Nguồn và năm của thông tin giúp người học kiểm tra lại những lựa chọn quan trọng trước khi đăng ký nguyện vọng.

Ở góc độ kỹ thuật, đề tài kết hợp ba công việc thường bị tách rời: quản lý dữ liệu có nguồn, dự đoán bằng thực nghiệm và phát triển ứng dụng có trạng thái người dùng. Dữ liệu đầu vào quyết định phạm vi trả lời; mô hình chỉ tạo một ước lượng trong phạm vi đó; giao diện và quản trị giúp người dùng khai thác, kiểm tra và cập nhật kết quả. Vì vậy, hoàn thiện hệ thống không chỉ là làm cho chatbot trả lời trôi chảy mà còn phải giữ đúng điều kiện của dữ liệu và khả năng truy vết khi có sai sót.


# Chương 2 Cơ sở lý thuyết và công nghệ

## 2.1 Kiến trúc ứng dụng web

Giao diện Vue tiếp nhận thao tác và gọi API. Backend Django xác thực, kiểm tra dữ liệu và thực hiện nghiệp vụ. MySQL lưu trạng thái cần giao dịch như tài khoản, tương tác, lịch sử hội thoại và các đợt công bố dữ liệu. Các tệp CSV phục vụ điểm lịch sử, metadata và dự đoán tính sẵn.

Cách tổ chức này tách việc cập nhật giao diện khỏi xử lý nghiệp vụ và tách tác vụ huấn luyện khỏi phục vụ yêu cầu web. Web không huấn luyện mô hình lại mỗi khi người dùng bấm tìm kiếm. Backend đọc kết quả đã tính sẵn, áp dụng điều kiện và trả dữ liệu cho giao diện.

## 2.2 Vue và Django

Vue hỗ trợ xây dựng giao diện theo thành phần, liên kết dữ liệu biểu mẫu và cập nhật nội dung theo trạng thái [1]. Trong dự án, các thành phần như biểu mẫu đăng nhập, hồ sơ, banner, ảnh bài viết và hộp thư được tách thành component. Vite cung cấp môi trường phát triển và tạo bản build.

Django cung cấp ORM, cơ chế xác thực, session, phân quyền và trang quản trị [2]. Dự án mở rộng giao diện quản trị theo các công việc thường dùng. Việc cấp quyền và kiểm tra chủ sở hữu được thực hiện phía backend; thao tác ẩn nút trên giao diện không được coi là cơ chế bảo vệ đầy đủ.

## 2.3 Cơ sở dữ liệu quan hệ và ORM

Các thực thể nghiệp vụ có quan hệ chặt chẽ: tài khoản có hồ sơ và bài viết; bài viết có bình luận, ảnh và bình chọn; cuộc hội thoại có nhiều tin nhắn. Mô hình quan hệ biểu diễn các liên kết bằng khóa ngoại. Các ràng buộc duy nhất ngăn lặp tương tác như một tài khoản lưu cùng trường nhiều lần hoặc bỏ nhiều phiếu cho cùng bài.

Django migrations quản lý phiên bản lược đồ. Khi chuyển máy hoặc tạo database mới, cấu trúc được khởi tạo qua migrations thay vì tạo bảng thủ công. MySQL hiện là hệ quản trị được sử dụng ở môi trường dự án; mã cấu hình vẫn giữ tùy chọn SQLite cho những tình huống phát triển hoặc kiểm thử riêng.

## 2.4 Dự đoán điểm bằng hồi quy

Đầu vào của bài toán là lịch sử điểm và đặc trưng chương trình, đầu ra là một giá trị điểm dự đoán. Các mô hình được triển khai gồm Ridge, RandomForestRegressor và GradientBoostingRegressor. Hai phương pháp đối chiếu là lấy điểm gần nhất và ngoại suy xu hướng.

Baseline_LastScore sử dụng điểm gần nhất làm dự đoán cho kỳ tiếp theo. Phương pháp đơn giản này là mốc so sánh cần thiết: mô hình phức tạp chỉ nên được ưu tiên nếu có bằng chứng phù hợp từ đánh giá. Baseline_Trend bổ sung xu hướng lịch sử, nhưng có thể nhạy với những thay đổi đột ngột của điểm qua các năm.

## 2.5 Thước đo và kiểm định theo thời gian

MAE là trung bình trị tuyệt đối của sai lệch giữa dự đoán và thực tế. RMSE lấy căn bậc hai của trung bình bình phương sai số, do đó nhạy hơn với sai lệch lớn. R² mô tả mức độ giải thích biến thiên của mô hình theo định nghĩa hồi quy. Các thước đo này được tính bằng scikit-learn [3].

Với n mẫu, MAE = tổng của |y thực tế − y dự đoán| chia n; RMSE = căn bậc hai của tổng (y thực tế − y dự đoán)² chia n. Báo cáo bổ sung tỷ lệ mẫu có sai số không quá một và hai điểm để dễ diễn giải. MAE không phải tỷ lệ chính xác và không phải xác suất trúng tuyển.

Dữ liệu được chia theo năm mục tiêu. Đặc trưng dự đoán cho năm t chỉ được tạo từ các năm trước t. Cách làm này phù hợp với tình huống vận hành, trong đó không thể sử dụng điểm thực tế của một năm chưa công bố để dự đoán chính năm đó.

## 2.6 Hội thoại có bằng chứng và hướng nghiệp

Trợ lý nhận câu hỏi, nhận diện ý định, cập nhật ngữ cảnh và truy xuất dữ liệu phù hợp. Gemini hỗ trợ diễn đạt và hội thoại; số liệu cần dựa trên dữ liệu mà backend cung cấp. Hệ thống hiện truy xuất theo trường, mã/tên ngành và các điều kiện, chưa sử dụng cơ sở dữ liệu vector. Vì vậy, báo cáo mô tả đây là hội thoại kết hợp truy xuất dữ liệu nội bộ, không khẳng định đã triển khai tìm kiếm ngữ nghĩa bằng vector.

Phần hướng nghiệp tham khảo sáu nhóm sở thích RIASEC: Realistic, Investigative, Artistic, Social, Enterprising và Conventional. Sáu nhóm này cũng được sử dụng trong O*NET Interest Profiler [4]. Bộ 24 câu tiếng Việt của dự án là bộ câu hỏi nội bộ phục vụ demo định hướng; chưa có nghiên cứu kiểm định tâm lý để coi là công cụ chuẩn hóa tương đương O*NET.

## 2.7 Lựa chọn công nghệ theo yêu cầu dự án

Vue phù hợp với giao diện có nhiều trạng thái như hồ sơ tư vấn, danh sách kết quả và hội thoại tiếp nối. Component giúp chia một màn hình lớn thành các phần có trách nhiệm riêng, còn lớp dịch vụ API tập trung cách gửi yêu cầu và xử lý lỗi. Khi sửa biểu mẫu hoặc cách hiển thị kết quả, phần xử lý dữ liệu phía máy chủ không cần thay đổi nếu hợp đồng API vẫn giữ nguyên.

Django được sử dụng để giải quyết đồng thời xác thực, quản lý phiên, ORM và quản trị dữ liệu. Đây là những phần cần tính nhất quán giữa các chức năng: một tài khoản dùng chung cho lưu trường, lịch sử AI và hoạt động cộng đồng. Việc dùng chung cơ chế quyền giúp hạn chế tình trạng mỗi chức năng tự kiểm tra vai trò theo một cách khác nhau.

MySQL lưu dữ liệu nghiệp vụ vì các bản ghi cần quan hệ, ràng buộc và giao dịch. Trong khi đó, tập điểm được xử lý theo lô và dùng cho thực nghiệm nên vẫn được quản lý bằng CSV có phiên bản. Hai cách lưu trữ phục vụ hai mục đích khác nhau. Nếu chuyển toàn bộ điểm vào MySQL trong tương lai, cần thiết kế riêng trường, chương trình, phương thức và nguồn thay vì chỉ thêm một bảng điểm chung rồi bỏ mất điều kiện xét tuyển.

Việc gọi Gemini qua backend giúp tập trung cấu hình và giữ khóa API ngoài mã giao diện. Tuy nhiên, mô hình hội thoại vẫn là dịch vụ ngoài, có thể bị giới hạn hoặc gián đoạn. Do đó, khả năng tra cứu dữ liệu có nguồn và cách thông báo lỗi là một phần của thiết kế ngay từ đầu, không phụ thuộc hoàn toàn vào chất lượng diễn đạt của nhà cung cấp.


# Chương 3 Phân tích yêu cầu và thiết kế hệ thống

## 3.1 Người dùng và yêu cầu nghiệp vụ

Hệ thống phục vụ bốn nhóm tác nhân theo mục đích sử dụng. Khách truy cập cần tìm hiểu trường, ngành, lịch sử điểm và dùng những chức năng tư vấn công khai. Thành viên cần thêm khả năng giữ hồ sơ, lưu trường, xem lại kết quả hướng nghiệp và tham gia cộng đồng. Mentor hỗ trợ trao đổi kinh nghiệm trong cộng đồng. Nhân sự quản trị kiểm soát tài khoản, nội dung và dữ liệu tuyển sinh theo quyền được cấp.

Các vai trò nghiệp vụ không được đồng nhất với quyền kỹ thuật. Cụ thể, role mentor trong hồ sơ không tự tạo quyền staff; một nhân sự có thể được phép xem nội dung nhưng chưa được phép công bố dữ liệu. Backend cần kiểm tra đúng quyền của mỗi thao tác, thay vì dựa vào tên vai trò hoặc việc một nút đã bị ẩn trên giao diện.

| Nhóm chức năng | Kết quả người dùng cần nhận |
|---|---|
| Tài khoản | Đăng ký đăng nhập hồ sơ và phân luồng theo quyền |
| Tra cứu | Trường ngành lịch sử điểm nguồn và điều kiện áp dụng |
| Tư vấn | Lựa chọn theo điểm tổ hợp ngành khu vực và mức tham khảo |
| Hội thoại | Trả lời tiếp nối dựa trên hồ sơ và bằng chứng tra cứu |
| Hướng nghiệp | Điểm các nhóm RIASEC và gợi ý ngành tham khảo |
| Cộng đồng | Bài viết ảnh bình luận bình chọn và trao đổi trực tiếp |
| Quản trị | Kiểm duyệt nội dung và quản lý các đợt dữ liệu có nguồn |

Về yêu cầu phi chức năng, giao diện cần sử dụng tiếng Việt rõ ràng, hoạt động trên máy tính và điện thoại, đồng thời phản hồi được các trường hợp dữ liệu chưa đủ hoặc dịch vụ AI bị lỗi. Những kết quả liên quan điểm phải đi kèm năm và phương thức. Hệ thống cần lưu lịch sử phục vụ truy vết, kiểm tra quyền ở máy chủ và hạn chế các yêu cầu lặp quá mức. Trong phạm vi hiện tại, hiệu năng được kiểm tra qua các luồng chức năng; chưa có số liệu thử tải để khẳng định năng lực phục vụ đồng thời.

## 3.2 Phân rã chức năng bằng BFD

BFD phân chia UniConnect AI thành sáu nhóm chính, từ những thao tác người dùng thường thực hiện đến các tác vụ dữ liệu vận hành phía sau. Sự phân chia này làm rõ phạm vi của từng phần và giúp tránh xây dựng các chức năng chồng lấn. Tài khoản là lớp dùng chung; tra cứu và tư vấn khai thác dữ liệu tuyển sinh; cộng đồng tạo môi trường trao đổi; quản trị kiểm soát nội dung; nhóm dữ liệu và mô hình duy trì chất lượng đầu vào.

{{FIGURE:gon_bfd}}

Trong mã nguồn, các chức năng tài khoản tập trung ở accounts, tra cứu ở catalog, tư vấn ở ai_api và ai_chat, hướng nghiệp ở career, cộng đồng ở social và connections. Các lớp admin mở rộng xử lý công việc quản trị. Tác vụ cào và huấn luyện nằm trong scraper và ai, được chạy ngoại tuyến. Một nhóm chức năng có thể sử dụng nhiều bảng dữ liệu, do đó không thể dùng BFD thay cho lược đồ cơ sở dữ liệu.

## 3.3 Kiến trúc tổng thể và ranh giới dữ liệu

Ứng dụng được chia thành giao diện, API nghiệp vụ và các nguồn lưu trữ. Vue tiếp nhận thao tác và gọi API Django. Django kiểm tra đầu vào, xác thực phiên, thực hiện quy tắc nghiệp vụ rồi trả JSON. MySQL giữ các bản ghi thay đổi theo hoạt động người dùng; CSV giữ lịch sử điểm và các kết quả dự đoán được tính trước. Gemini chỉ được gọi từ backend khi cần hỗ trợ phân tích hoặc diễn đạt hội thoại.

{{FIGURE:gon_architecture}}

Việc tách MySQL và CSV là quyết định quan trọng của phiên bản hiện tại. MySQL hỗ trợ giao dịch cho tài khoản, bài viết và hội thoại; CSV thuận tiện cho chuẩn hóa, kiểm toán nguồn và thực nghiệm mô hình theo lô. Vì vậy, câu hỏi “dữ liệu đã chuyển sang MySQL chưa” cần được trả lời theo loại dữ liệu: nghiệp vụ đã dùng MySQL, còn điểm chuẩn hóa và dự đoán vẫn phục vụ từ CSV. Những đợt điểm được nhập từ admin là một lớp bổ sung lưu trong MySQL và ghép vào tra cứu sau khi được duyệt.

Các lớp không tự thay đổi trách nhiệm của nhau. Trình duyệt không được giữ khóa Gemini, không trực tiếp đọc database và không quyết định quyền công bố. Một câu hỏi web không chạy lại crawler hoặc huấn luyện mô hình. Nếu dữ liệu được cập nhật, quy trình ngoại tuyến tạo lại đầu ra phục vụ sau khi đã kiểm tra, thay vì sửa ngẫu nhiên kết quả trong mỗi lượt tư vấn.

## 3.4 Luồng hoạt động chính

Luồng sử dụng bắt đầu ở trang chính, nơi người học có thể tìm trường hoặc mở biểu mẫu tư vấn. Với tra cứu, hệ thống nhận điều kiện và trả kết quả có nguồn. Với thao tác lưu hoặc tương tác cá nhân, hệ thống yêu cầu đăng nhập. Với quản trị, tài khoản phải vượt qua kiểm tra quyền trước khi nhìn thấy hoặc thực hiện công việc tương ứng.

{{FIGURE:gon_activity}}

Một hồ sơ tư vấn thông thường gồm điểm, tổ hợp, ngành và khu vực. Backend kiểm tra miền giá trị, đọc dữ liệu phục vụ và lọc các chương trình theo điều kiện đã biết. Kết quả chính chỉ chứa những lựa chọn đáp ứng yêu cầu xác minh. Nếu chưa đủ dữ liệu, giao diện cần nói rõ phần thiếu và phân biệt các lựa chọn mở rộng. Việc không tìm thấy kết quả không được diễn giải thành khẳng định rằng toàn bộ trường tại khu vực không tuyển sinh ngành đó.

Luồng quản trị dữ liệu có thêm bước đối chiếu thông báo gốc. Tệp hợp lệ về cấu trúc chỉ đủ để tạo một đợt chờ duyệt, chưa được công bố ngay. Người có quyền duyệt kiểm tra nguồn và tính trùng lặp trước khi đưa đợt vào phần tra cứu. Luồng này tạo ranh giới giữa thao tác nhập liệu và quyết định sử dụng dữ liệu.

## 3.5 Mô hình quan hệ nghiệp vụ

Tài khoản là thực thể trung tâm của các chức năng cá nhân. Mỗi tài khoản có tối đa một hồ sơ, nhưng có thể có nhiều bài viết, kết quả hướng nghiệp và cuộc hội thoại. Một cuộc hội thoại có nhiều tin nhắn. Một bài viết có nhiều bình luận, ảnh và tương tác. Sơ đồ ERD trình bày các quan hệ trọng tâm; những quan hệ hỗ trợ như lượt thích và theo dõi được mô tả trong phần thiết kế bảng.

{{FIGURE:gon_erd}}

Quan hệ giữa tài khoản và cuộc hội thoại cho phép tài khoản ở phía cha vắng mặt vì hệ thống còn phục vụ khách. Trong trường hợp đó, AIChatSession.user là NULL và session_key xác định phiên khách. Chuỗi này được sử dụng ở mức ứng dụng, không phải khóa ngoại vật lý đến bảng django_session. Thiết kế cho phép tiếp tục một cuộc trò chuyện trong cùng phiên mà không bắt buộc tạo tài khoản ngay từ đầu.

Quyền truy cập lịch sử không được xác định chỉ bằng mã cuộc hội thoại do trình duyệt gửi lên. Với thành viên, truy vấn phải giới hạn theo user hiện tại; với khách, truy vấn giới hạn theo phiên khách và điều kiện user rỗng. Nhờ đó, biết ID của một cuộc hội thoại không đủ để đọc dữ liệu của người khác. Đây là ví dụ cho thấy quan hệ dữ liệu và kiểm tra quyền cần được thiết kế cùng nhau.

## 3.6 Lược đồ SQL và các ràng buộc chính

Metadata MySQL được đối chiếu ngày 09/11/2026 gồm 27 bảng và 33 khóa ngoại vật lý. Phần nghiệp vụ chiếm 15 bảng, hệ thống xác thực và quản trị Django chiếm 10 bảng, hai bảng còn lại phục vụ điều phối công bố và giới hạn yêu cầu. Hình SQL dưới đây chọn sáu bảng liên quan trực tiếp đến tư vấn và tài khoản; danh mục đủ 27 bảng nằm ở Phụ lục A, còn DDL đầy đủ được lưu trong bộ tài liệu bàn giao.

{{FIGURE:gon_sql}}

auth_user lưu tên đăng nhập, mật khẩu đã băm, trạng thái tài khoản và các cờ quyền. accounts_profile mở rộng thông tin phục vụ tư vấn như điểm dự kiến, tổ hợp, ngành, khu vực, giới thiệu và ảnh đại diện. Ràng buộc duy nhất trên profile.user_id thể hiện quan hệ một–một. Trường email được ứng dụng kiểm tra trùng khi đăng ký, nhưng không có ràng buộc UNIQUE vật lý trong bảng auth_user hiện tại; hai lớp kiểm tra này cần được phân biệt khi phân tích thiết kế.

ai_chat_aichatsession lưu tiêu đề, chủ sở hữu nếu có, khóa phiên khách và context dạng JSON. ai_chat_aichatmessage lưu vai trò, nội dung, ý định, payload và khóa ngoại conversation_id. Context giữ hồ sơ tư vấn hiện tại, còn các tin nhắn giữ diễn biến đã trao đổi. Cách chia này tránh phải dựng lại toàn bộ trạng thái chỉ từ văn bản tự nhiên mỗi khi người dùng sửa một điều kiện.

catalog_saveduniversity liên kết user với university_key và có ràng buộc duy nhất theo cặp. university_key là khóa chuỗi để đối chiếu danh mục CSV, không tham chiếu một bảng University trong MySQL. Vì vậy, kiểm tra khóa trường hợp lệ phải được thực hiện ở lớp nghiệp vụ. Cùng một thành viên không thể tạo nhiều bản lưu cho cùng khóa trường, nhưng nhiều thành viên có thể lưu chung trường đó.

catalog_admissionrelease lưu tên đợt, danh sách rows dạng JSON, trạng thái, dấu kiểm tra nguồn và người tạo/người duyệt. Hai khóa ngoại đến User cho phép NULL để giữ bản ghi khi tài khoản liên quan không còn. catalog_admissionreleaselock là bản ghi khóa phụ trợ điều phối công bố, không phải một bảng điểm và không có khóa ngoại. Nó giúp tuần tự hóa bước kiểm tra–công bố khi có nhiều thao tác đồng thời.

Nhóm cộng đồng gồm social_post, social_comment, social_postimage, social_postlike, social_savedpost và social_pollvote. Post giữ nội dung và danh sách lựa chọn bình chọn; PollVote giữ lựa chọn của từng tài khoản. Các cặp post–user ở lượt thích, bài lưu và phiếu bầu có ràng buộc duy nhất phù hợp, nhờ đó tránh cộng trùng chỉ vì gửi lại cùng yêu cầu. Ảnh được lưu thành bản ghi liên kết với bài thay vì nhét toàn bộ tệp nhị phân vào cột nội dung bài viết.

social_notification liên kết người nhận, người tạo tương tác và bài viết khi có; social_directmessage có hai khóa ngoại riêng cho người gửi và người nhận. connections_userfollow cũng có hai vai trò tham chiếu User, kèm ràng buộc không tự theo dõi và không lặp cặp quan hệ. Hai liên kết cùng đến bảng User vẫn mang ý nghĩa khác nhau và cần giữ tên cột rõ ràng trong truy vấn.

career_careerassessment lưu câu trả lời, điểm sáu nhóm, mã Holland và gợi ý ngành ở từng thời điểm. Kết quả cũ được giữ dưới dạng bản ghi đánh giá, không thay thế trực tiếp hồ sơ đăng nhập. Những cột JSON được sử dụng cho cấu trúc linh hoạt như câu trả lời và payload, trong khi các quan hệ chủ sở hữu vẫn dùng khóa ngoại để bảo đảm liên kết.

Các bảng Django quản lý nhóm quyền, quyền theo model, phiên đăng nhập, lịch sử admin và migrations. Không phải bảng nào cũng có khóa chính id tự tăng: django_session dùng session_key, config_requestbucket dùng key và AdmissionReleaseLock dùng khóa id tự quy định. Hành vi on_delete=CASCADE hoặc SET_NULL trong model thể hiện cách Django xử lý khi xóa qua ORM; không tự đồng nghĩa với một mệnh đề ON DELETE CASCADE trong DDL MySQL. DDL thực tế là cơ sở khi cần phân tích hành vi SQL trực tiếp.

## 3.7 Thiết kế giao tiếp giữa frontend và backend

Các API được nhóm theo nghiệp vụ để giao diện gọi đến đúng phần xử lý: auth cho tài khoản, catalog cho trường và dữ liệu, ai cho đề xuất, ai-chat cho hội thoại, career cho hướng nghiệp, social và connections cho cộng đồng. Các yêu cầu thông thường trao đổi JSON; tải ảnh sử dụng FormData. Lớp dịch vụ frontend dùng fetch, gửi credentials và CSRF token ở những yêu cầu cần thiết.

Đầu vào phải được xác minh lại ở backend dù biểu mẫu đã có kiểm tra. Ví dụ, một giá trị điểm có thể là chuỗi không hợp lệ hoặc số ngoài miền; ID nội dung có thể thuộc người khác; một URL nguồn có thể không đáp ứng quy tắc nhập. Backend trả lỗi có mã trạng thái và thông tin cần thiết để giao diện hiển thị, thay vì giả trả một danh sách rỗng như thể tra cứu đã thành công.

Việc công bố và thu hồi đợt dữ liệu được thực hiện qua Django Admin có kiểm tra quyền, không qua một endpoint công khai cho phép người dùng tự đổi trạng thái. Cách tổ chức này tận dụng cơ chế quản trị hiện có và giữ những thao tác có tác động đến dữ liệu tra cứu trong một khu vực được kiểm soát.

Ví dụ, khi người học gửi một hồ sơ tư vấn, frontend gọi API đề xuất với điểm và các điều kiện hiện tại. Backend kiểm tra giá trị rồi chuyển yêu cầu đến lớp tư vấn, đọc đầu ra dự đoán và metadata, sau đó trả cấu trúc kết quả cho giao diện. Giao diện không tự tính lại điểm dự đoán từ những con số đang hiển thị. Nếu người dùng chuyển sang hỏi AI về lựa chọn đó, context được gửi cùng câu hỏi để backend nối tiếp hồ sơ, còn số liệu vẫn được lấy lại qua lớp bằng chứng.

Với thao tác lưu trường, yêu cầu cần phiên đăng nhập và một khóa trường hợp lệ. Backend xác định tài khoản từ session, không nhận một user_id tùy ý từ biểu mẫu để quyết định chủ sở hữu. Khi mở lại danh sách đã lưu, dữ liệu được truy vấn theo tài khoản hiện tại rồi đối chiếu danh mục trường. Cùng một nguyên tắc được áp dụng cho lịch sử hội thoại và kết quả hướng nghiệp: frontend yêu cầu xem dữ liệu, nhưng backend mới là nơi xác định dữ liệu nào thuộc quyền truy cập.

# Chương 4 Thu thập dữ liệu và xây dựng AI

## 4.1 Nguồn dữ liệu và nguyên tắc tiếp nhận

Dữ liệu được lấy từ thông báo của trường, các bảng HTML, PDF, ảnh và các nguồn công khai đã có trong bộ cào. Nguồn chính thức được ưu tiên khi bổ sung hoặc giải quyết khác biệt. Dự án cũng lưu bằng chứng của nguồn tổng hợp công khai và kiểm tra danh tính trường, năm, phương thức trước khi tiếp nhận.

Một bản ghi đủ điều kiện phải xác định được trường, chương trình, năm và ý nghĩa của điểm. Điểm sàn không được coi là điểm trúng tuyển. Các thang 40, 90, 100, điểm có môn nhân hệ số hoặc phương thức kết hợp không được tự chia tỷ lệ để đưa vào tập THPT thuần. Dữ liệu chưa chứng minh tương thích vẫn có thể phục vụ tra cứu với nhãn phương thức riêng.

## 4.2 Quy trình xử lý

Bộ cào tải nguồn và lưu URL, bản chụp nội dung cùng thông tin kiểm tra tệp. Với nguồn ảnh hoặc PDF khó trích xuất, người thực hiện kiểm tra trực quan để xác nhận cột, năm và mã chương trình. Một số bộ nhập cố định SHA-256 của tệp đã duyệt để phát hiện thay đổi nguồn trong những lần chạy sau.

Bước chuẩn hóa xử lý tên trường, mã ngành, kiểu số và danh sách tổ hợp. Các dòng lặp cùng chương trình–năm chỉ được hợp nhất khi thống nhất điểm; các tổ hợp và nguồn tương ứng được tổng hợp. Khi một chương trình–năm có nhiều điểm khác nhau chưa giải thích được, các dòng được chuyển sang tập cách ly, không tự lấy trung bình hoặc chọn giá trị thấp nhất.

Trường hợp đổi tên cần bằng chứng xác nhận cùng cơ sở đào tạo. Ví dụ, nguồn Vinh năm 2026 ghi việc đổi tên từ Sư phạm Kỹ thuật Vinh sang Công nghệ Kỹ thuật Vinh. Phần nối lịch sử giữ danh tính tương ứng để tránh tạo ra hai trường chỉ vì đổi tên.

{{FIGURE:gon_crawler}}

## 4.3 Kiểm soát lỗi và xung đột dữ liệu

Một lỗi thường gặp khi cào là chọn đúng số nhưng sai cột. Trên cùng một trang có thể có điểm sàn, điểm trúng tuyển, điểm học bạ và điểm quy đổi. Bộ nhập cần nhận diện tiêu đề bảng và ngữ cảnh năm trước khi đọc từng hàng. Khi tên cột hoặc phương thức chưa rõ, bản ghi chưa đủ điều kiện đi vào tập chuẩn hóa dù giá trị điểm nằm trong khoảng có vẻ hợp lý.

Danh tính chương trình cũng cần được bảo toàn. Cùng tên ngành nhưng khác chương trình, cơ sở hoặc điều kiện xét tuyển chưa chắc là một chuỗi lịch sử. Ngược lại, một trường đổi tên có thể vẫn là cùng cơ sở đào tạo. Vì vậy, chuẩn hóa không chỉ bỏ dấu hoặc rút gọn tên; cần đối chiếu mã, năm, thông báo và quy tắc đã rà soát. Ghép sai danh tính sẽ làm đặc trưng lịch sử có vẻ đầy đủ nhưng không còn phản ánh đúng một đối tượng.

Với hai nguồn cho điểm khác nhau, không lấy trung bình để tạo giá trị mới. Trước tiên cần xác định chúng có cùng năm, cùng ngành và cùng phương thức không. Nếu khác điều kiện, phải giữ riêng; nếu thật sự mâu thuẫn mà chưa có bằng chứng giải thích, đưa vào tập cách ly. Dữ liệu bị cách ly vẫn có giá trị cho việc rà soát, nhưng không nên được sử dụng để huấn luyện hoặc làm kết quả tư vấn chính.

Tính tái lập phụ thuộc cả mã xử lý và bằng chứng nguồn. Một URL có thể thay đổi nội dung sau ngày thu thập, vì vậy lưu HTML, PDF hoặc ảnh đã đọc giúp kiểm tra lại quyết định nhập. Dấu SHA-256 của các nguồn đã duyệt hỗ trợ phát hiện thay đổi tệp; nó không tự chứng minh nội dung tuyển sinh đúng, mà xác nhận rằng công cụ đang đọc đúng phiên bản nguồn từng được kiểm tra.

## 4.4 Quy mô dữ liệu tại mốc báo cáo

| Nội dung | Số lượng |
|---|---:|
| Bản ghi chương trình–năm sạch | 18.746 |
| Khóa trường trong tập sạch | 266 |
| Chương trình phân biệt | 7.517 |
| Chương trình có đủ bốn năm | 2.406 |
| Chương trình có ít nhất hai năm | 5.161 |
| Dòng metadata địa điểm | 50 |
| Dòng điểm chính thức theo phương thức ở tập riêng | 407 |

| Năm | Bản ghi chương trình–năm |
|---|---:|
| 2023 | 4.551 |
| 2024 | 4.841 |
| 2025 | 4.460 |
| 2026 | 4.894 |

Đơn vị thống kê là chương trình–năm, không phải số thí sinh. Một trường có dữ liệu không có nghĩa mọi ngành và năm của trường đã đầy đủ. Các con số được lấy từ coverage_summary.json và các tệp dữ liệu hiện hành; đây là ảnh chụp tại mốc báo cáo, không phải số liệu tuyển sinh toàn quốc.

## 4.5 Xây dựng đặc trưng

Với năm mục tiêu t, các đặc trưng được tạo từ lịch sử trước t: số năm quan sát, năm đầu/cuối, khoảng cách đến năm dự đoán, điểm gần nhất, điểm trước đó, trung bình, cực trị, độ lệch chuẩn, xu hướng và mức thay đổi. Tình trạng biết tổ hợp gần nhất, nhóm ngành và khóa trường cũng được sử dụng.

Đặc trưng lịch sử phải tuân thủ ranh giới thời gian. Chẳng hạn, để dự đoán mục tiêu 2026, phép tính trung bình hoặc xu hướng không được sử dụng điểm thực tế 2026. Chia ngẫu nhiên các dòng chương trình–năm có thể làm thông tin tương lai đi vào tập huấn luyện, dẫn đến kết quả đẹp hơn nhưng không phản ánh cách dùng thật. Thiết kế chia theo năm mục tiêu được áp dụng để hạn chế vấn đề đó.

Một chương trình không có đủ lịch sử cần được nhận diện về độ tin cậy và độ mới. Việc có một dòng dự đoán không chứng minh chương trình đủ điều kiện tư vấn cho mọi tổ hợp hoặc khu vực. Bộ lọc nghiệp vụ tiếp tục hoạt động sau bước dự đoán.

## 4.6 Thiết kế huấn luyện

{{FIGURE:gon_ml}}

Giai đoạn chọn mô hình sử dụng năm mục tiêu 2024 để huấn luyện và 2025 để validation. Sau đó mô hình được fit lại trên các mẫu mục tiêu 2024–2025, gồm 7.453 dòng, rồi đánh giá trên 3.776 mẫu mục tiêu 2026. Các đặc trưng của mỗi dòng chỉ lấy lịch sử trước năm mục tiêu.

Mô hình học máy được chọn theo validation là RandomForest. Sau đánh giá, mô hình học máy được refit trên 11.229 mẫu mục tiêu 2024–2026 để tạo dự đoán phục vụ năm 2027. Phương pháp có kết quả tốt nhất tổng thể được hệ thống sử dụng để phục vụ là Baseline_LastScore. Cần phân biệt tệp mô hình học máy đã lưu với phương pháp dự đoán cuối cùng mà bộ tư vấn lựa chọn.

| Mô hình | Cấu hình chính trong mã |
|---|---|
| Ridge | alpha bằng 10 |
| RandomForest | 500 cây, độ sâu tối đa 14, lá tối thiểu 2 mẫu, random_state bằng 42 |
| GradientBoosting | 350 cây, learning_rate 0,03, độ sâu 2, loss huber, random_state bằng 42 |
| LastScore | Điểm quan sát gần nhất, giới hạn trong thang phục vụ |
| Trend | Điểm gần nhất cộng xu hướng nhân khoảng cách năm |

## 4.7 Kết quả hồi quy

| Phương pháp | MAE | RMSE | R² | Sai số không quá 1 điểm |
|---|---:|---:|---:|---:|
| Baseline_LastScore | 1,2280 | 1,9272 | 0,7583 | 62,82% |
| GradientBoosting | 1,3017 | 1,8774 | 0,7706 | 54,03% |
| RandomForest | 1,3662 | 1,9274 | 0,7582 | 53,79% |
| Baseline_Trend | 1,7494 | 2,6496 | 0,5431 | 51,75% |
| Ridge | 1,7867 | 2,2567 | 0,6686 | 32,65% |

Các giá trị trên lấy từ cutoff_model_metrics_2026_holdout.csv, cùng tập 3.776 mẫu. LastScore tốt nhất về MAE, trong khi GradientBoosting có RMSE thấp hơn. Kết quả cho thấy thứ tự tốt nhất phụ thuộc thước đo; không có cơ sở kết luận mô hình phức tạp luôn tốt hơn. Đề tài giữ phương pháp phục vụ đơn giản và giải thích được theo tiêu chí lựa chọn hiện tại.

Việc bổ sung dữ liệu có thể thay đổi tập kiểm định và các chỉ số. Không so sánh trực tiếp hai chỉ số từ hai tập mẫu khác nhau để kết luận chất lượng đã tăng. Dữ liệu năm 2027 thực tế chưa được sử dụng để kiểm chứng dự đoán 2027.

## 4.8 Gán mức tư vấn và kiểm tra điều kiện

Đặt d bằng điểm người dùng trừ điểm dự đoán; q50 và q80 là các phân vị sai số tuyệt đối từ kết quả kiểm định, có thể xét theo nhóm độ dày lịch sử khi đủ dữ liệu. Hệ thống áp dụng quy tắc sau.

| Điều kiện | Mức tư vấn |
|---|---|
| d lớn hơn hoặc bằng q80 | An toàn |
| −q50 ≤ d < q80 | Phù hợp |
| −q80 ≤ d < −q50 | Thử sức |
| d < −q80 | Rủi ro cao |

Ngưỡng được hiệu chỉnh từ kết quả năm 2026 nên mức tư vấn cần được đánh giá thêm trên dữ liệu tương lai độc lập. Đây là cách phân nhóm tham khảo, không phải xác suất được hiệu chuẩn. Danh sách nguyện vọng còn phụ thuộc mức độ yêu thích, điều kiện học tập và quy định tuyển sinh; không tự gán thứ tự nguyện vọng chỉ dựa vào nhãn an toàn.

Chế độ kết quả chính yêu cầu ngành và tổ hợp đã xác minh, dữ liệu thực tế gần nhất phù hợp và địa điểm đã biết nếu người dùng chọn khu vực. Trường hợp thiếu tổ hợp hoặc chỉ có dữ liệu cũ được hiển thị ở nhóm mở rộng với chú thích. Bộ lọc không suy ra địa điểm từ tên trường để thay thế metadata xác minh.

## 4.9 Truy xuất bằng chứng và hội thoại tiếp nối

Backend xử lý các ý định tra lịch sử điểm, tư vấn, so sánh và giải thích kết quả. Ngữ cảnh lưu điểm, tổ hợp, ngành và khu vực khi phù hợp. Một số câu chào, cảm ơn và yêu cầu đơn giản được xử lý tại chỗ; luồng phức tạp có thể sử dụng Gemini để xác định hoặc diễn đạt câu trả lời.

Khi dịch vụ lỗi, hệ thống phân biệt lỗi cấu hình, quota, giới hạn tốc độ, quá tải và timeout; thực hiện số lần thử lại có giới hạn và khoảng chờ phù hợp. Kết quả tra cứu nội bộ vẫn có thể được trả về. Cơ chế này giảm phụ thuộc dịch vụ nhưng không bảo đảm Gemini luôn sẵn sàng. API key chỉ ở backend, không nhúng trong giao diện.

Bộ QA gồm 250 mẫu kiểm tra bằng chứng, phép tính, tình huống thiếu dữ liệu và cách chia tập. Bộ QA là tài sản đánh giá và phát triển, không phải bằng chứng rằng chatbot đã được fine-tune hoặc đạt chất lượng hội thoại tương đương 250 lượt chấm của người dùng.

## 4.10 Quản lý ngữ cảnh và giới hạn câu trả lời

Một lượt hội thoại được xử lý theo ba nguồn thông tin: câu hỏi hiện tại, context đã lưu và trạng thái biểu mẫu từ giao diện. Context có thể giữ điểm, tổ hợp, ngành và thành phố. Nếu người dùng chỉ nói “đổi sang A00”, hệ thống cần cập nhật tổ hợp mà không tự xóa ngành hoặc khu vực đã xác định. Nếu người dùng hỏi cho một người khác, hệ thống phải nhận diện việc đổi chủ thể và không mặc nhiên lấy hồ sơ cá nhân áp vào người đó.

Service nhận diện các ý định như tư vấn hồ sơ, tra lịch sử, so sánh, giải thích mô hình, chiến lược nguyện vọng và hỏi dữ liệu chưa có. Khi sử dụng bộ định tuyến bằng mô hình, đầu ra được ràng buộc theo schema và kiểm tra lại kiểu dữ liệu, miền điểm và độ dài chuỗi. Văn bản do mô hình trả về chưa được xem là dữ liệu đầu vào hợp lệ cho bộ tư vấn nếu chưa qua bước xác minh này.

Ở bước tạo nội dung, khối bằng chứng là kết quả tra cứu do backend xây dựng. Gemini được yêu cầu giữ nguyên trường, ngành, năm, phương thức và điểm trong khối đó. Nếu không có học phí hoặc học bổng trong tập dữ liệu, trợ lý cần nêu giới hạn thay vì tự điền số liệu. Đối với câu hỏi ngoài tuyển sinh như thời tiết, phản hồi không được lấy hồ sơ tuyển sinh làm câu trả lời thay thế hoặc giả nhận có dữ liệu thời gian thực.

Lịch sử gửi đến mô hình được giới hạn tối đa sáu tin gần nhất và có ngân sách ký tự. Cách này giảm dung lượng yêu cầu và hạn chế kéo toàn bộ lịch sử vào mỗi lượt hỏi, nhưng cũng có nghĩa hệ thống không có trí nhớ không giới hạn. Những điều kiện quan trọng cần được giữ trong context có cấu trúc; những chi tiết chỉ xuất hiện từ rất lâu trong văn bản có thể cần người dùng nhắc lại.

## 4.11 Xử lý khi dịch vụ AI không sẵn sàng

Độ ổn định của hội thoại phụ thuộc vào khóa cấu hình, hạn mức, mạng và trạng thái nhà cung cấp. Thử lại hữu hạn phù hợp với lỗi tạm thời, nhưng không thể khắc phục một cấu hình sai hoặc một hạn mức đã hết bằng cách gọi liên tục. Vì vậy, hệ thống cần phân loại lỗi và trả trạng thái rõ ràng thay vì chỉ thông báo chung rằng AI không khả dụng.

Ở service hiện tại, các trạng thái lỗi 502, 503 và 504 có thể chuyển sang đường trả lời dựa trên bằng chứng nội bộ. Phản hồi dự phòng giúp người dùng tiếp tục xem kết quả tra cứu, nhưng cách diễn đạt và khả năng xử lý câu hỏi mở có thể hạn chế hơn Gemini. Những lỗi không thuộc loại cho phép dự phòng được trả về dưới dạng lỗi; hệ thống không tạo một câu trả lời giả chỉ để làm đầy khung chat.

View đọc context và lịch sử trước khi gọi service. Sau khi có câu trả lời thành công hoặc kết quả dự phòng hợp lệ, transaction.atomic ghi đồng thời tin người dùng, tin trợ lý và context mới. Nếu service ném lỗi chưa được xử lý thành dự phòng, cặp tin chưa được ghi. Cách làm này tránh lưu một phần lượt trao đổi như thể nó đã hoàn thành, dù bản ghi cuộc hội thoại có thể đã được tạo trước bước gọi service.

Chất lượng hội thoại cần được đánh giá riêng với sai số hồi quy. Một dự đoán đúng phương pháp vẫn có thể bị giải thích sai năm hoặc sai tổ hợp; một câu trả lời tự nhiên vẫn có thể thiếu bằng chứng. Do đó, hướng đánh giá tiếp theo cần chấm độ đúng nguồn, tính nhất quán giữa nội dung và thẻ kết quả, khả năng giữ ngữ cảnh và cách phản hồi khi thiếu dữ liệu, thay vì chỉ xem số lượng câu trả lời thành công.


# Chương 5 Xây dựng ứng dụng và quản trị

## 5.1 Tổ chức mã nguồn

Mã nguồn được chia thành các thư mục theo nhiệm vụ. frontend chứa thành phần giao diện và lớp dịch vụ API. backend chứa các app Django, model, migration, view, kiểm tra quyền và quản trị. ai chứa công cụ chuẩn hóa, xây dựng đặc trưng, huấn luyện, gán mức tư vấn và bộ QA. scraper chứa bộ tải nguồn, bộ đọc và các quy tắc tiếp nhận dữ liệu. data giữ nguồn thô, đầu ra xử lý và tập dữ liệu phục vụ, còn docs lưu hướng dẫn và kết quả kiểm tra.

Cách tổ chức này tạo được ranh giới giữa tác vụ web và tác vụ ngoại tuyến. Môi trường chỉ phục vụ web có thể cài requirements-web.txt mà không cần toàn bộ thư viện huấn luyện. Môi trường phát triển dữ liệu dùng thêm requirements-training.txt để chạy mô hình. Khi bàn giao, mã nguồn, phiên bản phụ thuộc và các tệp dữ liệu phục vụ cần đi cùng nhau; chỉ sao chép giao diện sẽ không đủ để chạy chức năng tư vấn.

Migrations là nguồn tái tạo cấu trúc MySQL. Một máy mới được cấu hình kết nối, chạy migrate và tạo tài khoản quản trị riêng. Việc sửa trực tiếp tên cột trong Workbench có thể làm cấu trúc lệch khỏi model, vì vậy những thay đổi nghiệp vụ nên được thực hiện qua model và migration. Workbench chủ yếu hỗ trợ kiểm tra cấu trúc, xem quan hệ và đối chiếu dữ liệu trong quá trình phát triển.

## 5.2 Giao diện và hành trình người sử dụng

Trang chính đặt tìm kiếm và lối vào tư vấn ở khu vực dễ thấy. Người học có thể bắt đầu bằng tên trường/ngành hoặc nhập hồ sơ để nhận gợi ý. Các thành phần hồ sơ và bộ lọc giúp việc thay đổi điểm, tổ hợp hoặc khu vực không buộc người dùng phải bắt đầu lại toàn bộ quá trình. Với màn hình nhỏ, bố cục giảm số cột và điều chỉnh thanh bên để giữ vùng thao tác chính.

{{FIGURE:gon_ui}}

Kết quả tư vấn được trình bày theo chương trình thay vì chỉ một danh sách tên trường. Mỗi kết quả cần giúp người dùng hiểu đang xem ngành nào, dữ liệu năm nào, điểm quan sát hoặc dự đoán bao nhiêu và điều kiện nào đã được xác minh. Nguồn dữ liệu là điểm nối từ kết quả tổng hợp về thông báo gốc. Việc lưu trường hỗ trợ tạo danh sách xem lại, không đồng nghĩa trường đó đã được xác nhận đủ điều kiện xét tuyển của người dùng.

Ảnh giao diện được lấy từ tư liệu kiểm thử của dự án, minh họa bố cục và chức năng tại thời điểm kiểm tra. Các dữ liệu bài viết hoặc tài khoản xuất hiện trong kịch bản là dữ liệu thử. Đánh giá mức độ dễ dùng của sản phẩm vẫn cần người sử dụng thực tế; ảnh chụp và kịch bản tự động chưa thay thế cho một khảo sát khả dụng có phương pháp.

## 5.3 Đăng nhập và phân quyền

Hệ thống sử dụng một biểu mẫu đăng nhập chung cho thành viên và nhân sự quản trị. Sau khi Django xác thực thông tin, session được tạo và frontend nhận trạng thái người dùng. Cờ staff quyết định khả năng đi vào khu vực quản trị; quyền theo model hoặc quyền công bố quyết định thao tác cụ thể. Cách này đáp ứng yêu cầu người quản trị đăng nhập ngay từ trang sẵn có mà không duy trì một hệ tài khoản tách biệt.

Mật khẩu được quản lý qua cơ chế băm của Django, không lưu dạng văn bản rõ trong cơ sở dữ liệu. Các yêu cầu thay đổi trạng thái dùng session và CSRF. Việc xác định chủ sở hữu nội dung được thực hiện phía backend trước khi sửa hoặc xóa; giao diện chỉ hỗ trợ người dùng nhận biết chức năng có thể thao tác. Nếu gửi yêu cầu trực tiếp đến API, các kiểm tra quyền vẫn phải có hiệu lực.

Khôi phục mật khẩu sử dụng quy trình token và cần SMTP để gửi thư thật. Khi dịch vụ thư chưa được cấu hình, hệ thống thông báo trạng thái đó, không giả báo đã gửi thành công. Trong môi trường bàn giao, thông tin SMTP, khóa API và mật khẩu MySQL được đặt trong .env riêng, không đưa vào báo cáo hoặc gói mã nguồn chia sẻ.

## 5.4 Tra cứu lịch sử và so sánh trường

Tra cứu trường bắt đầu từ danh mục đã chuẩn hóa. Người dùng mở chi tiết để xem các chương trình và lịch sử điểm theo năm. Dữ liệu được giữ cùng nguồn và nhãn phương thức nhằm tránh việc một con số của học bạ bị hiểu thành điểm thi THPT. Khi chỉ có một số năm, giao diện cần thể hiện đúng khoảng dữ liệu còn có, thay vì tự nội suy thành lịch sử đầy đủ.

Chức năng so sánh đặt các lựa chọn cạnh nhau theo những thuộc tính có trong dữ liệu. Việc so sánh có ý nghĩa khi cùng thang và cùng bối cảnh; không dùng điểm của phương thức khác nhau để kết luận trường nào khó vào hơn một cách tuyệt đối. Đối với nội dung chưa có bằng chứng như học phí hoặc cơ hội việc làm, phiên bản hiện tại chưa có cơ sở dữ liệu đầy đủ để đưa ra xếp hạng định lượng.

Bộ lọc khu vực sử dụng metadata đã xác minh, gồm thông tin địa điểm và quy tắc cấp chương trình khi có. Không suy thành phố chỉ từ tên trường, vì trường có thể có nhiều cơ sở hoặc chương trình đặt ở địa điểm khác. Khi thiếu metadata, việc không xuất hiện trong kết quả lọc phản ánh giới hạn dữ liệu, chưa phải kết luận chương trình không tồn tại ở khu vực đó.

## 5.5 Hướng nghiệp theo nhóm sở thích

Chức năng hướng nghiệp sử dụng bộ 24 câu hỏi nội bộ theo sáu nhóm RIASEC. Câu trả lời được tổng hợp thành điểm nhóm, mã sở thích và các ngành gợi ý. Khi lưu, một bản CareerAssessment gắn với người dùng được tạo để có thể xem lại quá trình đánh giá. Kết quả này bổ sung góc nhìn sở thích cho lựa chọn ngành, trong khi điều kiện điểm và tổ hợp vẫn do bộ tư vấn tuyển sinh xử lý.

RIASEC trong sản phẩm có vai trò định hướng tham khảo. Một mã sở thích không quyết định người học chỉ được chọn một nhóm ngành, cũng không thay thế đánh giá năng lực hoặc tư vấn cá nhân. Bộ câu hỏi tiếng Việt của dự án chưa được khảo sát và kiểm định tâm lý như một công cụ chuẩn hóa. Vì vậy, cách trình bày kết quả cần khuyến khích người học đối chiếu với sở thích và trải nghiệm thực tế thay vì coi đây là kết luận nghề nghiệp cuối cùng.

## 5.6 Cộng đồng và kết nối

Không gian cộng đồng cho phép thành viên đăng bài theo nhóm nội dung, thêm ảnh và tạo bình chọn. Bình luận giúp trao đổi ngay dưới bài; lượt thích và lưu bài hỗ trợ tương tác cá nhân. Các ràng buộc duy nhất trong cơ sở dữ liệu ngăn trùng một số tương tác, còn backend kiểm tra nội dung và chủ sở hữu trước khi thực hiện thao tác sửa hoặc xóa.

Ảnh tải lên được kiểm tra kích thước, định dạng và số pixel, đồng thời mã hóa lại trước khi lưu. Tệp được quản lý theo cơ chế media, còn bảng ảnh giữ đường dẫn và quan hệ với bài viết. Cách này giúp kiểm soát tài nguyên và tránh đưa dữ liệu ảnh không hợp lệ trực tiếp vào phần hiển thị. Tuy vậy, kiểm tra tệp không đồng nghĩa nội dung ảnh đã được kiểm duyệt về mọi mặt; quản trị vẫn cần công cụ xử lý nội dung không phù hợp.

Theo dõi và thông báo kết nối các hoạt động giữa thành viên. Tin nhắn trực tiếp có người gửi, người nhận, thời gian và trạng thái đã đọc. Khi đọc lịch sử, API cần giới hạn trong những cuộc trao đổi mà tài khoản hiện tại là một bên, không trả toàn bộ tin nhắn rồi giao cho frontend tự lọc. Sự riêng tư ở đây phụ thuộc vào điều kiện truy vấn và kiểm tra quyền, không chỉ vào việc giao diện không hiển thị ID người dùng khác.

## 5.7 Quản trị nội dung và thành viên

Trang quản trị được tùy biến theo những công việc thường thực hiện: xem tổng quan, quản lý thành viên, hồ sơ và mentor, kiểm duyệt bài viết/bình luận, theo dõi dữ liệu tư vấn và xử lý các đợt tuyển sinh. Các bảng kỹ thuật ít dùng được giảm khỏi menu chính để người quản trị không phải bắt đầu từ toàn bộ danh sách model. Quyền thực tế của tài khoản quyết định nhóm dữ liệu và thao tác được truy cập.

Quản lý thành viên cần tách thông tin hồ sơ khỏi quyền quản trị. Cập nhật vai trò cộng đồng không được tự mở quyền công bố dữ liệu; ngược lại, người có quyền xử lý dữ liệu không nhất thiết phải được cấp mọi quyền hệ thống. Việc chia quyền theo công việc giúp giảm tác động của thao tác nhầm và hỗ trợ phân công khi có nhiều người cùng vận hành.

Đối với nội dung cộng đồng, mục tiêu quản trị là tìm và xử lý bài viết hoặc bình luận cần kiểm tra. Các chức năng sẵn có hỗ trợ tra cứu, lọc và thao tác theo quyền. Tuy nhiên, báo cáo chưa khẳng định hệ thống có bộ phân loại tự động mọi nội dung vi phạm; việc kiểm duyệt trong phiên bản này vẫn dựa trên chức năng quản trị và quyết định của người phụ trách.

## 5.8 Nhập duyệt và thu hồi dữ liệu tuyển sinh

Quy trình nhập bắt đầu bằng CSV theo mẫu. Bộ kiểm tra xác nhận cấu trúc, số dòng, kích thước, danh tính trường, năm, điểm và nguồn HTTPS thuộc miền .edu.vn. Giới hạn hiện tại là 1 MB và 1.000 dòng mỗi tệp; năm nằm trong giai đoạn cho phép từ 2023 đến năm hiện tại; điểm phải hữu hạn, lớn hơn 0 và không quá 1.500. Khoảng kiểm tra điểm rộng để chứa nhiều thang công bố, không phải bằng chứng rằng mọi dòng là điểm THPT thang 30.

Sau khi tệp được chấp nhận, AdmissionRelease ở trạng thái draft lưu nội dung chờ đối chiếu. Người có quyền publish_admissionrelease kiểm tra thông báo gốc và xác nhận trước khi công bố. Bước công bố sử dụng giao dịch và khóa phối hợp, kiểm tra trùng với dữ liệu đã hiển thị rồi cập nhật trạng thái, người xử lý và thời điểm. Cách xử lý này ngăn việc hai thao tác duyệt cùng vượt qua kiểm tra trùng trong một thời điểm.

Luồng trạng thái được giới hạn từ draft sang published và từ published sang withdrawn. Một đợt đã thu hồi không được bật lại trực tiếp thành published; nếu cần sửa, tạo đợt mới và duyệt lại. Thu hồi làm dữ liệu của đợt không còn được dùng trong phần công bố mà vẫn giữ lịch sử xử lý. Quy trình này phù hợp hơn việc xóa hẳn mọi dấu vết khi phát hiện nguồn hoặc nội dung nhập chưa đúng.

Những dòng nhập từ quản trị được đánh dấu comparable_thpt=False, phục vụ tra cứu theo phương thức riêng và không tự đi vào tập huấn luyện. Công bố một tệp không ghi đè CSV sạch, không tự huấn luyện lại mô hình và không tự chuyển thang điểm. Nếu muốn dùng dữ liệu đó cho hồi quy THPT, cần bổ sung một bước kiểm toán và chuẩn hóa ngoại tuyến có bằng chứng tương thích.

## 5.9 Kiểm soát lỗi vận hành và sao lưu

Endpoint health hỗ trợ kiểm tra kết nối database và sự có mặt của những dữ liệu phục vụ cơ bản. Giới hạn yêu cầu được áp dụng ở các luồng cần giảm lạm dụng như đăng nhập và chat. Bộ đếm được lưu trong RequestBucket để nhiều lần gọi có thể được kiểm soát nhất quán hơn việc chỉ đếm trong một biến giao diện. Đây là lớp bảo vệ ứng dụng, chưa thay thế cấu hình giới hạn ở reverse proxy hoặc thử tải hạ tầng.

Ở môi trường phát triển, frontend và backend chạy riêng tại cổng 5173 và 8000. Cấu hình triển khai dự kiến sử dụng module production, WSGI, reverse proxy, HTTPS và cách phục vụ static/media phù hợp. Dự án có mẫu cấu hình và tài liệu triển khai, nhưng chưa có bằng chứng nghiệm thu một hosting hoặc tên miền công khai đang hoạt động. Do đó, trạng thái chạy được tại localhost cần được tách khỏi trạng thái sẵn sàng vận hành thực tế.

Sao lưu cần bao gồm cả MySQL, media, tập dữ liệu phục vụ, mô hình và bằng chứng nguồn nếu cần tái lập. Chỉ sao lưu database sẽ mất phần điểm CSV; chỉ sao lưu mã nguồn sẽ mất các bản ghi nghiệp vụ và tệp ảnh. Gói sao lưu có manifest hỗ trợ kiểm tra thành phần, nhưng trước khi tạo bản nhất quán cần dừng tác vụ ghi hoặc áp dụng cơ chế snapshot phù hợp. Bản sao chứa dữ liệu người dùng phải được quản lý riêng với bộ mã nguồn nộp bài.

Khi khôi phục trên máy khác, cần kiểm tra từng lớp theo thứ tự: môi trường phụ thuộc, kết nối MySQL và migrations, sự có mặt của CSV phục vụ, đường dẫn media, sau cùng là cấu hình dịch vụ ngoài. Một trang chủ tải được chưa chứng minh lịch sử chat, ảnh và tư vấn đã được phục hồi đủ. Bộ kiểm tra sau khôi phục nên bao gồm đăng nhập, đọc một bản ghi nghiệp vụ, mở ảnh và thực hiện một hồ sơ tư vấn có kết quả đã biết.

Đối với bản bàn giao đồ án, .env.example mô tả tên biến cần cấu hình, còn thông tin bí mật được người nhận tạo riêng. Tài khoản quản trị mới được tạo bằng lệnh quản lý của Django thay vì chia sẻ mật khẩu cố định trong mã. Crawler và huấn luyện không nên tự chạy lúc khởi động web vì có thể thay đổi dữ liệu, kéo dài thời gian mở ứng dụng và làm kết quả khác với phiên bản đã kiểm tra. Các tác vụ đó cần được chạy chủ động theo hướng dẫn và đối chiếu đầu ra trước khi đưa vào phục vụ.

# Chương 6 Kiểm thử và đánh giá

## 6.1 Môi trường và cách kiểm tra

Các kết quả được ghi nhận tại mốc 08/11/2026 trên môi trường Windows, Python 3.11 của dự án, Django 5.2.19, Vue 3, Vite và MySQL. Kiểm thử tự động dùng database kiểm thử. Kịch bản trình duyệt sử dụng tài khoản và ảnh tạm, không thêm dữ liệu minh họa vào database nghiệp vụ đang dùng.

Tổng số kiểm thử không đồng nghĩa mọi lỗi đều đã được loại trừ. Connections và career hiện chưa có bộ kiểm thử app riêng trong lượt rà soát; một số chức năng của chúng được kiểm tra qua API đọc hoặc kịch bản tích hợp. Cần tiếp tục mở rộng những ca về quyền riêng tư, dữ liệu không hợp lệ và luồng nhiều người dùng.

## 6.2 Ma trận kết quả

| Nhóm | Nội dung kiểm tra | Kết quả ghi nhận |
|---|---|---|
| Backend | Tài khoản, cộng đồng, AI, giới hạn yêu cầu, admin và vận hành | 83 kiểm thử đạt |
| Crawler | Nguồn, năm, mã, cột phương thức, tổ hợp và thang điểm | 20 kiểm thử đạt |
| Frontend build | Biên dịch và đóng gói Vite | Thành công |
| Trình duyệt | Tư vấn, hồ sơ, ảnh, bình chọn, sửa/xóa bài và nhắn tin | Một kịch bản tích hợp đạt |
| Responsive | Màn hình 1440px và 390px trong kịch bản | Không lỗi JavaScript hoặc tràn ngang được phát hiện |
| Database | Kết nối, migration đã áp dụng, model và migration nhất quán | Đạt; 27 bảng |
| API đọc | Health, danh sách trường, câu hỏi hướng nghiệp, gợi ý kết nối | HTTP 200 ở cả bốn endpoint |
| Bộ QA | Tính nhất quán 250 mẫu, nguồn và phép tính | Đạt |
| Tra điểm có mục tiêu | Bốn câu nguồn xác định, chạy backend | Đạt 4/4 |

Các kiểm thử lỗi nhà cung cấp dùng phản hồi mô phỏng để kiểm tra cách xử lý quota, timeout và cấu hình. Việc các kiểm thử này đạt không khẳng định nhà cung cấp thực tế không lỗi.

## 6.3 Trường hợp kiểm tra có bằng chứng

| Câu hỏi hoặc hồ sơ | Kết quả dùng để đối chiếu |
|---|---|
| CNTT Đại học Tân Tạo năm 2026 | Mã 7480201, điểm 15,00 |
| Vật lý kỹ thuật UET năm 2026 | Mã CN3, điểm 25,41 |
| Cơ kỹ thuật UET năm 2026 | Mã CN4, điểm 26,13 |
| CNTT CMC năm 2026 | Mã IT, cột thang 30 công bố 18,98; dữ liệu phương thức riêng |
| 23 điểm, A00, mã 7510303, Nghệ An | Có ngành Điều khiển và tự động hóa của trường Vinh trong kết quả chính; điểm dự đoán 2027 là 22,50 |

Bốn câu tra lịch sử được chạy ở chế độ backend, không gọi Gemini trong đợt rà soát cuối. Trường hợp CMC minh họa việc giữ cột thang 30 do trường công bố để tra cứu mà không tự coi là dữ liệu THPT thuần dùng huấn luyện. Hồ sơ Vinh minh họa dữ liệu và địa điểm mới đã đi vào dịch vụ tư vấn.

## 6.4 Đánh giá mục tiêu

Đề tài đã hình thành các thành phần chính của một website tư vấn tuyển sinh: dữ liệu có nguồn, tra cứu theo điều kiện, dự đoán có đánh giá, hội thoại, cộng đồng và quản trị. Những luồng được kiểm tra có thể sử dụng để demo đồ án. Điểm mạnh là khả năng kiểm tra lại số liệu và việc giữ rõ các giới hạn của kết quả tư vấn.

Các hạn chế hiện tại tập trung ở dữ liệu và nghiệm thu thực tế. Metadata khu vực mới có 50 dòng; nguồn và mã chương trình giữa các năm còn có trường hợp cần đối chiếu; chưa có đánh giá hội thoại độc lập diện rộng hoặc khảo sát người dùng có phương pháp. Kết quả mô hình cũng chưa được xác nhận bằng điểm thực tế năm 2027.

## 6.5 Giới hạn triển khai

Kiểm tra check --deploy trên cấu hình phát triển hiện tại báo sáu cảnh báo liên quan DEBUG, secret, HTTPS, cookie và HSTS. Đây là trạng thái môi trường localhost, không phải kết quả nghiệm thu cấu hình production đã triển khai. Module production có cơ chế kiểm tra cấu hình riêng; trước khi mở công khai cần cấu hình tên miền, HTTPS, SMTP, quota, logging, lịch backup và thử khôi phục MySQL.

## 6.6 Nhận xét kết quả và tiêu chí hoàn thiện

Các kết quả đã ghi nhận cho thấy luồng chính có thể thực hiện từ đầu đến cuối trên môi trường kiểm tra: đăng nhập, cập nhật hồ sơ, tư vấn theo điều kiện, tương tác cộng đồng và quản trị dữ liệu. Những kiểm tra về nguồn, phương thức và thang điểm có vai trò trực tiếp đối với độ đúng của tư vấn. Nếu bỏ qua lớp này, số lượng bản ghi tăng vẫn có thể làm hệ thống trả lời kém chính xác hơn.

Ở phần dự đoán, kết quả cần được đọc theo từng thước đo. LastScore có MAE tốt nhất trên tập năm 2026, còn GradientBoosting có RMSE thấp hơn. Điều đó cho thấy một phương pháp có thể tốt hơn ở sai số trung bình tuyệt đối nhưng chưa tối ưu cho những sai lệch lớn. Lựa chọn phương pháp phục vụ là quyết định thực nghiệm theo tiêu chí hiện tại, không phải kết luận rằng học máy không có ích đối với mọi dữ liệu tuyển sinh.

Đối với hội thoại, bộ QA và bốn trường hợp tra cứu chứng minh một số quy tắc, dữ liệu và đường xử lý đang nhất quán. Chúng chưa chứng minh khả năng hiểu mọi cách diễn đạt tiếng Việt hoặc duy trì hội thoại dài. Một đợt đánh giá tiếp theo cần bộ câu hỏi tách khỏi quá trình phát triển, chấm câu trả lời bằng nguồn cố định và thử cả trường hợp đổi hồ sơ, hỏi cho người khác, thiếu năm, nhầm phương thức và dịch vụ ngoài lỗi.

Tiêu chí hoàn thiện nên được ưu tiên theo tác động: trước hết giữ dữ liệu đúng và nguồn rõ; tiếp theo bảo vệ quyền riêng tư và các thao tác ghi; sau đó cải thiện cách diễn đạt, tốc độ và tiện ích. Với phạm vi đồ án hiện tại, kết luận phù hợp là nguyên mẫu đã tích hợp các thành phần chính và có bằng chứng kiểm thử các luồng quan trọng. Việc mở rộng dùng thật cần thêm nghiệm thu trên hạ tầng đích và đánh giá với người sử dụng.


# Chương 7 Kết luận và hướng phát triển

## 7.1 Kết luận

UniConnect AI đã giải quyết bài toán tích hợp tra cứu tuyển sinh và tư vấn trong một nguyên mẫu web có các chức năng liên kết. Sản phẩm cung cấp nguồn cho dữ liệu, đánh giá các phương pháp dự đoán và có cơ chế quản trị nội dung cũng như dữ liệu nhập. Những kiểm thử hiện có tạo cơ sở để chốt phiên bản phần mềm phục vụ nộp và trình diễn trong phạm vi đề tài.

Kết quả dự đoán cho thấy LastScore là mốc cơ sở hiệu quả về MAE trên dữ liệu kiểm định hiện tại. Việc lựa chọn phương pháp đơn giản hơn được giữ minh bạch, đồng thời RandomForest và các mô hình khác cung cấp đối chiếu thực nghiệm. Trợ lý hội thoại sử dụng kết quả truy xuất làm cơ sở và có đường xử lý khi dịch vụ ngoài không sẵn sàng.

## 7.2 Hướng phát triển

Ưu tiên tiếp theo là mở rộng dữ liệu chính thức và metadata địa điểm, xác minh mã chương trình và biến thể qua các năm, đồng thời xây dựng lịch cập nhật có người duyệt. Với phương thức tổng hợp hoặc thang điểm khác, cần mô hình dữ liệu riêng để thể hiện điều kiện thay vì ép vào một thang chung.

Ở phần AI, cần đánh giá dự đoán trên dữ liệu năm mới và chấm hội thoại bằng bộ câu hỏi độc lập, bao gồm độ đúng nguồn, đúng năm, đúng phương thức và phản hồi khi thiếu dữ liệu. Có thể thử thêm đặc trưng khi có nguồn phù hợp, nhưng chỉ chấp nhận nếu cải thiện được đánh giá theo thời gian.

Ở phần ứng dụng, nên mở rộng kiểm thử hướng nghiệp/kết nối, kiểm thử đầu cuối đăng nhập và phân quyền quản trị, đánh giá khả dụng bằng người dùng thực tế. Triển khai công khai cần thử tải, bảo vệ thông tin cá nhân và quy trình phục hồi đã được kiểm chứng trên môi trường đích.

# Tài liệu tham khảo

[1] Vue.js. Introduction. https://vuejs.org/guide/introduction.html. Truy cập ngày 08/11/2026.

[2] Django Software Foundation. Django at a glance, Django 5.2 documentation. https://docs.djangoproject.com/en/5.2/intro/overview/. Truy cập ngày 08/11/2026.

[3] scikit-learn. Metrics and scoring: quantifying the quality of predictions. https://scikit-learn.org/stable/modules/model_evaluation.html. Truy cập ngày 08/11/2026.

[4] National Center for O*NET Development. O*NET Interest Profiler. https://www.onetcenter.org/IP.html. Truy cập ngày 08/11/2026. Dùng để tham khảo sáu nhóm sở thích, không khẳng định bộ câu hỏi dự án là bản chuẩn hóa của O*NET.

[5] Trường Đại học Công nghệ Kỹ thuật Vinh. Quyết định công bố điểm trúng tuyển đại học chính quy đợt 1 năm 2026. https://vuted.edu.vn/tin-tuc-17/cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026-dot-3753. Bản nguồn lưu trong data/raw/recovery_20261108/.

[6] Trường Đại học Công nghệ Thông tin, ĐHQG TP.HCM. Thông báo điểm trúng tuyển phương thức kết quả thi tốt nghiệp THPT năm 2025. https://tuyensinh.uit.edu.vn/node/4147. Bản nguồn lưu trong data/raw/recovery_20261108/.

[7] Dự án UniConnect AI. Mã nguồn, migrations và tệp dữ liệu tại mốc rà soát ngày 08/11/2026. Tài liệu nội bộ: GIAI_THICH_CAC_BANG_MYSQL.md; RA_SOAT_TRUOC_KHI_NOP_20261108.md; BO_SUNG_DU_LIEU_20261108.md.

[8] Dự án UniConnect AI. coverage_summary.json; cutoff_model_metrics_2026_holdout.csv; best_cutoff_model_metadata.json; DATA_RECOVERY_CHECK_20261108.json; RECOVERY_API_CHECK_20261108.json. Kết quả thực nghiệm nội bộ, không phải công bố khoa học bên ngoài.

# Phụ lục A Danh mục bảng MySQL

| Bảng | Nội dung |
|---|---|
| auth_user | Tài khoản và cờ quyền |
| accounts_profile | Hồ sơ và mục tiêu tư vấn |
| auth_group | Nhóm quyền |
| auth_permission | Quyền theo model |
| auth_user_groups | Quan hệ tài khoản–nhóm |
| auth_group_permissions | Quan hệ nhóm–quyền |
| auth_user_user_permissions | Quyền cấp trực tiếp |
| social_post | Bài viết và lựa chọn bình chọn |
| social_comment | Bình luận |
| social_postimage | Ảnh của bài viết |
| social_postlike | Lượt thích |
| social_savedpost | Bài viết đã lưu |
| social_pollvote | Phiếu bình chọn |
| social_notification | Thông báo tương tác |
| social_directmessage | Tin nhắn trực tiếp |
| connections_userfollow | Quan hệ theo dõi |
| catalog_saveduniversity | Trường đã lưu |
| career_careerassessment | Kết quả hướng nghiệp |
| ai_chat_aichatsession | Cuộc hội thoại AI |
| ai_chat_aichatmessage | Tin nhắn hội thoại AI |
| django_content_type | Danh mục model Django |
| django_admin_log | Nhật ký admin |
| django_session | Phiên đăng nhập |
| django_migrations | Phiên bản lược đồ đã áp dụng |
| catalog_admissionrelease | Đợt nhập và duyệt dữ liệu tuyển sinh |
| catalog_admissionreleaselock | Khóa phối hợp duyệt dữ liệu |
| config_requestbucket | Bộ đếm giới hạn yêu cầu |

# Phụ lục B Cài đặt và tái lập kết quả

Máy chạy cần Python phù hợp với requirements, Node.js/npm và MySQL. Tạo môi trường ảo, cài requirements-web.txt, cấu hình .env từ .env.example, khởi tạo database và chạy migrations. Tạo tài khoản quản trị bằng createsuperuser. Tại frontend, cài bằng npm ci rồi chạy npm run dev; hướng dẫn chi tiết nằm ở README.md.

Muốn tái huấn luyện, dùng môi trường có requirements-training.txt và dữ liệu nguồn cần thiết. Trình tự chính là prepare_dataset_4years_FINAL.py, kiểm toán nguồn, train_cutoff_models.py, audit_data.py và build_qa_dataset.py. Không chạy lại bộ cào hoặc ghi dữ liệu đồng thời trong lúc tạo bản sao nhất quán.

Các tệp .env, mật khẩu, API key, .venv, node_modules và bản sao có dữ liệu cá nhân không nằm trong báo cáo. Khi bàn giao nguồn và dữ liệu, cần nêu rõ những tệp cần thiết để chạy web và những tệp bổ sung để tái lập crawler/huấn luyện.

DDL đầy đủ nằm tại docs/bao_cao/so_do/schema_mysql.sql; ERD toàn bộ bảng dạng Mermaid nằm tại docs/bao_cao/so_do/erd_mysql_day_du.mmd. Hai tệp giúp đối chiếu cấu trúc khi bàn giao mà không cần đưa toàn bộ cột và sơ đồ 27 bảng vào phần trình bày chính. DDL chỉ chứa cấu trúc, không chứa bản ghi nghiệp vụ hoặc thông tin đăng nhập. Nếu thực thi để dựng mô hình, sử dụng database rỗng riêng.

Để tái lập các số liệu trong báo cáo, cần giữ cùng phiên bản tập sạch, metadata, kết quả huấn luyện và báo cáo kiểm tra. Số lượng bản ghi có thể thay đổi khi thu thập thêm nguồn; khi đó phải tính lại thống kê, chỉ số đánh giá và kết luận trên cùng mốc dữ liệu. Không thay một con số riêng lẻ trong bảng kết quả mà giữ nguyên những phần giải thích phụ thuộc vào nó.

