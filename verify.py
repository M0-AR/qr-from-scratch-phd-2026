#!/usr/bin/env python3
"""Live verification: every claim from the video checked against a real reader."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from qr_from_scratch import (make_matrix, write_png, encode_data, interleave,
                             rs_gen, rs_rem, fmt_bits, penalty, EC, pick_version)
import cv2

DET = cv2.QRCodeDetector()
OUT = os.path.join(os.path.dirname(__file__), 'out')

def decode(path):
    img = cv2.imread(path)
    txt, _, _ = DET.detectAndDecode(img)
    return txt

def test_hello():
    mat, ver, mask = make_matrix('hello, world', 'M')
    assert ver == 1 and len(mat) == 21, (ver, len(mat))
    assert mask == 0, f'expected mask 0 (transcript), got {mask}'
    p = os.path.join(OUT, 'hello.png')
    write_png(mat, p, scale=10)
    assert decode(p) == 'hello, world', 'OpenCV failed on hello,world'
    print(f'[PASS] hello,world V{ver} mask{mask} 21x21 -> OpenCV OK (penalty {penalty(mat)})')

def test_capacity():
    # V1-M holds 16 bytes; mode(4)+len(8)=12b => 14 letters max
    assert EC[(1, 'M')][0] == 16
    assert pick_version('A'*14, 'M') == 1
    assert pick_version('A'*15, 'M') == 2
    print('[PASS] capacity: 14 chars fit V1-M, 15 chars bumps to V2')

def test_rs_known():
    # format vectors from spec (verified via Thonky + larzqr + Nayuki)
    assert fmt_bits('M', 0) == 0x5412, hex(fmt_bits('M', 0))
    assert fmt_bits('L', 0) == 0x77C4, hex(fmt_bits('L', 0))
    # RS: V1-M hello world -> 10 EC bytes; full 26 must have zero remainder
    dc = encode_data('hello, world', 1, 'M')
    assert len(dc) == 16
    full = interleave(dc, 1, 'M')
    assert len(full) == 26
    gen = rs_gen(10)
    assert rs_rem(full, gen) == [0]*10, 'codewords must divide evenly'
    # each broken byte costs 2 EC bytes => 10 EC fixes 5
    print(f'[PASS] RS: data={dc[:4]}... ec={full[16:19]}... fmt M0=0x5412 L0=0x77C4')

def test_versions_levels():
    cases = [('Hi', 'L'), ('hello, world', 'M'), ('https://github.com/test/repo-link-example-xyz', 'M'),
             ('Version-4-split-test-0123456789-ABCDEFGHIJ', 'M')]
    for txt, lv in cases:
        mat, ver, mask = make_matrix(txt, lv)
        p = os.path.join(OUT, f't_{ver}_{lv}_{len(txt)}.png')
        write_png(mat, p, scale=8)
        got = decode(p)
        assert got == txt, f'{txt!r} decoded as {got!r} (V{ver} {lv})'
        print(f'[PASS] {txt[:30]!r} V{ver} {lv} mask{mask} {len(mat)}x{len(mat)} -> OK')
    # V4 must be 33x33 with 2 blocks
    mat, ver, _ = make_matrix('x'*43, 'M')
    assert ver == 4 and len(mat) == 33, (ver, len(mat))
    assert EC[(4, 'M')][2] == 2, 'V4-M must split into 2 blocks (transcript)'
    print('[PASS] V4 33x33 2-block interleave confirmed')

def test_all_levels_decode():
    for lv in 'LMQH':
        mat, ver, mask = make_matrix('hello, world', lv)
        p = os.path.join(OUT, f'lv_{lv}.png')
        write_png(mat, p, scale=8)
        assert decode(p) == 'hello, world', lv
        print(f'[PASS] level {lv} V{ver} mask{mask} decodes')

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    test_hello(); test_capacity(); test_rs_known()
    test_versions_levels(); test_all_levels_decode()
    print('\nALL VERIFY PASSED — every code checked with real OpenCV reader')
