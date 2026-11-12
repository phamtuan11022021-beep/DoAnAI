# Triển khai và sao lưu UniConnect AI

## Trạng thái

Django đã nâng lên 5.2.19 và chạy kiểm thử với MySQL. Chưa triển khai lên
hosting/tên miền thật trong đợt này. Cấu hình Nginx là mẫu, cần thay đường dẫn,
tên miền và chứng chỉ, sau đó kiểm tra bằng `nginx -t` trên máy chủ đích.

## Cấu hình production

Hướng dẫn khởi động local nằm ở [README](../README.md), cách đọc bảng ở
[Giải thích MySQL](GIAI_THICH_CAC_BANG_MYSQL.md), thao tác quản trị ở
[Hướng dẫn quản trị](QUAN_TRI_DE_SU_DUNG.md). Các mục bên dưới gộp phần cấu hình
còn cần dùng từ các tài liệu MySQL và nhà cung cấp AI trước đây.

1. Cài `requirements-web.txt`; build frontend bằng `npm ci` và `npm run build`.
2. Điền MySQL, nhà cung cấp AI, secret ngẫu nhiên đủ dài (ít nhất 50 ký tự),
   domain và CSRF origin HTTPS trong biến môi trường hoặc `.env` riêng của máy chủ.
   Không chép secret vào frontend, tài liệu hoặc Git. Không dùng root MySQL cho web.
3. Dùng `DJANGO_SETTINGS_MODULE=config.production` khi chạy các lệnh production.
   Module này ép DEBUG=false, kiểm tra secret/domain/CSRF và bật cookie HTTPS.
4. Chạy migrate, `setup_admin_roles`, `collectstatic --noinput` và `check --deploy`.
5. Dùng Nginx phục vụ `frontend/dist`, `backend/staticfiles`, `backend/media`;
   chuyển `/api/` và `/admin/` tới WSGI. Mẫu: `deploy/nginx.conf.example`.
6. Chạy worker bằng `python backend/serve.py` trong môi trường đã cài dependency.
   Worker chỉ nghe `127.0.0.1:8000`, tin một proxy ở loopback. Proxy phải ghi đè
   X-Forwarded-For/Proto/Host như mẫu để IP người dùng và giới hạn yêu cầu đúng.
   Không đưa trực tiếp worker này ra Internet hoặc tin proxy `*`.
7. Thiết lập service tự khởi động lại, kiểm tra `/api/health/`, logging, lịch
   dọn bộ đếm và sao lưu. Thử đăng nhập, upload ảnh, tra điểm và chat qua HTTPS.

Ví dụ trong PowerShell trước khi kiểm tra cấu hình production:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.production'
.venv/Scripts/python.exe -X utf8 backend/manage.py check --deploy
.venv/Scripts/python.exe -X utf8 backend/manage.py collectstatic --noinput
```

Không bật production trên localhost HTTP khi đang phát triển: cookie secure
và redirect HTTPS được thiết kế cho tên miền có chứng chỉ.

`DJANGO_HSTS_SECONDS` mặc định 3.600 giây. Include-subdomains và preload mặc
định tắt vì chưa có danh sách subdomain của máy chủ thật. Kiểm tra production
còn có thể báo W005/W021 về hai chính sách này; không bật chỉ để làm hết cảnh
báo. Chỉ bật khi mọi subdomain phù hợp HTTPS và đã quyết định đăng ký preload.
Không có mã nào tự tắt/ẩn các cảnh báo kiểm tra này.

Tham khảo [Django deployment](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
và [Waitress proxy headers](https://docs.pylonsproject.org/projects/waitress/en/latest/arguments.html).

## MySQL và chuyển dữ liệu từ SQLite

Điền `DB_ENGINE=mysql`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`,
`MYSQL_USER`, `MYSQL_PASSWORD` theo `.env.example`. Django đọc `.env` ở gốc dự án;
biến môi trường có sẵn được ưu tiên. Dùng database InnoDB, charset `utf8mb4`;
khi chuyển dữ liệu cũ, dùng collation `utf8mb4_bin` để giữ phân biệt hoa/thường
của các khóa duy nhất. Nếu hosting yêu cầu TLS, cấu hình `MYSQL_SSL_CA`.

