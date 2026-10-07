#!/usr/bin/env python3
"""QR Code maker from nothing: ~260 lines, zero third-party libraries.

Five pipeline stages (verified against Thonky/ISO 18004 + Nayuki reference):
  1. encode  - byte mode: mode(4b)+len(8b)+data, terminator, pad 0xEC/0x11
  2. ecc     - Reed-Solomon over GF(256) with primitive 0x11D
  3. place   - zigzag around finders/timing/alignment/dark/format
  4. mask    - try 8 masks, lowest 4-rule penalty wins
  5. format  - 15b BCH + XOR mask, written twice

Supports versions 1-6, EC levels L/M/Q/H, byte mode. Stdlib only.
Verified live with OpenCV QRCodeDetector (see verify.py).
Sources: Thonky tutorial, Denso Wave history, ISO/IEC 18004, Nayuki (MIT).
"""
import struct
import zlib

# --- EC block table: (ver,level)->(data_cw, ec_per_block, g1_n, g1_cw, g2_n, g2_cw) ---
EC = {
 (1,'L'):(19,7,1,19,0,0),(1,'M'):(16,10,1,16,0,0),(1,'Q'):(13,13,1,13,0,0),(1,'H'):(9,17,1,9,0,0),
 (2,'L'):(34,10,1,34,0,0),(2,'M'):(28,16,1,28,0,0),(2,'Q'):(22,22,1,22,0,0),(2,'H'):(16,28,1,16,0,0),
 (3,'L'):(55,15,1,55,0,0),(3,'M'):(44,26,1,44,0,0),(3,'Q'):(34,18,2,17,0,0),(3,'H'):(26,22,2,13,0,0),
 (4,'L'):(80,20,1,80,0,0),(4,'M'):(64,18,2,32,0,0),(4,'Q'):(48,26,2,24,0,0),(4,'H'):(36,16,4,9,0,0),
 (5,'L'):(108,26,1,108,0,0),(5,'M'):(86,24,2,43,0,0),(5,'Q'):(62,18,2,15,2,16),(5,'H'):(46,22,2,11,2,12),
 (6,'L'):(136,18,2,68,0,0),(6,'M'):(108,16,4,27,0,0),(6,'Q'):(76,24,4,19,0,0),(6,'H'):(60,28,4,15,0,0),
}
ALIGN = {1:[],2:[6,18],3:[6,22],4:[6,26],5:[6,30],6:[6,34]}
EC_BITS = {'L':0b01,'M':0b00,'Q':0b11,'H':0b10}
FMT_GEN = 0b10100110111
FMT_MASK = 0b101010000010010

# --- Galois field GF(256), primitive 0x11D ---
EXP = [0]*512
LOG = [0]*256
def _gf_init():
    x = 1
    for i in range(512):
        EXP[i] = x
        if i < 255:
            LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
_gf_init()
def gf_mul(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a]+LOG[b]]

def rs_gen(deg):
    p = [0]*(deg-1)+[1]
    r = 1
    for _ in range(deg):
        for j in range(deg):
            p[j] = gf_mul(p[j], r)
            if j+1 < deg:
                p[j] ^= p[j+1]
        r = gf_mul(r, 2)
    return p

def rs_rem(data, gen):
    r = [0]*len(gen)
    for b in data:
        f = b ^ r.pop(0)
        r.append(0)
        for i, c in enumerate(gen):
            r[i] ^= gf_mul(c, f)
    return r

