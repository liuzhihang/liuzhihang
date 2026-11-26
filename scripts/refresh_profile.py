"""Refresh public blog links and contribution visuals. No token or private data."""
from collections import Counter
from datetime import date, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import argparse
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BLOG = 'https://liuzhihang.com/rss.xml'
CONTRIBUTIONS = 'https://github.com/users/liuzhihang/contributions'
FEATURED = 'https://liuzhihang.com/posts/sdd-framework-why-openspec/'
START, END = '<!-- BLOG-POST-LIST:START -->', '<!-- BLOG-POST-LIST:END -->'


def download(url):
    with urlopen(Request(url, headers={'User-Agent': 'liuzhihang-profile-refresh'}), timeout=30) as response:
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError(f'Oversized response: {url}')
        return data


def articles(data):
    posts = {}
    for item in ET.fromstring(data).findall('./channel/item'):
        url = urlsplit((item.findtext('link') or '').strip())
        if (url.scheme, url.netloc) != ('https', 'liuzhihang.com') or not url.path.startswith('/posts/'):
            continue
        link = 'https://liuzhihang.com' + quote(url.path.rstrip('/') + '/', safe='/%-._~')
        if link == FEATURED:
            continue
        published = parsedate_to_datetime(item.findtext('pubDate'))
        if published.tzinfo is None:
            raise ValueError('RSS article timestamp missing timezone')
        title = ' '.join(item.findtext('title', default='').split())
        title = re.sub(r'([\\\[\]<>*_])', r'\\\1', title)
        if title and (link not in posts or published > posts[link][0]):
            posts[link] = (published, title)
    if len(posts) < 3:
        raise ValueError('Incomplete blog feed; refusing to drop existing items')
    return '\n'.join(f'- `{pub.astimezone(timezone(timedelta(hours=8))):%Y-%m-%d}` · [{title}]({url})'
                     for url, (pub, title) in sorted(posts.items(), key=lambda x: x[1][0], reverse=True)[:5])


class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.levels = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'td' and 'ContributionCalendar-day' in a.get('class', '') and 'data-date' in a:
            day, level = date.fromisoformat(a['data-date']), int(a['data-level'])
            if day in self.levels or not 0 <= level <= 4:
                raise ValueError('Invalid contribution calendar')
            self.levels[day] = level


