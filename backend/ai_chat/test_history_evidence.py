from unittest.mock import patch

import pandas as pd
from django.test import TestCase,override_settings

from . import engine


class HistoryEvidenceTests(TestCase):
    def test_subject_is_not_taken_from_school_name_or_long_fuzzy_description(self):
        self.assertEqual(engine.extract_major('Điểm chuẩn ngành Cơ kỹ thuật Đại học Công nghệ - ĐHQGHN năm 2026').casefold(), 'cơ kỹ thuật')
        self.assertEqual(engine.extract_major('Điểm chuẩn ngành Vật lý kỹ thuật Đại học Công nghệ - ĐHQGHN năm 2026').casefold(), 'vật lý kỹ thuật')
        self.assertEqual(engine.extract_major('Điểm chuẩn ngành Kế toán Đại học Tài chính Marketing năm 2026').casefold(), 'kế toán')

    @override_settings(CHAT_LOCAL_ROUTING=False)
    @patch('ai_chat.service.chat')
    @patch('ai_chat.service.engine.history_reply')
    def test_real_history_question_is_looked_up_when_model_claims_unsupported(self, lookup, chat):
        import json
        from .service import respond
        chat.side_effect=[json.dumps({'intent':'unsupported_data','query':'Không có điểm UET',
            'score':None,'combination':None,'major':None,'city':None}),'Kết quả']
        lookup.return_value={'intent':'history','text':'Kết quả','cards':[],'suggestions':[]}
        respond(message='Điểm chuẩn ngành Vật lý kỹ thuật Đại học Công nghệ - ĐHQGHN năm 2026',previous_context={},ui_context={})
        self.assertTrue(lookup.called)

    def setUp(self):
        self.frame = pd.DataFrame([
            dict(university_key='school', university_name='School', major_code='IT',
                 major_name='Công nghệ thông tin', year=year, cutoff_score=score,
                 eligible_combinations='A00', source_urls='https://school.edu.vn/notice')
            for year, score in [(2024, 20), (2025, 21)]])

    def lookup(self, message, official=()):
        with patch.object(engine, 'load_program_year', return_value=self.frame), \
             patch('catalog.official.official_rows', return_value=list(official)) as source:
            result = engine.history_reply(message=message, context={'school_key':'school'})
        return result, source

    def test_explicit_year_does_not_leak_other_years(self):
        result, source = self.lookup('Điểm CNTT năm 2025')
        self.assertEqual(len(result['cards']), 1)
        self.assertEqual(set(result['cards'][0]['history']), {'2025'})
        self.assertEqual(result['cards'][0]['history']['2025']['cutoff_score'], 21)
        self.assertIn('school.edu.vn', result['cards'][0]['history']['2025']['source_urls'])
        self.assertEqual(source.call_args.kwargs['years'], [2025])

    def test_missing_year_uses_official_method_without_stale_history(self):
        official = dict(university_name='School', major_name='Công nghệ thông tin',
                        year=2026, cutoff_score=15, admission_method='THPT PT100',
                        comparable_thpt=False, source_url='https://school.edu.vn/2026')
        result, _ = self.lookup('Điểm CNTT năm 2026', [official])
        self.assertEqual([card['kind'] for card in result['cards']], ['official_method'])
        self.assertEqual(result['cards'][0]['admission_method'], 'THPT PT100')
        self.assertNotIn('recommendation_level', result['cards'][0])

    def test_future_year_never_returns_historical_cutoff(self):
        result, _ = self.lookup('Điểm CNTT năm 2027')
        self.assertEqual(result['cards'], [])
        self.assertIn('dự đoán', result['text'])

    def test_year_ranges_and_unsupported_years(self):
        self.assertEqual(engine.extract_years('từ 2023 đến năm 2026'), [2023,2024,2025,2026])
        result, _ = self.lookup('Điểm CNTT năm 2022')
        self.assertEqual(result['cards'], [])

    def test_official_csv_filters_year_and_normalizes_boolean(self):
        from catalog.official import official_rows
        frame = pd.DataFrame([
            dict(university_key='school', city='', year=year, comparable_thpt='False')
            for year in [2025, 2026]])
        with patch('catalog.official.pd.read_csv', return_value=frame), \
             patch('pathlib.Path.exists', return_value=True):
            result = official_rows(university_key='school', years=[2026])
        self.assertEqual(len(result), 1)
        self.assertIs(result[0]['comparable_thpt'], False)

    def test_without_city_still_returns_official_methods(self):
        from ai_api.service import other_admission_methods
        with patch('catalog.official.official_rows', return_value=[{'comparable_thpt':False}]) as lookup:
            self.assertEqual(len(other_admission_methods(city='', major='CNTT')), 1)
        self.assertEqual(lookup.call_args.kwargs['city'], '')

    def test_exact_major_excludes_similar_subjects(self):
        extra = self.frame.iloc[[0]].assign(major_code='ROBOT', major_name='Kỹ thuật Robot')
        self.frame['major_name'] = 'Vật lý kỹ thuật'
        self.frame = pd.concat([self.frame, extra], ignore_index=True)
        result, _ = self.lookup('Điểm Vật lý kỹ thuật năm 2024')
        self.assertEqual([card['major_code'] for card in result['cards']], ['IT'])

    @override_settings(CHAT_LOCAL_ROUTING=False)
    @patch('ai_chat.service.chat')
    @patch('ai_chat.service.engine.history_reply')
    def test_router_cannot_replace_explicit_year(self, lookup, chat):
        import json
        from .service import respond
        chat.side_effect = [json.dumps({'intent':'history','query':'Điểm CNTT CMC năm 2025',
            'score':None,'combination':None,'major':None,'city':None}), 'Kết quả']
        lookup.return_value = {'intent':'history','text':'Kết quả','cards':[],'suggestions':[]}
        respond(message='Điểm CNTT CMC năm 2026', previous_context={}, ui_context={})
        self.assertEqual(engine.extract_years(lookup.call_args.kwargs['message']), [2026])
