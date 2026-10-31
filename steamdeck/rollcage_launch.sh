#!/bin/bash
# Rollcage (Attention to Detail / Psygnosis, 1999) Steam Deck launch wrapper.
#
# Keep it beside game/ (build.py puts it there). With the folder at /home/deck/Games/Rollcage:
#   Shortcut target: /home/deck/Games/Rollcage/game/Direct3D/Rollcage.exe, Start In: .../game/Direct3D/
#   Compatibility: Proton 9.0
#   Launch Options: /home/deck/Games/Rollcage/rollcage_launch.sh %command%
#
# Direct3D/Rollcage.exe is the disc's Direct3D exe patched (patch_exe.py): no CD check, no start-up dialog, settings
# and progress in game/Save/*.sav instead of the registry, the pad through XInput (separate analogue throttle and
# brake), the pad skips the movies, sleeping waits. It reads its data from ../IDXData and ../movies (Start In must be
# Direct3D/), and it re-starts itself ("Rollcage.exe /FRONTEND") between the front end and each race: the screen goes
# black for a moment there, that is the game.
# Every launch sets DLL overrides so Wine loads the DLLs beside the exe (the restarted copies inherit them):
#   ddraw + d3dimm = dgVoodoo2 2.79.3 (Direct3D 6 -> D3D11 -> DXVK; the game's 640x480 rendered at the screen's
#   height, 4:3 with black bars, vsync: dgVoodoo.conf)
#   winmm          = ogg-winmm (the CD music from Direct3D/Music/Track02..10.ogg; winmm.ini)
# RENDERER (before the script path in Launch Options, or a file RENDERER beside this script holding the word):
#   dgvoodoo  (default) ddraw + d3dimm from dgVoodoo2
#   wined3d   plain Wine DirectDraw / Direct3D (640x480 stretched to the screen by gamescope)

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HERE/launch.log"
log() { echo "[$(date '+%H:%M:%S')] $*" >>"$LOG"; }
: >"$LOG"
log "args: $*"
log "cwd: $(pwd)"

[ -z "${RENDERER:-}" ] && [ -s "$HERE/RENDERER" ] && RENDERER="$(tr -d ' \n' < "$HERE/RENDERER")"
RENDERER="${RENDERER:-dgvoodoo}"
log "RENDERER=$RENDERER  STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-unset}"

# Proton appends its own overrides after ours.
case "$RENDERER" in
  dgvoodoo) OVR="ddraw=n,b;d3dimm=n,b;winmm=n,b" ;;
  wined3d)  OVR="ddraw=b;d3dimm=b;winmm=n,b" ;;
  *)        log "unknown RENDERER '$RENDERER', using dgvoodoo"; OVR="ddraw=n,b;d3dimm=n,b;winmm=n,b" ;;
esac
export WINEDLLOVERRIDES="${OVR}${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
log "WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

# Debugging: if a file named PROTON_LOG exists beside this script, Proton writes steam-<appid>.log here. A file
# WINEDEBUG beside it adds Wine debug channels (e.g. +xinput,+dinput,+ddraw,+mci). Create / delete them from Desktop Mode.
if [ -e "$HERE/PROTON_LOG" ]; then
  export PROTON_LOG=1 PROTON_LOG_DIR="$HERE"
  log "PROTON_LOG on -> $HERE/steam-*.log"
  if [ -s "$HERE/WINEDEBUG" ]; then
    export WINEDEBUG="+timestamp,+tid,+seh,+loaddll,+process,$(tr -d ' \n' < "$HERE/WINEDEBUG")"
    log "WINEDEBUG=$WINEDEBUG"
  fi
fi

# Frame rate / GPU load overlay (DXVK, on top of dgVoodoo's D3D11): a file DXVK_HUD beside this script holding
# e.g. fps,gpuload.
if [ -s "$HERE/DXVK_HUD" ]; then
  export DXVK_HUD="$(tr -d ' \n' < "$HERE/DXVK_HUD")"
  log "DXVK_HUD=$DXVK_HUD"
fi

for f in Direct3D/Rollcage.exe Direct3D/QMIXER.DLL Direct3D/ddraw.dll Direct3D/d3dimm.dll Direct3D/dgVoodoo.conf \
         Direct3D/winmm.dll Direct3D/winmm.ini Direct3D/Music/Track02.ogg Direct3D/Music/Track10.ogg \
         IDXData/ROLLCAGE.IMG IDXData/Rollcage.idx movies/intro.fmv movies/psyg.fmv Save; do
  [ -e "$HERE/game/$f" ] || log "WARNING: game/$f missing"
done
log "saves: $(ls -l "$HERE"/game/Save/*.sav 2>/dev/null | awk '{print $5, $NF}' | tr '\n' ' ')"

# Testing another Proton without touching Steam's settings: a file PROTON_VERSION beside this script holding a folder
# name from steamapps/common (e.g. "Proton 11.0") replaces the Proton in Steam's command line.
if [ -s "$HERE/PROTON_VERSION" ]; then
  want="$(head -1 "$HERE/PROTON_VERSION")"; args=()
  for a in "$@"; do
    case "$a" in */steamapps/common/*/proton) a="${a%/steamapps/common/*}/steamapps/common/$want/proton";; esac
    args+=("$a")
  done
  set -- "${args[@]}"
  log "PROTON_VERSION=$want"
fi

log "exec: $*"
exec "$@"
