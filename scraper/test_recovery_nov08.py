import unittest
from unittest.mock import patch
from import_recovery_nov08 import candidates, reviewed_methods, checked, primary_keys, verified_location, VINH_SOURCE
from import_official_gaps import validate_primary_row

class NovemberRecoveryTests(unittest.TestCase):
 def test_location_uses_verified_primary_footer(self):
  row=verified_location()
  self.assertEqual(row['city'],'Nghệ An')
  self.assertEqual(row['university_key'],'dai hoc su pham ky thuat vinh')
  self.assertIn('117 - Nguyễn Viết Xuân',row['address'])
 def test_vinh_uses_pt100_not_first_score_column(self):
  rows=candidates().set_index('major_code')
  self.assertEqual(len(rows),14)
  self.assertEqual(float(rows.loc['7510303','cutoff_score']),22.5)
  self.assertEqual(float(rows.loc['7510201','cutoff_score']),18.2)
  self.assertEqual(float(rows.loc['7140246','cutoff_score']),20)
  self.assertIn('C01',rows.loc['7510303','combination'])
  self.assertNotIn('C01',rows.loc['7340101','combination'])
  self.assertEqual(len(primary_keys()),14)
  self.assertTrue(all(validate_primary_row(r) for r in candidates().to_dict('records')))

 def test_tampered_primary_row_rejected(self):
  row=candidates().to_dict('records')[-1]
  for changes in ({'cutoff_score':24.5},{'year':'2025'},{'major_code':'9999999'},
                  {'combination':'D99'},{'admission_method_codes':'HB'},{'university_name':'Trường Đại học Vinh'}):
   with self.subTest(changes=changes): self.assertFalse(validate_primary_row({**row,**changes}))

 def test_pinned_evidence_is_required(self):
  with patch('import_recovery_nov08.PINNED',{'vuted_2025.pdf':'bad-hash'}):
   with self.assertRaises(ValueError): checked('vuted_2025.pdf')

 def test_methods_and_branch_codes_preserved(self):
  rows=reviewed_methods()
  self.assertEqual(len(rows),148)
  tueba=rows[rows.school_code.str.startswith('DTE')]
  self.assertEqual(len(tueba),50)
  self.assertFalse(tueba.comparable_thpt.any())
  self.assertEqual(set(tueba[tueba.city.eq('Hà Giang')].major_code),{'7310101-HG','7810103-HG','7340301HG','7310110HG'})
  vinh=rows[rows.source_url.eq(VINH_SOURCE)]
  self.assertEqual(len(vinh),42)
  self.assertEqual(vinh.comparable_thpt.sum(),14)
  self.assertEqual(len(rows.drop_duplicates(['university_key','year','major_code','admission_method'])),148)

if __name__=='__main__': unittest.main()
