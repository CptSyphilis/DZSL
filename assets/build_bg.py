import os
import random, math

random.seed(7)

W, H = 1920, 1080
HORIZON = 772

BG_TOP   = "#070707"
BG_MID   = "#0d0d0d"
WARM     = "#16110a"
ACCENT   = "#d4b483"
RIDGE    = "#0f0f0f"
TREE_FAR = "#191919"
TREE_NEAR= "#101010"
TOWER    = "#161616"
PYLON    = "#161616"
CROW     = "#242424"
GROUND   = "#0b0b0b"
FIG      = "#050505"
DEADTREE = "#080808"
TUX_BODY = "#070707"
TUX_BELLY= "#1d1d1d"
TUX_FEET = "#2c281f"

parts = []

parts.append(f'''<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"  stop-color="{BG_TOP}"/>
    <stop offset="55%" stop-color="{BG_MID}"/>
    <stop offset="72%" stop-color="{WARM}"/>
    <stop offset="100%" stop-color="{BG_MID}"/>
  </linearGradient>
  <radialGradient id="moonGlow" cx="50%" cy="50%" r="50%">
    <stop offset="0%"  stop-color="{ACCENT}" stop-opacity="0.22"/>
    <stop offset="35%" stop-color="{ACCENT}" stop-opacity="0.08"/>
    <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vign" cx="50%" cy="46%" r="75%">
    <stop offset="0%"  stop-color="#000000" stop-opacity="0"/>
    <stop offset="70%" stop-color="#000000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0.55"/>
  </radialGradient>
</defs>''')

