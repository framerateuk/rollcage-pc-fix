# Rollcage (Direct3D\Rollcage.exe as the official 1.0b patch of 13 Feb 2001 installs it for the standard edition,
# 757,760 bytes, MSVC; Attention to Detail / Psygnosis): new code for patch_exe.py. It goes into a section
# patch_exe.py adds to the exe, ".rdeck" at VA 0x6d7000 (file offset 0xb9000, the end of the file, 0x1000 bytes,
# readable / writable / executable): this code from 0x6d7000, its variables from 0x6d7c00 (zero when the exe loads).
# The exe always loads at its 0x400000 base (no dynamic-base flag, "relocations stripped" already set), so absolute
# addresses are used throughout.
#
# Assembled with Apple clang (integrated assembler):
#   clang -target i386-pc-linux-gnu -c caves.s -o caves.o
# patch_exe.py carries the resulting bytes (CAVE) and checks them against this file when clang is around
# (patch_exe.py --check-caves). docs/TECHNICAL.md explains each routine.
#
# Lesson kept from Speedster (23 Oct 2026): never keep a value in ecx / edx across an API call (Proton's
# timeGetTime and friends change them). Every routine that calls an API saves what it uses with pushad / popad and
# keeps values across API calls only in ebx / esi / edi / ebp or memory.
.intel_syntax noprefix
.set BASE, 0x6d7000

# imports used (IAT slots of Rollcage.exe)
.set ReadFile,           0x4a406c
.set WriteFile,          0x4a4070
.set LoadLibraryA,       0x4a40a0
.set GetModuleFileNameA, 0x4a40c4
.set CreateFileA,        0x4a40f0
.set Sleep,              0x4a40f8
.set CreateDirectoryA,   0x4a4108
.set CloseHandle,        0x4a4134
.set GetProcAddress,     0x4a4170

# game
.set TIMENOW,  0x436fe9              # the game's timeGetTime wrapper (every wait loop calls it)
.set PADRAW,   0x429510              # (player) -> eax = action bits, edx = bytes: directions, X, Y, Z axis (-127..127)
.set MOVIECB,  0x42dfd0              # the movie player's per-frame callback: eax 1 = stop the movie (keys)
.set BRAKERET, 0x42862e              # back in the pad converter after the analogue brake (patch pad, brakez)

# our variables (.rdeck from 0x6d7c00, zero at load)
.set XGS,     0x6d7c00               # XInputGetState (0 = no XInput DLL)
.set XINIT,   0x6d7c04               # 1 once xget has looked for XInput
.set MOVPREV, 0x6d7c08               # movieskip: pad buttons down at the previous look
.set NRW,     0x6d7c0c               # bytes read / written (ReadFile / WriteFile)
.set XS,      0x6d7c10               # an XINPUT_STATE (16 bytes): +4 wButtons, +6 LT, +7 RT, +8 LX, +10 LY, +12 RX,
                                     #   +14 RY
.set PATH,    0x6d7d00               # a file name (0x200 bytes)

.set DZ,      7000                   # left stick dead zone (of 32767), about 21 % (scaled from its edge: no jump)
.set RDZ,     16000                  # right stick: half way = a look / zoom button
.set TDZ,     8                      # trigger dead zone (of 255)

.macro PUSHI v                       # push imm32 (clang's intel syntax would make "push offset" 16-bit)
  .byte 0x68
  .long \v
.endm
.macro CALLG target                  # call a game address (rel32)
  .byte 0xe8
  .long \target - (BASE + (. + 4 - start))
.endm
.macro JMPG target                   # jmp to a game address (rel32)
  .byte 0xe9
  .long \target - (BASE + (. + 4 - start))
.endm

.text
start:

# ---------------------------------------------------------------------------------------------------------------
# stime (patch nobusy): the game's wait loops spin on its timeGetTime wrapper TIMENOW ("call TIMENOW; cmp ...;
# jae out; jmp back"): the frame limiter (0x4371a5: until 32 ms since the last frame) and two pauses (0x435a52
# 3 s at start-up, 0x436c85 up to 1 s). Their "call TIMENOW" comes here:
# Sleep(1) first, then the time. The loops sleep instead of burning a CPU core.
stime:
  push 1
  call dword ptr [Sleep]
  JMPG TIMENOW

# ---------------------------------------------------------------------------------------------------------------
# xget: eax = XInput user index (0..3) -> XS = its state, eax = 1; eax = 0 if not connected or no XInput. The first
# call looks for XInputGetState in xinput1_4.dll, else xinput1_3.dll, else xinput9_1_0.dll (Proton has all three;
# Windows 8+ has 1_4 and 9_1_0; the exe imports none of them). Keeps every other register.
xget:
  pushad
  mov esi, eax
  cmp dword ptr [XINIT], 0
  jne 2f
  mov dword ptr [XINIT], 1
  .byte 0xbf                         # mov edi, the three names (16 bytes each)
  .long A_XINPUT
  mov ebx, 3
