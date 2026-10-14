#ifndef THEME_H
#define THEME_H

#include <stdbool.h>
#include <stdint.h>

/*
 * The screen's contrast mode: which of two palettes every screen is built in.
 *
 * Contrast is done in SOFTWARE, by the colours we draw, and that is a
 * decision with a failure behind it. 1.6.0's first attempt re-tuned the
 * panel controller's own gamma and voltage registers, and on the bench board
 * (2026-10-14) it came up rotated, mirrored and colour-swapped at every boot.
 * The likeliest reading is that this CYD batch's controller is not a genuine
 * ILI9341 -- an ST7789-family part answers the same drawing commands, and on
 * one of those 0xC0 is not power control but an orientation and colour-order
 * override -- and the panel cannot be asked: it does not drive MISO, so its
 * ID reads as zeros. Registers on an unidentified chip are not a setting to
 * ship. Colours are: they cannot garble anything, and every one of them is
 * checked by tests/usage_contrast and drawn by tools/panel_render first.
 *
 * Chosen once, at boot, from the stored level. Each screen takes its colours
 * as it is built, so a change is applied by restarting -- see
 * theme_set_and_restart().
 */
enum theme_contrast {
	THEME_NORMAL,
	THEME_HIGH,
	THEME_LEVELS
};

/* Read the stored level. After cfg_init(), before any screen is built. */
void theme_init(void);

/* The level this boot is drawing in. */
uint8_t theme_level(void);

static inline bool theme_high_contrast(void)
{
	return theme_level() == THEME_HIGH;
}

/* Persist a new level and restart into it. Returns only if `level` is out of
 * range or already the one in use. */
void theme_set_and_restart(uint8_t level);

/*
 * True once, on the boot that theme_set_and_restart() caused. The person who
 * pressed the button was on the Display screen, and the board should put them
 * back there rather than on the gauges -- see ui_settings_reopen_display().
 */
bool theme_take_reopen(void);

/* "Normal" / "High" -- the words the Display screen shows. */
const char *theme_name(uint8_t level);

/*
 * One colour in each palette. Every themed #define in the screen files is one
 * of these, so a palette is a column you can read down, and the contrast test
 * checks both columns against the same rules.
 */
#define THEMED(normal, high) \
	lv_color_hex(theme_high_contrast() ? (high) : (normal))

#endif /* THEME_H */
