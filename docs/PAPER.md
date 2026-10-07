# From Squares to Words: A Minimal Verified QR Generator and a Live Study of Damage, Masking and Logo Tolerance

**Draft — publication-ready structure. All numbers are live-measured with OpenCV in this repo (2026-10-07).**

## Abstract

We implement a complete QR Code Model 2 generator in ~325 lines of dependency-free Python (standard library only) covering versions 1–6, error-correction levels L/M/Q/H and byte mode, including Reed–Solomon coding over GF(256), zigzag placement, 8-mask penalty selection and BCH-coded format information with a stdlib PNG writer. Every artefact is gated on a production reader (OpenCV `QRCodeDetector`): no code is accepted unless it scans. We reproduce the canonical `hello, world` V1-M case exactly (21×21, mask 0, unmasked penalty 460 → masked 319, format M0 `0x5412`) and confirm the sharp Reed–Solomon threshold (10 EC bytes repair 5 fully-corrupted codewords 20/20, fail at 6 0/20). Central-logo occlusion tests show reader tolerance below nominal EC percentages on small symbols (V1/V2) and convergence toward theory on larger symbols (V4–V6: L 4.5%, M 8.8%, Q 15.2%), revealing a burst-vs-random gap and version-conditioned logo guidance. We document mask-selection bias, rule-3 dominance, format fragility asymmetry and a PNG-header pitfall, and release a Docker-reproducible harness (`verify.py`, `benchmark.py`). The work is pedagogical (five pipeline stages) and a baseline for extensions to alphanumeric mode, V7–40 and a companion reader.

**Keywords:** QR code, ISO/IEC 18004, Reed–Solomon, Galois field, masking, format information, reproducible research, OpenCV verification.

## 1. Introduction

Barcodes hold ~20 characters. In 1994 Denso Wave (Japan, Masahiro Hara team) needed more — including kanji — for automotive tracking. The QR code's three finder patterns with ratio `1:1:3:1:1`, chosen as rarest in surveyed print, enable omni-directional high-speed detection. Denso Wave retained the patent but declined enforcement, catalysing ubiquity.

This paper asks: *can the full pipeline be taught, built and verified from nothing in minutes, and what does live testing reveal beyond textbook EC percentages?* We answer by building `qr_from_scratch.py` and subjecting it to reader-gated benchmarks.

Contributions:

1. Minimal complete generator (V1–6, L/M/Q/H, byte mode) with stdlib PNG.
2. Exact reproduction of canonical vectors (penalties, format words, block splits).
3. Live robustness study (random-byte damage, central logo, mask/timing) with a real reader.
4. Novel spatial-tolerance observations and PhD-ready follow-ups.
5. Docker-reproducible artefact (`verify.py`, `benchmark.py`, `out/`).

## 2. Related work

**Specifications and tutorials.** ISO/IEC 18004 (Model 2); Thonky tutorial series (encoding, EC, placement, masking, format, EC/alignment/log tables) — our primary normative source, fetched page-by-page. BSI/ISO CrossRef records confirm standard lineage.

**Reference implementations.** Nayuki `QR-Code-generator` (6 languages, MIT) — used as a cross-check oracle for format BCH (`0x537`, XOR `0x5412`), placement zigzag, penalty weights and RS division; no code copied. Ecosystem voting included `paulmillr/qr` (0-dep + reader), `larzqr` (V1–10, RS vector `[196,35,…]`), `url2qr` (fixed-mask URL optimised), `zerodep` (V1–40).

**Literature.** Bajaj 2024 (`2407.17364`) on RS reliability and selective-manipulation; Botoluzzi et al. 2018 on camera-channel distortion vs. Zxing (SSR/PSNR); Alajmi et al. 2020 on steganography in valid QR; Garg 2025 on patterns/storage maths; Jonderko & Wodo 2026 on EdDSA/CBOR secure QR; Thai-embedding, colour-QR and print-quality studies (Google Scholar 2011–2026). Our contribution is orthogonal: a minimal *verified* baseline plus *spatial* robustness with a live reader.

**History.** Denso Wave development story, `qrcode.com/history`, Wikipedia `Masahiro Hara`/`QR code`, TinyQR history — all agree on 1994, Hara, `1:1:3:1:1`.

## 3. Method

### 3.1 Encoding

Byte mode: `0100` + char-count (8 b for V1–9) + data + terminator (≤4 zeros) + byte pad + `0xEC/0x11` alternation to data capacity. Version = smallest V with `4+8+8n ≤ 8·data_cw(V,EC)`. V1-M: 16 data → 14-char text max (overhead 1.5 B).

### 3.2 Reed–Solomon

GF(256) with primitive `0x11D`: add = XOR; multiply via 512-entry exp / 256-entry log tables. Generator `∏_{i=0}^{e-1}(x−α^i)` by iterative multiply; remainder by polynomial division (`rs_gen`, `rs_rem`). Multi-block split `(n1,c1),(n2,c2)` + interleave per Thonky EC table (V1–6 reproduced in `EC` dict). Each error costs 2 EC bytes (location + magnitude).

