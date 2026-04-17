from __future__ import annotations

import unittest

from src.utils.model_config import load_model_profile


class QualityUpgradeTests(unittest.TestCase):
    def test_load_model_profile_can_override_profile_name(self) -> None:
        profile = load_model_profile(profile_name='deep')

        self.assertEqual(profile.name, 'deep')
        self.assertEqual(profile.model, 'o3-mini')


if __name__ == '__main__':
    unittest.main()
