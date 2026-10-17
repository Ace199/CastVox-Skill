import json
import runpy
import unittest
from unittest.mock import patch

from tests.helpers import Fixture, ROOT


class RuntimeLocation(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.locate = runpy.run_path(str(ROOT / 'skills/soundmaker-dubbing/scripts/runtime_location.py'))['locate']

    def test_repository_location_needs_no_install_record(self):
        self.assertEqual(self.locate(ROOT / 'skills/soundmaker-dubbing', self.root / 'missing.json'), ROOT)

    def test_imported_copy_uses_install_record_without_scanning(self):
        record = self.dump('runtime.json', {'runtime_root': str(ROOT)})
        with patch('pathlib.Path.glob', side_effect=AssertionError('No directory search')), \
                patch('pathlib.Path.rglob', side_effect=AssertionError('No directory search')):
            self.assertEqual(self.locate(self.a, record), ROOT)

    def test_missing_install_record_stops_instead_of_searching(self):
        with self.assertRaises(ValueError):
            self.locate(self.a, self.root / 'missing.json')

    def test_invalid_or_relative_runtime_is_rejected(self):
        for value in (str(self.a), '.', ''):
            with self.subTest(value=value):
                record = self.dump('runtime.json', {'runtime_root': value})
                with self.assertRaises(ValueError):
                    self.locate(self.a, record)
