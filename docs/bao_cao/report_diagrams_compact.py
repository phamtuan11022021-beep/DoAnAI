"""Eight legible figures for the revised portrait report."""
import json
from pathlib import Path
from PIL import Image
from diagram_canvas import Canvas, ASSETS, SOURCES, MANIFEST

def generate():
 MANIFEST.clear()
 c=Canvas('gon_bfd','Phân rã chức năng UniConnect AI',1200,980)
 c.node('root','UNICONNECT AI',350,90,500,85,size=30)
 c.line([(600,175),(600,220),(20,220),(20,840)],arrow=False)
 groups=[('Tài khoản','Đăng nhập và phân quyền\nHồ sơ và khôi phục mật khẩu'),('Tra cứu tuyển sinh','Tìm trường ngành và lịch sử điểm\nSo sánh và lưu trường'),('Tư vấn và hướng nghiệp','Tư vấn hồ sơ và hội thoại\nTrắc nghiệm RIASEC'),('Cộng đồng','Bài viết bình luận và bình chọn\nTheo dõi thông báo và nhắn tin'),('Quản trị','Thành viên và kiểm duyệt\nNhập duyệt và thu hồi dữ liệu'),('Dữ liệu và mô hình','Cào nguồn và chuẩn hóa\nHuấn luyện đánh giá và sao lưu')]
 for i,(title,body) in enumerate(groups):
  x=55+(i%2)*575;y=265+(i//2)*220
  c.rect((x,y,x+520,y+175),'white');c.rect((x,y,x+520,y+53),'#edf0f4')
  c.text(x+260,y+27,title,28,True)
  for j,line in enumerate(c.wrap(body,490,25)):c.text(x+260,y+88+j*34,line,25)
  if i%2==0:c.line([(20,y+88),(x,y+88)],arrow=False)
  else:c.line([(600,220),(600,y+88),(x,y+88)],arrow=False)
 c.finish()

 c=Canvas('gon_architecture','Kiến trúc ứng dụng và các lớp dữ liệu',1200,800)
 for k,label,x,y,w in [('vue','Vue 3 và Vite\nGiao diện người dùng',30,175,330),('api','Django API\nNghiệp vụ và xác thực',440,175,330),('sql','MySQL\nTài khoản và nghiệp vụ',850,95,320),('csv','CSV điểm và dự đoán\nTra cứu tính sẵn',850,345,320),('ai','Gemini\nHội thoại qua backend',440,600,330),('off','Crawler và training\nXử lý ngoại tuyến',850,600,320)]:c.node(k,label,x,y,w,125,size=27)
 c.edge('vue','api','HTTP','right','left',at=(400,210));c.edge('api','sql','ORM','right','left',at=(810,160));c.edge('api','csv','Đọc','right','left',at=(810,370));c.edge('api','ai','HTTPS',at=(605,465));c.edge('off','csv','Cập nhật',side_a='top',side_b='bottom',at=(1010,535));c.finish()

 c=Canvas('gon_erd','Quan hệ nghiệp vụ trọng tâm',1200,930)
 for key,label,x,y,w in [('user','Tài khoản',430,130,340),('profile','Hồ sơ',20,130,320),('session','Cuộc hội thoại',860,130,320),('post','Bài viết',430,440,340),('comment','Bình luận',20,750,320),('message','Tin nhắn AI',860,750,320)]:c.node(key,label,x,y,w,105,size=29)
 c.edge('user','profile','1 / 0..1','left','right',at=(385,110),arrow=False,crow=False)
 c.edge('user','session','0..1 / 0..N','right','left',at=(815,110),arrow=False,crow=True)
 c.edge('user','post','1 / 0..N',at=(600,330),arrow=False,crow=True)
 c.edge('post','comment','1 / 0..N',at=(350,650),arrow=False,crow=True)
 c.edge('session','message','1 / 0..N',side_a='bottom',side_b='top',at=(1020,490),arrow=False,crow=True)
 c.finish('Bội số ghi theo phía tài khoản hoặc cha / phía con; các quan hệ còn lại được giải thích trong nội dung.')

 c=Canvas('gon_sql','Lược đồ SQL các bảng tư vấn và tài khoản',1200,1010)
 cards=[('auth_user',['PK id : int','username : varchar(150) UQ','password : varchar(128)','is_staff / is_superuser : tinyint(1)']),('accounts_profile',['PK id : bigint','FK user_id : int UQ','role : varchar(20)','expected_score : decimal(4,2) NULL']),('ai_chat_aichatsession',['PK id : bigint','FK user_id : int NULL','session_key : varchar(64)','context : json']),('ai_chat_aichatmessage',['PK id : bigint','FK conversation_id : bigint','role : varchar(20)','content : longtext']),('catalog_saveduniversity',['PK id : bigint','FK user_id : int','university_key : varchar(220)','UQ (user_id, university_key)']),('catalog_admissionrelease',['PK id : bigint','FK created_by_id : int NULL','FK reviewed_by_id : int NULL','rows : json; status : varchar(12)'])]
 for i,(name,fields) in enumerate(cards):
  x=30+(i%2)*610;y=90+(i//2)*275
  c.rect((x,y,x+530,y+225),'white');c.rect((x,y,x+530,y+49),'#edf0f4');c.text(x+265,y+25,name,25,True)
  for j,line in enumerate(fields):c.text(x+15,y+80+j*35,line,26,anchor='lm')
 # Relations run through the central gutter or the space between rows.
 c.line([(640,205),(560,205)],arrow=True)
 c.line([(295,365),(295,340),(16,340),(16,205),(30,205)],arrow=True)
 c.line([(640,480),(560,480)],arrow=True)
 c.text(600,910,'Các FK user_id created_by_id reviewed_by_id tham chiếu auth_user.id',25)
 c.text(600,950,'conversation_id tham chiếu ai_chat_aichatsession.id; các cột đã được rút gọn',25)
 c.finish()

 c=Canvas('gon_crawler','Luồng thu thập và chuẩn hóa dữ liệu',1200,1120)
 steps=[('source','Chọn trường năm và thông báo nguồn','process'),('fetch','Tải HTML PDF hoặc ảnh và lưu bằng chứng','process'),('valid','Xác định đúng trường năm và phương thức?','decision'),('parse','Trích mã ngành tên chương trình điểm và tổ hợp','process'),('compatible','Điểm THPT tương thích và không xung đột?','decision'),('clean','Chuẩn hóa hợp nhất bản trùng có cùng điểm','process'),('save','Xuất CSV sạch metadata và báo cáo độ phủ','end')]
 for i,(k,label,kind) in enumerate(steps):
  c.node(k,label,410,90+i*140,750,100,kind,28)
  if i:c.edge(steps[i-1][0],k,'Có' if steps[i-1][2]=='decision' else '')
 c.node('reject','Dừng và rà soát\nnguồn chưa xác minh',20,365,310,110,'end',27);c.edge('valid','reject','Không','left','right',at=(365,395))
 c.node('other','Lưu riêng theo phương thức\nhoặc cách ly xung đột',20,640,310,120,'end',26);c.edge('compatible','other','Không','left','right',at=(365,675))
 c.finish('Điểm phương thức riêng có thể phục vụ tra cứu; không tự đưa vào tập huấn luyện THPT.')

 c=Canvas('gon_activity','Luồng hoạt động tư vấn và quản trị',1200,1120)
 for k,label,x,y,w,h,kind in [('start','Mở ứng dụng',400,95,400,85,'start'),('choice','Chọn chức năng',400,270,400,90,'process'),('lookup','Tra cứu hoặc tư vấn\nNhập hồ sơ và điều kiện',25,465,520,115,'process'),('admin','Đăng nhập quản trị\nKiểm tra quyền thao tác',655,465,520,115,'process'),('check','Kiểm tra đầu vào\nvà bằng chứng dữ liệu',25,680,520,115,'process'),('publish','Nhập và đối chiếu CSV\nCông bố hoặc thu hồi',655,680,520,115,'process'),('end','Hiển thị kết quả hoặc lỗi có lý do',310,955,580,90,'end')]:c.node(k,label,x,y,w,h,kind,28)
 c.edge('start','choice');c.edge('choice','lookup');c.edge('choice','admin');c.edge('lookup','check');c.edge('admin','publish');c.edge('check','end');c.edge('publish','end');c.finish()

 c=Canvas('gon_ml','Chia tập theo thời gian và tạo dự đoán',1200,810)
 rows=[('Chọn mô hình',['Đặc trưng từ quá khứ','Train mục tiêu 2024','Validation năm 2025']),('Kiểm định',['Fit lại mục tiêu 2024–2025','7.453 mẫu huấn luyện','3.776 mẫu test năm 2026']),('Phục vụ năm 2027',['Refit ML trên 2024–2026','11.229 mẫu khi refit','Phục vụ Baseline LastScore'])]
 for i,(head,items) in enumerate(rows):
  y=150+i*225;c.text(600,y-35,head,29,True)
  for j,label in enumerate(items):
   c.node(f'n{i}_{j}',label,25+j*405,y,340,105,size=27)
   if j:c.edge(f'n{i}_{j-1}',f'n{i}_{j}',side_a='right',side_b='left')
 c.finish('Năm mục tiêu không được đưa vào đặc trưng của chính năm đó; mô hình phục vụ do kiểm định quyết định.')

 here=Path(__file__).resolve().parent
 im=Image.open(here.parent/'ui_review_campus/advisor-desktop.png')
 im=im.crop((0,0,im.width,min(im.height,1050)));im.save(ASSETS/'gon_ui.png')
 MANIFEST['gon_ui']={'title':'Giao diện tư vấn UniConnect AI','image':'assets/gon_ui.png','landscape':False,'width':im.width,'height':im.height}
 (SOURCES/'danh_muc_so_do_tinh_gon.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')
 return MANIFEST.copy()

if __name__=='__main__':print(len(generate()))
