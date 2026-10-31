#!/usr/bin/env python3
"""Patch Rollcage's Direct3D exe as the official 1.0b patch installs it (Patch_Rollcage.exe of 13 Feb 2001, its
resource BINARY 113: the build for the standard edition (this kit's disc); 757,760 bytes, MD5
81257282ddf2927e99012c43582f1d59, MSVC; Attention to Detail / Psygnosis) into a copy.

  patch_exe.py <Rollcage.exe 1.0b> <out.exe>   write the patched exe (refuses, writes nothing, on any unexpected byte)
  patch_exe.py --check-caves                   re-assemble caves.s with clang and compare with CAVE below

New code (caves.s, assembled bytes in CAVE) goes into a section the patch adds: ".rdeck", VA 0x6d7000, 0x1000 bytes
at file offset 0xb9000 (the end of the file, right after .rsrc), readable / writable / executable; its variables
from 0x6d7c00. The section table had room for a sixth entry (it ended at 0x2c0, the first section starts at
0x1000); SizeOfImage 0x2d7000 -> 0x2d8000. The exe has no checksum, no relocations ("relocations stripped" is
already set) and loads at its 0x400000 base.

The disc's own exe (1 Feb 1999) has the same code at other addresses (the patch rebuilt it); every site below was
found in both from the same strings and code (docs/TECHNICAL.md), so it can be found again in another build of
the engine (the Glide exe, Rollcage Stage II). Addresses are the 1.0b exe's.

  rdeck      the section (above) with the code of caves.s.
  nocd       the CD check 0x475360 (found from "Rollcage needs to be installed from a CD ROM drive." / "Please
             insert the Rollcage CD into the CD ROM drive.", 0x4b23fc / 0x4b23b4): reads the installer's CD path
             (HKLM\\Software\\Psygnosis\\Rollcage\\Installer "Source"), wants GetDriveTypeA = CD-ROM and
             Rollcage\\IDXData\\ROLLCAGE.IDX on it; returns 2 = disc found, 1 / 0 = not (the front end then greys
             out menu items where it tests "!= 2"). Now "mov eax, 2; ret" at its entry. Nothing is read from a CD:
             the data comes from ..\\IDXData\\rollcage.img and ..\\movies\\ beside the exe's folder, as installed.
  nodialog   the start-up dialog (resource 129: language, display device, display mode; 0x437775) appears when no
             settings were saved yet ([0x4beee8] = DataPC byte 0x0a). Its "show it?" jump 0x4377a0 (jne) is now jmp:
             never shown; the game keeps its built-in 640 x 480 x 16 (0x4acd2c / 0x4acd30), the first display
             device and English (Installer "Language" missing = 0). dgVoodoo2 renders that at the screen's height.
  savefile   the registry. Settings, controls, records and progress are binary values in HKLM\\Software\\Psygnosis\\
             Rollcage\\BootSys ("DataPC" 0x1854 bytes, "DataPSX" 0xaa0, "DataReplay" 0xaa0; strings 0x4b2378 /
             0x4b2370 / 0x4b2380), read by 0x474b50 -> "call 0x46c030" (0x474b8d) and written by 0x474d50 ->
             "call 0x46c090" (0x474d64). Both calls now go to regget / regset: the files ..\\Save\\DataPC.sav,
             DataPSX.sav, DataReplay.sav beside the exe's folder. The other registry reads (Installer "Source",
             "Language", "Uninstall") find nothing and the game takes its defaults; nothing else is written.
  pad        the Xbox pad through XInput. The game builds each local player's raw input once a frame with
             0x429510(player) (action bits from the bindings + the joystick's X / Y / Z bytes), called at
             0x437097, 0x4370dc, 0x4370f6: those calls go to padraw (caves.s), which adds the pad of the same
             number (docs/TECHNICAL.md, "Pad"). Race set-up stores each player's analogue flags with "mov [esi+0x26e], ax"
             (0x46ad95, 7 bytes): now "call padflags" + 2 nops (analogue steer / accelerate / brake when that
             player has a pad). The pad converter's analogue brake (0x428620, 14 bytes, "test dl, 1" ... "mov
             [esi+0xa], al") is now "jmp brakez" + 9 nops: the brake from LT (Z byte), separate from the throttle.
  movieskip  the movie player's per-frame callback (0x42dfd0, "mov [esp+0x30], 0x42dfd0" at 0x42df80, found from
             the "movies" / "psyg.fmv" strings 0x4ac880 / 0x4ac888): the pointer is now movieskip (the pad's A B X
             Y View Start also skip; the keys still do).
  nobusy     the wait loops spin on 0x436fe9 (timeGetTime): the frame limiter 0x437111 (32 ms a frame: the game
             runs its logic once a frame at 31.25 frames a second), and pauses at 0x435a52 (3 s) and 0x436c85.
             Each loop's "call 0x436fe9" (0x435a52, 0x436c85, 0x4371a5) now calls stime: Sleep(1), then the time.

Not patched (docs/TECHNICAL.md): the frame time itself (32 ms; with dgVoodoo's vsync at 60 Hz every frame lands on every
second refresh: a steady 30), the "THIS IS NOT THE CORRECT VERSION ... FOR THIS TERRITORY" test (Japanese system
locale only), the process chaining (the race and the front end are separate runs of Rollcage.exe: it starts
"Rollcage.exe /FRONTEND" from its own folder and exits), the CD music code (MCI cdaudio by device type, polled: no
notify wait).
"""
import hashlib, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE, MD5 = 757760, "81257282ddf2927e99012c43582f1d59"

