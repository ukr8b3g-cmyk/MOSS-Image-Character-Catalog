import unittest
from prompt_revision_rules import repair_caption,OLD_FRAME,NEW_FRAME,ui_changes

class RepairTests(unittest.TestCase):
 def test_true_anatomical_traits_and_series_retained(self):
  old='lucy from fairy tail. A female human character. Appearance: fox tail, animal ears, ponytail.'
  new,_=repair_caption(old)
  self.assertIn('lucy from fairy tail.',new)
  self.assertIn('fox tail, animal ears',new)
  self.assertIn('hair gathered and tied at the back of the head',new)
  self.assertIn('female human character',new)
 def test_species_inference_and_nonhuman(self):
  self.assertEqual(repair_caption('A non-human character.')[0],'A non-human character.')
  self.assertEqual(repair_caption('A single male human character. Appearance: android.')[0],'A single male character. Appearance: android.')
  self.assertEqual(repair_caption('A female human character. Appearance: cyborg.')[0],'A female human character. Appearance: cyborg.')
 def test_framing_only(self):
  self.assertEqual(repair_caption('A character. '+OLD_FRAME)[0],'A character. '+NEW_FRAME)
 def test_no_global_tail_replacement(self):
  old='Tails from Sonic. Appearance: two tails, fox tail, pony (animal), tail ribbon, twin braids.'
  self.assertEqual(repair_caption(old)[0],old)
 def test_style_prose_untouched(self):
  old='A painting of a woman with a ponytail and an animal tail.'
  self.assertEqual(repair_caption(old,False)[0],old)
 def test_appearance_end_and_generation_suffix(self):
  old='x from y. Appearance: blonde hair, ponytail, ponytail. Fully clothed, relaxed standing pose.'
  new,_=repair_caption(old)
  self.assertTrue(new.endswith('. Fully clothed, relaxed standing pose.'))
  self.assertEqual(new.count('hair gathered and tied'),1)
  self.assertEqual(repair_caption(new)[0],new)
 def test_missing_appearance_not_invented(self):
  self.assertEqual(repair_caption('x from y.')[0],'x from y.')

if __name__=='__main__':unittest.main()