Với database mới, chạy `migrate`, `setup_admin_roles` và `createsuperuser` theo
README. Nếu tài khoản có quyền tạo database, `manage.py init_mysql` tạo database
khi chưa có; không cần chạy nếu hosting đã cấp database. Kiểm tra bằng:

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py check --database default
.venv/Scripts/python.exe -X utf8 backend/manage.py migrate --check
```

Để chuyển SQLite cũ sang **database MySQL trống riêng**, dừng các tác vụ đang ghi
và chạy `manage.py import_sqlite --source backend/db.sqlite3`. Lệnh tạo snapshot,
chạy migrations, giữ khóa chính và mật khẩu đã băm, rồi kiểm tra số bản ghi trong
giao dịch. Đích đã có dữ liệu ứng dụng sẽ bị từ chối; không xóa database đang dùng
để cố nhập lại. Khi lỗi, phần nhập rollback nhưng schema migrations có thể đã tạo.

Trong MySQL Workbench, kết nối đúng host/port, chọn tab **Schemas**, bấm Refresh
và mở database theo `MYSQL_DATABASE`. Dùng `SHOW TABLES;` hoặc tệp
`docs/VIEW_MYSQL.sql` để xem cấu trúc. MySQL lưu tài khoản và nghiệp vụ; điểm
chuẩn hóa/dự đoán vẫn ở CSV. Ảnh nằm trong `backend/media/`.

## Cấu hình dịch vụ hội thoại

`CHAT_PROVIDER` nhận `gemini`, `openai` hoặc `ollama`. Nên đặt rõ provider;
khi biến này chưa có, mã hiện tại ưu tiên Gemini nếu có key Gemini, tiếp theo
OpenAI nếu có key tương ứng, rồi Ollama. Chọn provider không làm tự tải mô hình
hoặc tự chuyển sang nhà cung cấp khác khi lỗi. Khởi động lại backend sau khi đổi.

| Provider | Các biến cấu hình chính |
|---|---|
| Gemini | `CHAT_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT`, `GEMINI_MAX_OUTPUT_TOKENS` |
| OpenAI | `CHAT_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT`, `OPENAI_MAX_OUTPUT_TOKENS` |
| Ollama | `CHAT_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX`, `OLLAMA_KEEP_ALIVE` |

Tên model cấu hình theo quyền truy cập và dịch vụ của môi trường đang dùng;
các giá trị mẫu nằm trong `.env.example` và `backend/config/settings.py`.
Key chỉ đặt ở backend, không đặt vào `VITE_*`, frontend hoặc tài liệu bàn giao.
Provider cloud có thể nhận câu hỏi, hồ sơ, bằng chứng và một phần lịch sử;
cần trình bày luồng này trong chính sách dữ liệu của website.

Với Ollama, cài dịch vụ trên máy chạy model và tải đúng tên trong `OLLAMA_MODEL`.
Địa chỉ mặc định trong mã là `http://127.0.0.1:11434`. Ví dụ với model mặc định
hiện tại: `ollama pull qwen3:8b-q4_K_M`; dùng `ollama serve` nếu dịch vụ chưa chạy.
Không cần API key cho adapter local hiện tại. Không cần Ollama khi chỉ dùng cloud.

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py check_chat --diagnose
.venv/Scripts/python.exe -X utf8 backend/manage.py check_chat --admissions
# Chỉ khi sử dụng Ollama:
.venv/Scripts/python.exe -X utf8 backend/manage.py check_ollama --generate
```

Các lệnh gọi dịch vụ thật cần mạng/model và có thể tiêu thụ hạn mức API.
`--diagnose` in trạng thái/mã lỗi an toàn; không in key. Kết quả tra cứu thành công
có thể đến từ `evidence_fallback`, nên không tự chứng minh cloud đang hoạt động.
Gemini có thử lại hữu hạn và cooldown qua `GEMINI_MAX_RETRIES`,
`GEMINI_RETRY_BUDGET`; hạn mức hoặc cấu hình sai không được giải quyết bằng cách
tạo thêm key tùy ý. Phân biệt lỗi xác thực/cấu hình, quota, giới hạn tốc độ và timeout
trước khi điều chỉnh. Kiểm tra hạn mức và quyền model trên tài khoản nhà cung cấp.

Hội thoại lấy số liệu từ backend, giữ context và tối đa sáu tin gần nhất theo giới
hạn dung lượng. Một số câu trả lời cục bộ không cần gọi cloud; lỗi service phù hợp
có thể dùng bằng chứng nội bộ. Mô hình hội thoại diễn đạt kết quả, còn dự đoán điểm
là pipeline riêng; không mặc định rằng Ollama hoặc Gemini tự dự đoán điểm chuẩn.

Khi đóng gói web, giữ `backend/`, `ai/recommendation_engine.py`, metadata model
và `data/dataset/`. Cài `requirements-web.txt`; huấn luyện/OCR chạy riêng với
`requirements-training.txt`. Không cần mang `.venv`, `node_modules`, nguồn OCR
hoặc trọng số `.joblib` lên máy chỉ phục vụ CSV. Bản sao lưu phục vụ tái lập vẫn
cần giữ dữ liệu nguồn và mô hình theo mục sao lưu bên dưới.

## Email khôi phục mật khẩu

Điền `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`EMAIL_USE_TLS` và `DEFAULT_FROM_EMAIL` trên máy chủ. Mật khẩu SMTP không
phải mật khẩu đăng nhập web. Mặc định TLS/587; cấu hình này dành cho SMTP STARTTLS.

