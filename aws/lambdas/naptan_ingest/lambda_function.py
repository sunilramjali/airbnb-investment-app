"""NaPTAN -> S3 ingestion Lambda.

Downloads the DfT NaPTAN national access-nodes export (CSV) and lands it in the
project's raw S3 bucket under a dated snapshot prefix, mirroring the Land Registry
(`land_registry_ppd`) ingestion pattern.

Landing layout:
    s3://<BUCKET>/<PREFIX>/snapshot_date=<YYYY-MM-DD>/naptan.csv

The whole national file is landed as-is (faithful bronze); scoping to the
project's cities happens later in Snowflake (Bronze -> Silver via ST_WITHIN).
Re-running on the same day overwrites that day's object, so it is idempotent.

Source: https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv
License: Open Government Licence v3.0.

Environment variables:
    BUCKET       (required)  target S3 bucket name
    PREFIX       (optional)  key prefix, default "raw/naptan"
    NAPTAN_URL   (optional)  override the DfT export URL
"""

import os
import urllib.request
from datetime import date, timezone, datetime

import boto3

NAPTAN_URL_DEFAULT = "https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv"

# 5 min connect/read timeout — the national CSV is ~150 MB and can be slow.
HTTP_TIMEOUT_SECONDS = 300

s3 = boto3.client("s3")


def _target_key(prefix: str, snapshot: str) -> str:
    """Dated snapshot key, e.g. raw/naptan/snapshot_date=2026-07-01/naptan.csv."""
    return f"{prefix.rstrip('/')}/snapshot_date={snapshot}/naptan.csv"


def handler(event, context):
    bucket = os.environ["BUCKET"]                      # fail fast if unset
    prefix = os.environ.get("PREFIX", "raw/naptan")
    url = os.environ.get("NAPTAN_URL", NAPTAN_URL_DEFAULT)

    snapshot = date.today().isoformat()
    key = _target_key(prefix, snapshot)

    # Stream the DfT export into memory, then put to S3. The national file is
    # large but comfortably within Lambda's /tmp-free in-memory budget when the
    # function is given >=512 MB; bump memory in the deploy if needed.
    req = urllib.request.Request(url, headers={"User-Agent": "airbnb-investment-app/naptan-ingest"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
        if resp.status != 200:
            raise RuntimeError(f"NaPTAN download failed: HTTP {resp.status}")
        body = resp.read()

    if not body:
        raise RuntimeError("NaPTAN download returned an empty body")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="text/csv",
        Metadata={
            "source": url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    result = {
        "bucket": bucket,
        "key": key,
        "bytes": len(body),
        "snapshot_date": snapshot,
    }
    print(f"Landed NaPTAN snapshot: {result}")
    return result


# Local smoke test: BUCKET=... python lambda_function.py
if __name__ == "__main__":
    print(handler({}, None))
