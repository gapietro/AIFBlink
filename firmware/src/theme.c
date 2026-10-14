/*
 * The contrast mode -- see theme.h for why it is colours and not registers.
 */
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/reboot.h>

#include "theme.h"
#include "cfg_store.h"
#include "ui_boot.h"

static uint8_t level;

/* Survives the warm reset theme_set_and_restart() does, like ui_boot.c's
 * skip_magic; the magic guards against power-on garbage. */
static __noinit uint32_t reopen_magic;
#define REOPEN_MAGIC 0xc0e7a57u

static const char *const names[THEME_LEVELS] = { "Normal", "High" };

void theme_init(void)
{
	uint8_t stored = cfg_get_contrast();

	/* Anything this firmware does not know -- a level from a newer build,
	 * or 1.6.0's "Max" -- is Normal, the palette every board shipped in. */
	level = stored < THEME_LEVELS ? stored : THEME_NORMAL;
	printk("[theme] contrast: %s\n", names[level]);
}

uint8_t theme_level(void)
{
	return level;
}

void theme_set_and_restart(uint8_t next)
{
	if (next >= THEME_LEVELS || next == level) {
		return;
	}
	cfg_set_contrast(next);
	printk("[theme] contrast -> %s, restarting\n", names[next]);
	k_msleep(200);	/* let the NVS write land, as the settings actions do */
	reopen_magic = REOPEN_MAGIC;
	ui_boot_mark_intentional_reboot();
	sys_reboot(SYS_REBOOT_COLD);
}

bool theme_take_reopen(void)
{
	bool was = reopen_magic == REOPEN_MAGIC;

	reopen_magic = 0;
	return was;
}

const char *theme_name(uint8_t l)
{
	return l < THEME_LEVELS ? names[l] : names[0];
}
