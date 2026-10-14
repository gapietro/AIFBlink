/*
 * The badge table and the collection the board holds -- see badges.h.
 *
 * Pure C with no LVGL and no Zephyr in it, so tests/badges can check every
 * sentence the screen will show. The icons are LVGL's FontAwesome symbols,
 * spelled as their UTF-8 bytes so this file does not need lvgl.h to name
 * them; ui_badges.c draws them in the montserrat fonts, which carry that
 * range.
 *
 * Every sentence is sentence case, and each fits the detail line's 47
 * characters (CLAUDE.md) -- tests/badges checks both.
 */
#include <stdio.h>
#include <string.h>

#include "badges.h"

/* LV_SYMBOL_* as their UTF-8, so this file stays free of lvgl.h. */
#define SYM_EYE_OPEN	"\xEF\x81\xAE"
#define SYM_EYE_CLOSE	"\xEF\x81\xB0"
#define SYM_UP		"\xEF\x81\xB7"
#define SYM_LIST	"\xEF\x80\x8B"
#define SYM_SHUFFLE	"\xEF\x81\xB4"
#define SYM_LOOP	"\xEF\x81\xB9"
#define SYM_CHARGE	"\xEF\x83\xA7"
#define SYM_BELL	"\xEF\x83\xB3"
#define SYM_TINT	"\xEF\x81\x83"
#define SYM_OK		"\xEF\x80\x8C"
#define SYM_BATTERY	"\xEF\x89\x80"
#define SYM_GPS		"\xEF\x84\xA4"
#define SYM_BARS	"\xEF\x83\x89"
#define SYM_SETTINGS	"\xEF\x80\x93"

static const struct badge table[BADGE_COUNT] = {
	{ "First Light", "Your first live reading on the board",
	  SYM_EYE_OPEN, BADGE_TIER_NORMAL },
	{ "Early Bird", "A session running between 4 and 6 am",
	  SYM_UP, BADGE_TIER_NORMAL },
	{ "Night Owl", "A session running between midnight and 4 am",
	  SYM_EYE_CLOSE, BADGE_TIER_NORMAL },
	{ "Multitasker", "Three sessions running at once",
	  SYM_LIST, BADGE_TIER_NORMAL },
	{ "Agent Wrangler", "Five subagents running at once",
	  SYM_SHUFFLE, BADGE_TIER_NORMAL },
	{ "Polyglot", "Claude and Codex both used in one day",
	  SYM_LOOP, BADGE_TIER_NORMAL },
	{ "Week Streak", "Claude used seven days in a row",
	  SYM_CHARGE, BADGE_TIER_NORMAL },
	{ "Quick Draw", "Answer a waiting session in 10 s, 10 times",
	  SYM_BELL, BADGE_TIER_NORMAL },
	{ "Cool Head", "A week reset with under half of it used",
	  SYM_TINT, BADGE_TIER_NORMAL },
	{ "Centurion", "A hundred sessions finished",
	  SYM_OK, BADGE_TIER_NORMAL },
	{ "Iron Streak", "Claude used thirty days in a row",
	  SYM_BATTERY, BADGE_TIER_HARD },
	{ "Bullseye", "A week closed at 95% or more, never over",
	  SYM_GPS, BADGE_TIER_HARD },
	{ "Swarm Lord", "Four sessions and ten subagents at once",
	  SYM_BARS, BADGE_TIER_HARD },
	{ "Blacksmith", "You found the forge",
	  SYM_SETTINGS, BADGE_TIER_SECRET },
	{ "Don't Panic", "A gauge stopped at exactly 42%",
	  "42", BADGE_TIER_SECRET },
};

static uint32_t got;

const struct badge *badge_get(int i)
{
	return (i >= 0 && i < BADGE_COUNT) ? &table[i] : NULL;
}

void badges_set_mask(uint32_t mask)
{
	/* Bits past the table are badges from a newer daemon. Kept, so a
	 * later firmware that knows them finds them; never drawn here. */
	got = mask;
}

uint32_t badges_mask(void)
{
	return got;
}

bool badge_earned(int i)
{
	return i >= 0 && i < BADGE_COUNT && (got & (1u << i)) != 0;
}

int badges_earned_count(void)
{
	int n = 0;

	for (int i = 0; i < BADGE_COUNT; i++) {
		n += badge_earned(i) ? 1 : 0;
	}
	return n;
}

const char *badge_title(int i)
{
	const struct badge *b = badge_get(i);

	if (b == NULL) {
		return "";
	}
	if (b->tier == BADGE_TIER_SECRET && !badge_earned(i)) {
		return "???";
	}
	return b->name;
}

const char *badge_detail(int i)
{
	const struct badge *b = badge_get(i);

	if (b == NULL) {
		return "";
	}
	if (b->tier == BADGE_TIER_SECRET && !badge_earned(i)) {
		return "Hidden. Keep exploring.";
	}
	return b->how;
}

void badge_announcement(int i, char *buf, size_t len)
{
	const struct badge *b = badge_get(i);

	if (buf == NULL || len == 0) {
		return;
	}
	snprintf(buf, len, "Badge earned: %s", b ? b->name : "?");
}

void badges_summary(char *buf, size_t len)
{
	if (buf == NULL || len == 0) {
		return;
	}
	snprintf(buf, len, "%d of %d", badges_earned_count(), BADGE_COUNT);
}