# --- 1. encode ---
def encode_data(txt, ver, lv):
    dc, _, _, _, _, _ = EC[(ver, lv)]
    bits = []
    def put(v, n):
        for i in range(n-1, -1, -1):
            bits.append((v >> i) & 1)
    raw = txt.encode('utf-8')
    put(0b0100, 4)
    put(len(raw), 8)
    for b in raw:
        put(b, 8)
    put(0, min(4, dc*8-len(bits)))
    while len(bits) % 8:
        bits.append(0)
    for i, pb in enumerate([0xEC, 0x11]*((dc*8-len(bits))//16+2)):
        if len(bits) >= dc*8:
            break
        put(pb, 8)
    return [sum(bits[i+j] << (7-j) for j in range(8)) for i in range(0, len(bits), 8)]

def pick_version(txt, lv):
    n = len(txt.encode('utf-8'))
    for v in range(1, 7):
        dc, _, _, _, _, _ = EC[(v, lv)]
        if 4+8+n*8 <= dc*8:
            return v
    raise ValueError('too long for V1-V6 at %s' % lv)

def interleave(dcws, ver, lv):
    _, eb, n1, c1, n2, c2 = EC[(ver, lv)]
    blks, off, gen = [], 0, rs_gen(eb)
    for n, c in ((n1, c1), (n2, c2)):
        for _ in range(n):
            d = dcws[off:off+c]
            off += c
            e = rs_rem(d, gen)
            blks.append((d, e))
    out = []
    for i in range(max(len(d) for d, _ in blks)):
        for d, _ in blks:
            if i < len(d):
                out.append(d[i])
    for i in range(eb):
        for _, e in blks:
            out.append(e[i])
    return out

# --- matrix helpers (x=col, y=row) ---
def new_grid(n):
    return [[False]*n for _ in range(n)]

def draw_finder(m, f, cx, cy):
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            x, y = cx+dx, cy+dy
            if 0 <= x < len(m) and 0 <= y < len(m):
                m[y][x] = max(abs(dx), abs(dy)) not in (2, 4)
                f[y][x] = True

def draw_align(m, f, cx, cy):
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            m[cy+dy][cx+dx] = max(abs(dx), abs(dy)) != 1
            f[cy+dy][cx+dx] = True

def fmt_bits(lv, mask):
    d = (EC_BITS[lv] << 3) | mask
    r = d
    for _ in range(10):
        r = (r << 1) ^ ((r >> 9)*0x537)
    return ((d << 10) | r) ^ FMT_MASK

def draw_format(m, f, n, lv, mask):
    b = fmt_bits(lv, mask)
    def bit(i):
        return bool((b >> i) & 1)
    # first copy around top-left finder (Nayuki-exact)
    for i in range(6):
        m[i][8] = bit(i); f[i][8] = True
    m[7][8] = bit(6); f[7][8] = True
    m[8][8] = bit(7); f[8][8] = True
    m[8][7] = bit(8); f[8][7] = True
    for i in range(9, 15):
        m[8][14-i] = bit(i); f[8][14-i] = True
    # second copy: row 8 right side + column 8 bottom side
    for i in range(8):
        m[8][n-1-i] = bit(i); f[8][n-1-i] = True
    for i in range(8, 15):
        m[n-15+i][8] = bit(i); f[n-15+i][8] = True
    m[n-8][8] = True; f[n-8][8] = True  # dark module

def build_base(ver):
    n = ver*4+17
    m, f = new_grid(n), new_grid(n)
    for i in range(n):  # timing (marked as function)
        m[6][i] = (i % 2 == 0); f[6][i] = True
        m[i][6] = (i % 2 == 0); f[i][6] = True
    draw_finder(m, f, 3, 3)
    draw_finder(m, f, n-4, 3)
    draw_finder(m, f, 3, n-4)
    for a in ALIGN[ver]:
        for b in ALIGN[ver]:
            if (a <= 8 and b <= 8) or (a >= n-9 and b <= 8) or (a <= 8 and b >= n-9):
                continue
            if not f[b][a]:
                draw_align(m, f, a, b)
    # reserve format areas as function (dummy)
    draw_format(m, f, n, 'M', 0)
    return m, f

def place_data(m, f, cws):
    n = len(m)
    k = 0
    tot = len(cws)*8
    for r in range(n-1, 0, -2):
        if r <= 6:
            r -= 1
        up = ((r+1) & 2) == 0
        for v in range(n):
            for j in range(2):
                x = r-j
                y = n-1-v if up else v
                if f[y][x] or k >= tot:
                    continue
                m[y][x] = bool((cws[k >> 3] >> (7-(k & 7))) & 1)
                k += 1
    return k

def mask_ok(mm, r, c):
    x, y = c, r
    if mm == 0:
        return (x+y) % 2 == 0
    if mm == 1:
        return y % 2 == 0
    if mm == 2:
        return x % 3 == 0
    if mm == 3:
        return (x+y) % 3 == 0
    if mm == 4:
        return (x//3+y//2) % 2 == 0
    if mm == 5:
        return (x*y) % 2+(x*y) % 3 == 0
    if mm == 6:
        return ((x*y) % 2+(x*y) % 3) % 2 == 0
    return ((x+y) % 2+(x*y) % 3) % 2 == 0

def penalty(m):
    n = len(m)
    s = 0
    for y in range(n):
        run, last = 1, m[y][0]
        for x in range(1, n):
            if m[y][x] == last:
                run += 1
            else:
                if run >= 5:
                    s += 3+(run-5)
                run, last = 1, m[y][x]
        if run >= 5:
            s += 3+(run-5)
    for x in range(n):
        run, last = 1, m[0][x]
        for y in range(1, n):
            if m[y][x] == last:
                run += 1
            else:
                if run >= 5:
                    s += 3+(run-5)
                run, last = 1, m[y][x]
        if run >= 5:
            s += 3+(run-5)
    for y in range(n-1):
        for x in range(n-1):
            if m[y][x] == m[y][x+1] == m[y+1][x] == m[y+1][x+1]:
                s += 3
    pat1 = [True, False, True, True, True, False, True, False, False, False, False]
    pat2 = [False, False, False, False, True, False, True, True, True, False, True]
    for y in range(n):
        for x in range(n-10):
            w = [m[y][x+i] for i in range(11)]
            if w == pat1 or w == pat2:
                s += 40
    for x in range(n):
        for y in range(n-10):
            w = [m[y+i][x] for i in range(11)]
            if w == pat1 or w == pat2:
                s += 40
    dark = sum(r.count(True) for r in m)
    tot = n*n
    k = (abs(dark*20-tot*10)+tot-1)//tot-1
    return s+k*10

def make_matrix(txt, lv='M', ver=None, mask=-1):
    ver = ver or pick_version(txt, lv)
    dc = encode_data(txt, ver, lv)
    full = interleave(dc, ver, lv)
    base, func = build_base(ver)
    place_data(base, func, full)
    if mask < 0:
        best, bs = 0, None
        for mm in range(8):
            t = [row[:] for row in base]
            tf = [row[:] for row in func]
            n = len(t)
            for y in range(n):
                for x in range(n):
                    if not func[y][x] and mask_ok(mm, y, x):
                        t[y][x] = not t[y][x]
            draw_format(t, tf, n, lv, mm)
            sc = penalty(t)
            if bs is None or sc < bs:
                bs, best = sc, mm
        mask = best
    n = len(base)
    for y in range(n):
        for x in range(n):
            if not func[y][x] and mask_ok(mask, y, x):
                base[y][x] = not base[y][x]
    # real format (overwrites + dark module)
    draw_format(base, func, n, lv, mask)
    return base, ver, mask

# --- tiny PNG writer (stdlib: struct+zlib) ---
def write_png(mat, path, scale=10, quiet=4):
    n = len(mat)
    W = (n+quiet*2)*scale
    raw = b''
    q = [[False]*(n+quiet*2) for _ in range(n+quiet*2)]
    for y in range(n):
        for x in range(n):
            q[y+quiet][x+quiet] = mat[y][x]
    for row in q:
        px = bytearray()
        for v in row:
            px += bytes([0, 0, 0])*scale if v else bytes([255, 255, 255])*scale
        for _ in range(scale):
            raw += b'\x00'+bytes(px)
    def chunk(t, d):
        c = t+d
        return struct.pack('>I', len(d))+t+d+struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', W, W, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw))
    png += chunk(b'IEND', b'')
    open(path, 'wb').write(png)
    return path

def make_qr(txt, path, lv='M', ver=None, scale=10):
    mat, v, mk = make_matrix(txt, lv, ver)
    write_png(mat, path, scale)
    return {'version': v, 'mask': mk, 'level': lv, 'size': len(mat), 'path': path}

if __name__ == '__main__':
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else 'hello, world'
    o = sys.argv[2] if len(sys.argv) > 2 else 'out/hello.png'
    r = make_qr(t, o)
    print(r)