SECTIONS = [(0x401000, 0x4a4000, 0x1000), (0x4a4000, 0x4a7000, 0xa4000), (0x4a7000, 0x4b6000, 0xa7000)]
def T(va):                             # file offset of a VA in .text / .rdata / initialised .data
    for lo, hi, off in SECTIONS:
        if lo <= va < hi: return va - lo + off
    raise AssertionError(hex(va))

def rel32(src, dst, op):               # e8 / e9 at src (5 bytes) -> dst
    return bytes([op]) + (dst - (src + 5)).to_bytes(4, "little", signed=True)

SECT_VA, SECT_RVA, SECT_OFF, SECT_SIZE = 0x6d7000, 0x2d7000, 0xb9000, 0x1000
CAVE_VA = SECT_VA
CAVE = bytes.fromhex(
    "6a01ff15f8404a00e9dcffd5ff6089c6833d047c6d0000753cc705047c6d0001000000bf00746d00bb0300000057ff15"
    "a0404a0085c0741768d8736d0050ff1570414a0085c07407a3007c6d00eb0683c7104b75d8a1007c6d0085c0741883fe"
    "03771368107c6d0056ffd085c0750761b801000000c36131c0c3ff742404e88d24d5ff83c404608b442424e87dffffff"
    "85c00f84e90000000fb71d147c6d0031ffbe88736d008b0685c0740c85c374030b7e0483c608ebee0fbf051c7c6d003d"
    "80c1ffff7f0681cf000001003d803e00007c0681cf000002000fbf051e7c6d003d803e00007c0383cf023d80c1ffff7f"
    "0383cf010fbf05187c6d00e883000000f6c3047405b881fffffff6c3087405b87f00000083f8c07f0681cf0080000083"
    "f8407c0681cf002000000fb6e8c1e5080fb605177c6d003d80000000720383cf40e86d000000f7d80fb6c0c1e01009c5"
    "0fb605167c6d003d80000000720681cf80000000e84a000000c1e01809c58b44241425ff00000009e889442414097c24"
    "1c61c389c19931d029d02d581b00007f0331c0c36bc07f31d251b9a7640000f7f15983f87f7605b87f00000085c97902"
    "f7d8c383f808730331c0c3d1e8c36089f8e847feffff85c0740766814c241c8f00616689866e020000c3f6c201741cf6"
    "c208740e8a450784c07e10d0e088460aeb0985c07c05d0e088460ae92e14d5ffe8cb6dd5ff85c075326031c0e8fcfdff"
    "ff85c074250fb705147c6d002530f000008b0d087c6d00a3087c6d00f7d121c87408c744241c0100000061c3608b7424"
    "288b7c242c8b6c2430e8cd0000006a0068800000006a036a006a01680000008068007d6d00ff15f0404a0083f8ff742e"
    "89c3c7050c7c6d00000000006a00680c7c6d00555753ff156c404a0053ff1534414a00a10c7c6d008944241c61c3c744"
    "241cffffffff61c3608b7424288b7c242c8b6c2430e8610000006a0068800000006a026a006a00680000004068007d6d"
    "00ff15f0404a0083f8ff743589c3c7050c7c6d00000000006a00680c7c6d00555753ff1570404a0053ff1534414a0039"
    "2d0c7c6d00750ac744241c0000000061c3c744241cffffffff61c35768c001000068007d6d006a00ff15c4404a00bf00"
    "7d6d0089fb8a0784c07409473c5c75f589fbebf189df56bee7736d00e8270000005e576a0068007d6d00ff1508414a00"
    "5fc6075c47e80e00000056beef736d00e8030000005e5fc3568a06880784c074044647ebf45ec3900010000008000000"
    "004000000400000000200000100000000080000020000000000100000010000000020000000000804000000000000040"
    "80000000004000003000000000080000000000000000000058496e7075744765745374617465002e2e5c53617665002e"
    "73617600662e0f1f840000000000669078696e707574315f342e646c6c00669078696e707574315f332e646c6c006690"
    "78696e707574395f315f302e646c6c00")
