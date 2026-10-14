/* Host test for the badge table and collection (firmware/src/badges.c).
 *   cc -Wall -I firmware/src tests/badges/host_test.c firmware/src/badges.c
 */
#include <stdio.h>
#include <string.h>
#include "badges.h"

static int failures;
#define CHECK(c, m) do { if (!(c)) { printf("FAIL: %s\n", m); failures++; } \
	else { printf("PASS: %s\n", m); } } while (0)

/* Sentence case: one capital at the start, and no other capital letter
 * except where a proper name or a unit needs one (Claude, Codex, the
 * hidden badge's "?" aside). Names are titles and are exempt. */
static int sentence_case(const char *s)
{
	if (s[0] < 'A' || s[0] > 'Z') {
		return 0;
	}
	for (const char *p = s + 1; *p; p++) {
		if (*p >= 'A' && *p <= 'Z' &&
		    strncmp(p, "Claude", 6) != 0 && strncmp(p, "Codex", 5) != 0) {
			return 0;
		}
	}
	return 1;
}

int main(void)
{
	char buf[64], msg[128];

	badges_set_mask(0);
	CHECK(badges_earned_count() == 0, "an empty collection counts zero");
	CHECK(strcmp(badge_title(13), "???") == 0,
	      "a hidden badge is ??? until found");
	CHECK(strcmp(badge_detail(13), "Hidden. Keep exploring.") == 0,
	      "and its detail gives nothing away");
	CHECK(strcmp(badge_title(2), "Night Owl") == 0,
	      "an ordinary badge shows its name while locked");

	badges_set_mask((1u << 2) | (1u << 13) | (1u << 20));
	CHECK(badges_earned_count() == 2,
	      "bits past the table are kept but not counted");
	CHECK(strcmp(badge_title(13), "Blacksmith") == 0,
	      "a found hidden badge shows its name");
	badges_summary(buf, sizeof(buf));
	CHECK(strcmp(buf, "2 of 15") == 0, "the settings subtitle");
	badge_announcement(2, buf, sizeof(buf));
	CHECK(strcmp(buf, "Badge earned: Night Owl") == 0, "the card's words");

	CHECK(badge_get(-1) == NULL && badge_get(BADGE_COUNT) == NULL,
	      "out-of-range indices are refused");
	CHECK(strcmp(badge_title(99), "") == 0 && !badge_earned(99),
	      "and answer harmlessly");

	for (int i = 0; i < BADGE_COUNT; i++) {
		const struct badge *b = badge_get(i);

		snprintf(msg, sizeof(msg), "%s: detail fits 47 characters",
			 b->name);
		CHECK(strlen(b->how) <= 47, msg);
		snprintf(msg, sizeof(msg), "%s: detail is sentence case",
			 b->name);
		CHECK(sentence_case(b->how), msg);
		snprintf(msg, sizeof(msg), "%s: name fits the grid label",
			 b->name);
		CHECK(strlen(b->name) <= 14, msg);
	}
	{
		int hard = 0, secret = 0;

		for (int i = 0; i < BADGE_COUNT; i++) {
			hard += badge_get(i)->tier == BADGE_TIER_HARD;
			secret += badge_get(i)->tier == BADGE_TIER_SECRET;
		}
		CHECK(hard == 3 && secret == 2, "ten, three hard, two hidden");
	}

	printf(failures ? "\n%d FAILED\n" : "\nall badge checks passed\n",
	       failures);
	return failures ? 1 : 0;
}
