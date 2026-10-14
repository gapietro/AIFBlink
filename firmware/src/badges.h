#ifndef BADGES_H
#define BADGES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * Badges: goals met while using the board (pc/badges.py, where the rules
 * live). The board holds the words and the collection it was last sent;
 * the daemon decides what has been earned.
 *
 * INDEX N HERE IS BIT N ON THE WIRE, and is badge N in pc/badges.BADGES --
 * tests/pc/test_badges.py reads this file's table and checks the names
 * line up. Never reorder; add at the end.
 */
#define BADGE_COUNT 15

enum badge_tier {
	BADGE_TIER_NORMAL,	/* the ten everyday ones */
	BADGE_TIER_HARD,	/* the three that take weeks */
	BADGE_TIER_SECRET,	/* hidden until found: "???" */
};

struct badge {
	const char *name;	/* "Night Owl" */
	const char *how;	/* one sentence, what earns it */
	const char *icon;	/* an LV_SYMBOL glyph, or a short text */
	enum badge_tier tier;
};

const struct badge *badge_get(int i);

/* The collection, as last sent by the daemon (protocol `badges`). */
void badges_set_mask(uint32_t mask);
uint32_t badges_mask(void);
bool badge_earned(int i);
int badges_earned_count(void);

/* "Night Owl", or "???" for a hidden badge not yet found. */
const char *badge_title(int i);

/* What the detail line under the grid says for badge i: the earning rule,
 * or a nudge for a hidden one not yet found. */
const char *badge_detail(int i);

/* "Badge earned: Night Owl" -- the card the gauges show. Always the real
 * name: by the time it is announced, it has been found. */
void badge_announcement(int i, char *buf, size_t len);

/* "7 of 15" -- the settings row's subtitle. */
void badges_summary(char *buf, size_t len);

#endif /* BADGES_H */
