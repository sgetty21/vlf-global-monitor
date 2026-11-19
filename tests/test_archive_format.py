import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT))

from archive_format import classify_archive_file, eligible_for_current_engine

class ArchiveFormatTests(unittest.TestCase):
    def test_type_a_is_narrowband_amplitude(self):
        self.assertTrue(eligible_for_current_engine("FE151022000500NAA_008A.mat","narrowband"))
    def test_phase_is_not_amplitude(self):
        self.assertFalse(eligible_for_current_engine("FE151022000500NAA_008B.mat","narrowband"))
    def test_broadband_amplitude_is_not_current_engine_input(self):
        self.assertFalse(eligible_for_current_engine("FE151022000500NAA_008C.mat","broadband"))
    def test_type_mapping(self):
        self.assertEqual(classify_archive_file("FE151022000500NAA_008F.mat")["measurement"],"group_delay")
    def test_unknown_suffix_rejected(self):
        with self.assertRaises(ValueError):
            classify_archive_file("unknown.mat")

if __name__=="__main__":
    unittest.main()
