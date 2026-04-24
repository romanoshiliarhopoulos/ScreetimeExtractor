"""
Extract screen time sessions from the macOS Biome database.

Reads binary App.InFocus records from:
  ~/Library/Biome/streams/restricted/App.InFocus/remote/<device-uuid>/

Writes a CSV with columns: app, start_time, end_time, duration_seconds
"""

import struct
import os
import re
import csv
import datetime
import sys

BIOME_BASE = os.path.expanduser("~/Library/Biome/streams/restricted/App.InFocus")
DEFAULT_OUTPUT = "screentime.csv"

IOS_MARKERS = [
    b"com.apple.SpringBoard",
    b"com.apple.mobileslideshow",
    b"com.burbn.instagram",
    b"com.toyopagroup.picaboo",
    b"com.apple.MobileSMS",
]

UNIX_OFFSET = 978307200  # Mac absolute time -> Unix epoch


def is_ios_device(device_dir: str) -> bool:
    files = [f for f in os.listdir(device_dir) if f != "tombstone"]
    for fname in files:
        with open(os.path.join(device_dir, fname), "rb") as f:
            data = f.read()
        for marker in IOS_MARKERS:
            if marker in data:
                return True
    return False


def parse_entries(data: bytes) -> list:
    pattern = re.compile(b"\x21(.{8})\x32([\x01-\x7f])")
    entries = []

    for m in pattern.finditer(data):
        ts_bytes = m.group(1)
        length = m.group(2)[0]
        ts = struct.unpack_from("<d", ts_bytes)[0]

        if not (600_000_000 < ts < 820_000_000):
            continue

        bundle_start = m.end()
        bundle_id = data[bundle_start: bundle_start + length]
        try:
            bundle_id = bundle_id.decode("utf-8")
        except UnicodeDecodeError:
            continue

        if not bundle_id.startswith(("com.", "net.", "org.", "io.")):
            continue

        dt = datetime.datetime.fromtimestamp(ts + UNIX_OFFSET)
        entries.append((ts, dt, bundle_id))

    return entries


def pair_entries(entries: list) -> list:
    SKIP = {
        "com.apple.SpringBoard",
        "com.apple.springboard.lock-screen",
        "com.apple.springboard.today-view",
    }
    filtered = [
        (ts, dt, bid)
        for ts, dt, bid in entries
        if bid not in SKIP and "springboard" not in bid.lower()
    ]

    sessions = []
    i = 0
    while i + 1 < len(filtered):
        ts1, dt1, bid1 = filtered[i]
        ts2, dt2, bid2 = filtered[i + 1]
        if bid1 == bid2:
            duration = ts2 - ts1
            if 0 < duration < 86400:
                sessions.append({
                    "app": bid1,
                    "start_time": dt1.isoformat(),
                    "end_time": dt2.isoformat(),
                    "duration_seconds": round(duration, 2),
                })
            i += 2
        else:
            i += 1

    return sessions


def extract(output: str = DEFAULT_OUTPUT, verbose: bool = True) -> int:
    """
    Extract sessions from Biome and write to CSV.
    Returns the number of sessions written.
    """
    remote_dir = os.path.join(BIOME_BASE, "remote")
    if not os.path.isdir(remote_dir):
        raise FileNotFoundError(
            f"Biome directory not found: {remote_dir}\n"
            "Make sure you are on a Mac with an iPhone synced via iCloud / Screen Time sharing."
        )

    all_sessions = []

    for device_uuid in os.listdir(remote_dir):
        device_path = os.path.join(remote_dir, device_uuid)
        if not os.path.isdir(device_path):
            continue
        if not is_ios_device(device_path):
            if verbose:
                print(f"Skipping non-iOS device: {device_uuid}")
            continue

        if verbose:
            print(f"Processing iPhone device: {device_uuid}")
        files = sorted([f for f in os.listdir(device_path) if f != "tombstone"])

        all_entries = []
        for fname in files:
            fpath = os.path.join(device_path, fname)
            with open(fpath, "rb") as f:
                data = f.read()
            entries = parse_entries(data)
            if verbose:
                print(f"  {fname}: {len(entries)} raw entries")
            all_entries.extend(entries)

        all_entries.sort(key=lambda x: x[0])
        sessions = pair_entries(all_entries)
        if verbose:
            print(f"  -> {len(sessions)} sessions extracted")
        all_sessions.extend(sessions)

    if not all_sessions:
        raise ValueError("No sessions found in Biome database.")

    # Load existing CSV and merge — so each extract run accumulates history
    existing_sessions = []
    if os.path.isfile(output):
        with open(output, newline="") as f:
            existing_sessions = list(csv.DictReader(f))
        if verbose:
            print(f"\nMerging with {len(existing_sessions)} existing sessions in {output}")

    combined = existing_sessions + all_sessions
    combined.sort(key=lambda x: x["start_time"])
    seen: set = set()
    unique_sessions = []
    for s in combined:
        key = (s["app"], s["start_time"])
        if key not in seen:
            seen.add(key)
            unique_sessions.append(s)

    new_count = len(unique_sessions) - len(existing_sessions)

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["app", "start_time", "end_time", "duration_seconds"]
        )
        writer.writeheader()
        writer.writerows(unique_sessions)

    if verbose:
        print(f"\nDone. {len(unique_sessions)} total sessions in {output} "
              f"(+{new_count} new)")
        from collections import defaultdict
        totals: dict = defaultdict(float)
        for s in unique_sessions:
            totals[s["app"]] += float(s["duration_seconds"])
        top = sorted(totals.items(), key=lambda x: -x[1])[:10]
        print("\nTop 10 apps by total time:")
        for app, secs in top:
            print(f"  {app}: {secs/3600:.2f}h")

    return len(unique_sessions)
