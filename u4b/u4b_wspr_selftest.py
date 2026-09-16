#!/usr/bin/env python3
"""Validate the U4B WSPR telemetry mixed-radix packing math before it's
transcribed into LightAPRS-W-2-pico-balloon.ino.

Two independent checks:
  1. Basic Telemetry encode, against 3 known-good test vectors from the
     reference implementation's own unit tests (traquito/WsprEncoded,
     TestWsprMessageTelemetryBasic.cpp).
  2. Extended Telemetry header encode (no data fields yet), against a
     hand-derivable all-zero base case plus a round-trip decode check
     across every (hdrSlot, hdrType) combination -- there is no published
     external vector for a zero-data-field Extended message, so self
     round-trip is the available check.

Run: python3 ci/u4b_wspr_selftest.py
Exits non-zero on any mismatch.
"""

VALID_DBM = (0, 3, 7, 10, 13, 17, 20, 23, 27, 30, 33, 37, 40, 43, 47, 50, 53, 57, 60)


# ---- clamp / quantize helpers (mirror u4b*ToStep() in the .ino) -----------

def alt_to_step(meters):
    meters = max(0.0, min(21340.0, meters))
    return int(meters / 20.0 + 0.5)


def temp_to_step(celsius):
    celsius = max(-50.0, min(39.0, celsius))
    return int(celsius - (-50))


def volt_to_step(volts):
    volts = max(3.00, min(4.95, volts))
    quantized = int((volts - 3.0) / 0.05 + 0.5)
    return (quantized + 20) % 40  # reference impl rotates by 20 out of 40 -- self-inverse


def speed_to_step(knots):
    knots = max(0.0, min(82.0, knots))
    return int(knots / 2.0 + 0.5)


# ---- Basic Telemetry (mirrors u4bEncodeCallsign / u4bEncodeGridPower) -----

def u4b_encode_callsign(id1, id3, grid5_val, grid6_val, alt_frac_m):
    val = 0
    val = val * 24 + grid5_val
    val = val * 24 + grid6_val
    val = val * 1068 + alt_frac_m

    id6_val = val % 26; val //= 26
    id5_val = val % 26; val //= 26
    id4_val = val % 26; val //= 26
    id2_val = val % 36

    id2 = str(id2_val) if id2_val < 10 else chr(ord('A') + id2_val - 10)
    return id1 + id2 + id3 + chr(ord('A') + id4_val) + chr(ord('A') + id5_val) + chr(ord('A') + id6_val)


def u4b_encode_grid_power(temp_c_num, voltage_num, speed_knots_num, gps_valid_num):
    val = 0
    val = val * 90 + temp_c_num
    val = val * 40 + voltage_num
    val = val * 42 + speed_knots_num
    val = val * 2 + gps_valid_num
    val = val * 2 + 1  # fixed "basic telemetry" marker bit

    power_val = val % 19; val //= 19
    g4_val = val % 10; val //= 10
    g3_val = val % 10; val //= 10
    g2_val = val % 18; val //= 18
    g1_val = val % 18

    grid = chr(ord('A') + g1_val) + chr(ord('A') + g2_val) + str(g3_val) + str(g4_val)
    return grid, VALID_DBM[power_val]


# ---- Extended Telemetry header (mirrors u4bEncodeExtendedHeader) ---------

def u4b_encode_extended_header(id1, id3, hdr_type, hdr_slot):
    val = 0
    val = val * 5 + hdr_slot
    val = val * 16 + hdr_type
    val = val * 4 + 0   # HdrRESERVED
    val = val * 2 + 0   # HdrTelemetryType = 0 -> Extended

    power_val = val % 19; val //= 19
    g4_val = val % 10; val //= 10
    g3_val = val % 10; val //= 10
    g2_val = val % 18; val //= 18
    g1_val = val % 18; val //= 18
    id6_val = val % 26; val //= 26
    id5_val = val % 26; val //= 26
    id4_val = val % 26; val //= 26
    id2_val = val % 36

    id2 = str(id2_val) if id2_val < 10 else chr(ord('A') + id2_val - 10)
    call = id1 + id2 + id3 + chr(ord('A') + id4_val) + chr(ord('A') + id5_val) + chr(ord('A') + id6_val)
    grid = chr(ord('A') + g1_val) + chr(ord('A') + g2_val) + str(g3_val) + str(g4_val)
    return call, grid, VALID_DBM[power_val]