Link **Quên mật khẩu?** nằm trong form đăng nhập. Khi chưa cấu hình SMTP,
trang báo dịch vụ chưa sẵn sàng. Khi đã cấu hình, phản hồi không cho biết email
có tồn tại hay không. Token hết hạn sau một giờ, dùng một lần; mật khẩu mới
tiếp tục được kiểm tra theo chính sách Django. Chưa gửi thư thật từ tài khoản
người dùng trong đợt kiểm thử này; kiểm thử dùng hộp thư trong bộ nhớ.

## Giới hạn yêu cầu

- Đăng nhập: mặc định 20 yêu cầu/phút/IP.
- Chat: 6 yêu cầu/phút/tài khoản; khách chưa đăng nhập tính theo IP.
- Chat còn có trần 30 yêu cầu/phút/IP; đăng ký và xin khôi phục: 5/10 phút/IP.
- Trả HTTP 429 với `Retry-After`; bộ đếm MySQL dùng chung giữa các worker,
  lưu HMAC thay vì địa chỉ IP thô. Đây là cửa sổ cố định, không thay thế bảo vệ
  DDoS ở tầng mạng hoặc giới hạn đồng thời/quota tại nhà cung cấp AI.
- Lập lịch mỗi giờ: `python backend/manage.py cleanup_limits`.

## Sao lưu và thử khôi phục

Dừng web worker, tác vụ cào dữ liệu và tác vụ ghi dữ liệu trước khi tạo bản sao
nhất quán. Sau đó:

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py backup_project --maintenance-confirmed
```

Tệp ZIP trong `backups/` gồm dữ liệu nghiệp vụ, media, dataset, dữ liệu xử lý,
mô hình, QA và bằng chứng `data/raw`. Có manifest SHA-256 và kiểm tra CRC.
Không chứa `.env`; bản sao chứa dữ liệu cá nhân và hash mật khẩu nên phải lưu
riêng, hạn chế quyền truy cập, có bản ngoài máy chủ và chính sách lưu trữ.
CLI không tự đưa bản sao lên dịch vụ khác hoặc tự tạo lịch chạy.

Thử tính toàn vẹn và nạp dữ liệu vào SQLite **tạm**, không đụng MySQL đang dùng:

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py verify_backup backups/TEN_BAN_SAO.zip
```

Lệnh đối chiếu hash mọi tệp, tạo database tạm, migrate, nạp fixture và kiểm tra
số bản ghi theo model. Đây không thay thế thử phục hồi MySQL trên máy chủ đích.
Để phục hồi thật: dùng một database MySQL trống riêng, migrate cùng phiên bản
mã nguồn, nạp `database.json` bằng `loaddata`, phục hồi các thư mục media/data/model,
kiểm tra chức năng rồi mới chuyển dịch vụ sang database đó. Không nạp đè lên
database đang có người dùng. `.env`, secret, SMTP và cấu hình hosting phải được
khôi phục từ nơi quản lý bí mật riêng.

## Việc cần chốt trước khi mở công khai

Tên miền/hosting/chứng chỉ thật; SMTP; thông tin liên hệ và thời hạn lưu dữ liệu;
quota AI, thử tải; lịch backup và một lần thử phục hồi MySQL. Các giá trị này
phụ thuộc môi trường vận hành, không được tự bịa trong cấu hình mẫu.
