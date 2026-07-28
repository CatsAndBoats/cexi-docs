# FFXiMain.dll — Gear Model ID → File ID Formula

Searched `pol_decompressed.bin` for race-specific FTABLE offsets derived from retail BigDats JSON files.


## CMP 25088=0x6200 @ 0x1030EF13

```asm
    1030EEF3:  006000                add byte ptr [eax], ah
    1030EEF6:  0000                  add byte ptr [eax], al
    1030EEF8:  0cff                  or al, 0xff
    1030EEFA:  ff8000000000          inc dword ptr [eax]
    1030EF00:  0000                  add byte ptr [eax], al
    1030EF02:  0000                  add byte ptr [eax], al
    1030EF04:  61                    popal 
    1030EF05:  0000                  add byte ptr [eax], al
    1030EF07:  000cff                add byte ptr [edi + edi*8], cl
    1030EF0A:  ff8000000000          inc dword ptr [eax]
    1030EF10:  0000                  add byte ptr [eax], al
    1030EF12:  0000                  add byte ptr [eax], al
    1030EF14:  6200                  bound eax, qword ptr [eax]
    1030EF16:  0000                  add byte ptr [eax], al
    1030EF18:  0cff                  or al, 0xff
    1030EF1A:  ff8000000000          inc dword ptr [eax]
    1030EF20:  0000                  add byte ptr [eax], al
    1030EF22:  0000                  add byte ptr [eax], al
    1030EF24:  6300                  arpl word ptr [eax], ax
    1030EF26:  0000                  add byte ptr [eax], al
    1030EF28:  0cff                  or al, 0xff
    1030EF2A:  ff8000000000          inc dword ptr [eax]
    1030EF30:  0000                  add byte ptr [eax], al
    1030EF32:  0000                  add byte ptr [eax], al
    1030EF34:  640000                add byte ptr fs:[eax], al
    1030EF37:  000cff                add byte ptr [edi + edi*8], cl
    1030EF3A:  ff8000000000          inc dword ptr [eax]
    1030EF40:  0000                  add byte ptr [eax], al
    1030EF42:  0000                  add byte ptr [eax], al
    1030EF44:  650000                add byte ptr gs:[eax], al
    1030EF47:  000cff                add byte ptr [edi + edi*8], cl
    1030EF4A:  ff8000000000          inc dword ptr [eax]
    1030EF50:  0000                  add byte ptr [eax], al
```


## CMP 24640=0x6040 @ 0x1026EBAC

```asm
    1026EB8C:  0450                  add al, 0x50
    1026EB8E:  51                    push ecx
    1026EB8F:  52                    push edx
    1026EB90:  e83be80100            call 0x1028d3d0
    1026EB95:  83c414                add esp, 0x14
    1026EB98:  8bf8                  mov edi, eax
    1026EB9A:  6a00                  push 0
    1026EB9C:  57                    push edi
    1026EB9D:  e89e670100            call 0x10285340
    1026EBA2:  83c408                add esp, 8
    1026EBA5:  89bebc000000          mov dword ptr [esi + 0xbc], edi
    1026EBAB:  e840600000            call 0x10274bf0
    1026EBB0:  2bc3                  sub eax, ebx
    1026EBB2:  5f                    pop edi
    1026EBB3:  898688000000          mov dword ptr [esi + 0x88], eax
    1026EBB9:  5e                    pop esi
    1026EBBA:  33c0                  xor eax, eax
    1026EBBC:  5b                    pop ebx
    1026EBBD:  83c408                add esp, 8
    1026EBC0:  c3                    ret 
    1026EBC1:  50                    push eax
    1026EBC2:  681c1b3b10            push 0x103b1b1c
    1026EBC7:  e824680100            call 0x102853f0
    1026EBCC:  83c408                add esp, 8
    1026EBCF:  83c8ff                or eax, 0xffffffff
    1026EBD2:  5f                    pop edi
    1026EBD3:  5e                    pop esi
    1026EBD4:  5b                    pop ebx
    1026EBD5:  83c408                add esp, 8
    1026EBD8:  c3                    ret 
    1026EBD9:  90                    nop 
    1026EBDA:  90                    nop 
    1026EBDB:  90                    nop 
    1026EBDC:  90                    nop 
    1026EBDD:  90                    nop 
    1026EBDE:  90                    nop 
    1026EBDF:  90                    nop 
    1026EBE0:  51                    push ecx
    1026EBE1:  55                    push ebp
    1026EBE2:  56                    push esi
    1026EBE3:  57                    push edi
    1026EBE4:  e807600000            call 0x10274bf0
```
