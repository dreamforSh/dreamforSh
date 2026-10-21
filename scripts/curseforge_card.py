#!/usr/bin/env python3
"""Render the CurseForge download card (assets/curseforge-{dark,light}.svg).

Project list and download counts come from the public CFWidget API, which
mirrors CurseForge without needing an API key. If any request fails, the
existing cards are left untouched so a bad fetch never publishes a wrong total.
"""
import datetime
import json
import pathlib
import subprocess
import sys
import time
from xml.sax.saxutils import escape

AUTHOR = 'dreamforsh'
API = 'https://api.cfwidget.com'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'assets'
TOP = 5

FONT = ("'Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',"
        "'PingFang SC','Microsoft YaHei','Noto Sans CJK SC',sans-serif")
MONO = "'JetBrains Mono','SF Mono',Consolas,'Liberation Mono',Menlo,monospace"
REDUCED = '@media (prefers-reduced-motion:reduce){*{animation:none!important}}'
# CurseForge logo from Simple Icons (CC0).
LOGO = ('M18.326 9.2145S23.2261 8.4418 24 6.1882h-7.5066V4.4H0l2.0318 2.3576V9.173'
        's5.1267-.2665 7.1098 1.2372c2.7146 2.516-3.053 5.917-3.053 5.917L5.0995 19.6'
        'c1.5465-1.4726 4.494-3.3775 9.8983-3.2857-2.0565.65-4.1245 1.6651-5.7344 '
        '3.2857h10.9248l-1.0288-3.2726s-7.918-4.6688-.8336-7.1127z')
ACCENT = '#F16436'
W, H = 840, 214

THEMES = {
    'dark': dict(card='#161b22', border='#30363d', title='#e6edf3',
                 muted='#8b949e', label='#c9d1d9', track='#21262d',
                 glow=.18, dots=.07, mark=.06),
    'light': dict(card='#ffffff', border='#d0d7de', title='#1f2328',
                  muted='#656d76', label='#424a53', track='#eaeef2',
                  glow=.11, dots=.07, mark=.05),
}


def get_json(url, attempts=3):
    for n in range(attempts):
        p = subprocess.run(['curl', '-sfL', '--max-time', '60', '-A',
                            'dreamforSh-profile-card', url], capture_output=True)
        if p.returncode == 0:
            data = json.loads(p.stdout.decode('utf-8'))
            if 'error' not in data:
                return data
        time.sleep(15 * (n + 1))
    raise RuntimeError(f'failed to fetch {url}')


def fetch_projects():
    author = get_json(f'{API}/author/search/{AUTHOR}')
    projects = []
    for p in author['projects']:
        d = get_json(f'{API}/{p["id"]}')
        projects.append((d['title'].strip(), int(d['downloads']['total'])))
    return sorted(projects, key=lambda p: -p[1])


def short(n):
    if n >= 1_000_000:
        return f'{n / 1_000_000:.2f}M'
    if n >= 1_000:
        return f'{n / 1_000:.1f}K'
    return str(n)


def clip_text(s, limit):
    s = ' '.join(s.split())
    return s if len(s) <= limit else s[:limit - 1].rstrip(' -') + '…'


def round_rect_path(x, y, w, h, r):
    return (f'M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}'
            f'V{y + h - r}A{r} {r} 0 0 1 {x + w - r} {y + h}H{x + r}'
            f'A{r} {r} 0 0 1 {x} {y + h - r}V{y + r}A{r} {r} 0 0 1 {x + r} {y}Z')


def comets(path, colors, dur=12):
    out = []
    for n, color in enumerate(colors):
        phase = n * dur / len(colors)
        for dash, ahead, width, op in ((18, 0, 3, .16), (9, 9, 2, .45), (2.5, 15.5, 2.6, 1)):
            out.append(f'<path class="cm" d="{path}" pathLength="100" stroke="{color}" '
                       f'stroke-width="{width}" stroke-opacity="{op}" stroke-linecap="round" '
                       f'stroke-dasharray="{dash} {100 - dash}" '
                       f'style="animation-delay:{-(phase + ahead / 100 * dur):.2f}s"/>')
    return ''.join(out)


