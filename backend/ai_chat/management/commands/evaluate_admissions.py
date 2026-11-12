"""Small reproducible acceptance checks; live mode calls the configured provider."""
import json
import time
from unittest.mock import patch
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from ai_chat import engine
from ai_chat.service import respond
from ai_chat.provider import provider_info

CASES=[
    ('ttu_it_2026','Điểm chuẩn ngành Công nghệ thông tin Đại học Tân Tạo năm 2026 là bao nhiêu?',
     'dai hoc tan tao','7480201',15.0),
    ('uet_physics_2026','Điểm chuẩn ngành Vật lý kỹ thuật Đại học Công nghệ - ĐHQGHN năm 2026 là bao nhiêu?',
     'dai hoc cong nghe dai hoc quoc gia ha noi','CN3',25.41),
    ('uet_mechanics_2026','Điểm chuẩn ngành Cơ kỹ thuật Đại học Công nghệ - ĐHQGHN năm 2026 là bao nhiêu?',
     'dai hoc cong nghe dai hoc quoc gia ha noi','CN4',26.13),
    ('cmc_it_2026','Điểm chuẩn ngành Công nghệ thông tin Đại học CMC năm 2026 là bao nhiêu?',
     'dai hoc cmc','IT',18.98),
]


class Command(BaseCommand):
    help='Evaluate four real-source history cases without saving conversations. --live may retry transient HTTP failures.'

    def add_arguments(self,parser):
        parser.add_argument('--live',action='store_true')

    def handle(self,*args,**options):
        rows=[]
        for case,question,school,code,score in CASES:
            start=time.monotonic()
            lookup=engine.history_reply
            with patch('ai_chat.service.engine.history_reply',wraps=lookup) as traced:
                result=respond(message=question,previous_context={},ui_context={}) if options['live'] else lookup(message=question,context={'school_key':school})
                lookup_query=traced.call_args.kwargs['message'] if traced.called else None
            cards=result.get('cards',[])
            data=engine.load_program_year()
            names={engine.normalize(value) for value in data.loc[data.university_key.eq(school),'university_name']}
            exact=[card for card in cards if card.get('major_code')==code and engine.normalize(card.get('university_name','')) in names]
            values=[(c.get('history',{}).get('2026') or {}).get('cutoff_score') if c.get('kind')=='history' else c.get('cutoff_score') for c in exact]
            found=any(value is not None and abs(float(value)-score)<1e-8 for value in values)
            other_years=any(set(c.get('history',{}))-{'2026'} for c in cards)
            text=result.get('text','')
            mentioned=(str(score).rstrip('0').rstrip('.') in text.replace(',','.'))
            llm=result.get('diagnostics',{}).get('answer_mode')!='evidence_fallback'
            passed=found and not other_years and (not options['live'] or (mentioned and llm))
            rows.append({'id':case,'question':question,'expected_code':code,'expected_score':score,
                'evidence_correct':found,'wrong_years_present':other_years,'score_mentioned':mentioned,
                'passed':passed,'seconds':round(time.monotonic()-start,2),'answer':text,
                'cards':cards,'diagnostics':result.get('diagnostics',{})})
            rows[-1]['lookup_query']=lookup_query
            self.stdout.write(f'{case}: {"PASS" if passed else "FAIL"}; {rows[-1]["seconds"]}s')
            self.stdout.flush()
        report={'mode':'live' if options['live'] else 'backend_only','provider':provider_info(),
                'passed':sum(r['passed'] for r in rows),'total':len(rows),
                'limitation':'Four targeted source checks, not a comprehensive or human-reviewed evaluation.', 'cases':rows}
        path=settings.BASE_DIR.parent/'docs'/('AI_ACCEPTANCE_LIVE_20261106.json' if options['live'] else 'AI_ACCEPTANCE_BACKEND_20261106.json')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.stdout.write(f'Report: {path.name}')
        if report['passed']!=len(rows): raise CommandError('Some acceptance checks failed. Review the saved report.')
