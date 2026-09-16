#!/usr/bin/env python3
"""Look up a U4B WSPR channel number (as listed at
https://traquito.github.io/channelmap/) and print the derived
id1/id3/start-minute/frequency values ready to paste into
LightAPRS-W-2-pico-balloon.ino's "U4B protocol channel identity" config
block.

This is a 1:1 port of the reference implementation's channel<->parameter
mapping (traquito/WsprEncoded: WsprChannelMap.h, Wspr.h, WsprUtl.h,
fetched and transcribed directly -- not from a summary), not a
reimplementation from a written description. GetChannelDetails() runs a
self-check against 3 known-good vectors from that reference
implementation's own unit tests every time it's invoked, and refuses to
print an answer if that check fails.

Usage:
    uv run u4b_channel.py --channel 226 [--band 20m]
    uv run u4b_channel.py --list-bands
"""

import argparse
import sys

# ---- reference tables (traquito/WsprEncoded: Wspr.h) ----------------------

BAND_DATA = [
    ("2190m", 136_000),
    ("630m", 474_200),
    ("160m", 1_836_600),
    ("80m", 3_568_600),
    ("60m", 5_287_200),
    ("40m", 7_038_600),
    ("30m", 10_138_700),
    ("20m", 14_095_600),
    ("17m", 18_104_600),
    ("15m", 21_094_600),
    ("12m", 24_924_600),
    ("10m", 28_124_600),
    ("6m", 50_293_000),
    ("4m", 70_091_000),
    ("2m", 144_489_000),
    ("70cm", 432_300_000),
    ("23cm", 1_296_500_000),
]
BAND_NAMES = [b for b, _ in BAND_DATA]
BAND_DIAL_FREQ = dict(BAND_DATA)

# Only 20m is currently wired up in LightAPRS-W-2-pico-balloon.ino
# (WSPR_LANE_FREQ's commented options). Other bands are supported by this
# calculator for completeness / future firmware work, but picking one
# won't do anything until the sketch itself supports that band's WSPR TX.
FIRMWARE_SUPPORTED_BANDS = {"20m"}

ID1_LIST = ["0", "1", "Q"]
ID3_LIST = [str(d) for d in range(10)]
FREQ_BAND_LIST = [1, 2, 4, 5]          # skips the middle (3rd) 40 Hz lane as a guard band
ROTATION_LIST = [4, 2, 0, 3, 1]        # WsprChannelMap::GetMinuteListForBand's rotationList
BASE_MINUTE_LIST = [8, 0, 2, 4, 6]     # WsprChannelMap::GetMinuteListForBand's minuteList


def wspr_rotate(values, count):
    """WsprUtl::Rotate: positive = rotate right, negative = rotate left, 0 = no-op."""
    n = len(values)
    if count > 0:
        count = count % n
        return values[-count:] + values[:-count] if count else list(values)
    else:
        count = (-count) % n
        return values[count:] + values[:count]


def minute_list_for_band(band):
    idx = BAND_NAMES.index(band)
    rotation = ROTATION_LIST[idx % 5]
    return wspr_rotate(BASE_MINUTE_LIST, rotation)


def channel_details(band, channel):
    """Port of WsprChannelMap::GetChannelDetails(). Returns a dict with
    band, channel, id1, id3, id13, minute, lane (1-4), freq (Hz), freq_dial (Hz)."""
    if band not in BAND_DIAL_FREQ:
        raise ValueError(f"unknown band {band!r}; see --list-bands")
    if not (0 <= channel <= 599):
        raise ValueError("channel must be 0..599")

    dial_freq = BAND_DIAL_FREQ[band]
    freq_tx_low = dial_freq + 1500 - 100
    freq_tx_high = dial_freq + 1500 + 100
    freq_tx_window = freq_tx_high - freq_tx_low        # 200 Hz
    freq_band_count = 5
    band_size_hz = freq_tx_window // freq_band_count   # 40 Hz

    minute_list = minute_list_for_band(band)
    rows_per_col = freq_band_count * len(FREQ_BAND_LIST)  # 20

    row_count = 0
    for freq_band in FREQ_BAND_LIST:
        freq_band_low = (freq_band - 1) * band_size_hz
        freq_band_center = freq_band_low + band_size_hz // 2

        for minute in minute_list:
            freq_band_label = freq_band - 1 if freq_band >= 4 else freq_band

            for id1 in ID1_LIST:
                id1_offset = {"0": 0, "1": 200, "Q": 400}[id1]
                for col_count, id3 in enumerate(ID3_LIST):
                    channel_calc = id1_offset + col_count * rows_per_col + row_count
                    if channel_calc == channel:
                        return {
                            "band": band,
                            "channel": channel_calc,
                            "id1": id1,
                            "id3": id3,
                            "id13": id1 + id3,
                            "minute": minute,
                            "lane": freq_band_label,
                            "freq": freq_tx_low + freq_band_center,
                            "freq_dial": dial_freq,
                        }

            row_count += 1

    raise AssertionError(f"channel {channel} not found for band {band} -- should be unreachable for 0..599")