def u4b_decode_extended_header(call, grid, dbm):
    """Inverse of u4b_encode_extended_header -- self-test only, not needed on-device."""
    id2_val = int(call[1]) if call[1].isdigit() else (ord(call[1]) - ord('A') + 10)
    id4_val = ord(call[3]) - ord('A')
    id5_val = ord(call[4]) - ord('A')
    id6_val = ord(call[5]) - ord('A')
    g1_val = ord(grid[0]) - ord('A')
    g2_val = ord(grid[1]) - ord('A')
    g3_val = int(grid[2])
    g4_val = int(grid[3])
    power_val = VALID_DBM.index(dbm)

    val = id2_val
    val = val * 26 + id4_val
    val = val * 26 + id5_val
    val = val * 26 + id6_val
    val = val * 18 + g1_val
    val = val * 18 + g2_val
    val = val * 10 + g3_val
    val = val * 10 + g4_val
    val = val * 19 + power_val

    telemetry_type = val % 2; val //= 2
    reserved = val % 4; val //= 4
    hdr_type = val % 16; val //= 16
    hdr_slot = val % 5

    return hdr_slot, hdr_type, reserved, telemetry_type


def check(label, got, want):
    status = "ok" if got == want else "FAIL"
    print(f"[{status}] {label}: got={got!r} want={want!r}")
    return got == want


def main():
    ok = True

    # ---- Basic Telemetry: 3 verified test vectors ----
    vectors = [
        # id1, id3, grid5, grid6, alt_m, temp_c, volt, speed_kt, gps_valid, want_call, want_grid, want_dbm
        ('1', '4', 'X', 'R', 1000, -12, 4.95, 0, True, '1Y4PAS', 'HK08', 10),
        ('Q', '7', 'W', 'R', 3000, 0, 3.18, 10, False, 'QX7DGS', 'JQ97', 33),
        ('0', '2', 'W', 'S', 7000, 13, 3.00, 60, True, '0X2FDM', 'MI65', 27),
    ]
    for id1, id3, g5, g6, alt_m, temp_c, volt, speed_kt, gps_valid, want_call, want_grid, want_dbm in vectors:
        alt_step = alt_to_step(alt_m)
        temp_step = temp_to_step(temp_c)
        volt_step = volt_to_step(volt)
        speed_step = speed_to_step(speed_kt)
        gps_step = 1 if gps_valid else 0

        call = u4b_encode_callsign(id1, id3, ord(g5) - ord('A'), ord(g6) - ord('A'), alt_step)
        grid, dbm = u4b_encode_grid_power(temp_step, volt_step, speed_step, gps_step)

        label = f"basic id13={id1}{id3} grid56={g5}{g6} alt={alt_m}m"
        ok &= check(f"{label} callsign", call, want_call)
        ok &= check(f"{label} grid", grid, want_grid)
        ok &= check(f"{label} dbm", dbm, want_dbm)

    # ---- Extended Telemetry header: hand-derivable all-zero base case ----
    call, grid, dbm = u4b_encode_extended_header('0', '0', 0, 0)
    ok &= check("extended base case callsign", call, "000AAA")
    ok &= check("extended base case grid", grid, "AA00")
    ok &= check("extended base case dbm", dbm, 0)

    # ---- Extended Telemetry header: round-trip over every (slot, type) ----
    mismatches = 0
    for hdr_slot in range(5):
        for hdr_type in range(16):
            call, grid, dbm = u4b_encode_extended_header('0', '0', hdr_type, hdr_slot)
            got_slot, got_type, got_reserved, got_ttype = u4b_decode_extended_header(call, grid, dbm)
            if (got_slot, got_type, got_reserved, got_ttype) != (hdr_slot, hdr_type, 0, 0):
                mismatches += 1
                print(f"[FAIL] round-trip slot={hdr_slot} type={hdr_type} -> "
                      f"decoded slot={got_slot} type={got_type} reserved={got_reserved} ttype={got_ttype}")
    ok &= check("extended round-trip (80 combinations)", mismatches, 0)

    print()
    print("ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
