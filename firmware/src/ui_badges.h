#ifndef UI_BADGES_H
#define UI_BADGES_H

#include <stdbool.h>
#include <lvgl.h>

/*
 * The Badges screen: every badge in a grid, earned ones in their tier's
 * colour, the rest dimmed. Opened from the settings panel, over it, the way
 * the Display screen is. See badges.h for the table and pc/badges.py for
 * the rules.
 */
void ui_badges_open(lv_obj_t *parent);
void ui_badges_close(void);
bool ui_badges_is_open(void);

/* Show badge i's name and rule in the detail lines, as a tap does. For the
 * panel renderer, which cannot tap. */
void ui_badges_select(int i);

#endif /* UI_BADGES_H */
