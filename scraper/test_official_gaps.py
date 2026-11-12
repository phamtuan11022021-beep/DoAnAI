import unittest
from import_official_gaps import (source_soup, parse_vimaru, parse_udn, parse_uneti,
                                  reviewed_cmc_2026, validate_primary_row, normalize_school_key)


class PrimaryNoticeTests(unittest.TestCase):
    def test_vimaru_uses_pt1_reference_combination_not_conversion_tables(self):
        rows = parse_vimaru(source_soup('vimaru_2025'), 2025)
        indexed = {r['major_code']: r for r in rows}
        self.assertEqual(indexed['D101']['cutoff_score'], 22.25)
        self.assertEqual(indexed['D101']['combination'], 'D01')
        self.assertNotIn('D124', indexed)
        self.assertNotIn('D125', indexed)  # 28.5 is below 30, but still on a 40-point scale
        self.assertTrue(validate_primary_row(indexed['D101']))
        self.assertFalse(validate_primary_row({**indexed['D101'], 'year': '2026'}))
        self.assertFalse(validate_primary_row({**indexed['D101'], 'cutoff_score': 24.5}))
        self.assertFalse(validate_primary_row({**indexed['D101'], 'combination': 'A00'}))

    def test_udn_skips_weighted_languages_and_aptitude_programs(self):
        rows = parse_udn(source_soup('udn_2025'), 2025)
        self.assertFalse(any(r['major_code'].startswith(('722', '714', '7580101')) for r in rows))
        row = next(r for r in rows if r['major_code'] == '7480201' and 'DDK' in r['admission_note'])
        self.assertEqual(row['cutoff_score'], 25.57)
        self.assertEqual(row['combination'], '')

    def test_uneti_takes_thpt_column_and_preserves_campus_code(self):
        rows = parse_uneti(source_soup('uneti_2025'))
        row = next(r for r in rows if r['major_code'] == '7480201DKK')
        self.assertEqual(row['cutoff_score'], 24)
        self.assertNotEqual(row['cutoff_score'], 26.750)
        self.assertTrue(any(r['major_code'] == '7480201DKD' for r in rows))
        self.assertEqual(normalize_school_key('Trường ĐH Kinh tế Kỹ thuật CN'),
                         normalize_school_key('Trường Đại Học Kinh Tế Kỹ Thuật Công Nghiệp'))

    def test_cmc_is_kept_separate_from_comparable_training_rows(self):
        rows = reviewed_cmc_2026()
        self.assertEqual(len(rows), 20)
        self.assertTrue(all(not r['comparable_thpt'] for r in rows))
        self.assertEqual(next(r for r in rows if r['major_code'] == 'AI')['cutoff_score'], 20.18)
        self.assertTrue(all(r['year'] == 2026 for r in rows))

    def test_previous_reviewed_primary_udn_rows_survive_mixed_method_audit(self):
        from import_official_gaps import primary_keys, OLD_UDN_SOURCE
        school, code, year, score, combination = next(iter(primary_keys(OLD_UDN_SOURCE)))
        self.assertTrue(validate_primary_row(dict(university_name=school, major_code=code, year=year,
                        cutoff_score=score, combination=combination, admission_method_codes='THPT',
                        source_url=OLD_UDN_SOURCE)))


if __name__ == '__main__':
    unittest.main()