def skyline(d, theme):
    days = sorted(d)
    bg, fg, muted, grid, c = (
        ('#F6F8FA', '#1F2328', '#59636E', '#E6EBF0', ['#E6EBF0','#C8E2F5','#9CCCEB','#61AFEF','#257AA9'])
        if theme == 'light' else
        ('#161B22', '#E6EDF3', '#8B949E', '#21262D', ['#21262D','#26415C','#315A7F','#427CAC','#58A6FF'])
    )
    def shade(color, fraction):
        values = (int(color[i:i+2], 16) for i in (1,3,5))
        return '#' + ''.join(f'{round(value*fraction):02x}' for value in values)
    def xy(i, dx=0, dy=0, h=0):
        x,y = i//7+dx, i%7+dy
        return f'{80+x*14-y*7.8:.1f},{107+x*1.25+y*5.5-h:.1f}'
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="229" viewBox="0 0 880 229" role="img" aria-label="Public GitHub contributions">',
          f'<rect width="880" height="229" rx="12" fill="{bg}"/>',
          f'<text x="30" y="41" font-family="monospace" font-size="18" font-weight="700" fill="{fg}">CONTRIBUTION SKYLINE</text>',
          f'<text x="30" y="63" font-family="monospace" font-size="12" fill="{muted}">PUBLIC GITHUB ACTIVITY / {days[0]} TO {days[-1]}</text>']
    indices = [(day-days[0]).days for day in days]
    for i in sorted(indices,key=lambda i:(i//7)*1.25+(i%7)*5.5):
        lev = d[days[0]+timedelta(days=i)]
        h = (0,10,19,29,40)[lev]
        a,b,e,f = [(x,y) for x,y in ((0,0),(.76,0),(.76,.76),(0,.76))]
        def poly(points, fill):
            el.append(f'<polygon points="{" ".join(points)}" fill="{fill}"/>')
        if h:
            poly([xy(i,*f,h),xy(i,*e,h),xy(i,*e),xy(i,*f)],shade(c[lev], .92 if theme == "light" else .84))
            poly([xy(i,*e,h),xy(i,*b,h),xy(i,*b),xy(i,*e)],shade(c[lev], .84 if theme == "light" else .71))
        poly([xy(i,*a,h),xy(i,*b,h),xy(i,*e,h),xy(i,*f,h)],c[lev] if h else grid)
    el.append('</svg>')
    return ''.join(el) + '\n'


def refresh(feed, calendar, output):
    links = articles(feed)
    parser = Calendar()
    parser.feed(calendar.decode())
    dates = sorted(parser.levels)
    if not 350 <= len(dates) <= 380 or (dates[-1]-dates[0]).days != len(dates)-1:
        raise ValueError('Unexpected contribution range; refusing to overwrite')
    path = output/'README.md'
    readme = path.read_text()
    if readme.count(START) != 1 or readme.count(END) != 1 or readme.index(START) >= readme.index(END):
        raise ValueError('Expected one ordered blog marker pair')
    a,b = readme.index(START)+len(START),readme.index(END)
    images = {theme: skyline(parser.levels, theme) for theme in ('light','dark')}
    for svg in images.values():
        ET.fromstring(svg)
    path.write_text(readme[:a]+'\n'+links+'\n'+readme[b:])
    for theme,svg in images.items():
        (output/'assets'/f'profile-skyline-{theme}.svg').write_text(svg)


def arcade_fallbacks(output):
    for theme in ('light','dark'):
        source = (output/'assets'/f'profile-arcade-{theme}.svg').read_text()
        # Reapply the profile palette after each upstream refresh, including the
        # color strings inside animated contribution tiles.
        palettes = {
            'light': {'#ffffff':'#F6F8FA', '#ebedf0':'#E6EBF0', '#57606a':'#59636E', '#4d5869':'#59636E',
                      '#9be9a8':'#C8E2F5', '#40c463':'#9CCCEB', '#30a14e':'#61AFEF', '#216e39':'#257AA9'},
            'dark': {'#0d1117':'#161B22', '#282c34':'#161B22', '#161b22':'#21262D', '#343a46':'#21262D', '#abb2bf':'#8B949E',
                     '#0e4429':'#26415C', '#355c78':'#26415C', '#006d32':'#315A7F', '#4784ad':'#315A7F', '#26a641':'#427CAC', '#61afef':'#427CAC', '#39d353':'#58A6FF', '#98c379':'#58A6FF'},
        }
        palette = palettes[theme]
        source = re.sub(r'#[0-9a-fA-F]{6}\b', lambda color: color[0] if color[0] == "#161B22" else palette.get(color[0].lower(), color[0]), source)
        # Strip wall-clock metadata; retain the dated map, animation, and credit.
        source = re.sub(r'<desc>Generated with pacman-contribution-graph on [^<]+</desc>',
                        '<desc>Generated with pacman-contribution-graph</desc>', source)
        source = re.sub(r'<generatedOn>[^<]+</generatedOn>', '', source)
        ET.fromstring(source)
        (output/'assets'/f'profile-arcade-{theme}.svg').write_text(source)
        if not re.search(r'<animate(?:Transform|Motion)?\b', source):
            raise ValueError('Pac-Man output contains no animations')
        static = re.sub(r'<(?:animate(?:Transform|Motion)?|set)\b[^>]*(?:/>|>.*?</(?:animate(?:Transform|Motion)?|set)>)', '', source, flags=re.S)
        ET.fromstring(static)
        (output/'assets'/f'profile-arcade-still-{theme}.svg').write_text(static)


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--feed',type=Path)
    cli.add_argument('--calendar',type=Path)
    cli.add_argument('--output',type=Path,default=ROOT)
    cli.add_argument('--arcade-fallbacks',action='store_true')
    args = cli.parse_args()
    if args.arcade_fallbacks:
        arcade_fallbacks(args.output)
    else:
        refresh(args.feed.read_bytes() if args.feed else download(BLOG),
                args.calendar.read_bytes() if args.calendar else download(CONTRIBUTIONS), args.output)
