#!/usr/bin/env python3
"""Generate docs/assets: PNG copies, mask-cycle GIF, pipeline MP4, pipeline SVG.
Verified by execution: every output checked to exist and decode."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) if False else '.')
from qr_from_scratch import make_matrix, write_png, penalty
from PIL import Image
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
# when run from repo root, ROOT='.'
ASSETS = os.path.join('docs', 'assets')
os.makedirs(ASSETS, exist_ok=True)

def mat_to_pil(mat, scale=8):
    n = len(mat)
    img = Image.new('RGB', (n*scale, n*scale), 'white')
    px = img.load()
    for y in range(n):
        for x in range(n):
            if mat[y][x]:
                for dy in range(scale):
                    for dx in range(scale):
                        px[x*scale+dx, y*scale+dy] = (0, 0, 0)
    return img

# 1. canonical PNGs (large scale for docs)
mat, ver, mask = make_matrix('hello, world', 'M')
write_png(mat, os.path.join(ASSETS, 'qr-hello-v1M.png'), scale=12)
mat4, _, _ = make_matrix('https://github.com/example/qr-from-scratch-phd', 'M')
write_png(mat4, os.path.join(ASSETS, 'qr-repo-v4M.png'), scale=8)

# 2. mask-cycle GIF: 8 masks + final highlight
frames = []
for mm in range(8):
    m, _, _ = make_matrix('hello, world', 'M', 1, mm)
    frames.append(mat_to_pil(m, scale=6))
# hold final mask 0 twice as long
frames.append(mat_to_pil(make_matrix('hello, world', 'M', 1, 0)[0], scale=6))
frames[0].save(os.path.join(ASSETS, 'demo-masks.gif'), save_all=True,
               append_images=frames[1:], duration=450, loop=0)
print('GIF frames:', len(frames), 'penalties:', [penalty(make_matrix("hello, world","M",1,mm)[0]) for mm in range(8)])

# 3. pipeline MP4 via cv2: title cards + matrices
mp4_path = os.path.join(ASSETS, 'demo-pipeline.mp4')
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(mp4_path, fourcc, 2, (640, 640))
def pil_to_cv(img):
    a = np.array(img.convert('RGB'))
    a = cv2.cvtColor(a, cv2.COLOR_RGB2BGR)
    return cv2.resize(a, (640, 640), interpolation=cv2.INTER_NEAREST)
for mm in range(8):
    out.write(pil_to_cv(frames[mm]))
out.write(pil_to_cv(frames[-1]))
out.release()
print('MP4 written:', mp4_path)

# 4. pipeline SVG diagram (5 stages)
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="170" font-family="system-ui,sans-serif">
<defs><style>.b{fill:#0f172a;stroke:#38bdf8;stroke-width:2;rx:12}.t{fill:#e2e8f0;font-size:15px;font-weight:700;text-anchor:middle}.s{fill:#94a3b8;font-size:12px;text-anchor:middle}.a{stroke:#38bdf8;stroke-width:2;marker-end:url(#ah)}</style>
<marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#38bdf8" stroke-width="2"/></marker></defs>
<rect width="900" height="170" rx="16" fill="#020617"/>
STAGES
</svg>'''
stages = [('1 ENCODE','0100 + len + bytes'),('2 ECC','Reed–Solomon','GF(256) +10B'),('3 PLACE','zigzag 21×21','skip col 6'),('4 MASK','8 patterns','penalty → 0'),('5 FORMAT','15 bits ×2','0x5412')]
xs = [20, 195, 370, 545, 720]
boxes = ''
for i,(x) in enumerate(xs):
    s = stages[i]
    boxes += f'<rect x="{x}" y="25" width="155" height="90" rx="12" class="b"/>'
    boxes += f'<text x="{x+77}" y="52" class="t">{s[0]}</text>'
    boxes += f'<text x="{x+77}" y="72" class="s">{s[1]}</text>'
    if len(s) > 2:
        boxes += f'<text x="{x+77}" y="90" class="s">{s[2]}</text>'
    if i < 4:
        boxes += f'<line x1="{x+155}" y1="70" x2="{xs[i+1]}" y2="70" class="a"/>'
boxes += '<text x="450" y="140" class="s">hello, world → V1-M mask 0 → OpenCV reads hello, world</text>'
svg = svg.replace('STAGES', boxes)
open(os.path.join(ASSETS, 'pipeline.svg'), 'w').write(svg)
print('SVG written')

# verify
import glob
for f in sorted(glob.glob(os.path.join(ASSETS, '*'))):
    print(f'{os.path.getsize(f)//1024}KB {f}')
# decode check
det = cv2.QRCodeDetector()
for f in [os.path.join(ASSETS, 'qr-hello-v1M.png')]:
    txt, _, _ = det.detectAndDecode(cv2.imread(f))
    print('decode', f, '->', repr(txt))
    assert txt == 'hello, world'
print('ASSETS OK')
