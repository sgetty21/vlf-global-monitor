#!/usr/bin/env python3
"""Discover public Open VLF objects in the CRAAM S3 archive.

This is a read-only source-discovery step. It does not download or alter data.
The archive prefix is configurable because the exact key layout must be
verified before building the ingestion adapter.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BUCKET_URL = "https://craam-files-bucket.s3.sa-east-1.amazonaws.com/"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def list_objects(prefix: str, max_pages: int = 100) -> list[dict]:
    objects = []
    token = None

    for _ in range(max_pages):
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        url = BUCKET_URL + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url, headers={"User-Agent": "vlf-global-monitor-archive-discovery/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                root = ET.fromstring(response.read())
        except (urllib.error.URLError, ET.ParseError, TimeoutError) as exc:
            raise RuntimeError(f"Could not list public S3 objects: {exc}") from exc

        for item in root.findall("s3:Contents", NS):
            key = item.findtext("s3:Key", default="", namespaces=NS)
            size = item.findtext("s3:Size", default="0", namespaces=NS)
            modified = item.findtext("s3:LastModified", default="", namespaces=NS)
            etag = item.findtext("s3:ETag", default="", namespaces=NS)
            objects.append({
                "key": key,
                "size_bytes": int(size),
                "last_modified": modified,
                "etag": etag.strip('"'),
            })

        truncated = root.findtext("s3:IsTruncated", default="false", namespaces=NS)
        if truncated.lower() != "true":
            break
        token = root.findtext("s3:NextContinuationToken", default="", namespaces=NS)
        if not token:
            raise RuntimeError("S3 indicated more results but supplied no continuation token.")
    else:
        raise RuntimeError(
            f"Stopped after {max_pages} pages. Narrow the prefix to continue safely."
        )

    return objects


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prefix", default="2015/10/22/narrowband/",
        help="S3 key prefix to inspect (default: Patricia reference date/path).",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/archive_inventory.json"),
        help="JSON inventory output path.",
    )
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()

    try:
        objects = list_objects(args.prefix, args.max_pages)
        result = {
            "source": "CRAAM Open VLF public S3 bucket",
            "bucket": "craam-files-bucket",
            "region": "sa-east-1",
            "prefix_checked": args.prefix,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "object_count": len(objects),
            "total_size_bytes": sum(item["size_bytes"] for item in objects),
            "objects": objects,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Found {len(objects)} objects under s3://craam-files-bucket/{args.prefix}")
        print(f"Inventory written to {args.output}")
        if not objects:
            print("No objects matched. Verify the prefix before configuring ingestion.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
