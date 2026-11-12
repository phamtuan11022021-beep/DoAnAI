"""Short conversational responses and explicit changes of applicant."""
import re


def new_profile_request(message):
    from .engine import normalize
    text=normalize(message)
    return any(re.search(rf'\b{phrase}\b',text) for phrase in
        ['ban toi','ban minh','ban em','nguoi ban','toi co ban','em co ban','minh co ban',
         'cho nguoi khac','em trai','em gai','con toi','con minh','ho so moi','bat dau lai',
         'con minh thi','con toi thi'])


def quick_reply(message,context):
    from .engine import normalize
    text=normalize(message)
    text=re.sub(r'[^a-z0-9 ]','',text).strip()
    reply=None
    intent='general'
    suggestions=[]
    choosing = any(phrase in text for phrase in ['chon nganh nao','chon nhanh nao','nen hoc nganh gi','chua biet chon nganh','nganh gi phu hop'])
    if choosing:
        context['major']=''
        context['major_code']=''
    if (choosing or new_profile_request(message)) and not context.get('major'):
        actor='Bạn ấy' if context.get('profile_subject') == 'other' else 'Bạn'
        score=context.get('score')
        prefix=f'Với {float(score):g} điểm, mình có thể giúp khoanh vùng lựa chọn. ' if score is not None else ''
        reply=prefix+f'{actor} thích lĩnh vực nào và học tốt những môn nào? Cho mình biết thêm tổ hợp xét tuyển và khu vực muốn học nhé; chỉ điểm số thôi chưa đủ để chọn ngành phù hợp.'
        return {'intent':'clarification','text':reply,'cards':[],
                'suggestions':['Thích công nghệ và tính toán','Thích kinh doanh và giao tiếp','Chưa rõ sở thích, muốn hướng nghiệp'],
                'context':context,'diagnostics':{'answer_mode':'local'}}
    if text in {'hello','hi','hey','chao','xin chao','chao ban','alo','helo'}:
        intent='greeting'
        reply='Chào bạn! Mình có thể giúp bạn chọn ngành, tìm trường và tra điểm chuẩn. Bạn đang muốn tìm hiểu điều gì?'
        suggestions=['Tư vấn chọn ngành','Tìm trường theo điểm','Tra điểm chuẩn']
    elif text in {'cam on','cam on ban','thank you','thanks','ok cam on','cam on nhe'}:
        reply='Không có gì! Khi cần xem thêm trường hoặc so sánh các lựa chọn, bạn cứ hỏi mình nhé.'
    elif 'thoi tiet' in text or 'nhiet do hom nay' in text:
        reply='Mình chưa tra cứu được thời tiết trực tiếp. Mình có thể hỗ trợ bạn chọn ngành, tìm trường hoặc xem điểm chuẩn.'
    elif any(phrase in text for phrase in ['ban la ai','ban giup duoc gi','ban lam duoc gi']):
        reply='Mình là trợ lý chọn trường và ngành học của UniConnect AI. Bạn có thể hỏi điểm chuẩn, so sánh trường hoặc cùng mình tìm ngành phù hợp với sở thích và điểm thi.'
    if reply is None: return None
    return {'intent':intent,'text':reply,'cards':[],'suggestions':suggestions,'context':context,
            'diagnostics':{'answer_mode':'local'},'_preserve_profile':True}
