/*
 * The Badges screen -- see ui_badges.h.
 *
 * LAYOUT, on the 320 x 240 panel, in the same measured terms as the settings
 * panel it opens over:
 *
 *   0..40     back control, title and count, title rule at y=40
 *   44..200   the grid: 5 x 3 cells of 56 x 48 (10.0 x 8.5 mm), pitch 60 x 52
 *   204, 220  two lines: the selected badge's name, and what earns it
 *
 * 48 px is under the 51 px the settings rows are held to. The cells are a
 * grid of fifteen, which a 51 px row cannot fit with the detail lines under
 * it, and a mis-tap here costs nothing: it shows the neighbouring badge's
 * description, and the right one is a second tap away.
 *
 * Icons are LVGL's built-in symbols (badges.c has the table), coloured by
 * tier once earned -- AIF green for the ten, gold for the three hard ones,
 * violet for the hidden two -- and a dim grey while locked.
 */
#include <stdio.h>
#include <lvgl.h>

#include "ui_badges.h"
#include "badges.h"
#include "theme.h"

#define COL_BG		THEMED(0x011824, 0x000A10)
#define COL_PANEL	THEMED(0x0C3347, 0x0E3D55)
#define COL_TRACK	THEMED(0x143B4F, 0x2A5A72)
#define COL_TEXT	lv_color_hex(0xFFFFFF)
#define COL_DIM		THEMED(0xB4C6D2, 0xD2DEE6)
#define COL_LOCKED	THEMED(0x3E5A6B, 0x4F6E80)
#define COL_LINE	THEMED(0x1A4A62, 0x2E6684)
#define COL_TIER_NORMAL	lv_color_hex(0x6AC251)	/* the AIF green */
#define COL_TIER_HARD	lv_color_hex(0xE0B341)	/* gold */
#define COL_TIER_SECRET	lv_color_hex(0xB48CF0)	/* violet */

#define GRID_COLS	5
#define CELL_W		56
#define CELL_H		48
#define PITCH_X		60
#define PITCH_Y		52
#define GRID_X		12
#define GRID_Y		44
#define DETAIL_Y1	204
#define DETAIL_Y2	220

static lv_obj_t *ov;
static lv_obj_t *cell[BADGE_COUNT];
static lv_obj_t *name_lbl;
static lv_obj_t *how_lbl;
static int selected = -1;

static lv_color_t tier_colour(int i)
{
	switch (badge_get(i)->tier) {
	case BADGE_TIER_HARD:	return COL_TIER_HARD;
	case BADGE_TIER_SECRET:	return COL_TIER_SECRET;
	default:		return COL_TIER_NORMAL;
	}
}

static void paint_cell(int i)
{
	bool got = badge_earned(i);
	lv_obj_t *icon = lv_obj_get_child(cell[i], 0);

	lv_obj_set_style_border_color(cell[i],
		i == selected ? COL_TEXT : (got ? tier_colour(i) : COL_TRACK), 0);
	lv_obj_set_style_border_width(cell[i], i == selected ? 2 : 1, 0);
	lv_obj_set_style_text_color(icon, got ? tier_colour(i) : COL_LOCKED, 0);
	/* A hidden badge shows no icon until it is found: the glyph alone
	 * would give the game away. */
	if (badge_get(i)->tier == BADGE_TIER_SECRET && !got) {
		lv_label_set_text(icon, "?");
	} else {
		lv_label_set_text(icon, badge_get(i)->icon);
	}
}

void ui_badges_select(int i)
{
	int was = selected;

	if (ov == NULL || i < 0 || i >= BADGE_COUNT) {
		return;
	}
	selected = i;
	if (was >= 0) {
		paint_cell(was);
	}
	paint_cell(i);
	lv_label_set_text(name_lbl, badge_title(i));
	lv_obj_set_style_text_color(name_lbl,
		badge_earned(i) ? tier_colour(i) : COL_TEXT, 0);
	lv_label_set_text(how_lbl, badge_detail(i));
}

static void cell_cb(lv_event_t *e)
{
	ui_badges_select((int)(intptr_t)lv_event_get_user_data(e));
}

static void back_cb(lv_event_t *e)
{
	(void)e;
	ui_badges_close();
}

static void gesture_cb(lv_event_t *e)
{
	(void)e;
	/* The same swipe that closes the settings panel closes this first, as
	 * on the Display screen. */
	if (lv_indev_get_gesture_dir(lv_indev_active()) == LV_DIR_RIGHT) {
		ui_badges_close();
	}
}

bool ui_badges_is_open(void)
{
	return ov != NULL;
}

void ui_badges_close(void)
{
	if (ov == NULL) {
		return;
	}
	/* Children first, as the Display screen does: nothing may write
	 * through these after the parent is gone. */
	for (int i = 0; i < BADGE_COUNT; i++) {
		cell[i] = NULL;
	}
	name_lbl = NULL;
	how_lbl = NULL;
	selected = -1;
	lv_obj_del(ov);
	ov = NULL;
}