def odometer(total, x, baseline, size):
    """Digits roll up like an odometer; the resting transform is the final value."""
    step, digit_w, comma_w = size + 10, size * .62, size * .3
    css, out, i = set(), [], 0
    for ch in f'{total:,}':
        if ch == ',':
            out.append(f'<text class="num" x="{x:.1f}" y="{baseline}">,</text>')
            x += comma_w
            continue
        target = 10 + int(ch)
        css.add(f'@keyframes o{target}{{from{{transform:translateY(0)}}'
                f'to{{transform:translateY(-{target * step}px)}}}}')
        strip = ''.join(f'<text class="num" x="{x:.1f}" y="{baseline + k * step}">{k % 10}</text>'
                        for k in range(20))
        out.append(f'<g class="roll" style="transform:translateY(-{target * step}px);'
                   f'animation:o{target} {1.6 + i * .12:.2f}s cubic-bezier(.15,.85,.25,1) '
                   f'{.5 + i * .08:.2f}s both">{strip}</g>')
        x += digit_w
        i += 1
    window = (f'<clipPath id="odo"><rect x="0" y="{baseline - size * .82:.0f}" width="{W}" '
              f'height="{size * 1.06:.0f}"/></clipPath>')
    return window, ''.join(sorted(css)), f'<g clip-path="url(#odo)">{"".join(out)}</g>'


