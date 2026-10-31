# How it works

Notes on Rollcage (Attention to Detail / Psygnosis, 1999), the standard European CD (files dated
3 February 1999; English, French, German, Spanish and Italian in one exe), with the official 1.0b
patch (13 February 2001). Addresses are virtual addresses in the 1.0b Direct3D exe.

## The disc and the installer

Track 1 is the data track; tracks 2-10 are the music. `DISK1\ROLLCAGE\` holds the installed files:
the `ROLLCAGE.EXE` launcher (starts the Direct3D or Glide build from the registry),
`DIRECT3D\ROLLCAGE.EXE` + `QMIXER.DLL` (QSound), `GLIDE\ROLLCAGE.EXE` + `QMIXER.DLL`,
`IDXDATA\ROLLCAGE.IMG` + `.IDX` (all the game's data, an archive) and `MOVIES\` (14 movies). The
InstallShield 5 installer's `DATA1.CAB` holds only the file list. `build.py` copies what it installs,
with its names (`readme.txt`, `Direct3D\`, `IDXData\Rollcage.idx`, the movies' mixed case).

The standard edition's `rollcage.img` is 70,912,802 bytes; the 1.0b patcher takes anything over
71,680,000 as the Pentium III edition.

## Patch 1.0b

`rollcagepatch10b.zip` holds `Rollcage 1.0b Patch.zip` (compressed with Deflate64, zip method 9,
which Python's `zipfile` can't read; `deflate64.py` does), which holds `Patch_Rollcage.exe` (13 Feb
2001, SHA-256 `99a4a9ed...4447`). Its fix list: 32-bit display modes, the network lobby, the German
league screen, Pentium III support, car reflections, "graphics disappearing occasionally", rendering
speed, "Windows 2000 memory access bugs". It carries four exes as BINARY resources: the Pentium III
edition's (110 / 111) and the standard edition's (113 Direct3D, 112 Glide). `build.py` cuts out 113
(757,760 bytes at file offset 0x22aec0) and 112 (741,376 at 0x175ec0), checked by MD5. The patcher
itself isn't run: it wants the installer's registry key.

PCGamingWiki warns the patch "removes analogue support for controllers". The analogue code is still
in the 1.0b exe, and this kit feeds the pad past the game's DirectInput side anyway.

## The patches

`patch_exe.py` adds a section `.rdeck` (VA 0x6d7000, 4 KB, at the end of the file) holding the new
code from `caves.s`. Every site was found first in the disc's 1999 exe, then again in the 1.0b exe
(the patch rebuilt the whole program: the same code at other addresses).

| Patch | Hooks | Was | Now |
|---|---|---|---|
| `nocd` | the CD check 0x475360: the installer's CD path from the registry, a CD-ROM drive, `Rollcage\IDXData\ROLLCAGE.IDX` on it | Without the installer's key and a disc: "Rollcage needs to be installed from a CD ROM drive", quit | Returns "disc found" (2: the front end also enables everything that wants the disc). Nothing is read from a CD |
| `nodialog` | the start-up dialog (language, display device, display mode), shown while no settings are saved | A Windows dialog before the game | Never shown: 640x480x16, the first display device, English |
| `savefile` | the registry read / write of `HKLM\Software\Psygnosis\Rollcage\BootSys` "DataPC", "DataPSX", "DataReplay" (0x474b8d, 0x474d64) | Binary registry values | Files `Save\DataPC.sav`, `DataPSX.sav`, `DataReplay.sav` (the folder is made if missing) |
| `pad` | the raw-input builder 0x429510 (its three callers), the race's analogue-flags store 0x46ad95, the pad converter's analogue brake 0x428620 | DirectInput only, through the bindings; under Proton an Xbox pad's triggers are one shared axis, and the game took throttle and brake from one axis anyway | The XInput pad of the same number added to each player's input: analogue steering, RT / LT as separate analogue throttle and brake, the buttons as actions. Replays record it like the game's own input |
| `movieskip` | the movie player's per-frame callback (0x42dfd0) | Only Backspace, Tab, Enter, Esc or Space skip | Also A, B, X, Y, View or Start |
| `nobusy` | the waits on `timeGetTime`: the frame limiter 0x4371a5, the 3 s start-up pause 0x435a52, a 1 s wait 0x436c85 | Spin a CPU core | `Sleep(1)` each time round |

Not patched: the frame time, the territory test (refuses only a Japanese system locale), the
process restarts, the CD music code.

## Process restarts

The front end and every race are separate runs of the exe: the game restarts
`..\Direct3D\Rollcage.exe /FRONTEND` itself between them. So the exe must be called `Rollcage.exe` in
a folder called `Direct3D`, beside `IDXData` and `movies`. Each run loads `winmm.dll` afresh (Proton's
DLL overrides are inherited by the restarted copy) and opens the CD device again.

## Picture

Direct3D 6 on DirectDraw; the game lists the display modes and devices itself and picks 640x480x16.
dgVoodoo2 2.79.3: `Resolution = max` renders the 3D at the screen's height while the game thinks
640x480, `ScalingMode = stretched_ar` keeps 4:3 with black bars, 32-bit internal precision, VRAM
256 MB, vsync.

Widescreen: the game can run a wide mode, but its 3D is then Vert- (cropped top and bottom), and
every 2D element is placed on the PlayStation's 512x256 screen and scaled by width / 512 and
height / 256 separately (0x431a96), so at 16:10 all of it is stretched sideways by 1.2.
AlphaYellow's FOV fix makes the 3D Hor+ but leaves the 2D stretched.

**Frame rate.** The game runs its logic once a frame and holds each frame to 32 ms (31.25 a second)
in what was a busy loop. With vsync on a 60 Hz screen each frame lands on every second refresh: a
steady 30, about 4% slower than an unsynced 1999 PC; on a 90 Hz screen every third refresh, the
same 30.

## Music

The game opens the MCI `cdaudio` device by device type (`MCI_OPEN_TYPE_ID`, never the string
"open cdaudio", so ogg-winmm is used as released), sets TMSF, plays one whole track with no notify,
and polls the device's mode every frame to start the next. Nothing waits for a notification. The CD
volume slider is `auxSetVolume` on the CD aux device, which ogg-winmm provides. Each track is ripped
from its INDEX 01 (the 2-second pregaps left out) minus the few sectors of digital silence at its
end. Effects and speech are QSound over DirectSound.

## Pad

Up to four local players, each read through their bindings (keyboard by default) and turned into a
PlayStation pad, the analogue parts a NeGcon-style twist / throttle / brake. `pad` adds XInput user
n to player n+1 whatever the bindings say, and switches that player's car to analogue steering,
throttle and brake at the start of each race. The front end and the pause menu are keyboard only,
hence Start = Enter, View = Esc and the D-pad as arrows in Steam Input on the Deck.