SYM = {"stime": 0x000, "padraw": 0x07a, "padflags": 0x1be, "brakez": 0x1da, "movieskip": 0x200,
       "regget": 0x23c, "regset": 0x2a8}                         # labels of caves.s
def C(name): return CAVE_VA + SYM[name]

def build():
    """(name, va, old bytes, new bytes) for every patch site."""
    e = []
    # nocd: "sub esp, 0x30c" at the CD check's entry -> "mov eax, 2; ret"
    e.append(("nocd", 0x475360, bytes.fromhex("81ec0c030000"), bytes.fromhex("b802000000c3")))
    # nodialog: "jne 0x43780e" (no saved settings: show the dialog) -> "jmp 0x43780e"
    e.append(("nodialog", 0x4377a0, bytes.fromhex("756c"), bytes.fromhex("eb6c")))
    # savefile: the registry read / write calls -> regget / regset
    e.append(("savefile", 0x474b8d, rel32(0x474b8d, 0x46c030, 0xe8), rel32(0x474b8d, C("regget"), 0xe8)))
    e.append(("savefile", 0x474d64, rel32(0x474d64, 0x46c090, 0xe8), rel32(0x474d64, C("regset"), 0xe8)))
    # pad: the raw-input builder's three callers -> padraw; the analogue flags store -> padflags; the converter's
    # analogue brake -> brakez
    for va in (0x437097, 0x4370dc, 0x4370f6):
        e.append(("pad", va, rel32(va, 0x429510, 0xe8), rel32(va, C("padraw"), 0xe8)))
    e.append(("pad", 0x46ad95, bytes.fromhex("6689866e020000"), rel32(0x46ad95, C("padflags"), 0xe8) + b"\x90" * 2))
    e.append(("pad", 0x428620, bytes.fromhex("f6c201740985c07c05d0e088460a"),
              rel32(0x428620, C("brakez"), 0xe9) + b"\x90" * 9))
    # movieskip: the movie callback pointer 0x42dfd0 (the immediate of "mov dword [esp+0x30], 0x42dfd0")
    e.append(("movieskip", 0x42df84, (0x42dfd0).to_bytes(4, "little"), C("movieskip").to_bytes(4, "little")))
    # nobusy: "call 0x436fe9" in the wait loops -> call stime
    for va in (0x435a52, 0x436c85, 0x4371a5):
        e.append(("nobusy", va, rel32(va, 0x436fe9, 0xe8), rel32(va, C("stime"), 0xe8)))
    return e

