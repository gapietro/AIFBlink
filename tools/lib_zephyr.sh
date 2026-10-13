# Find the Zephyr workspace instead of naming one. Sourced, not run.
#
# This used to be spelled "$HOME/zephyr-v4.4.0" in four scripts, and that path
# was wrong twice over. The workspace on the machine those scripts were written
# on was ~/zephyrproject, so the literal never resolved there either -- burn.sh
# only survived because its `. activate` is followed by `|| true`, and
# release.sh would have failed outright the first time anyone ran it from a
# clean shell.
#
# The second way it was wrong is worse: Zephyr 4.4.0 CANNOT BUILD THIS
# FIRMWARE. Measured 2026-09-09 -- its mbedTLS is 4.1.0, which removed the
# legacy mbedtls/sha256.h that src/ota.c:21 includes (there are no sha headers
# in that module at all), and the LVGL it pins moved `gesture_limit` out of the
# public lv_indev headers, which src/ui_settings.c:2189 reads. Zephyr 4.3.1 has
# both -- mbedTLS 3.6.6 and gesture_limit at lv_indev_private.h:69 -- and wants
# SDK 0.17.4 rather than the 1.0.1 that 4.4.0 asks for.
#
# So a directory name that carries a version number is a claim this repo cannot
# keep. Searching for a workspace costs nothing and does not go stale.
#
# BLINK_ZEPHYR wins if it is set, for a machine that keeps several. Otherwise
# the first candidate that looks like a west workspace is taken, and "looks
# like" means it holds the venv these scripts are about to source -- not merely
# that a directory of that name exists. A half-finished checkout should read as
# absent here, not as a workspace that then fails deep inside a build.
blink_zephyr_ws() {
	# zsh, the macOS login shell, aborts the whole command on a glob that
	# matches nothing -- "no matches found: ~/zephyr-v*" -- so the documented
	# `. tools/lib_zephyr.sh && blink_zephyr_activate` died on any Mac with
	# just one of the four candidates (2026-10-12). nullglob drops an
	# unmatched pattern instead, and localoptions undoes it when this returns.
	# sh and bash never run the line.
	[ -n "${ZSH_VERSION:-}" ] && setopt localoptions nullglob
	if [ -n "${BLINK_ZEPHYR:-}" ]; then
		[ -f "$BLINK_ZEPHYR/.venv/bin/activate" ] || return 1
		printf '%s\n' "$BLINK_ZEPHYR"
		return 0
	fi
	for _bz_d in "$HOME"/zephyrproject "$HOME"/zephyr-v* \
	             "$HOME"/Projects/zephyrproject "$HOME"/Projects/zephyr-v*; do
		[ -f "$_bz_d/.venv/bin/activate" ] || continue
		[ -d "$_bz_d/zephyr" ] || continue
		printf '%s\n' "$_bz_d"
		return 0
	done
	return 1
}

# Put a Zephyr build environment in this shell, or say why it cannot.
#
# ZEPHYR_TOOLCHAIN_VARIANT has to be exported before the build: Zephyr 4.3.1's
# cmake/modules/FindZephyr-sdk.cmake:57 uses it unquoted inside an if(), so
# when it is unset CMake 4.4.3 -- what Homebrew ships as of 2026-09 -- sees an
# empty operand and fails the configure with "Unknown arguments specified".
# Older CMake tolerated the empty expansion, which is why this appears only on
# newly set-up machines and never on one that has been building for a year.
blink_zephyr_activate() {
	_bz_ws=$(blink_zephyr_ws) || {
		echo "FATAL: no Zephyr workspace found." >&2
		echo "       Looked for a directory holding .venv/bin/activate and zephyr/ under" >&2
		echo "       ~/zephyrproject, ~/zephyr-v*, ~/Projects/zephyrproject, ~/Projects/zephyr-v*." >&2
		echo "       Set BLINK_ZEPHYR to the workspace, or see firmware/README.md." >&2
		return 1
	}
	# shellcheck disable=SC1090
	. "$_bz_ws/.venv/bin/activate"
	ZEPHYR_BASE="${ZEPHYR_BASE:-$_bz_ws/zephyr}"
	export ZEPHYR_BASE
	export ZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT:-zephyr}"
	# Kept because release.sh sourced it before this helper existed. Exporting
	# ZEPHYR_BASE is enough for `west build` on its own; this also puts
	# zephyr/scripts on PATH, and dropping it silently would be a behaviour
	# change buried in a refactor.
	# shellcheck disable=SC1090
	. "$_bz_ws/zephyr/zephyr-env.sh" >/dev/null 2>&1 || true
	# The ESP32 image step runs a bare `esptool elf2image`, and Zephyr's own
	# requirements do not install it. A workspace without it configures, then
	# compiles for two minutes, then stops with "esptool: command not found"
	# (release.sh, 2026-10-13: burn.sh had passed only because the caller's
	# PATH happened to carry another venv). Say so before the build starts.
	command -v esptool >/dev/null 2>&1 || {
		echo "FATAL: esptool is not on PATH, and the ESP32 build needs it." >&2
		echo "       Install the pinned one into the workspace venv:" >&2
		echo "         $_bz_ws/.venv/bin/pip install esptool==5.3.1 bitstring==4.4.0" >&2
		echo "       (the versions pc/requirements.txt pins)." >&2
		return 1
	}
}
