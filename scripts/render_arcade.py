#!/usr/bin/env python3
"""Render an original arcade SVG contribution footer using only Python stdlib."""
import argparse
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen

THEMES = {
    "light": ("#f6f8fa", "#d0d7de", "#57606a", ("#e8eef4", "#b8dfed", "#75c4de", "#3598c1", "#16637f")),
    "dark": ("#0d1117", "#30363d", "#8b949e", ("#161f2b", "#173852", "#205b7d", "#2485ac", "#54bedb")),
}
MAX_BYTES = 2_000_000
WIDTH = 724


class CalendarParser(HTMLParser):
    """Extract only GitHub's contribution grid's typed cells, not arbitrary page text."""
    def __init__(self):
        super().__init__()
        self.in_grid = False
        self.grid_count = 0
        self.cells = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and "ContributionCalendar-grid" in (attrs.get("class") or "").split():
            self.in_grid = True
            self.grid_count += 1
            return
        if not self.in_grid or tag != "td" or "data-date" not in attrs:
            return
        raw_date, level = attrs["data-date"], attrs.get("data-level")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date or "") or level not in {"0","1","2","3","4"}:
            raise ValueError("Invalid calendar cell")
        day = date.fromisoformat(raw_date)
        if day in self.cells:
            raise ValueError("Duplicate calendar day")
        self.cells[day] = int(level)

    def handle_endtag(self, tag):
        if tag == "table" and self.in_grid:
            self.in_grid = False


def parse_calendar(html):
    parser = CalendarParser()
    parser.feed(html)
    parser.close()
    cells = parser.cells
    if parser.grid_count != 1 or parser.in_grid or not 350 <= len(cells) <= 371:
        raise ValueError("Expected exactly one complete public contribution calendar")
    first, last = min(cells), max(cells)
    if len(cells) != (last - first).days + 1 or (last - sunday(first)).days >= 54 * 7:
        raise ValueError("Contribution calendar has gaps or unexpected span")
    return cells


def sunday(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def sample_calendar():
    start = date(2025, 1, 5)
    return {start + timedelta(days=i): (0,0,0,1,1,2,3,4)[(i*13 + (i//7)*11 + (i//31)*9)%8]
            for i in range(371)}


def fetch_calendar(username):
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise ValueError("Invalid GitHub username")
    req = Request(f"https://github.com/users/{username}/contributions", headers={"User-Agent": "ProfileArcade/1.0"})
    with urlopen(req, timeout=15) as response:
        if response.geturl() != req.full_url:
            raise ValueError("Unexpected calendar redirect")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Calendar response too large")
    return parse_calendar(raw.decode("utf-8"))


def render(cells, theme, sample=False):
    bg, border, muted, colors = THEMES[theme]
    start = sunday(min(cells))
    columns = (max(cells) - start).days // 7 + 1
    step = 13
    left = (WIDTH - (columns * step - 2)) // 2
    grid = []
    for day, level in sorted(cells.items()):
        col, row = divmod((day - start).days, 7)
        grid.append(f'<rect x="{left + step*col}" y="{29 + step*row}" width="11" height="11" rx="2" fill="{colors[level]}"/>')
    grid_text = "\n".join(grid)
    subtitle = "Illustrative sample grid; not actual contribution data." if sample else "GitHub public contribution calendar; cell color indicates contribution level."
    label = "Contribution arcade · preview" if sample else "Contribution arcade"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} 137" width="{WIDTH}" height="137" role="img" aria-labelledby="title desc">
<title id="title">{label}</title><desc id="desc">{subtitle} An animated pixel character moves across the grid.</desc>
<style>
.runner{{animation:sweep 18s linear infinite}}
.jaw{{animation:chew .32s steps(1,end) infinite}}
@keyframes sweep{{from{{transform:translateX(-80px)}}to{{transform:translateX({WIDTH + 50}px)}}}}
@keyframes chew{{50%{{opacity:0}}}}
@media(prefers-reduced-motion:reduce){{.runner,.jaw{{animation:none}}.runner{{display:none}}}}
</style>
<defs><clipPath id="track"><rect x="1" y="26" width="{WIDTH - 2}" height="92" rx="3"/></clipPath>
<path id="ghost" d="M4 1h8v2h3v3h2v12h-4v-3h-3v3H7v-3H4v3H0V6h2V3h2z"/>
<path id="eyes" fill="#fff" d="M4 6h4v5H4zm7 0h4v5h-4z"/><path id="pupils" fill="#182c52" d="M6 7h2v3H6zm7 0h2v3h-2z"/></defs>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="136" rx="10" fill="{bg}" stroke="{border}"/>
<text x="{left}" y="19" fill="{muted}" font-family="system-ui,sans-serif" font-size="10" font-weight="600">{label}</text>
{grid_text}
<g clip-path="url(#track)" aria-hidden="true"><g transform="translate(0 58)"><g class="runner">
<g transform="translate(-56 0)" fill="#a78bfa"><use href="#ghost"/><use href="#eyes"/><use href="#pupils"/></g>
<g transform="translate(-31 0)" fill="#66a9e9"><use href="#ghost"/><use href="#eyes"/><use href="#pupils"/></g>
<g fill="#ffd24d"><path d="M5 0h10v2h4v3h3v2h-5v2h-5v2h5v2h5v2h-3v3h-4v2H5v-2H2v-3H0V5h2V2h3z"/>
<path class="jaw" d="M17 7h5v6h-5v-2h-5V9h5z"/><path fill="#523609" d="M12 4h3v3h-3z"/></g>
</g></g></g>
</svg>
"""


def write_assets(cells, out, sample):
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=out, delete=False) as handle:
            handle.write(render(cells, theme, sample))
        temp = Path(handle.name)
        try:
            temp.chmod(0o644)
            temp.replace(out / f"arcade-{theme}.svg")
        finally:
            temp.unlink(missing_ok=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    source = cli.add_mutually_exclusive_group(required=True)
    source.add_argument("--sample", action="store_true", help="Use explicitly labeled illustration data")
    source.add_argument("--username", help="Read the user's public GitHub contribution calendar")
    source.add_argument("--html", type=Path, help="Parse downloaded public contribution HTML")
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    try:
        if args.sample:
            cells = sample_calendar()
        elif args.html:
            with args.html.open("rb") as file:
                raw = file.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Calendar HTML too large")
            cells = parse_calendar(raw.decode("utf-8"))
        else:
            cells = fetch_calendar(args.username)
        write_assets(cells, args.output, args.sample)
    except (OSError, ValueError) as exc:
        cli.exit(1, f"Unable to render contribution calendar: {exc}\n")


if __name__ == "__main__":
    main()