def add_section(data):
    lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    nsec = struct.unpack_from("<H", data, lfanew + 6)[0]
    optsize = struct.unpack_from("<H", data, lfanew + 20)[0]
    sh = lfanew + 24 + optsize + 40 * nsec
    if nsec != 5 or sh != 0x2c0 or any(data[sh:sh + 40]) or len(data) != SECT_OFF:
        sys.exit("unexpected PE header; nothing written")
    struct.pack_into("<8sIIIIIIHHI", data, sh, b".rdeck", SECT_SIZE, SECT_RVA, SECT_SIZE, SECT_OFF, 0, 0, 0, 0,
                     0xE0000060)       # code | initialised data | execute | read | write
    struct.pack_into("<H", data, lfanew + 6, nsec + 1)
    if not struct.unpack_from("<H", data, lfanew + 22)[0] & 1: sys.exit("relocations not stripped?")
    if struct.unpack_from("<I", data, lfanew + 24 + 56)[0] != SECT_RVA: sys.exit("unexpected SizeOfImage")
    struct.pack_into("<I", data, lfanew + 24 + 56, SECT_RVA + SECT_SIZE)
    data += CAVE + bytes(SECT_SIZE - len(CAVE))

def elf_text(path):                    # .text bytes and label offsets of an i386 ELF object (no relocations)
    d = open(path, "rb").read()
    shoff = struct.unpack_from("<I", d, 0x20)[0]; shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2e)
    secs = [struct.unpack_from("<10I", d, shoff + i * shentsize) for i in range(shnum)]
    names = [d[secs[shstrndx][4] + x[0]:].split(b"\0")[0].decode() for x in secs]
    if any(n.startswith(".rel") and x[5] for n, x in zip(names, secs)): sys.exit("caves.o has relocations")
    ti = names.index(".text"); text = d[secs[ti][4]:secs[ti][4] + secs[ti][5]]; syms = {}
    for x in secs:
        if x[1] != 2: continue                                   # SHT_SYMTAB
        strs = secs[x[6]]
        for i in range(x[5] // 16):
            nm, val, size, info, oth, shn = struct.unpack_from("<IIIBBH", d, x[4] + 16 * i)
            if shn == ti: syms[d[strs[4] + nm:].split(b"\0")[0].decode()] = val
    return text, syms

def check_caves():
    with tempfile.TemporaryDirectory() as t:
        o = os.path.join(t, "caves.o")
        subprocess.run(["clang", "-target", "i386-pc-linux-gnu", "-c", os.path.join(HERE, "caves.s"), "-o", o], check=True)
        text, syms = elf_text(o)
    ok = text == CAVE and all(syms.get(k) == v for k, v in SYM.items())
    print("caves.s matches CAVE" if ok else "caves.s differs from CAVE / SYM: update patch_exe.py")
    if not ok:
        print("CAVE =", text.hex()); print("SYM =", {k: hex(syms[k]) for k in SYM})
    return ok

def patch(data, label="Rollcage.exe"):
    """Returns the patched exe; exits on any unexpected byte."""
    data = bytearray(data)
    if len(data) != SIZE or hashlib.md5(data).hexdigest() != MD5:
        sys.exit(f"{label}: not the 1.0b patch's Direct3D Rollcage.exe (size {SIZE}, MD5 {MD5}); nothing written")
    assert 0 < len(CAVE) < 0xc00, "CAVE empty or running into the variables at 0x6d7c00"
    edits = build()
    for name, va, old, new in edits:
        off = T(va)
        if bytes(data[off:off + len(old)]) != old or len(old) != len(new):
            sys.exit(f"{name}: unexpected bytes at VA {va:#x}; nothing written")
    for name, va, old, new in edits:
        data[T(va):T(va) + len(new)] = new
    add_section(data)
    names = " ".join(dict.fromkeys(["rdeck"] + [n for n, *_ in edits]))
    print(f"  {names} ({len(edits)} edits)")
    return bytes(data)

def main(src, dst):
    data = patch(open(src, "rb").read(), src)
    tmp = dst + ".tmp"
    open(tmp, "wb").write(data)
    os.replace(tmp, dst)
    print(f"{dst}: MD5 {hashlib.md5(data).hexdigest()}")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--check-caves": sys.exit(0 if check_caves() else 1)
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
