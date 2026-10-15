# Blink firmware

The firmware that runs on the **ESP32-2432S028 "Cheap Yellow Display" (CYD)**: two
270° gauges for your Claude Code **session (5 h)** and **weekly (7 d)** usage, a wall
clock, per-model breakdown, and over-the-air updates. Built on **Zephyr** + LVGL,
booting through **MCUboot**, with flash encryption on units whose eFuses are burned.

The firmware version lives in [`src/version.h`](src/version.h) and is reported over
serial in the boot `hello` message.

## How it gets your usage

Over USB, from the daemon on your computer, and nothing else. The board says `hello`
over serial at boot; the daemon answers and streams usage, the time and updates to it
as NDJSON. There is no Wi-Fi and no token on the device.

A standalone Wi-Fi mode - on-device sign-in, captive-portal setup, its own usage
fetch - lived here, compiled out of every release, until 2026-10-15. It was removed
because it signed the board in to Anthropic as Claude Code, which
[Anthropic's terms](https://code.claude.com/docs/en/legal-and-compliance) do not
allow, and because it had stopped fitting in RAM. git history has it.

## Prerequisites

- **Zephyr v4.3.x** with its Python venv, and **Zephyr SDK 0.17.4**. The build
  scripts find the workspace themselves (`tools/lib_zephyr.sh` looks under
  `~/zephyrproject`, `~/zephyr-v*` and the same two under `~/Projects`); set
  `BLINK_ZEPHYR` to override.

  **Not v4.4.0.** Measured 2026-09-09: its mbedTLS is 4.1.0, which removed the
  legacy `mbedtls/sha256.h` that [`src/ota.c`](src/ota.c) includes, and the
  LVGL it pins moved `gesture_limit` out of the public `lv_indev` headers,
  which [`src/ui_settings.c`](src/ui_settings.c) reads. 4.3.1 has both
  (mbedTLS 3.6.6, `gesture_limit` in `lv_indev_private.h`) and wants SDK
  0.17.4 rather than the 1.0.1 that 4.4.0 asks for. Do not register both SDKs
  at once -- 1.0.1's CMake config breaks 4.3.1's configure even when 0.17.4 is
  registered alongside it.
- The **CYD board** on USB (a CH340 serial port, `/dev/cu.usbserial-*` on macOS).
- Your **signing keys** (see [Keys](#keys)).

## Build

```bash
. tools/lib_zephyr.sh && blink_zephyr_activate   # from the repo root

cd firmware
west build --sysbuild -d build-sb -b esp32_devkitc/esp32/procpu . \
  -- -DSB_CONFIG_BOOTLOADER_MCUBOOT=y -DUSE_CCACHE=0 \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE="\"$HOME/.blink/ota_signing_key_p256.pem\""
```

Notes:

- **There is one configuration, and it ships: USB only.** No radio, no sign-in, no
  token store. `tools/release.sh` still refuses an image carrying the old Wi-Fi mode's
  strings, checking the artifact and not only the config, so it cannot come back
  unnoticed.
- **Sysbuild + MCUboot is required.** Flash encryption needs the MCUboot boot chain;
  a plain single-image build produces something the encrypted chip can't boot.
- The board target is **`esp32_devkitc/esp32/procpu`** - there's no upstream CYD board,
  so [`boards/esp32_devkitc_esp32_procpu.overlay`](boards/) describes the wiring.
  Building with a different `-b` pollutes the build dir; recover with `-p always`.
- **Display SPI is pinned at 25 MHz.** The common 40 MHz CYD overclock white-screens
  some panels (init never latches) - see the overlay comment.

## Flash

**Not every CYD is fused, so check which one you have first.** A unit whose
flash-encryption eFuses are burned boots *only* images encrypted with its device key;
an unfused unit boots plaintext and cannot read an encrypted image at all. Cross the
two and the board sits in a boot loop (`invalid header: ...`) until it is re-flashed
the other way. Nothing is bricked - flashing burns no eFuses - but a cycle is lost
finding out.

```bash
espefuse.py --port <port> summary | grep FLASH_CRYPT_CNT
```

An **odd** number of bits set means encryption is on; `0` is a plaintext board.

**Fused unit** - use the script, which re-reads the eFuse itself and refuses a
plaintext chip (override with `BLINK_SKIP_EFUSE_CHECK=1`):

```bash
tools/flash_encrypted.sh        # defaults to the first /dev/cu.usbserial* port
```

**Plaintext unit** - two commands, because `west flash` writes only the app at
`0x20000` and leaves MCUboot at `0x1000` untouched:

```bash
west flash -d build-sb --esp-device <port> --esp-baud-rate 115200
esptool.py --port <port> --baud 115200 write_flash 0x1000 build-sb/mcuboot/zephyr/zephyr.bin
```

Port notes: opening the port resets the board, and only one process can own it at a
time. To watch the console without disturbing behavior, use
`tools/passive_log.py <port>` (resets once on open, then read-only). To wipe the
stored settings, erase the settings region:
`esptool.py --port <port> erase_region 0x3b0000 0x30000`.

Flash map (4 MB): MCUboot `0x1000`, slot 0 `0x20000`, slot 1 `0x170000`,
scratch `0x2C0000` (unused in swap-move mode), **company logo `0x330000`
(512 KB, see `src/logo_parse.h`)**, settings `0x3B0000`. The logo partition is
written only by `tools/burn.sh --logo` / `tools/flash_encrypted.sh --logo` and
read memory-mapped at boot; erase it (`erase_region 0x330000 0x80000`) to turn
a bench board back into an individual unit. `tools/flash_encrypted.sh` erases
it by default -- pass `--keep-logo` when re-flashing a dev board that should
keep its logo.

## Keys

Two secrets live **outside the repo**, in `~/.blink/`:

| Key | Purpose |
|-----|---------|
| `flash_key.bin` | Encrypts what's written to flash. Override with `BLINK_FLASH_KEY`. |
| `ota_signing_key_p256.pem` | Signs firmware images (ECDSA P-256) so the board will boot them. Override with `OTA_SIGNING_KEY`. |

**Back both up off this machine.** The eFuse copy of the flash key is sealed and
unreadable - the file is the only usable copy. Lose the signing key and you can no
longer ship updates that installed devices will accept (only a USB reflash with a new
key recovers).

## Releasing an update

```bash
# 1. bump BLINK_FW_VERSION in src/version.h, commit
# 2. from the repo root:
tools/release.sh
```

`release.sh` builds from the committed tree (it refuses a dirty tree or a reused
version), signs the image, and attaches `blink-fw.bin` + `manifest.json` to the
`v<version>` release on **`gapietro/AIFBlink`** - which is the feed every board
flashed from this fork reads. (Upstream's boards read `KfirLevy258/Blink`, and
verify against a key this fork does not have.)

The board has no network of its own, so it only *approves*: the daemon fetches the
release and writes slot0 with esptool. About 75 s, and no swap, because the bytes land
where the bootloader already looks. The trade is no automatic rollback; it is
acceptable only because a machine that can reflash the board is by definition already
cabled to it. Requires `pip install esptool` wherever the daemon runs.

A check runs as soon as the board is up (and daily after that). Anything newer raises a
prompt on the gauge screen -- **Update now** / **Later** -- and the settings row still
offers **Software update → Install x.y.z** on demand. The outcome is reported on the
next boot.

## How updates stay safe

Three independent layers, each guarding one thing:

- **HTTPS** authenticates the *download*: the daemon fetches it from GitHub,
  verified against the system's certificates and certifi's (`pc/ota.py`).
- **The manifest's SHA-256** pins the *exact bytes*: the daemon checks the
  download against it before writing anything.
- **MCUboot's ECDSA P-256 signature check** gates *what may boot* - only images signed
  with your private key run, so even a hash-passing forgery is rejected.

There is no automatic rollback: slot0 is written in place, so there is no spare copy
to fall back to. The daemon compensates where it can: it verifies the asset before
writing, and it reads the chip's eFuses and refuses outright if it cannot tell whether
flash encryption is burned, since a plaintext write to a fused board leaves it dark.

The board holds no secret worth encrypting: no Wi-Fi password, and no token -- a board
that once ran a Wi-Fi build erases any token it finds on its first boot. Published
images hold no secrets either - installability is gated by the signing key, not
secrecy.

## Hardware notes

Things worth knowing when hacking on the CYD:

- Touch (XPT2046) needs averaging (`reads = <8>`), and devicetree properties are
  last-one-wins - a stray duplicate silently degrades it.
- The backlight (GPIO 21) runs on LEDC PWM and is adjustable in Settings.

## Source map

| Area | Files |
|------|-------|
| Boot, orchestration, workers | `main.c` |
| Boot splash (streamed past LVGL) | `ui_boot.c`, `bootanim_dec.c` |
| Gauges and warnings | `usage_view.c` |
| Settings + software-update UI | `ui_settings.c` |
| OTA engine (check, install, verify) | `ota.c`, `ota_parse.c` |
| Wall clock (set by the daemon) | `net_time.c` |
| Persisted config (A/B, CRC-sealed) | `cfg_store.c` |
| Serial NDJSON protocol | `proto.c`, `msg_parse.c` |

Parsers and the protocol have host-side unit tests under [`../tests/`](../tests/).
