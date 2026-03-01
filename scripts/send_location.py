#!/usr/bin/env python3
"""Send a location update to the Deep Trip extension via HTTP POST.

Usage:
    python scripts/send_location.py --location sensoji
    python scripts/send_location.py --lat 35.6812 --lng 139.7671
    python scripts/send_location.py --location shibuya --url http://localhost:8080/data
"""
import argparse
import json
import sys

import requests

TOKYO_LOCATIONS = {
    "sensoji": (35.7148, 139.7967),
    "shibuya": (35.6580, 139.7016),
    "meiji-jingu": (35.6764, 139.6993),
    "tokyo-tower": (35.6586, 139.7454),
    "tsukiji": (35.6654, 139.7707),
    "ueno": (35.7146, 139.7734),
    "akihabara": (35.7023, 139.7745),
    "tokyo-station": (35.6812, 139.7671),
}

DEFAULT_URL = "http://localhost:8080/data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send location update to Deep Trip")
    parser.add_argument(
        "--location", "-l",
        choices=list(TOKYO_LOCATIONS.keys()),
        help="Pre-defined Tokyo location name",
    )
    parser.add_argument("--lat", type=float, help="Latitude (custom)")
    parser.add_argument("--lng", type=float, help="Longitude (custom)")
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Server endpoint URL (default: {DEFAULT_URL})",
    )
    args = parser.parse_args()

    if args.location:
        lat, lng = TOKYO_LOCATIONS[args.location]
        label = args.location
    elif args.lat is not None and args.lng is not None:
        lat, lng = args.lat, args.lng
        label = f"({lat}, {lng})"
    else:
        parser.error("Provide --location or both --lat and --lng")
        return

    payload = {"cmd": "update_location", "lat": lat, "lng": lng}
    print(f"Sending location '{label}': lat={lat}, lng={lng}")
    print(f"POST {args.url}")

    try:
        resp = requests.post(
            args.url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        print(f"Response: {resp.status_code} {resp.text}")
    except requests.ConnectionError:
        print(f"ERROR: Could not connect to {args.url}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
