/*
 * Screen contrast, by re-tuning the panel controller after boot.
 *
 * WHY THIS EXISTS. The CYD's 2.8" panel is a cheap TN part, and on the owner's
 * desk (2026-10-14) it read washed out: a mid navy lifted towards grey-blue,
 * small text went soft. Darkening the palette (1.5.1) helped the colours; it
 * cannot help the panel's own response curve, which is what washes out. That
 * curve is set inside the ILI9341 by five registers the Zephyr driver writes
 * once at init, from devicetree defaults nobody chose for this glass:
 *
 *   PWCTRL1  (0xC0)  GVDD, the reference voltage the grey levels are cut
 *                    from. Higher spreads them over a wider swing, which on
 *                    a normally-white TN panel is deeper blacks.
 *   VMCTRL1  (0xC5)  VCOMH / VCOML, the common-electrode voltages.
 *   VMCTRL2  (0xC7)  the VCOM offset.
 *   PGAMCTRL (0xE0)  the positive-polarity gamma curve, 15 points.
 *   NGAMCTRL (0xE1)  the negative-polarity gamma curve, 15 points.
 *
 * THE LEVELS ARE TUNED BY EYE, and they have to be: there is no formula from
 * register values to "looks right", and panels vary by batch (backlight.c
 * already carries a correction for a batch that came out brighter). So:
 *
 *   Normal  exactly what the driver wrote -- taken from the same devicetree
 *           properties, not copied, so it cannot drift from them.
 *   High    the ILI9341 set most ESP32 display libraries ship (Adafruit's,
 *           TFT_eSPI's): a steeper gamma, GVDD 4.60 V, VCOMH 4.25 V. The
 *           CYD community's usual answer to this panel looking flat.
 *   Max     High with GVDD raised two steps to 4.70 V, for deeper blacks
 *           again. The first candidate to change if the panel says so.
 *
 * Judged on the owner's production board from their seat, 2026-10-14: High
 * looked best of the three. Normal stays the default all the same, so a board
 * updated into this release looks exactly as it did until somebody chooses.
 *
 * Every value is inside the ranges the datasheet gives, so a level that looks
 * wrong is a level that looks wrong, not a damaged panel -- and the setting
 * is always one tap from Normal, on a screen whose layout does not depend on
 * which level is showing.
 *
 * The registers are volatile: the panel forgets them on power loss and the
 * driver rewrites its defaults on every boot, which is why init re-applies
 * the stored level rather than trusting the panel to remember it.
 */
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/mipi_dbi.h>
#include <zephyr/sys/printk.h>

#include "panel_tune.h"
#include "cfg_store.h"

#define CMD_PWCTRL1	0xC0
#define CMD_VMCTRL1	0xC5
#define CMD_VMCTRL2	0xC7
#define CMD_PGAMCTRL	0xE0
#define CMD_NGAMCTRL	0xE1

struct contrast_regs {
	uint8_t pwctrl1[1];
	uint8_t vmctrl1[2];
	uint8_t vmctrl2[1];
	uint8_t pgam[15];
	uint8_t ngam[15];
};

#define PANEL_NODE DT_NODELABEL(ili9341)

static const struct contrast_regs levels[PANEL_CONTRAST_LEVELS] = {
	[PANEL_CONTRAST_NORMAL] = {
		.pwctrl1 = DT_PROP(PANEL_NODE, pwctrl1),
		.vmctrl1 = DT_PROP(PANEL_NODE, vmctrl1),
		.vmctrl2 = DT_PROP(PANEL_NODE, vmctrl2),
		.pgam = DT_PROP(PANEL_NODE, pgamctrl),
		.ngam = DT_PROP(PANEL_NODE, ngamctrl),
	},
	[PANEL_CONTRAST_HIGH] = {
		.pwctrl1 = { 0x23 },
		.vmctrl1 = { 0x3E, 0x28 },
		.vmctrl2 = { 0x86 },
		.pgam = { 0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1,
			  0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00 },
		.ngam = { 0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1,
			  0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F },
	},
	[PANEL_CONTRAST_MAX] = {
		.pwctrl1 = { 0x25 },
		.vmctrl1 = { 0x3E, 0x28 },
		.vmctrl2 = { 0x86 },
		.pgam = { 0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1,
			  0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00 },
		.ngam = { 0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1,
			  0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F },
	},
};

static const char *const names[PANEL_CONTRAST_LEVELS] = {
	"Normal", "High", "Max",
};

static uint8_t level;

#ifdef CONFIG_BLINK_PANEL_PILOT
/* Pilot panels keep the driver's own init, as they do for MADCTL in main.c:
 * the levels were tuned on production glass and mean nothing on theirs. */
static void apply(void)
{
}
#else
static const struct device *const panel_dbi =
	DEVICE_DT_GET(DT_PARENT(PANEL_NODE));
static const struct mipi_dbi_config panel_dbi_cfg =
	MIPI_DBI_CONFIG_DT(PANEL_NODE, SPI_OP_MODE_MASTER | SPI_WORD_SET(8), 0);

static void write_reg(uint8_t cmd, const uint8_t *data, size_t len)
{
	int r = mipi_dbi_command_write(panel_dbi, &panel_dbi_cfg, cmd, data, len);

	if (r < 0) {
		printk("[panel] contrast: write 0x%02x failed (%d)\n", cmd, r);
	}
}

static void apply(void)
{
	const struct contrast_regs *c = &levels[level];

	if (!device_is_ready(panel_dbi)) {
		return;
	}
	write_reg(CMD_PWCTRL1, c->pwctrl1, sizeof(c->pwctrl1));
	write_reg(CMD_VMCTRL1, c->vmctrl1, sizeof(c->vmctrl1));
	write_reg(CMD_VMCTRL2, c->vmctrl2, sizeof(c->vmctrl2));
	write_reg(CMD_PGAMCTRL, c->pgam, sizeof(c->pgam));
	write_reg(CMD_NGAMCTRL, c->ngam, sizeof(c->ngam));
	printk("[panel] contrast: %s\n", names[level]);
}
#endif

void panel_contrast_init(void)
{
	uint8_t stored = cfg_get_contrast();

	/* A level from a newer firmware, or a stray byte, is Normal: the one
	 * value that is certainly what this panel looked like before. */
	level = stored < PANEL_CONTRAST_LEVELS ? stored : PANEL_CONTRAST_NORMAL;
	if (level != PANEL_CONTRAST_NORMAL) {
		apply();	/* Normal is already what the driver wrote */
	}
}

void panel_contrast_set(uint8_t next)
{
	if (next >= PANEL_CONTRAST_LEVELS || next == level) {
		return;
	}
	level = next;
	cfg_set_contrast(level);
	apply();
}

uint8_t panel_contrast_get(void)
{
	return level;
}

const char *panel_contrast_name(uint8_t l)
{
	return l < PANEL_CONTRAST_LEVELS ? names[l] : names[0];
}
