"""Deflate64 ("enhanced deflate", zip method 9) in pure Python: Python's zipfile can't read it, and the official
Rollcage 1.0b patch zip uses it.

Deflate64 is deflate (RFC 1951) with three changes: a 64 KB window, length code 285 = 3 + a 16-bit extra
(instead of 258), and distance codes 30 / 31 (32769 and 49153, 14 extra bits each).

    unzip(path_or_bytes) -> {name: bytes}    every member, methods 0 (stored), 8 (deflate) and 9 (deflate64)
"""
import io, struct, zlib

LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195,
            227, 3]
LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 16]
DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073,
             4097, 6145, 8193, 12289, 16385, 24577, 32769, 49153]
DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14]
CL_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]


class Bits:
    def __init__(self, data): self.d, self.pos, self.buf, self.n = data, 0, 0, 0

    def need(self, k):
        while self.n < k:
            self.buf |= (self.d[self.pos] if self.pos < len(self.d) else 0) << self.n
            self.pos += 1; self.n += 8

    def get(self, k):
        if k == 0: return 0
        self.need(k); v = self.buf & ((1 << k) - 1); self.buf >>= k; self.n -= k
        return v

    def align(self): self.buf >>= self.n & 7; self.n -= self.n & 7


def table(lengths):
    """Canonical Huffman: {(length, code read bit by bit): symbol} as a lookup by the first `maxlen` bits."""
    maxlen = max(lengths) or 1
    counts = [0] * (maxlen + 1)
    for l in lengths:
        if l: counts[l] += 1
    code, nxt = 0, [0] * (maxlen + 2)
    for b in range(1, maxlen + 1):
        code = (code + counts[b - 1]) << 1; nxt[b] = code
    look = [None] * (1 << maxlen)
    for sym, l in enumerate(lengths):
        if not l: continue
        c = nxt[l]; nxt[l] += 1
        r = int(format(c, f"0{l}b")[::-1], 2)                 # deflate sends codes most significant bit first
        for fill in range(0, 1 << maxlen, 1 << l): look[r | fill] = (sym, l)
    return look, maxlen


def decode(bits, t):
    look, maxlen = t
    bits.need(maxlen)
    sym, l = look[bits.buf & ((1 << maxlen) - 1)]
    bits.buf >>= l; bits.n -= l
    return sym


FIXED = None


def inflate64(data):
    global FIXED
    if FIXED is None:
        FIXED = (table([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8), table([5] * 32))
    bits, out = Bits(data), bytearray()
    while True:
        final, kind = bits.get(1), bits.get(2)
        if kind == 0:
            bits.align(); n = bits.get(16); bits.get(16)
            for _ in range(n): out.append(bits.get(8))
        else:
            if kind == 1: lit, dist = FIXED
            elif kind == 2:
                hlit, hdist, hclen = bits.get(5) + 257, bits.get(5) + 1, bits.get(4) + 4
                cl = [0] * 19
                for i in range(hclen): cl[CL_ORDER[i]] = bits.get(3)
                ct, lens = table(cl), []
                while len(lens) < hlit + hdist:
                    s = decode(bits, ct)
                    if s < 16: lens.append(s)
                    elif s == 16: lens += [lens[-1]] * (3 + bits.get(2))
                    elif s == 17: lens += [0] * (3 + bits.get(3))
                    else: lens += [0] * (11 + bits.get(7))
                lit, dist = table(lens[:hlit]), table(lens[hlit:])
            else: raise ValueError("bad deflate64 block type")
            while True:
                s = decode(bits, lit)
                if s < 256: out.append(s)
                elif s == 256: break
                else:
                    s -= 257; n = LEN_BASE[s] + bits.get(LEN_EXTRA[s])
                    d = decode(bits, dist); back = DIST_BASE[d] + bits.get(DIST_EXTRA[d])
                    start = len(out) - back
                    if back >= n: out += out[start:start + n]
                    else:
                        for i in range(n): out.append(out[start + i])
        if final: return bytes(out)


def unzip(src):
    """{name: bytes} for every member of a zip (stored, deflate or deflate64), CRCs checked."""
    d = open(src, "rb").read() if isinstance(src, str) else src
    e = d.rfind(b"PK\x05\x06")
    if e < 0: raise ValueError("not a zip file")
    count, cd_size, cd_off = struct.unpack_from("<HII", d, e + 10)
    files, o = {}, cd_off
    for _ in range(count):
        method, crc, csize, size, nlen, xlen, clen = struct.unpack_from("<HxxxxIIIHHH", d, o + 10)
        local = struct.unpack_from("<I", d, o + 42)[0]
        name = d[o + 46:o + 46 + nlen].decode("cp437"); o += 46 + nlen + xlen + clen
        lnlen, lxlen = struct.unpack_from("<HH", d, local + 26)
        raw = d[local + 30 + lnlen + lxlen:local + 30 + lnlen + lxlen + csize]
        if method == 0: data = raw
        elif method == 8: data = zlib.decompress(raw, -15)
        elif method == 9: data = inflate64(raw)
        else: raise ValueError(f"{name}: zip method {method} not supported")
        if len(data) != size or zlib.crc32(data) != crc: raise ValueError(f"{name}: damaged (size or CRC)")
        files[name] = data
    return files
