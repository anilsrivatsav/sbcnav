from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests


def get_data(session: requests.Session, url: str, **params) -> dict:
    response = session.get(url, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if payload.get("success") is not True or not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"Invalid API response from {response.url}")
    return payload["data"]


def build_pack(api_url: str) -> dict:
    base = api_url.rstrip("/")
    with requests.Session() as session:
        bootstrap = get_data(session, f"{base}/api/mobile/v1/bootstrap")
        works = bootstrap.get("all_works")
        if not isinstance(works, list) or not works:
            raise RuntimeError("Mobile bootstrap did not include sanctioned works")

        details = []
        offset = 0
        total = None
        while total is None or offset < total:
            page = get_data(
                session,
                f"{base}/api/mobile/v1/offline/station-details",
                offset=offset,
                limit=25,
            )
            items = page.get("items")
            if not isinstance(items, list):
                raise RuntimeError("Station detail page did not contain an item list")
            details.extend(items)
            total = int(page.get("total") or 0)
            next_offset = int(page.get("next_offset") or offset)
            if page.get("has_more") and next_offset <= offset:
                raise RuntimeError("Station detail pagination did not advance")
            offset = next_offset
            if not page.get("has_more"):
                break

    if len(details) != total:
        raise RuntimeError(
            f"Offline station details are incomplete: {len(details)} of {total}"
        )
    totals = bootstrap.get("portfolio_totals") or {}
    if int(totals.get("works") or 0) != len(works):
        raise RuntimeError("Portfolio work total does not match the works payload")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **bootstrap,
        "station_details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Flutter offline station pack from PostgreSQL-backed APIs."
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    pack = build_pack(args.api_url)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(pack, ensure_ascii=True, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
    print(
        json.dumps(
            {
                "output": str(output),
                "stations": len(pack.get("stations", [])),
                "works": len(pack.get("all_works", [])),
                "station_details": len(pack.get("station_details", [])),
            }
        )
    )


if __name__ == "__main__":
    main()
