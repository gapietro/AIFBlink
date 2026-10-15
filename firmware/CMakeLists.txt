cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(claude_usage_display)

target_sources(app PRIVATE
	src/main.c
	src/proto.c
	src/msg_parse.c
	src/usage_view.c
	src/fmt.c
	src/cfg_store.c
	src/net_time.c
	src/ui_boot.c
	src/bootanim_dec.c
	src/bootclip.c
	src/ui_sleep.c
	src/sleep_gate.c
	src/upd_prompt.c
	src/upd_row.c
	src/upd_tap.c
	src/whatsnew.c
	src/logo_parse.c
	src/logo.c
	src/ui_settings.c
	src/ui_anim.c
	src/ui_slide.c
	src/ui_swipe.c
	src/backlight.c
	src/theme.c
	src/badges.c
	src/ui_badges.c
	src/ota_parse.c
	src/ota.c
	src/ui_touchfx.c
	src/usage_state.c
	src/usage_freshness.c
)

# Diagnostic only; CONFIG_BLINK_TOUCH_TRACE is off in release builds.
target_sources_ifdef(CONFIG_BLINK_TOUCH_TRACE app PRIVATE src/touch_trace.c)