def card(theme, projects, updated):
    t = THEMES[theme]
    total = sum(d for _, d in projects)
    top = projects[:TOP]
    peak = top[0][1] if top else 1
    border = round_rect_path(.5, .5, W - 1, H - 1, 14)
    window, roll_css, number = odometer(total, 31, 112, 46)

    rows = []
    bar_x, bar_w, y0, gap = 540, 190, 76, 27
    for i, (name, downloads) in enumerate(top):
        cy = y0 + i * gap
        w = max(6, bar_w * downloads / peak)
        d = .7 + i * .12
        rows.append(
            f'<g class="fade" style="animation-delay:{d:.2f}s">'
            f'<text class="rk" x="336" y="{cy + 4}">{i + 1:02d}</text>'
            f'<text class="nm" x="362" y="{cy + 4.5}">{escape(clip_text(name, 24))}</text>'
            f'<text class="val" x="{W - 24}" y="{cy + 4.5}">{short(downloads)}</text></g>'
            f'<rect x="{bar_x}" y="{cy - 4}" width="{bar_w}" height="8" rx="4" fill="{t["track"]}"/>'
            f'<g class="bar" style="animation-delay:{d + .1:.2f}s">'
            f'<rect x="{bar_x}" y="{cy - 4}" width="{w:.1f}" height="8" rx="4" fill="url(#bf)"/>'
            f'<rect x="{bar_x}" y="{cy - 4}" width="{w:.1f}" height="8" rx="4" fill="url(#bs)"/></g>')

    style = (
        '.card{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}'
        '.cm{animation:run 12s linear infinite}'
        '.orb{animation:drift 14s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:center}'
        '.mark{animation:bob 6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
        '.fade{animation:fade .7s ease both}'
        '.bar{animation:grow 1.2s cubic-bezier(.2,.8,.2,1) both;transform-box:fill-box;transform-origin:left center}'
        '.lead{animation:slide .7s cubic-bezier(.2,.8,.2,1) .2s both}'
        f'.ttl{{font:700 15px {FONT};fill:{t["title"]}}}'
        f'.en{{font:700 10px {FONT};letter-spacing:1.6px;fill:{ACCENT}}}'
        f'.num{{font:800 46px {FONT};fill:url(#ng)}}'
        f'.sub{{font:600 12px {FONT};fill:{t["label"]}}}'
        f'.meta{{font:500 11px {FONT};fill:{t["muted"]}}}'
        f'.rk{{font:700 11px {MONO};fill:{t["muted"]}}}'
        f'.nm{{font:600 12.5px {FONT};fill:{t["title"]}}}'
        f'.val{{font:700 12px {MONO};fill:{t["label"]};text-anchor:end}}'
        '@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}'
        '@keyframes run{from{stroke-dashoffset:0}to{stroke-dashoffset:-100}}'
        '@keyframes drift{from{transform:translate(0,0)}to{transform:translate(70px,30px)}}'
        '@keyframes bob{0%,100%{transform:translateY(0) rotate(-6deg)}50%{transform:translateY(-6px) rotate(-2deg)}}'
        '@keyframes fade{from{opacity:0}to{opacity:1}}'
        '@keyframes grow{from{transform:scaleX(0)}to{transform:none}}'
        '@keyframes slide{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}'
        f'{roll_css}{REDUCED}')
    defs = (
        f'<clipPath id="cc"><rect width="{W}" height="{H}" rx="14"/></clipPath>{window}'
        f'<pattern id="cdots" width="18" height="18" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r=".9" fill="{t["title"]}" fill-opacity="{t["dots"]}"/></pattern>'
        f'<radialGradient id="gl"><stop offset="0" stop-color="{ACCENT}" stop-opacity="{t["glow"]}"/>'
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="ng" gradientUnits="userSpaceOnUse" x1="31" y1="0" x2="270" y2="0">'
        f'<stop offset="0" stop-color="#FF8A3D"/><stop offset=".55" stop-color="{ACCENT}"/>'
        f'<stop offset="1" stop-color="#F472B6"/></linearGradient>'
        f'<linearGradient id="bf" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFB067"/>'
        f'<stop offset="1" stop-color="{ACCENT}"/></linearGradient>'
        f'<linearGradient id="bs" gradientUnits="userSpaceOnUse" x1="{bar_x - 120}" y1="0" '
        f'x2="{bar_x - 20}" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="#fff" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="0 0;{bar_w + 140} 0;{bar_w + 140} 0" keyTimes="0;.45;1" dur="4s" begin="2s" '
        f'repeatCount="indefinite"/></linearGradient>')
    mid = 306
    body = (
        f'<path d="{border}" fill="{t["card"]}" stroke="{t["border"]}"/>'
        f'<g clip-path="url(#cc)"><rect width="{W}" height="{H}" fill="url(#cdots)"/>'
        f'<circle class="orb" cx="90" cy="30" r="200" fill="url(#gl)"/>'
        f'<g class="mark"><path transform="translate(192 116) scale(4.6)" d="{LOGO}" '
        f'fill="{ACCENT}" fill-opacity="{t["mark"]}"/></g></g>'
        f'{comets(border, [ACCENT, "#FBBF24"])}'
        f'<line x1="{mid}" y1="28" x2="{mid}" y2="{H - 28}" stroke="{t["border"]}" '
        f'stroke-dasharray="2 5" stroke-linecap="round"/>'
        f'<g class="lead"><path transform="translate(31 26) scale(.75)" d="{LOGO}" fill="{ACCENT}"/>'
        f'<text class="ttl" x="57" y="41">CurseForge 下载量</text>'
        f'<text class="en" x="210" y="40">DOWNLOADS</text></g>'
        f'{number}'
        f'<g class="fade" style="animation-delay:1.2s">'
        f'<text class="sub" x="31" y="146">总下载量</text>'
        f'<text class="meta" x="31" y="170">{len(projects)} 个项目 · 更新于 {updated}</text></g>'
        f'<g class="fade" style="animation-delay:.5s"><text class="en" x="336" y="40" '
        f'style="fill:{t["muted"]}">TOP {len(top)}</text></g>'
        f'{"".join(rows)}')
    label = f'CurseForge 总下载量 {total:,}'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" fill="none" role="img" aria-label="{escape(label)}">'
            f'<style>{style}</style><defs>{defs}</defs><g class="card">{body}</g></svg>')


def main():
    try:
        projects = fetch_projects()
    except Exception as e:  # keep the last good cards
        print(f'::warning::CurseForge fetch failed, cards not updated: {e}')
        return 0
    if not projects:
        print('::warning::no CurseForge projects returned, cards not updated')
        return 0
    updated = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (OUT / f'curseforge-{theme}.svg').write_text(card(theme, projects, updated),
                                                     encoding='utf-8')
    print(f'{len(projects)} projects, {sum(d for _, d in projects):,} downloads')
    return 0


if __name__ == '__main__':
    sys.exit(main())