# ---- self-check: 3 known-good vectors from the reference implementation's
# own unit tests (traquito/WsprEncoded test/unit/TestWsprChannelMap.cpp),
# confirmed by hand against this port before it was trusted. -----------------

_KNOWN_VECTORS = [
    # band, channel -> id1, id3, minute, freq
    ("20m", 0, "0", "0", 8, 14_097_020),
    ("20m", 226, "1", "1", 0, 14_097_060),
    ("20m", 452, "Q", "2", 2, 14_097_140),
]


def selfcheck():
    for band, channel, want_id1, want_id3, want_minute, want_freq in _KNOWN_VECTORS:
        got = channel_details(band, channel)
        if (got["id1"], got["id3"], got["minute"], got["freq"]) != (want_id1, want_id3, want_minute, want_freq):
            raise AssertionError(
                f"self-check failed for {band} channel {channel}: got {got}, "
                f"want id1={want_id1} id3={want_id3} minute={want_minute} freq={want_freq}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Look up a U4B WSPR channel number and print the derived "
                     "id1/id3/start-minute/frequency, ready to paste into "
                     "LightAPRS-W-2-pico-balloon.ino."
    )
    parser.add_argument("--channel", type=int, help="Channel number, 0-599 (see https://traquito.github.io/channelmap/)")
    parser.add_argument("--band", default="20m", help="Band name, e.g. 20m (default: 20m -- the only band this firmware currently supports)")
    parser.add_argument("--list-bands", action="store_true", help="List supported band names and exit")
    args = parser.parse_args()

    if args.list_bands:
        for b in BAND_NAMES:
            note = "" if b in FIRMWARE_SUPPORTED_BANDS else "  (not wired up in the current .ino)"
            print(f"{b}{note}")
        return 0

    if args.channel is None:
        parser.error("--channel is required (or pass --list-bands)")

    try:
        selfcheck()
    except AssertionError as e:
        print(f"REFUSING TO ANSWER -- internal self-check failed: {e}", file=sys.stderr)
        return 1

    try:
        details = channel_details(args.band, args.channel)
    except ValueError as e:
        parser.error(str(e))
        return 2

    if details["band"] not in FIRMWARE_SUPPORTED_BANDS:
        print(f"NOTE: {details['band']} is not currently wired up in "
              f"LightAPRS-W-2-pico-balloon.ino (only 20m is). These values "
              f"are still correct for that band, but the firmware needs "
              f"changes to actually transmit on it.\n", file=sys.stderr)

    print(f"Channel {details['channel']} on {details['band']}:")
    print(f"  id1        = {details['id1']!r}")
    print(f"  id3        = {details['id3']!r}")
    print(f"  id13       = \"{details['id13']}\"")
    print(f"  minute     = {details['minute']}  (Regular msg starts here; Basic Telemetry follows +2 min)")
    print(f"  lane       = {details['lane']} of 4")
    print(f"  freq       = {details['freq']} Hz  (dial {details['freq_dial']} Hz + audio offset)")
    print()
    print("Paste into LightAPRS-W-2-pico-balloon.ino's U4B protocol channel identity block:")
    print(f"  #define U4B_ID1            '{details['id1']}'")
    print(f"  #define U4B_ID3            '{details['id3']}'")
    print(f"  #define WSPR_START_MINUTE  {details['minute']}")
    print(f"  #define WSPR_LANE_FREQ     {details['freq']}UL")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
