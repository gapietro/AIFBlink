#ifndef PANEL_TUNE_H
#define PANEL_TUNE_H

#include <stdint.h>

/*
 * Screen contrast: which drive settings the ILI9341 is given.
 *
 * Three levels, picked in the Display screen and persisted (cfg_store). 0 is
 * what the Zephyr driver wrote at boot, so a board that never touches the
 * setting looks exactly as it always did.
 */
enum panel_contrast {
	PANEL_CONTRAST_NORMAL,
	PANEL_CONTRAST_HIGH,
	PANEL_CONTRAST_MAX,
	PANEL_CONTRAST_LEVELS
};

/* Load the persisted level and write it to the panel. After the driver's own
 * init and the MADCTL fix in main.c. */
void panel_contrast_init(void);

/* Apply and persist. Out-of-range values are ignored. */
void panel_contrast_set(uint8_t level);

uint8_t panel_contrast_get(void);

/* "Normal", "High", "Max" -- the words the Display screen shows. */
const char *panel_contrast_name(uint8_t level);

#endif /* PANEL_TUNE_H */
