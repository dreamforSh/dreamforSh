#!/usr/bin/env python3
"""Render the CurseForge download card (assets/curseforge-{dark,light}.svg).

Project list and download counts come from the public CFWidget API, which
mirrors CurseForge without needing an API key. If any request fails, the
existing cards are left untouched so a bad fetch never publishes a wrong total.
"""
import json
import pathlib
import subprocess
import sys
import time
from xml.sax.saxutils import escape

AUTHOR = 'dreamforsh'
API = 'https://api.cfwidget.com'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'assets'

FONT = ("'Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',"
        "'PingFang SC','Microsoft YaHei','Noto Sans CJK SC',sans-serif")
REDUCED = '@media (prefers-reduced-motion:reduce){*{animation:none!important}}'
# CurseForge logo from Simple Icons (CC0).
LOGO = ('M18.326 9.2145S23.2261 8.4418 24 6.1882h-7.5066V4.4H0l2.0318 2.3576V9.173'
        's5.1267-.2665 7.1098 1.2372c2.7146 2.516-3.053 5.917-3.053 5.917L5.0995 19.6'
        'c1.5465-1.4726 4.494-3.3775 9.8983-3.2857-2.0565.65-4.1245 1.6651-5.7344 '
        '3.2857h10.9248l-1.0288-3.2726s-7.918-4.6688-.8336-7.1127z')
ACCENT = '#F16436'
W, H = 840, 132