1:
  push edi
  call dword ptr [LoadLibraryA]
  test eax, eax
  jz 3f
  PUSHI A_XGS
  push eax
  call dword ptr [GetProcAddress]
  test eax, eax
  jz 3f
  mov dword ptr [XGS], eax
  jmp 2f
3:
  add edi, 16
  dec ebx
  jnz 1b
2:
  mov eax, dword ptr [XGS]
  test eax, eax
  jz 9f
  cmp esi, 3
  ja 9f
  PUSHI XS
  push esi
  call eax
  test eax, eax
  jnz 9f
  popad
  mov eax, 1
  ret
9:
  popad
  xor eax, eax
  ret

# ---------------------------------------------------------------------------------------------------------------
# padraw (patch pad): the game builds each local player's input once a frame with PADRAW(player) (0x429510, called
# at 0x437097 and 0x4370dc / 0x4370f6): eax = the 32 action bits from the player's bindings (keyboard by default),
# edx = 4 bytes: direction bits, then the joystick's X, Y and Z axes (-127..127). That raw input is what replays
# and network games record; the pad converter (0x4284e0) turns it into the PlayStation pad the game logic reads.
# The calls come here: the game's own result, plus the Xbox pad with the player's number (XInput user 0 = player 1):
#   edx byte 1 (X)  the left stick (dead zone DZ), the D-pad left / right at full deflection: analogue steering
#   edx byte 2 (Y)  -RT / 2 (0..-127): analogue accelerate (the converter takes Y < 0 as accelerate)
#   edx byte 3 (Z)  LT / 2 (0..127): analogue brake (brakez makes the converter read it from Z)
#   eax |= the actions in padmap (buttons), Look Left / Right and Zoom in / out from the right stick, and the
#          digital steer / accelerate / brake bits past half way (for anything that reads those)
# Without a connected pad for that player: the game's result unchanged.
padraw:
  push dword ptr [esp + 4]
  CALLG PADRAW
  add esp, 4
  pushad                             # [esp + 0x1c] = eax (actions), [esp + 0x14] = edx (bytes)
  mov eax, dword ptr [esp + 0x24]    # the player (pushad 0x20 + return address)
  call xget
  test eax, eax
  jz 90f
  movzx ebx, word ptr [XS + 4]       # buttons
  xor edi, edi                       # actions to add
  .byte 0xbe                         # mov esi, padmap
  .long A_PADMAP
1:
  mov eax, dword ptr [esi]
  test eax, eax
  jz 2f
  test ebx, eax
  jz 3f
  or edi, dword ptr [esi + 4]
3:
  add esi, 8
  jmp 1b
2:
  movsx eax, word ptr [XS + 12]      # right stick X: look left / right
  cmp eax, -RDZ
  jg 4f
  or edi, 0x10000                    # Look Left
4:
  cmp eax, RDZ
  jl 5f
  or edi, 0x20000                    # Look Right
5:
  movsx eax, word ptr [XS + 14]      # right stick Y (up +): zoom in / out
  cmp eax, RDZ
  jl 6f
  or edi, 0x2                        # Zoom in
6:
  cmp eax, -RDZ
  jg 7f
  or edi, 0x1                        # Zoom out
7:
  movsx eax, word ptr [XS + 8]       # left stick X -> -127..127
  call axisb
  test bl, 4                         # D-pad left / right: full
  jz 8f
  mov eax, -127
8:
  test bl, 8
  jz 10f
  mov eax, 127
10:
  cmp eax, -64
  jg 11f
  or edi, 0x8000                     # Left
11:
  cmp eax, 64
  jl 12f
  or edi, 0x2000                     # Right
12:
  movzx ebp, al
  shl ebp, 8                         # ebp: X in byte 1
  movzx eax, byte ptr [XS + 7]       # RT: accelerate
  cmp eax, 128
  jb 13f
  or edi, 0x40                       # Accelerate
13:
  call trigb
  neg eax
  movzx eax, al
  shl eax, 16
  or ebp, eax                        # Y = -RT / 2 in byte 2
  movzx eax, byte ptr [XS + 6]       # LT: brake
  cmp eax, 128
  jb 14f
  or edi, 0x80                       # Brake
14:
  call trigb
  shl eax, 24
  or ebp, eax                        # Z = LT / 2 in byte 3
  mov eax, dword ptr [esp + 0x14]
  and eax, 0xff                      # keep the game's direction bits
  or eax, ebp
  mov dword ptr [esp + 0x14], eax
  or dword ptr [esp + 0x1c], edi
