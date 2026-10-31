# Rollcage (PC, 1999) on modern PCs and the Steam Deck

## Why this exists

Rollcage was like a spiritual successor to Wipeout, but less futuristic, with the weapons playing a
bigger role, and cars that drive on the walls and ceilings. On modern systems it wants its CD, a
registry key from its installer and a start-up dialog, and a modern pad's triggers can't be
throttle and brake. This kit sorts that out, so it can be played again.

**Looking for widescreen and high resolution?** [Rollcage Redux](https://codemonkey.me.uk) by Robert
Baker, one of the original programmers, is a rebuilt version with a new renderer, sound and online
play (the movies were taken out). This kit is the other option: the original 1999 game with the
official 1.0b patch, kept as it was, just made to run.

## What this does

Turns **your own** Rollcage CD and the official 1.0b patch into a folder that runs on the Steam Deck
(Proton) or on Windows 10/11, with no installer and no registry entries:

- **Copied straight from the CD**: what the installer copies, with the 1.0b patch's Direct3D exe
  (Windows 2000 memory bugs, 32-bit modes, rendering fixes) taken out of the patch without running
  its patcher, which needs the installer's registry key.
- **No CD check, no start-up dialog**, and settings, controls, records and progress saved to files
  in `game/Save/` instead of the registry.
- **Direct3D through dgVoodoo2**: 640x480 rendered at your screen's height, 4:3 with black bars, a
  steady 30 frames a second (the game's own rate).
- **CD soundtrack** (Fatboy Slim, EZ Rollers and others) from OGG files ripped from your disc.
- **Gamepad**: an Xbox-style pad (the Steam Deck's included) is read directly: analogue steering,
  analogue throttle and brake on the two triggers, weapons and cameras on the buttons. The pad skips
  the movies.
- **No busy waits**: the frame limiter and the start-up pauses used to spin a CPU core at 100%.

**No game files are in this repository.** Everything from the game comes from your disc and the
official patch when you run `build.py`.

## What you need

| | |
|---|---|
| The game | The **standard European Rollcage CD** (Attention to Detail / Psygnosis, 1999; English, French, German, Spanish and Italian) as `.cue` + `.bin` (one file or one per track) or CloneCD `.ccd` + `.img`, with its 9 audio tracks. `build.py` checks the exe and the game data and stops on another edition (the Pentium III edition isn't supported yet). |
| Patch 1.0b | The official patch, `rollcagepatch10b.zip` (13 February 2001), for example from [gamepressure.com](https://www.gamepressure.com/download/rollcage-10b-patch/z8139c8). Keep it as downloaded; it isn't run. The zip inside it, or the `Patch_Rollcage.exe` inside that, works too. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). |
| An OGG encoder | `oggenc` (vorbis-tools; Windows builds at rarewares.org) or `ffmpeg`, on the PATH. |
| dgVoodoo2 **2.79.3** | by Dege: [GitHub release v2.79.3](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.79.3). Use 2.79.3: newer versions don't start under Wine/Proton. Keep the zip as downloaded. |
| ogg-winmm **v2025.01.16** | by AyuanX: [GitHub releases](https://github.com/ayuanx/ogg-winmm/releases). Keep the zip as downloaded; `build.py` checks it's that release. |

## Build

```
python3 build.py "Rollcage (Europe) (En,Fr,De,Es,It).cue" --patch rollcagepatch10b.zip \
    --dgvoodoo dgVoodoo2_79_3.zip --ogg-winmm ogg-winmm_binary.zip
```

creates `Rollcage/` with `game/` and `rollcage_launch.sh` (for the Steam Deck), in about a minute.
The same `game/` folder runs on Windows; `--windows` leaves out the launch script. `--out DIR` puts
the result somewhere else. The disc's original exes, the untouched 1.0b exe and the 1.0b Glide exe
are kept in `game/_spare/`.

## Play on the Steam Deck

1. Copy `Rollcage/` to the Deck, for example to `/home/deck/Games/Rollcage/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../Rollcage/game/Direct3D/Rollcage.exe`.
   Rename the shortcut "Rollcage". Start In must be the `Direct3D` folder (Steam sets it).
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/Rollcage/rollcage_launch.sh %command%
   ```
5. Controller layout: start from the standard **Gamepad** layout and set these to keyboard keys:
   **Start = Enter**, **View = Esc**, **D-pad = arrow keys**. The front end and the pause menu are
   keyboard only; everything in a race is the pad as itself.

## Play on Windows

Run `game/Direct3D/Rollcage.exe`. An Xbox pad works in races as on the Deck, and Start or View
pause; the menus are on the keyboard (arrows, Enter, Esc), unless you map them in Steam or your pad
software.

## Controls

| Pad | In a race |
|---|---|
| Left stick | steer (analogue) |
| RT / LT | throttle / brake (analogue; both at once work) |
| A / X | fire left / right weapon slot |
| B | reverse |
| Y | face forward (after a spin) |
| LB | target car |
| RB | cinematic camera |
| Right stick | look left / right, zoom the camera in / out |
| L3 | rear-view mirror on / off |
| R3 | look back |
| View (Esc) | pause |

In the menus: D-pad (arrows) to move, Start (Enter) to choose, View (Esc) to go back. A, B, X, Y,
Start or View skip the movies. The keyboard keeps the game's own bindings (Options > Controls); with
a pad connected, that player's steering, throttle and brake come from the pad. Pads 1-4 are players
1-4.

## Settings

`game/Save/DataPC.sav` holds all settings, controls, player names, records and progress;
`DataPSX.sav` the rest of the game state, `DataReplay.sav` the saved replay. The game writes them;
the kit ships none.

- Sharper or softer: `[DirectX] Resolution` in `game/Direct3D/dgVoodoo.conf`.
- Music level: the in-game CD volume, or `CDDAVolume` in `game/Direct3D/winmm.ini`.
- Deck renderer: `RENDERER=wined3d` before the script path in the launch options uses Wine's own
  Direct3D instead of dgVoodoo.

**Widescreen**: not in this kit. The game can run a wide mode, but its 3D is then cropped and every
2D element (HUD, menus, fonts) is placed on the PlayStation's 512x256 screen and stretched. For real
widescreen, see Rollcage Redux above.

## Troubleshooting

- *"Please insert the Rollcage CD"* or a start-up dialog: you're running an unpatched exe from
  `_spare/`.
- *The race doesn't start, or the game can't find its data*: the shortcut must start in
  `game/Direct3D/`, and the folder names `Direct3D`, `IDXData` and `movies` must stay as they are
  (the game restarts `..\Direct3D\Rollcage.exe` between the front end and each race).
- *No music*: on the Deck `launch.log` must show `WINEDLLOVERRIDES=winmm=n,b;...` (no log: the
  launch option is missing `%command%`), and `game/Direct3D/Music/Track02.ogg` must exist.
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: copies the CD's game files, takes the 1.0b exes out of the patch, patches the exe, rips the soundtrack, adds the wrappers and settings. Python standard library only. |
| `patch_exe.py` | The exe patches, each explained; adds a code section to the exe. Also runs on its own. |
| `caves.s` | The new code's source (x86 assembly). `python3 patch_exe.py --check-caves` re-assembles it with clang and checks it against the bytes in `patch_exe.py`. |
| `deflate64.py` | Reads the patch download: its zip uses Deflate64, which Python's own zip reader can't. |
| `disc.py` | Reads the CD image: `.cue`/`.bin` or `.ccd`/`.img`, ISO 9660 and audio tracks. |
| `config/dgVoodoo.conf` | dgVoodoo2's settings. |
| `steamdeck/rollcage_launch.sh` | Proton launch wrapper: DLL overrides. |
| `docs/TECHNICAL.md` | How the game works and what each patch does. |

## Credits

- **Attention to Detail** made Rollcage; **Psygnosis** published it. Please own the game: this kit
  needs your disc.
- **Dege**: dgVoodoo2. **AyuanX**: ogg-winmm.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, its patch, dgVoodoo2 or ogg-winmm.

Not affiliated with or endorsed by the game's rights holders.
