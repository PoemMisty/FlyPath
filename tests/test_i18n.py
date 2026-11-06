"""Translation helper tests. Pure Python, no QGIS or Qt required."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flypath_i18n import _load_ts, tr, trn  # noqa: E402
import flypath_i18n  # noqa: E402


class TranslationHelpers(unittest.TestCase):
    def test_english_falls_back_to_the_source(self):
        self.assertEqual(tr('Mission Setup'), 'Mission Setup')

    def test_installed_translator_is_used(self):
        catalogue = {
            'Mission Setup': '任务设置',
            'Area {area:.1f} ha': '面积 {area:.1f} 公顷',
            '{n} point': '{n} 个点',
            '{n} points': '{n} 个点',
        }
        original = flypath_i18n._translate
        flypath_i18n._translate = lambda context, text: catalogue.get(text, text)
        try:
            self.assertEqual(tr('Mission Setup'), '任务设置')
            self.assertEqual(tr('Area {area:.1f} ha', area=12.34), '面积 12.3 公顷')
            self.assertEqual(tr('Not in the catalog'), 'Not in the catalog')
            self.assertEqual(trn('{n} point', '{n} points', 2, n=2), '2 个点')
        finally:
            flypath_i18n._translate = original

    def test_bad_placeholder_does_not_crash(self):
        original = flypath_i18n._translate
        flypath_i18n._translate = lambda context, text: '面积 {missing} 公顷'
        try:
            self.assertEqual(tr('Area', area=1.5), '面积 {missing} 公顷')
        finally:
            flypath_i18n._translate = original

    def test_named_placeholders(self):
        self.assertEqual(tr('Area {area:.1f} ha', area=12.34), 'Area 12.3 ha')

    def test_plural_choice(self):
        self.assertEqual(trn('{n} point', '{n} points', 1), '1 point')
        self.assertEqual(trn('{n} point', '{n} points', 3), '3 points')

    def test_ts_catalog_keeps_only_finished_entries(self):
        text = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN">
 <context>
  <name>FlyPath</name>
  <message><source>Mission Setup</source><translation>任务设置</translation></message>
  <message><source>Photos</source><translation type="unfinished"></translation></message>
  <message><source>Waypoints</source><translation type="unfinished">航点</translation></message>
 </context>
 <context>
  <name>Other</name>
  <message><source>Ignored</source><translation>忽略</translation></message>
 </context>
</TS>"""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'FlyPath_zh_CN.ts')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(text)
            self.assertEqual(_load_ts(path), {'Mission Setup': '任务设置'})

    def test_missing_catalog_is_empty(self):
        self.assertEqual(_load_ts('/does/not/exist.ts'), {})


if __name__ == '__main__':
    unittest.main()