90:
  popad
  ret

# axisb: eax = a stick axis (-32768..32767) -> eax = -127..127, 0 inside the dead zone DZ and scaled from its edge.
# Changes eax, ecx, edx.
axisb:
  mov ecx, eax
  cdq
  xor eax, edx
  sub eax, edx                       # |value|
  sub eax, DZ
  jg 1f
  xor eax, eax
  ret
1:
  imul eax, eax, 127
  xor edx, edx
  push ecx
  mov ecx, 32767 - DZ
  div ecx
  pop ecx
  cmp eax, 127
  jbe 2f
  mov eax, 127
2:
  test ecx, ecx
  jns 3f
  neg eax
3:
  ret

# trigb: eax = a trigger (0..255) -> eax = 0..127, 0 below TDZ.
trigb:
  cmp eax, TDZ
  jae 1f
  xor eax, eax
  ret
1:
  shr eax, 1
  ret

# ---------------------------------------------------------------------------------------------------------------
# padflags (patch pad): when a race is set up, each player's analogue flags are worked out (0x44a430: from the
# Controls menu's "Joystick Analogue" switch and which actions are bound to joystick axes; 0x80 analogue, 4 steer,
# 1 accelerate, 2 brake) and stored with "mov [esi + 0x26e], ax" (0x46ad95; edi = the player). That store comes
# here: with an Xbox pad for that player the flags get 0x80 | 4 | 2 | 1 (analogue steering, accelerate and brake
# from padraw's X / Y / Z) and 8 (ours: brake from Z, brakez). Without one, the game's flags. (ecx and edx must
# survive: pushad.)
padflags:
  pushad
  mov eax, edi
  call xget
  test eax, eax
  jz 1f
  or word ptr [esp + 0x1c], 0x8f
1:
  popad
  mov word ptr [esi + 0x26e], ax
  ret

# brakez (patch pad): the pad converter (0x4284e0) takes the analogue brake from the joystick's Y axis (Y > 0,
# written under "test dl, 1"; dl = the flags, al = Y): an Xbox pad's brake and throttle would share one axis (both
# held = neither). With our flag 8 the brake comes from the Z byte padraw fills from LT instead, so RT and LT work
# together. The converter's 14 bytes at 0x428620 jump here; back to 0x42862e.
brakez:
  test dl, 1
  jz 9f
  test dl, 8
  jz 5f
  mov al, byte ptr [ebp + 7]         # Z: LT / 2
  test al, al
  jle 9f
  shl al, 1
  mov byte ptr [esi + 0xa], al
  jmp 9f
5:
  test eax, eax                      # the game's own: Y >= 0 is brake
  jl 9f
  shl al, 1
  mov byte ptr [esi + 0xa], al
9:
  JMPG BRAKERET

# ---------------------------------------------------------------------------------------------------------------
# movieskip (patch movieskip): the movie player calls a per-frame callback (0x42dfd0, set at 0x42df80) that stops
# the movie on Backspace, Tab, Enter, Esc or Space. The callback pointer is now this: the game's callback, or "stop"
# when A, B, X, Y, View or Start on the first Xbox pad is newly pressed.
movieskip:
  CALLG MOVIECB
  test eax, eax
  jnz 9f
  pushad
  xor eax, eax
  call xget
  test eax, eax
  jz 8f
  movzx eax, word ptr [XS + 4]
  and eax, 0xf030                    # A B X Y View Start
  mov ecx, dword ptr [MOVPREV]
  mov dword ptr [MOVPREV], eax
  not ecx
  and eax, ecx                       # newly pressed
  jz 8f
  mov dword ptr [esp + 0x1c], 1
8:
  popad
9:
  ret

# ---------------------------------------------------------------------------------------------------------------
# regget / regset (patch savefile): the game keeps its settings, records and progress as binary registry values in
# HKLM\Software\Psygnosis\Rollcage\BootSys: "DataPC" (0x1854 bytes), "DataPSX" (0xaa0) and "DataReplay" (0xaa0),
# read with 0x46c030(key, name, buffer, size) at 0x474b8d (-> bytes read, or -1) and written with
# 0x46c090(key, name, buffer, size) at 0x474d64 (-> 0, or -1). Those two calls come here: the same, with the file
# <exe folder>\..\Save\<name>.sav (the folder is made if missing) instead of the registry value.
regget:
  pushad
  mov esi, dword ptr [esp + 0x28]    # name
  mov edi, dword ptr [esp + 0x2c]    # buffer
  mov ebp, dword ptr [esp + 0x30]    # size
  call mkpath
  push 0
  push 0x80                          # FILE_ATTRIBUTE_NORMAL
  push 3                             # OPEN_EXISTING
  push 0
  push 1                             # FILE_SHARE_READ
  PUSHI 0x80000000                   # GENERIC_READ
  PUSHI PATH
  call dword ptr [CreateFileA]
  cmp eax, -1
  je 9f
  mov ebx, eax
  mov dword ptr [NRW], 0
  push 0
  PUSHI NRW
  push ebp
  push edi
  push ebx
  call dword ptr [ReadFile]
  push ebx
  call dword ptr [CloseHandle]
  mov eax, dword ptr [NRW]
  mov dword ptr [esp + 0x1c], eax
  popad
  ret