void ui_badges_open(lv_obj_t *parent)
{
	char buf[24];

	if (ov != NULL) {
		return;
	}
	ov = lv_obj_create(parent);
	lv_obj_set_size(ov, LV_PCT(100), LV_PCT(100));
	lv_obj_set_style_bg_color(ov, COL_BG, 0);
	lv_obj_set_style_bg_opa(ov, LV_OPA_COVER, 0);
	lv_obj_set_style_border_width(ov, 0, 0);
	lv_obj_set_style_radius(ov, 0, 0);
	lv_obj_set_style_pad_all(ov, 0, 0);
	lv_obj_clear_flag(ov, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_clear_flag(ov, LV_OBJ_FLAG_GESTURE_BUBBLE);
	lv_obj_add_event_cb(ov, gesture_cb, LV_EVENT_GESTURE, NULL);
	lv_obj_center(ov);

	/* The back control, drawn as the settings panel draws its own. */
	lv_obj_t *back = lv_button_create(ov);

	lv_obj_set_size(back, 60, 36);
	lv_obj_align(back, LV_ALIGN_TOP_LEFT, 6, 2);
	lv_obj_set_style_bg_color(back, COL_PANEL, 0);
	lv_obj_set_style_bg_opa(back, LV_OPA_COVER, 0);
	lv_obj_set_style_border_width(back, 0, 0);
	lv_obj_set_style_radius(back, 9, 0);
	lv_obj_set_style_shadow_width(back, 0, 0);
	lv_obj_add_flag(back, LV_OBJ_FLAG_GESTURE_BUBBLE);
	lv_obj_set_ext_click_area(back, 10);
	lv_obj_add_event_cb(back, back_cb, LV_EVENT_CLICKED, NULL);

	lv_obj_t *chev = lv_label_create(back);

	lv_label_set_text(chev, LV_SYMBOL_LEFT);
	lv_obj_set_style_text_color(chev, COL_DIM, 0);
	lv_obj_center(chev);

	lv_obj_t *title = lv_label_create(ov);

	lv_label_set_text(title, "Badges");
	lv_obj_set_style_text_font(title, &lv_font_montserrat_16, 0);
	lv_obj_set_style_text_color(title, COL_TEXT, 0);
	lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 10);

	lv_obj_t *count = lv_label_create(ov);

	badges_summary(buf, sizeof(buf));
	lv_label_set_text(count, buf);
	lv_obj_set_style_text_color(count, COL_DIM, 0);
	lv_obj_align(count, LV_ALIGN_TOP_RIGHT, -12, 12);

	lv_obj_t *rule = lv_obj_create(ov);

	lv_obj_set_size(rule, LV_HOR_RES, 1);
	lv_obj_align(rule, LV_ALIGN_TOP_LEFT, 0, 40);
	lv_obj_set_style_bg_color(rule, COL_LINE, 0);
	lv_obj_set_style_bg_opa(rule, LV_OPA_COVER, 0);
	lv_obj_set_style_border_width(rule, 0, 0);
	lv_obj_set_style_radius(rule, 0, 0);

	for (int i = 0; i < BADGE_COUNT; i++) {
		lv_obj_t *c = lv_button_create(ov);

		cell[i] = c;
		lv_obj_set_size(c, CELL_W, CELL_H);
		lv_obj_align(c, LV_ALIGN_TOP_LEFT,
			     GRID_X + (i % GRID_COLS) * PITCH_X,
			     GRID_Y + (i / GRID_COLS) * PITCH_Y);
		lv_obj_set_style_bg_color(c, COL_PANEL, 0);
		lv_obj_set_style_bg_opa(c, LV_OPA_COVER, 0);
		lv_obj_set_style_radius(c, 10, 0);
		lv_obj_set_style_shadow_width(c, 0, 0);
		lv_obj_set_style_pad_all(c, 0, 0);
		lv_obj_clear_flag(c, LV_OBJ_FLAG_SCROLLABLE);
		lv_obj_clear_flag(c, LV_OBJ_FLAG_GESTURE_BUBBLE);
		lv_obj_add_event_cb(c, cell_cb, LV_EVENT_CLICKED,
				    (void *)(intptr_t)i);

		lv_obj_t *icon = lv_label_create(c);

		lv_obj_set_style_text_font(icon, &lv_font_montserrat_20, 0);
		lv_obj_center(icon);
		paint_cell(i);
	}

	name_lbl = lv_label_create(ov);
	lv_label_set_text(name_lbl, "Tap a badge");
	lv_obj_set_style_text_color(name_lbl, COL_TEXT, 0);
	lv_obj_align(name_lbl, LV_ALIGN_TOP_MID, 0, DETAIL_Y1);

	how_lbl = lv_label_create(ov);
	lv_label_set_text(how_lbl, "to see what earns it");
	lv_obj_set_style_text_color(how_lbl, COL_DIM, 0);
	lv_obj_set_width(how_lbl, 300);
	lv_obj_set_style_text_align(how_lbl, LV_TEXT_ALIGN_CENTER, 0);
	lv_label_set_long_mode(how_lbl, LV_LABEL_LONG_DOT);
	lv_obj_align(how_lbl, LV_ALIGN_TOP_MID, 0, DETAIL_Y2);
}
