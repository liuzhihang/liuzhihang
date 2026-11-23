import re
import unittest
from datetime import date, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from xml.etree import ElementTree as ET

import render_arcade as renderer

SVG = {"svg": "http://www.w3.org/2000/svg"}


def fixture(n=366):
    first = date(2025, 11, 23)
    return '<table class="ContributionCalendar-grid js-calendar-graph-table">' + ''.join(
        f'<td data-date="{first + timedelta(days=i)}" data-level="{i%5}"></td>'
        for i in range(n)
    ) + '</table>'


class TestCalendar(unittest.TestCase):
    def test_exact_dates_and_ignores_outside_cells(self):
        cells = renderer.parse_calendar('<td data-date="other" data-level="9"></td>' + fixture())
        self.assertEqual(len(cells), 366)
        self.assertEqual(cells[date(2025, 11, 27)], 4)

    def test_rejects_partial_ambiguous_or_invalid_input(self):
        invalid = [
            '', fixture(20), fixture() * 2, fixture().replace('</table>', ''),
            fixture().replace('2025-11-24', '2025-11-23'),
            fixture().replace('2025-11-24', '2026-11-26'),
            fixture().replace('data-level="1"', 'data-level="9"'),
        ]
        for html in invalid:
            with self.subTest(length=len(html)), self.assertRaises(ValueError):
                renderer.parse_calendar(html)

    def test_light_and_dark_assets_are_accessible_and_deterministic(self):
        cells = renderer.sample_calendar()
        for theme in renderer.THEMES:
            contents = renderer.render(cells, theme, sample=True)
            root = ET.fromstring(contents)
            self.assertEqual(root.attrib['role'], 'img')
            self.assertIn('preview', root.find('svg:title', SVG).text)
            self.assertIn('not actual contribution data', root.find('svg:desc', SVG).text)
            self.assertEqual(len(root.findall('svg:rect', SVG)), len(cells) + 1)
            self.assertIn('prefers-reduced-motion:reduce', contents)
            self.assertIn('.runner{display:none}', contents)
            self.assertEqual(contents, renderer.render(cells, theme, sample=True))
            self.assertNotRegex(contents, re.compile(r'(?:<script|<foreignObject|href="https?:)', re.I))

    def test_real_asset_is_not_labeled_preview(self):
        cells = renderer.parse_calendar(fixture())
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            renderer.write_assets(cells, root, False)
            self.assertEqual(set(p.name for p in root.iterdir()), {'arcade-light.svg', 'arcade-dark.svg'})
            for file in root.iterdir():
                text = file.read_text()
                self.assertIn('GitHub public contribution calendar', text)
                self.assertNotIn('preview', text)


if __name__ == '__main__':
    unittest.main()