9:
  mov dword ptr [esp + 0x1c], -1
  popad
  ret

regset:
  pushad
  mov esi, dword ptr [esp + 0x28]
  mov edi, dword ptr [esp + 0x2c]
  mov ebp, dword ptr [esp + 0x30]
  call mkpath
  push 0
  push 0x80
  push 2                             # CREATE_ALWAYS
  push 0
  push 0
  PUSHI 0x40000000                   # GENERIC_WRITE
  PUSHI PATH
  call dword ptr [CreateFileA]
  cmp eax, -1
  je 9f
  mov ebx, eax
  mov dword ptr [NRW], 0
  push 0
  PUSHI NRW
  push ebp
  push edi
  push ebx
  call dword ptr [WriteFile]
  push ebx
  call dword ptr [CloseHandle]
  cmp dword ptr [NRW], ebp
  jne 9f
  mov dword ptr [esp + 0x1c], 0
  popad
  ret
9:
  mov dword ptr [esp + 0x1c], -1
  popad
  ret

# mkpath: esi = a value name -> PATH = "<exe folder>\..\Save\<name>.sav", and the Save folder made if missing.
# Changes eax, ebx, ecx, edx, edi... (called inside pushad; keeps esi only).
mkpath:
  push edi
  push 0x1c0
  PUSHI PATH
  push 0
  call dword ptr [GetModuleFileNameA]
  .byte 0xbf                         # mov edi, PATH
  .long PATH
  mov ebx, edi                       # just after the last backslash
1:
  mov al, byte ptr [edi]
  test al, al
  jz 2f
  inc edi
  cmp al, 0x5c
  jne 1b
  mov ebx, edi
  jmp 1b
2:
  mov edi, ebx
  push esi
  .byte 0xbe                         # mov esi, "..\Save"
  .long A_SAVEDIR
  call scopy
  pop esi
  push edi
  push 0
  PUSHI PATH
  call dword ptr [CreateDirectoryA]  # fails harmlessly when it is there
  pop edi
  mov byte ptr [edi], 0x5c
  inc edi
  call scopy                         # the name
  push esi
  .byte 0xbe                         # mov esi, ".sav"
  .long A_SAVEEXT
  call scopy
  pop esi
  pop edi
  ret

# scopy: copy the string at esi to edi (with its 0); edi -> that 0, esi unchanged. Changes eax.
scopy:
  push esi
1:
  mov al, byte ptr [esi]
  mov byte ptr [edi], al
  test al, al
  jz 2f
  inc esi
  inc edi
  jmp 1b
2:
  pop esi
  ret

# ---------------------------------------------------------------------------------------------------------------
  .p2align 2
padmap:                              # XInput button -> Rollcage action bits (docs/TECHNICAL.md, "Pad")
  .long 0x1000, 0x00000008           # A      Fire 1
  .long 0x4000, 0x00000004           # X      Fire 2
  .long 0x2000, 0x00000010           # B      Reverse
  .long 0x8000, 0x00000020           # Y      Face Forward
  .long 0x0100, 0x00001000           # LB     Target Car
  .long 0x0200, 0x80000000           # RB     Cinematic Camera
  .long 0x0040, 0x40000000           # L3     Rear View Mirror
  .long 0x0080, 0x00004000           # R3     Look Back
  .long 0x0030, 0x00000800           # Start / View: Pause (Windows: on the Deck Steam Input sends Enter / Esc)
  .long 0, 0
s_xgs:     .asciz "XInputGetState"
s_savedir: .asciz "..\\Save"
s_saveext: .asciz ".sav"
  .p2align 4
s_xinput:  .asciz "xinput1_4.dll"
  .p2align 4
           .asciz "xinput1_3.dll"
  .p2align 4
           .asciz "xinput9_1_0.dll"
.set A_XGS,     BASE + (s_xgs - start)
.set A_SAVEDIR, BASE + (s_savedir - start)
.set A_SAVEEXT, BASE + (s_saveext - start)
.set A_XINPUT,  BASE + (s_xinput - start)
.set A_PADMAP,  BASE + (padmap - start)
