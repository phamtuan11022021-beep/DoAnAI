import unittest
import pandas as pd
from scrape_missing_2025_2026 import accept_new, COLUMNS, safe_api_row, page_school_id
import json
from unittest.mock import Mock, patch
from pathlib import Path
from tempfile import TemporaryDirectory

class RecoveryTests(unittest.TestCase):
    def test_endpoint_rows_must_match_requested_school_year_and_method(self):
        import scrape_missing_2025_2026 as recovery
        item = {'school_code': 'ABC', 'school_name': 'A university', 'score_url': 'https://example.edu/ABC'}
        html = '<script>self.__next_f.push(' + json.dumps([1, '{"school_id":7}']) + ')</script>'
        row = dict(school_id=7, year=2024, mark_type=1, code='7480201',
                   display_code=None, name='Công nghệ thông tin', mark=24,
                   is_converted_score=0, admission_alias='diem-thi-thpt',
                   formula='MON_1+MON_2+MON_3+UT', introtext='', block='A00')
        api = Mock()
        api.json.return_value = [row, {**row, 'year': 2025}, {**row, 'school_id': 8},
                                 {**row, 'mark_type': 2}, {**row, 'is_converted_score': 1}]
        with TemporaryDirectory() as temp, patch.object(recovery, 'RECOVERY', Path(temp)), \
             patch.object(recovery.legacy, 'match_tuyensinh247_school', return_value=(item, 1)), \
             patch.object(recovery.legacy, 'validate_ts247_page_identity', return_value=(True, '')), \
             patch.object(recovery.legacy, 'get_url', side_effect=[Mock(text=html), api]):
            rows, _ = recovery.recover_2025_api('A university', [], year=2024)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['year'], '2024')
        self.assertEqual(rows[0]['cutoff_score'], 24)

    def test_school_id_uses_explicit_code_not_nested_other_school(self):
        body = '{"school_id":999},' + '{"data":{"school_id":247},"schoolAliasCode":{"alias":"hoc-vien-ngan-hang","code":"NHH"}}'
        html = '<script>self.__next_f.push(' + json.dumps([1, body]) + ')</script>'
        self.assertEqual(page_school_id(html, 'NHH'), '247')
        self.assertIsNone(page_school_id(html, 'OTHER'))

    def test_only_explicit_unconverted_thpt_and_additive_formula(self):
        row = dict(is_converted_score=0, admission_alias='diem-thi-thpt',
                   formula='(MON_1+MON_2+MON_3)+UT+KK', introtext='')
        self.assertTrue(safe_api_row(row))
        for changes in [dict(is_converted_score=1), dict(is_converted_score=None),
                        dict(admission_alias='hoc-ba'), dict(formula='(MON_1*2+MON_2+MON_3)*3/4+UT'),
                        dict(formula='MON_1+MON_2+UT'), dict(introtext='Môn tiếng Anh nhân 2')]:
            with self.subTest(changes=changes):
                self.assertFalse(safe_api_row({**row, **changes}))
    def row(self, **changes):
        return dict(dict(zip(COLUMNS, ['School','7480201','Information technology','2025','THPT','A00',24,'','https://example.edu'])), **changes)

    def test_missing_major_in_existing_school_is_added(self):
        base = pd.DataFrame([self.row(major_code='7480202')])
        added, rejected = accept_new(base, pd.DataFrame([self.row()]))
        self.assertEqual(len(added), 1)
        self.assertTrue(rejected.empty)

    def test_existing_scores_are_preserved(self):
        added, _ = accept_new(pd.DataFrame([self.row()]), pd.DataFrame([self.row(cutoff_score=25)]))
        self.assertTrue(added.empty)

    def test_conflicting_program_year_is_quarantined(self):
        added, rejected = accept_new(pd.DataFrame(columns=COLUMNS), pd.DataFrame([self.row(),self.row(cutoff_score=25)]))
        self.assertTrue(added.empty)
        self.assertEqual(len(rejected), 2)

    def test_wrong_scale_and_method_are_rejected(self):
        for row in [self.row(cutoff_score=40), self.row(admission_method_codes='HSA')]:
            added, rejected = accept_new(pd.DataFrame(columns=COLUMNS), pd.DataFrame([row]))
            self.assertTrue(added.empty)
            self.assertEqual(len(rejected), 1)

if __name__ == '__main__':
    unittest.main()
