#!/usr/bin/env python3
"""Build a ready-to-run Rollcage folder for modern PCs from your own CD and the official 1.0b patch.

Usage:
  python3 build.py DISC.cue|DISC.ccd --patch rollcagepatch10b.zip --dgvoodoo DGVOODOO.zip --ogg-winmm OGG-WINMM.zip
                   [--out DIR] [--windows]

  DISC          your Rollcage CD (Attention to Detail / Psygnosis, 1999, the standard European edition, English /
                French / German / Spanish / Italian) as .cue + .bin or .ccd + .img, with its audio tracks
  --patch       the official 1.0b patch as downloaded (rollcagepatch10b.zip), the zip inside it
                ("Rollcage 1.0b Patch.zip"), or the Patch_Rollcage.exe inside that. It isn't run: build.py takes
                the 1.0b exes out of it
  --dgvoodoo    dgVoodoo2 2.79.3 zip (or its unpacked folder)
  --ogg-winmm   ogg-winmm v2025.01.16 release zip (or folder)
  --out         where to create Rollcage/ (default: this folder)
  --windows     a folder for Windows only: the same game/ folder, without the Steam Deck launch script

Needs Python 3.8+ and an Ogg Vorbis encoder on the PATH: oggenc (vorbis-tools) or ffmpeg.
Nothing from the game is in this repository: every game file comes from your disc and the patch.
"""
import argparse, hashlib, os, shutil, struct, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deflate64, disc, patch_exe

DISC_EXE_MD5 = "3ca880181b3331dfe394875d57227329"       # DISK1\ROLLCAGE\DIRECT3D\ROLLCAGE.EXE, 1 Feb 1999
IMG_MD5 = "a7bf2d0e18012632ab63911c6b58d1d8"            # DISK1\ROLLCAGE\IDXDATA\ROLLCAGE.IMG (standard edition)
PATCHER_SHA256 = "99a4a9eda6d275ee0eb4f7aa2d6d8c1db78ad148e403e170aa587f3ac22e4447"   # Patch_Rollcage.exe, 13 Feb 2001
# Patch_Rollcage.exe carries four exes as BINARY resources; the standard edition's (chosen by the size of
# rollcage.img) are 113 (Direct3D) and 112 (Glide), at these file offsets
RESOURCES = {"d3d": (0x22aec0, 757760, patch_exe.MD5), "glide": (0x175ec0, 741376, "eee81f98b0093ca5acdda0ae6bff8748")}
PATCHED_MD5 = "241c44b2e03519e23792f514388146d5"
WINMM_MD5 = "f4896addb8e4da30ebcfa2d9cc203c0e"          # ogg-winmm v2025.01.16 (used as released: the game opens the
                                                        # CD with mciSendCommand, never the string "open cdaudio")
R = "DISK1/ROLLCAGE/"
MOVIES_LOWER = ["intro", "psyg", "atd", "copchal", "coploses", "credits"]       # the installer's names for them
MOVIES_UPPER = ["UKWIN", "FRENWIN", "GERWIN", "ITALWIN", "JAPWIN", "POLWIN", "AMERWIN", "EXPERT"]


def md5(data): return hashlib.md5(data).hexdigest()


def patcher(path):
    """Patch_Rollcage.exe from the download (the outer zip is Deflate64, which Python's zipfile can't read)."""
    d = open(path, "rb").read()
    for _ in range(2):
        if d[:2] == b"MZ": break
        if d[:2] != b"PK": sys.exit(f"{path}: not the 1.0b patch zip or Patch_Rollcage.exe")
        files = deflate64.unzip(d)
        inner = [v for k, v in files.items() if k.lower().endswith((".zip", ".exe"))]
        if len(inner) != 1: sys.exit(f"{path}: not the 1.0b patch zip (expected one file inside)")
        d = inner[0]
    if hashlib.sha256(d).hexdigest() != PATCHER_SHA256:
        sys.exit(f"{path}: Patch_Rollcage.exe is not the official 1.0b one (13 Feb 2001)")
    exes = {}
    for name, (off, size, want) in RESOURCES.items():
        exes[name] = d[off:off + size]
        if md5(exes[name]) != want: sys.exit(f"Patch_Rollcage.exe: its {name} exe isn't where expected")
    return exes


