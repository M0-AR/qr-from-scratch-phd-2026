# Live results log — 2026-10-07, opencv-python 5.0.0.93, Python 3.12

## verify.py
```
[PASS] hello,world V1 mask0 21x21 -> OpenCV OK (penalty 319)
[PASS] capacity: 14 chars fit V1-M, 15th bumps to V2
[PASS] RS: fmt M0=0x5412 L0=0x77C4; 26 codewords divide evenly
[PASS] Hi V1-L, hello V1-M, URL V4-M 33x33, 42-char V3-M -> all OK
[PASS] V4 33x33 2-block interleave confirmed
[PASS] level L V1 mask3, M V1 mask0, Q V2 mask2, H V2 mask6 decodes
ALL VERIFY PASSED
```

## benchmark.py (seed 0, 20 trials)
```
DAMAGE V1-M: 1:20/20 2:20/20 3:20/20 4:20/20 5:20/20 6:0/20
LOGO small (hello): L 4x4=3.6% M 6x6=8.2% Q 7x7=7.8% H 8x8=10.2%
LOGO large (URL V4-V6): L 7x7=4.5% M 11x11=8.8% Q 16x16=15.2% (H needs V7+)
MASK hello V1-M: unmasked 460; 0:319 1:469 2:360 3:478 4:483 5:437 6:384 7:403 -> 0
TIMING V4 avg 11.9 ms (video ~8 ms, same order)
```

## Interpretation
- Damage threshold sharp at 5 = floor(10/2). Never 6.
- Logo theory (4/9/14/19%) holds for larger versions; small V1/V2 underperform
  because burst erasure + single block + detector strictness.
  -> version-conditioned logo guidance (novel).
- Mask 0 wins for hello world; repo URL V4-M wins mask 3 -> always trial all 8.

## Artefacts
- out/hello-world-v1M.png, out/repo-v4M.png — both OpenCV-decodable.
- Rerun: `python3 verify.py`, `python3 benchmark.py`, `docker compose run qr-verify`
