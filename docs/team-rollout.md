# Rolling BLINK out to a team

For a handful of boards -- five to ten -- on teammates' desks, all burned and
updated from this fork. Each board is driven by the BLINK app on its owner's
computer, over USB. Nothing is shared between desks, and a board shows only
its own owner's usage.

## Before buying boards

Buy **one** board from the listing you mean to use, burn it (below), and look
at it before ordering the rest. CYD batches differ in ways the firmware has to
be told about: this repository already carries two panel batches that differ
three ways -- mirrored, red and blue swapped, and much brighter at the same
backlight duty (`BLINK_PANEL_PILOT` in `firmware/Kconfig`). The default build
corrects for the production batch only. A board that comes up mirrored,
colour-swapped or glaring is a third batch, and ten of them are ten problems.

## Burning a board

On this Mac, one board at a time, from the repository root:

```sh
BLINK_PYTHON=$PWD/.venv-test/bin/python PATH=$PWD/.venv-test/bin:$PATH \
  sh tools/burn.sh --edition claude --logo dist/aif-startup.png \
  --port /dev/cu.usbserial-XXXX
```

- **`--logo` is not optional for a team unit.** Without it burn.sh *erases*
  the logo partition, on purpose, and the board boots as an individual unit.
- **The edition latches on the first write.** A board burned as `claude`
  stays `claude`; only an esptool erase with the board held in its bootloader
  undoes it.
- burn.sh stops the daemon on this Mac and restores it afterwards, and ends
  with `booted: fw <version>, board_id <id>`. Write the board id down against
  the person who gets the board -- `blink status` on their machine shows the
  same id, and it is the only way to tell two boards apart remotely.

**Do not burn the flash-encryption eFuses on team boards.** The shipped
firmware is USB-only: it stores no WiFi password and no sign-in token, so
encryption would protect nothing. The fuses cannot be unburned, and a fused
board can only ever be flashed with `tools/flash_encrypted.sh` and its own key
file -- lose that file and the board takes no update again.

## Installing on a teammate's computer

They paste the one-liner from the README into a terminal -- **not** a browser
download:

```bash
curl -fsSL https://github.com/gapietro/AIFBlink/releases/latest/download/blink-macos-arm64.tar.gz | tar xz && ./blink/blink
```

(`blink-macos-x86_64` on an Intel Mac; Windows and Linux are in the README.)

The app is not notarised, and this is why that does not matter here: a file
fetched by curl carries no quarantine flag, so macOS runs it, while the same
archive saved by a browser is quarantined and Gatekeeper refuses it. Someone
who used a browser anyway can clear the flag with
`xattr -dr com.apple.quarantine ./blink` and run it again.

It needs Claude Code 2.1.100 or newer. Then plug the board in;
`~/.blink/bin/blink status` says whether the panel is getting data.

## Releasing an update

A release reaches every desk: each board shows a prompt, and one tap installs
the app and the firmware together. So prove it on yours first.

1. Bump the version in `firmware/src/version.h` **and** `pc/version.py`.
   `tests/ci/check_versions.sh` refuses a release where they differ.
2. Commit, and burn your own board with it (above, with your port). Change
   nothing after this commit: the fleet gate checks that the run was at the
   commit being released, and `release.sh` refuses a dirty tree.
3. **Open Settings, then Badges, on the board, then go back to the gauges.**
   The fleet cannot tap a screen, and 1.7.0 passed it with a crash on the
   first Settings tap. `tools/release.sh` refuses until the board's log
   shows both screens on this version with memory to spare
   (`pc/screen_gate.py`).
4. Run the fleet with the board left on the gauges -- an open settings panel
   blocks sleep and fails the sleep scenario:
   `.venv-test/bin/python tools/fleet/run.py`. Check its exit status on its
   own; never pipe it into a push.
5. Tag and push the tag (`git tag v<version> && git push origin v<version>`),
   then:
   `BLINK_RELEASE_DRAFT=1 BLINK_PYTHON=$PWD/.venv-test/bin/python bash tools/release.sh`.
   That builds and signs the firmware, starts the binary builds, and leaves a
   complete draft. Publishing it is what puts the prompt on every board.

## Keep off this Mac

Two things exist only here, and the team depends on both:

- **The signing keys** (`~/.blink/*_signing_key_p256.pem`) and their
  encrypted backup (`~/blink-keys-2026-10-13.tar.gz.enc`). Lose every copy
  and no board accepts another update: each one has to come back to this
  desk to be re-burned with new keys.
- **`dist/aif-startup.png`**, the team logo. `dist/` is gitignored, so it is
  in no commit.