def encoder():
    if shutil.which("oggenc"): return lambda wav, ogg: ["oggenc", "-Q", "-q", "7", wav, "-o", ogg]
    if shutil.which("ffmpeg"):
        return lambda wav, ogg: ["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "7", ogg]
    sys.exit("needs oggenc (vorbis-tools) or ffmpeg on the PATH to encode the soundtrack")


def rip(tracks, music):
    enc = encoder(); os.makedirs(music, exist_ok=True); zero = bytes(2352); n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for t in tracks:
            if t.kind != "AUDIO": continue
            data = disc.audio(t)          # INDEX 01 to the next track's start (or its file's end)
            tail = 0                      # minus up to 2 s of digital silence at the end
            while tail < 150 and data[len(data) - (tail + 1) * 2352:len(data) - tail * 2352] == zero: tail += 1
            if tail: data = data[:len(data) - tail * 2352]
            wav = os.path.join(tmp, f"track{t.n:02d}.wav")
            with open(wav, "wb") as o:
                o.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                        struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16) + b"data" +
                        struct.pack("<I", len(data)) + data)
            subprocess.run(enc(wav, os.path.join(music, f"Track{t.n:02d}.ogg")), check=True); os.remove(wav)
            print(f"  Music/Track{t.n:02d}.ogg  {len(data) / 2352 / 75:6.1f} s"); n += 1
    if n != 9: sys.exit(f"expected 9 audio tracks (the game's music), found {n}: is the image missing them?")


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--patch", required=True)
    ap.add_argument("--dgvoodoo", required=True); ap.add_argument("--ogg-winmm", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    a = ap.parse_args()

    tracks = disc.tracks(a.disc)
    data = [t for t in tracks if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    entries = {p.upper(): (p, is_dir, l, s) for p, is_dir, l, s in dt.walk()}
    for key, want in [(R + "DIRECT3D/ROLLCAGE.EXE", DISC_EXE_MD5), (R + "IDXDATA/ROLLCAGE.IMG", IMG_MD5)]:
        if key not in entries: sys.exit(f"no {key} on this CD: it isn't the Rollcage disc the kit was made for")
        got = md5(dt.read_file(*entries[key][2:]))
        if got != want:
            sys.exit(f"this CD's {key} is not the 1999 standard edition's the kit was made for (MD5 {got}); "
                     "the Pentium III edition and others aren't supported yet")
    exes = patcher(a.patch)
    winmm = take(a.ogg_winmm, "winmm.dll")
    if md5(winmm) != WINMM_MD5: sys.exit(f"{a.ogg_winmm}: winmm.dll is not ogg-winmm v2025.01.16")

    pkg = os.path.join(os.path.abspath(a.out), "Rollcage"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    print("1/5 game files from the CD")   # what the installer puts in the install folder, with its names
    def copy(key, dst): dt.copy_file(*entries[key][2:], os.path.join(game, *dst.split("/")))
    for key, dst in [(R + "README.TXT", "readme.txt"), (R + "DIRECT3D/QMIXER.DLL", "Direct3D/QMIXER.DLL"),
                     (R + "IDXDATA/ROLLCAGE.IMG", "IDXData/ROLLCAGE.IMG"), (R + "IDXDATA/ROLLCAGE.IDX", "IDXData/Rollcage.idx"),
                     (R + "ROLLCAGE.EXE", "_spare/RollCage.exe"), (R + "GLIDE/QMIXER.DLL", "_spare/Glide/QMIXER.DLL"),
                     (R + "DIRECT3D/ROLLCAGE.EXE", "_spare/Rollcage-D3D-1999.exe"),
                     (R + "GLIDE/ROLLCAGE.EXE", "_spare/Rollcage-Glide-1999.exe"), ("README.TXT", "_spare/README-disc.TXT")]:
        copy(key, dst)
    for m in MOVIES_LOWER: copy(R + f"MOVIES/{m.upper()}.FMV", f"movies/{m}.fmv")
    for m in MOVIES_UPPER: copy(R + f"MOVIES/{m}.FMV", f"movies/{m}.FMV")
    os.makedirs(os.path.join(game, "Save"))      # settings, controls, records and progress (patch savefile)
    open(os.path.join(game, "_spare", "Glide", "Rollcage.exe"), "wb").write(exes["glide"])   # the 1.0b Glide build
    open(os.path.join(game, "_spare", "Rollcage-D3D-1.0b.exe"), "wb").write(exes["d3d"])     # untouched

    print("2/5 exe patches (the 1.0b Direct3D exe)")
    out = patch_exe.patch(exes["d3d"])
    if md5(out) != PATCHED_MD5: sys.exit("patching gave an unexpected Rollcage.exe")
    # the name Rollcage.exe and the folder Direct3D are fixed: the game re-starts ..\Direct3D\Rollcage.exe /FRONTEND
    # itself between the front end and a race
    open(os.path.join(game, "Direct3D", "Rollcage.exe"), "wb").write(out)

    print("3/5 soundtrack")
    rip(tracks, os.path.join(game, "Direct3D", "Music"))

    print("4/5 wrappers and settings")
    for member, name in [("MS/x86/DDraw.dll", "ddraw.dll"), ("MS/x86/D3DImm.dll", "d3dimm.dll")]:
        open(os.path.join(game, "Direct3D", name), "wb").write(take(a.dgvoodoo, member))
    open(os.path.join(game, "Direct3D", "winmm.dll"), "wb").write(winmm)
    with open(os.path.join(game, "Direct3D", "winmm.ini"), "wb") as f:
        f.write(b"[OGG-WinMM]\r\nCDDAPath = Music\r\nCDDAVolume = 100\r\nMIDIVolume = 100\r\nWAVEVolume = 100\r\n")
    shutil.copyfile(os.path.join(HERE, "config", "dgVoodoo.conf"), os.path.join(game, "Direct3D", "dgVoodoo.conf"))

    print("5/5 Steam Deck launch script" if not a.windows else "5/5 done")
    if not a.windows:
        launch = os.path.join(pkg, "rollcage_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "rollcage_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
