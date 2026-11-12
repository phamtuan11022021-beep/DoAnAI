import unittest
from import_completion_ttu import candidates,primary_keys,normalize_school_key,normalize_major_code
from import_official_gaps import validate_primary_row


class TTUCompletionTests(unittest.TestCase):
    def test_hict_former_name_resolves_to_verified_renamed_school(self):
        self.assertEqual(normalize_school_key('Trường ĐH Công nghiệp Dệt May HN'),
                         normalize_school_key('Trường Đại học Công nghiệp và Thương mại Hà Nội'))
    def test_all_reviewed_training_rows_have_exact_primary_evidence(self):
        rows=candidates().to_dict('records')
        self.assertEqual(len(rows),18)
        self.assertEqual(len(primary_keys()),18)
        self.assertTrue(all(validate_primary_row(row) for row in rows))
        self.assertTrue(all(not row['major_code'].startswith('722') for row in rows))

    def test_tampered_score_combination_and_code_rejected(self):
        row=candidates().to_dict('records')[0]
        for changes in [{'cutoff_score':1},{'combination':'D99'},{'major_code':'9999999'},{'year':'2025'}]:
            with self.subTest(changes=changes):
                self.assertFalse(validate_primary_row({**row,**changes}))
