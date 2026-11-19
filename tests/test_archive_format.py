import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT))

from archive_format import classify_archive_file, eligible_for_current_engine
from pull_openvlf_date import verify_mat_metadata

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

class MatMetadataTests(unittest.TestCase):
    def test_accepts_verified_1hz_amplitude(self):
        self.assertEqual(verify_mat_metadata({"fs":1.0,"is_amp":1,"is_broadband":0},"fixture.mat"),1.0)
    def test_rejects_missing_sample_rate(self):
        with self.assertRaisesRegex(ValueError,"does not expose"):
            verify_mat_metadata({"is_amp":1},"fixture.mat")
    def test_rejects_wrong_sample_rate(self):
        with self.assertRaisesRegex(ValueError,"requires exactly 1 Hz"):
            verify_mat_metadata({"fs":10.0,"is_amp":1},"fixture.mat")
    def test_rejects_phase(self):
        with self.assertRaisesRegex(ValueError,"does not confirm amplitude"):
            verify_mat_metadata({"fs":1.0,"is_amp":0},"fixture.mat")
    def test_rejects_broadband(self):
        with self.assertRaisesRegex(ValueError,"broadband"):
            verify_mat_metadata({"fs":1.0,"is_amp":1,"is_broadband":1},"fixture.mat")

if __name__=="__main__":
    unittest.main()
