import pandas as pd
from django.test import TestCase
from .service import _engine, recommend_for_api


class DanangRecommendationTests(TestCase):
    def test_ufm_hue_program_is_not_located_at_hcm_main_campus(self):
        engine = _engine()
        frame = pd.DataFrame([
            {'university_key': 'dai hoc tai chinh marketing', 'major_code_key': '7340101', 'major_name': 'Quản trị kinh doanh - CS Huế'},
            {'university_key': 'dai hoc tai chinh marketing', 'major_code_key': '7340101TH', 'major_name': 'Quản trị kinh doanh - Chương trình tích hợp'},
        ])
        self.assertEqual(list(engine.apply_location_filter(frame, city='Hồ Chí Minh').major_code_key), ['7340101TH'])
        self.assertEqual(list(engine.apply_location_filter(frame, city='Huế').major_code_key), ['7340101'])

    def test_hcm_business_recommends_multiple_schools(self):
        result = recommend_for_api(dict(score=25, combination='A01',
            major='Quản trị kinh doanh', city='Hồ Chí Minh', top=30))
        self.assertGreaterEqual(len({r['university_name'] for r in result['results']}), 3)
        self.assertTrue(result['alternatives']['same_city_unverified_combination'])

    def test_combined_method_never_compared_to_pure_thpt(self):
        result = recommend_for_api(dict(score=28, combination='A00',
            major='Công nghệ thông tin', city='Đà Nẵng', top=30))
        others = result['other_admission_methods']
        self.assertTrue(any('Việt Hàn' in r['university_name'] for r in others))
        self.assertTrue(all(not r['comparable_thpt'] for r in others))
        self.assertTrue(all('predicted_cutoff_2027' not in r for r in others))
        self.assertTrue(all('recommendation_level' not in r for r in others))

    def test_branch_program_does_not_inherit_main_campus_city(self):
        engine = _engine()
        frame = pd.DataFrame([
            {'university_key': 'dai hoc dong a', 'major_code_key': '120DL'},
            {'university_key': 'dai hoc dong a', 'major_code_key': '7480201DL'},
            {'university_key': 'dai hoc dong a', 'major_code_key': '7480201'},
        ])
        self.assertEqual(list(engine.apply_location_filter(frame, city='Đà Nẵng').major_code_key), ['7480201'])
        self.assertEqual(set(engine.apply_location_filter(frame, city='Đắk Lắk').major_code_key),
                         {'120DL', '7480201DL'})

    def test_28_it_in_danang_includes_verified_bach_khoa(self):
        for combination in ('A00', 'A01'):
            with self.subTest(combination=combination):
                result = recommend_for_api(dict(score=28, combination=combination,
                    major='Công nghệ thông tin', city='Đà Nẵng', top=20))
                bk = [r for r in result['results'] if 'Bách khoa' in r['university_name']]
                self.assertTrue({'7480201', '7480201A', '7480201B', '7480201C'}.issubset(
                    {r['major_code'] for r in bk}))
                self.assertTrue(all(r['combination_status'] == 'VERIFIED' for r in bk))
                self.assertNotIn('7510601', {r['major_code'] for r in result['results']})
                self.assertTrue(result['alternatives']['same_city_historical'])

    def test_code_can_recover_ocr_but_reject_wrong_subject(self):
        frame = pd.DataFrame([
            {'major_name': 'Cong nghethong tin', 'major_code_norm': '7480201'},
            {'major_name': 'Công nghệ thông tin Quản lý công nghiệp', 'major_code_norm': '7510601'},
        ])
        result = _engine().filter_major(frame, major_query='CNTT', major_code='')
        self.assertEqual(list(result.major_code_norm), ['7480201'])