THEMES = {
    'dark': dict(card='#161b22', border='#30363d', title='#e6edf3',
                 tile='#242938', edge='#ffffff', edge_op=.10, gloss=.13,
                 glow=.18, dots=.07, mark=.06),
    'light': dict(card='#ffffff', border='#d0d7de', title='#1f2328',
                  tile='#F4F2ED', edge='#000000', edge_op=.07, gloss=.55,
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


def fetch_total():
    author = get_json(f'{API}/author/search/{AUTHOR}')
    if not author.get('projects'):
        raise RuntimeError('no projects returned')
    return sum(int(get_json(f'{API}/{p["id"]}')['downloads']['total'])
               for p in author['projects'])


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


def sparkle(x, y, r, fill, delay):
    k = r * .22
    return (f'<path class="spk" style="animation-delay:{delay}s" fill="{fill}" '
            f'd="M{x} {y - r}Q{x + k} {y - k} {x + r} {y}Q{x + k} {y + k} {x} {y + r}'
            f'Q{x - k} {y + k} {x - r} {y}Q{x - k} {y - k} {x} {y - r}Z"/>')


def odometer(total, right, baseline, size):
    """Right-aligned digits that roll up like an odometer.

    The resting transform is the final value, so the number is still correct
    when animations are disabled.
    """
    step, digit_w, comma_w = size + 10, size * .62, size * .3
    text = f'{total:,}'
    x = right - sum(comma_w if c == ',' else digit_w for c in text)
    left = x
    css, out, i = set(), [], 0
    for ch in text:
        if ch == ',':
            out.append(f'<text class="num" x="{x:.1f}" y="{baseline}">,</text>')
            x += comma_w
            continue
        target = 10 + int(ch)
        css.add(f'@keyframes o{target}{{from{{transform:translateY(0)}}'
                f'to{{transform:translateY(-{target * step}px)}}}}')
        strip = ''.join(f'<text class="num" x="{x:.1f}" y="{baseline + k * step}">{k % 10}</text>'
                        for k in range(20))
        out.append(f'<g style="transform:translateY(-{target * step}px);'
                   f'animation:o{target} {1.6 + i * .12:.2f}s cubic-bezier(.15,.85,.25,1) '
                   f'{.5 + i * .08:.2f}s both">{strip}</g>')
        x += digit_w
        i += 1
    window = (f'<clipPath id="odo"><rect x="0" y="{baseline - size * .82:.0f}" width="{W}" '
              f'height="{size * 1.06:.0f}"/></clipPath>')
    return left, window, ''.join(sorted(css)), f'<g clip-path="url(#odo)">{"".join(out)}</g>'


def card(theme, total):
    t = THEMES[theme]
    border = round_rect_path(.5, .5, W - 1, H - 1, 14)
    right, size = W - 30, 56
    baseline = H / 2 + size * .36
    left, window, roll_css, number = odometer(total, right, baseline, size)
    tile_x, tile_y, tile = 28, (H - 64) / 2, 64

    box = 'transform-box:fill-box;transform-origin:center'
    style = (
        '.card{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}'
        '.cm{animation:run 12s linear infinite}'
        f'.orb{{animation:drift 14s ease-in-out infinite alternate;{box}}}'
        f'.mark{{animation:bob 6s ease-in-out infinite;{box}}}'
        '.flt{animation:flt 3.6s ease-in-out infinite}'
        f'.ping{{animation:ping 6s ease-out 1.5s infinite;opacity:0;{box}}}'
        f'.spk{{animation:spk 2.4s ease-in-out infinite;opacity:0;{box}}}'
        '.lead{animation:slide .7s cubic-bezier(.2,.8,.2,1) .2s both}'
        f'.uline{{animation:grow 1.4s cubic-bezier(.2,.8,.2,1) 1.6s both;'
        'transform-box:fill-box;transform-origin:right center}'
        f'.ttl{{font:700 16px {FONT};fill:{t["title"]}}}'
        f'.en{{font:700 10px {FONT};letter-spacing:1.8px;fill:{ACCENT}}}'
        f'.num{{font:800 {size}px {FONT};fill:url(#ng)}}'
        '@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}'
        '@keyframes run{from{stroke-dashoffset:0}to{stroke-dashoffset:-100}}'
        '@keyframes drift{from{transform:translate(0,0)}to{transform:translate(60px,20px)}}'
        '@keyframes bob{0%,100%{transform:translateY(0) rotate(-6deg)}'
        '50%{transform:translateY(-6px) rotate(-2deg)}}'
        '@keyframes flt{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}'
        '@keyframes ping{0%{opacity:0;transform:scale(.9)}6%{opacity:1;transform:scale(1)}'
        '25%,100%{opacity:0;transform:scale(1.25)}}'
        '@keyframes spk{0%,100%{opacity:0;transform:scale(.4)}50%{opacity:1;transform:scale(1)}}'
        '@keyframes slide{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}'
        '@keyframes grow{from{transform:scaleX(0)}to{transform:none}}'
        f'{roll_css}{REDUCED}')
    defs = (
        f'<clipPath id="cc"><rect width="{W}" height="{H}" rx="14"/></clipPath>{window}'
        f'<pattern id="cdots" width="18" height="18" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r=".9" fill="{t["title"]}" fill-opacity="{t["dots"]}"/></pattern>'
        f'<radialGradient id="gl"><stop offset="0" stop-color="{ACCENT}" stop-opacity="{t["glow"]}"/>'
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="ng" gradientUnits="userSpaceOnUse" x1="{left:.0f}" y1="0" '
        f'x2="{right}" y2="0"><stop offset="0" stop-color="#FF8A3D"/>'
        f'<stop offset=".55" stop-color="{ACCENT}"/><stop offset="1" stop-color="#F472B6"/>'
        f'</linearGradient>'
        f'<linearGradient id="ul" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="#F472B6"/></linearGradient>'
        f'<linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="#fff" stop-opacity="{t["gloss"]}"/>'
        f'<stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    logo_tile = (
        f'<g transform="translate({tile_x} {tile_y})"><g class="flt">'
        f'<rect class="ping" x="-4" y="-4" width="{tile + 8}" height="{tile + 8}" rx="20" '
        f'fill="{ACCENT}" fill-opacity=".12" stroke="{ACCENT}" stroke-width="1.6"/>'
        f'<rect width="{tile}" height="{tile}" rx="16" fill="{t["tile"]}"/>'
        f'<path transform="translate(8 {32 - 12 * 2 + .2}) scale(2)" d="{LOGO}" fill="{ACCENT}"/>'
        f'<rect width="{tile}" height="{tile}" rx="16" fill="url(#gloss)"/>'
        f'<rect x=".75" y=".75" width="{tile - 1.5}" height="{tile - 1.5}" rx="15.25" '
        f'stroke="{t["edge"]}" stroke-opacity="{t["edge_op"]}" stroke-width="1.5"/></g></g>')
    sparks = (sparkle(right + 8, baseline - size * .78, 7, '#FBBF24', 2.6)
              + sparkle(right - 22, baseline - size * .98, 4.5, '#F472B6', 3.3)
              + sparkle(left - 14, baseline - size * .2, 5, '#FFB067', 3.9))
    body = (
        f'<path d="{border}" fill="{t["card"]}" stroke="{t["border"]}"/>'
        f'<g clip-path="url(#cc)"><rect width="{W}" height="{H}" fill="url(#cdots)"/>'
        f'<circle class="orb" cx="70" cy="20" r="170" fill="url(#gl)"/>'
        f'<circle class="orb" style="animation-delay:-7s" cx="{right - 120}" cy="{H}" r="190" '
        f'fill="url(#gl)"/>'
        f'<g class="mark"><path transform="translate(330 28) scale(5)" d="{LOGO}" '
        f'fill="{ACCENT}" fill-opacity="{t["mark"]}"/></g></g>'
        f'{comets(border, [ACCENT, "#FBBF24"])}'
        f'{logo_tile}'
        f'<g class="lead"><text class="ttl" x="{tile_x + tile + 18}" y="{H / 2 - 3}">'
        f'CurseForge 总下载量</text>'
        f'<text class="en" x="{tile_x + tile + 18}" y="{H / 2 + 19}">TOTAL DOWNLOADS</text></g>'
        f'{number}'
        f'<rect class="uline" x="{left:.0f}" y="{baseline + 12:.0f}" width="{right - left:.0f}" '
        f'height="2" rx="1" fill="url(#ul)"/>'
        f'{sparks}')
    label = f'CurseForge 总下载量 {total:,}'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" fill="none" role="img" aria-label="{escape(label)}">'
            f'<style>{style}</style><defs>{defs}</defs><g class="card">{body}</g></svg>')


def main():
    try:
        total = fetch_total()
    except Exception as e:  # keep the last good cards
        print(f'::warning::CurseForge fetch failed, cards not updated: {e}')
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (OUT / f'curseforge-{theme}.svg').write_text(card(theme, total), encoding='utf-8')
    print(f'{total:,} downloads')
    return 0


if __name__ == '__main__':
    sys.exit(main())