parts.append(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')

star = []
for _ in range(70):
    x = random.uniform(0, W); y = random.uniform(0, HORIZON-120)
    r = random.uniform(0.4, 1.3)
    o = random.uniform(0.05, 0.30)
    star.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#c9c9c9" opacity="{o:.2f}"/>')
parts.append('<g>' + ''.join(star) + '</g>')

MX, MY = 470, 360
parts.append(f'<circle cx="{MX}" cy="{MY}" r="320" fill="url(#moonGlow)"/>')
parts.append(f'<circle cx="{MX}" cy="{MY}" r="58" fill="{ACCENT}" opacity="0.85"/>')
parts.append(f'<circle cx="{MX-18}" cy="{MY-14}" r="10" fill="{BG_MID}" opacity="0.18"/>')
parts.append(f'<circle cx="{MX+16}" cy="{MY+10}" r="14" fill="{BG_MID}" opacity="0.15"/>')
parts.append(f'<circle cx="{MX+4}" cy="{MY-26}" r="6"  fill="{BG_MID}" opacity="0.18"/>')

def crow(x, y, s, op):
    return (f'<path d="M {x:.0f} {y:.0f} Q {x+s*0.5:.0f} {y-s*0.65:.0f} {x+s:.0f} {y:.0f} '
            f'Q {x+s*1.5:.0f} {y-s*0.65:.0f} {x+s*2:.0f} {y:.0f}" '
            f'fill="none" stroke="{CROW}" stroke-width="{max(1.4,s*0.10):.1f}" '
            f'stroke-linecap="round" opacity="{op:.2f}"/>')
crows = [crow(720,250,22,.8), crow(790,230,17,.7), crow(840,265,13,.6),
         crow(640,300,11,.5), crow(900,210,9,.45)]
parts.append('<g>' + ''.join(crows) + '</g>')

ridge = [f'M 0 {HORIZON}']
x = 0
y = HORIZON-30
while x < W:
    x += random.uniform(90,180)
    y = HORIZON - random.uniform(10, 70)
    ridge.append(f'L {x:.0f} {y:.0f}')
ridge.append(f'L {W} {HORIZON} L {W} {H} L 0 {H} Z')
parts.append(f'<path d="{" ".join(ridge)}" fill="{RIDGE}"/>')

def pylon(cx, base, h, w, op=0.9):
    top = base - h
    tw = w*0.32
    g = [f'<g stroke="{PYLON}" fill="none" stroke-width="2.2" opacity="{op}">']
    g.append(f'<path d="M {cx-w} {base} L {cx-tw} {top} M {cx+w} {base} L {cx+tw} {top}"/>')
    n=6
    for i in range(n):
        t0=i/n; t1=(i+1)/n
        lx0=cx-w+(w-tw)*t0; rx0=cx+w-(w-tw)*t0; yy0=base-(h)*t0
        lx1=cx-w+(w-tw)*t1; rx1=cx+w-(w-tw)*t1; yy1=base-(h)*t1
        g.append(f'<path d="M {lx0:.0f} {yy0:.0f} L {rx1:.0f} {yy1:.0f} M {rx0:.0f} {yy0:.0f} L {lx1:.0f} {yy1:.0f}"/>')
        g.append(f'<path d="M {lx0:.0f} {yy0:.0f} L {rx0:.0f} {yy0:.0f}"/>')
    g.append(f'<path d="M {cx-w*1.5} {top+22} L {cx+w*1.5} {top+22}"/>')
    g.append(f'<path d="M {cx-w*1.2} {top+44} L {cx+w*1.2} {top+44}"/>')
    g.append(f'<path d="M {cx} {top} L {cx} {top+44}"/>')
    g.append('</g>')
    return ''.join(g), (cx-w*1.5, top+22), (cx+w*1.5, top+22)

p1, l1, r1 = pylon(995, HORIZON-6, 150, 30, op=0.55)
p2, l2, r2 = pylon(1210, HORIZON-2, 120, 24, op=0.45)
def wire(a, b, sag, op):
    mx=(a[0]+b[0])/2; my=max(a[1],b[1])+sag
    return f'<path d="M {a[0]:.0f} {a[1]:.0f} Q {mx:.0f} {my:.0f} {b[0]:.0f} {b[1]:.0f}" fill="none" stroke="{PYLON}" stroke-width="1.4" opacity="{op}"/>'
parts.append(wire(r1, l2, 34, 0.4))
parts.append(p1); parts.append(p2)

def fir(x, ground, h, w):
    p = (f'M {x-w:.0f} {ground:.0f} '
         f'L {x-w*0.48:.0f} {ground-h*0.42:.0f} L {x-w*0.66:.0f} {ground-h*0.42:.0f} '
         f'L {x-w*0.34:.0f} {ground-h*0.72:.0f} L {x-w*0.48:.0f} {ground-h*0.72:.0f} '
         f'L {x:.0f} {ground-h:.0f} '
         f'L {x+w*0.48:.0f} {ground-h*0.72:.0f} L {x+w*0.34:.0f} {ground-h*0.72:.0f} '
         f'L {x+w*0.66:.0f} {ground-h*0.42:.0f} L {x+w*0.48:.0f} {ground-h*0.42:.0f} '
         f'L {x+w:.0f} {ground:.0f} Z')
    return f'<path d="{p}"/>'

far = [f'<g fill="{TREE_FAR}">']
x = -20
while x < W+20:
    x += random.uniform(26, 46)
    if 360 < x < 660:
        continue
    h = random.uniform(40, 78); w = h*random.uniform(0.34,0.42)
    far.append(fir(x, HORIZON+random.uniform(0,8), h, w))
far.append('</g>')
parts.append(''.join(far))

def water_tower(cx, base, scale=1.0):
    s=scale
    tankw=58*s; tankh=46*s; legh=120*s; top=base-legh
    g=[f'<g fill="{TOWER}" stroke="{TOWER}">']
    g.append(f'<path d="M {cx-tankw} {top} '
             f'Q {cx-tankw} {top-tankh} {cx} {top-tankh} '
             f'Q {cx+tankw} {top-tankh} {cx+tankw} {top} '
             f'L {cx+tankw*0.8} {top+14*s} L {cx-tankw*0.8} {top+14*s} Z"/>')
    g.append(f'<path d="M {cx-10*s} {top-tankh} L {cx} {top-tankh-12*s} L {cx+10*s} {top-tankh} Z"/>')
    g.append('</g>')
    g2=[f'<g stroke="{TOWER}" stroke-width="{3*s:.1f}" fill="none">']
    g2.append(f'<path d="M {cx-tankw*0.7} {top+12*s} L {cx-tankw*0.5} {base}"/>')
    g2.append(f'<path d="M {cx+tankw*0.7} {top+12*s} L {cx+tankw*0.5} {base}"/>')
    g2.append(f'<path d="M {cx-tankw*0.35} {top+12*s} L {cx-tankw*0.22} {base}"/>')
    g2.append(f'<path d="M {cx+tankw*0.35} {top+12*s} L {cx+tankw*0.22} {base}"/>')
    for t in (0.33,0.66):
        yy=top+12*s+(base-(top+12*s))*t
        sp=tankw*(0.7-(0.7-0.22)*t)
        g2.append(f'<path d="M {cx-sp} {yy:.0f} L {cx+sp} {yy:.0f}"/>')
    g2.append('</g>')
    return ''.join(g)+''.join(g2)
parts.append(water_tower(760, HORIZON+6, 1.05))

near = [f'<g fill="{TREE_NEAR}">']
for x in list(range(-10, 360, 30)) + list(range(1500, W+20, 32)):
    xx = x + random.uniform(-6,6)
    h = random.uniform(70, 130); w = h*random.uniform(0.36,0.44)
    near.append(fir(xx, HORIZON+random.uniform(6,18), h, w))
near.append('</g>')
parts.append(''.join(near))

parts.append(f'<path d="M 0 {H} L 0 905 '
             f'Q 480 868 980 892 Q 1430 912 1920 872 L {W} {H} Z" fill="{GROUND}"/>')

def dead_tree(x0, y0):
    g=[f'<g stroke="{DEADTREE}" stroke-linecap="round" fill="none">']
    g.append(f'<path d="M {x0} {y0} C {x0-6} {y0-90} {x0+8} {y0-150} {x0} {y0-210}" stroke-width="11"/>')
    br=[(y0-150, -1, 70, 5),(y0-120, 1, 86, 6),(y0-185, 1, 54, 4),(y0-175,-1,60,4),(y0-205,1,40,3)]
    for by, d, ln, sw in br:
        ex=x0+d*ln; ey=by-ln*0.7
        g.append(f'<path d="M {x0+ (0 if d<0 else 4)} {by} Q {x0+d*ln*0.5:.0f} {by-ln*0.2:.0f} {ex:.0f} {ey:.0f}" stroke-width="{sw}"/>')
        g.append(f'<path d="M {ex:.0f} {ey:.0f} l {d*16} {-10}" stroke-width="2"/>')
        g.append(f'<path d="M {ex:.0f} {ey:.0f} l {d*8} {-18}" stroke-width="2"/>')
    g.append('</g>')
    return ''.join(g)
parts.append(dead_tree(1120, 892))

def tux(cx, base, s=1.0):
    g=[]
    bw=30*s; bh=46*s
    bodyTop=base-bh*2
    g.append(f'<g fill="{TUX_FEET}">')
    g.append(f'<ellipse cx="{cx-12*s}" cy="{base-2}" rx="{12*s}" ry="{5*s}"/>')
    g.append(f'<ellipse cx="{cx+12*s}" cy="{base-2}" rx="{12*s}" ry="{5*s}"/>')
    g.append('</g>')
    g.append(f'<path fill="{TUX_BODY}" d="M {cx} {bodyTop} '
             f'C {cx-bw*1.3} {bodyTop} {cx-bw*1.45} {base-bh*0.2} {cx-bw*0.9} {base-4} '
             f'L {cx+bw*0.9} {base-4} '
             f'C {cx+bw*1.45} {base-bh*0.2} {cx+bw*1.3} {bodyTop} {cx} {bodyTop} Z"/>')
    g.append(f'<path fill="{TUX_BELLY}" d="M {cx} {bodyTop+14*s} '
             f'C {cx-bw*0.78} {bodyTop+14*s} {cx-bw*0.86} {base-bh*0.18} {cx-bw*0.5} {base-6} '
             f'L {cx+bw*0.5} {base-6} '
             f'C {cx+bw*0.86} {base-bh*0.18} {cx+bw*0.78} {bodyTop+14*s} {cx} {bodyTop+14*s} Z"/>')
    g.append(f'<path fill="{TUX_BODY}" d="M {cx-bw*1.05} {bodyTop+26*s} q {-14*s} {18*s} {2*s} {34*s} q {6*s} {-6*s} {6*s} {-20*s} Z"/>')
    g.append(f'<path fill="{TUX_BODY}" d="M {cx+bw*1.05} {bodyTop+26*s} q {14*s} {18*s} {-2*s} {34*s} q {-6*s} {-6*s} {-6*s} {-20*s} Z"/>')
    hr=20*s; hy=bodyTop-hr*0.5
    g.append(f'<circle fill="{TUX_BODY}" cx="{cx}" cy="{hy:.0f}" r="{hr:.0f}"/>')
    g.append(f'<path fill="{ACCENT}" opacity="0.8" d="M {cx-3*s} {hy+4*s} l {-12*s} {3*s} l {12*s} {5*s} Z"/>')
    return '<g>'+''.join(g)+'</g>'
parts.append(tux(1318, 880, 0.92))

def survivor(cx, feet):
    g=[f'<g fill="{FIG}">']
    g.append(f'<ellipse cx="{cx}" cy="{feet-244}" rx="16" ry="18"/>')
    g.append(f'<rect x="{cx-17}" y="{feet-236}" width="34" height="9" rx="3"/>')
    g.append(f'<circle cx="{cx}" cy="{feet-258}" r="4"/>')
    g.append(f'<rect x="{cx-6}" y="{feet-228}" width="12" height="12"/>')
    g.append(f'<path d="M {cx-18} {feet-218} L {cx+20} {feet-220} '
             f'L {cx+24} {feet-150} L {cx+18} {feet-104} L {cx-16} {feet-104} '
             f'L {cx-20} {feet-160} Z"/>')
    g.append(f'<rect x="{cx+16}" y="{feet-214}" width="26" height="86" rx="9"/>')
    g.append(f'<rect x="{cx+14}" y="{feet-198}" width="8" height="54" rx="3"/>')
    g.append(f'<path d="M {cx-14} {feet-212} L {cx-30} {feet-150} L {cx-18} {feet-128} '
             f'L {cx-8} {feet-150} L {cx-2} {feet-204} Z"/>')
    g.append(f'<path d="M {cx-30} {feet-150} L {cx-6} {feet-132} L {cx-10} {feet-120} '
             f'L {cx-34} {feet-140} Z"/>')
    g.append(f'<path d="M {cx-16} {feet-106} L {cx-2} {feet-106} L {cx-2} {feet} L {cx-18} {feet} Z"/>')
    g.append(f'<path d="M {cx} {feet-106} L {cx+16} {feet-106} L {cx+20} {feet} L {cx+4} {feet} Z"/>')
    g.append(f'<path d="M {cx-22} {feet} L {cx-2} {feet} L {cx-2} {feet-8} L {cx-22} {feet-6} Z"/>')
    g.append(f'<path d="M {cx} {feet} L {cx+22} {feet} L {cx+22} {feet-6} L {cx} {feet-8} Z"/>')
    g.append('</g>')
    g.append(f'<g fill="{FIG}">'
             f'<path d="M {cx+8} {feet-156} L {cx-44} {feet-118} L {cx-40} {feet-110} L {cx+12} {feet-148} Z"/>'
             f'<path d="M {cx+8} {feet-160} L {cx+22} {feet-150} L {cx+18} {feet-140} L {cx+6} {feet-148} Z"/>'
             f'<rect x="{cx-30}" y="{feet-126}" width="7" height="16" rx="2" transform="rotate(-34 {cx-26} {feet-118})"/>'
             f'</g>')
    return ''.join(g)
parts.append(survivor(1410, 876))

scan=['<g opacity="0.05">']
yv=0
while yv<H:
    scan.append(f'<rect x="0" y="{yv}" width="{W}" height="1" fill="#000"/>')
    yv+=3
scan.append('</g>')
parts.append(''.join(scan))

parts.append(f'<rect width="{W}" height="{H}" fill="url(#vign)"/>')
parts.append(f'''<g font-family="monospace" fill="{ACCENT}" opacity="0.16">
  <text x="40" y="{H-44}" font-size="15" letter-spacing="3">CHERNARUS · 221100</text>
  <text x="40" y="{H-24}" font-size="12" letter-spacing="2">S 45.18°  E 014.31°  · DZSL</text>
  <rect x="40" y="{H-66}" width="150" height="1.4"/>
</g>''')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
       f'width="{W}" height="{H}">' + ''.join(parts) + '</svg>')

ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_PATH = os.path.join(ASSET_DIR, "dzsl-bg.svg")
PNG_PATH = os.path.join(ASSET_DIR, "dzsl-bg.png")

with open(SVG_PATH, 'w') as f:
    f.write(svg)
print("wrote svg", len(svg), "bytes")

import cairosvg
cairosvg.svg2png(url=SVG_PATH, write_to=PNG_PATH,
                 output_width=1920, output_height=1080)
print("wrote png")