### 3.3 Placement

Size `17+4V`. Order: timing (marked function) → 3 finders (Chebyshev `max(|dx|,|dy|)∉{2,4}`) → alignments (skip finder overlap) → reserve format (dummy M0) → zigzag data (bottom-right, 2-col pairs, skip x=6, up/down alternation) → trial masks → final format + dark module `(8,4V+9)`. V1 fixed cost 233 → 208 data bits = 26 B.

### 3.4 Masking and penalty

Eight formulas (§2.4 README) applied to data-only modules. Penalty N1=3 (runs), N2=3 (2×2), N3=40 (finder-like 11-patterns both axes), N4=10 (dark balance). Entire matrix scored *including* function modules, *after* drawing candidate format (Nayuki-fair).

### 3.5 Format and PNG

Format 5 b (`EC_bits<<3|mask`, L=01 M=00 Q=11 H=10) → 10 b BCH (`0x537` division) → XOR `0x5412`; dual placement + dark module. PNG via `struct+zlib` (IHDR `>IIBBBBB`, quiet 4, scale 10 default).

## 4. Verification protocol

Triangulation (≥2 sources per constant), live-reader gate (OpenCV 5.0.0), seeded deterministic damage (20 trials), containerised rerun. One-search-at-a-time web discipline to avoid rate limits; votes across Exa, DuckDuckGo, OpenAlex, arXiv, Semantic, CrossRef, Scholar, PMC-adjacent, Thonky, Nayuki, Wikipedia, Kaggle, GSD.

## 5. Experiments

### 5.1 Decode gate (verify.py)

All pass: V1-M hello (mask 0, 319), capacity bump 14→V1/15→V2, RS divisibility, format vectors `0x5412/0x77C4`, multi-version URLs, L/M/Q/H hello (V1,V1,V2,V2).

### 5.2 Random-byte damage

V1-M, flip `0xFF` on N random codewords, same mask, OpenCV decode. 1–5: 20/20; 6: 0/20. Sharp threshold at `⌊10/2⌋`. Stronger than single-bit flips; confirms textbook budget live.

### 5.3 Central logo

White square centred, grow to failure. Small symbols underperform nominal EC% (Q 7.8% vs. 25% EC, H 10.2% vs. 30% EC) because the test measures *spatial burst* tolerance through a real detector, not random-codeword capacity. Larger symbols converge (Q 15.2% on V6). H needs V7+ for long URLs — out of V1–6 scope, documented.

Interpretation: quote *two* numbers — EC% (code theory) and spatial % (reader-measured, version-conditioned). Logo guides must be version-conditioned; single-block V1 cannot interleave bursts.

### 5.4 Mask and timing

Full penalty table (§4.4 README); winner 0. Build ~12 ms V4 (vs. ~8 ms video; CPU-dependent; mask trial dominates).

## 6. Discussion — hidden patterns

See README §5 (burst-vs-random gap, small-symbol penalty, mask-0 bias for short ASCII+pad tails, rule-3 dominance, format asymmetry, PNG-header pitfall). Each is a PhD seed with a concrete follow-up experiment (e.g., separate format-hit vs. data-hit failure curves; mask histogram over URL corpus; pyzbar/ZXing reader comparison).

## 7. Limitations

V1–6, byte mode only; alphanumeric (≈30% saving for uppercase) and kanji/ECI not yet; no reader; single-reader (OpenCV) thresholds; no print-scan channel (blur/lighting/pincushion per Botoluzzi) — future.

## 8. Conclusion

441 modules can hold words because 208 of them are a carefully coded polynomial with 80 check bits, wrapped in finders a reader can locate from any angle, masked to be readable and labelled with its own decoding instructions twice. We built it from nothing, checked every code with a real reader, broke it to find exactly where it breaks, and packaged the lab so anyone can rerun it in one command.

## References

Denso Wave history; qrcode.com/history; Wikipedia Hara/QR; Thonky tutorial + EC/mask/format/alignment tables; Nayuki QR-Code-generator (MIT); ISO/IEC 18004:2015/2024 + BSI CrossRef; Bajaj 2407.17364; Botoluzzi 2018; Alajmi 2020; Garg 2025; Jonderko 2026; qrcodefyi RS guides; paulmillr/qr; larzqr; url2qr; zerodep. Full URLs in README §9; fetched 2026-10-07.

## Appendix A. EC table (V1–6, this implementation)

V1 L19/7 M16/10 Q13/13 H9/17; V2 L34/10 M28/16 Q22/22 H16/28; V3 L55/15 M44/26 Q34/18×2 H26/22×2; V4 L80/20 M64/18×2 Q48/26×2 H36/16×4; V5 L108/26 M86/24×2 Q62/18(15×2+16×2) H46/22(11×2+12×2); V6 L136/18×2 M108/16×4 Q76/24×4 H60/28×4. Notation data/EC-per-block×blocks.

## Appendix B. Reproduce

`python3 verify.py && python3 benchmark.py` or `docker compose run qr-verify / qr-bench`. Seed 0. OpenCV 5.0.0. Outputs in `out/`.
