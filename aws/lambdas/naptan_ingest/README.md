# NaPTAN ingestion Lambda (`naptan_ingest`)

Monthly AWS Lambda that downloads the **DfT NaPTAN** national access-nodes export
and lands it in the project's raw S3 bucket, mirroring the `land_registry_ppd`
pattern. Snowflake reads it from there via the existing `AIRBNB_S3_INT` storage
integration.

- **Source:** `https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv` (~435k
  stops, WGS84 lat/long, `StopType`, `CommonName`, `ATCOCode`, …)
- **License:** Open Government Licence v3.0 — attribute:
  *"Contains public sector information licensed under the Open Government Licence v3.0."*
- **Lands to:**
  ```
  s3://<BUCKET>/<PREFIX>/snapshot_date=<YYYY-MM-DD>/naptan.csv
  ```
  The whole national file is landed as-is; scoping to the project's cities happens
  in Snowflake (Bronze → Silver via `ST_WITHIN` on the borough polygons).

## Configuration (environment variables)

| Var | Required | Default | Notes |
|---|---|---|---|
| `BUCKET` | yes | — | `airbnb-investment-app-988261629236-eu-west-2-an` |
| `PREFIX` | no | `raw/naptan` | key prefix under the bucket |
| `NAPTAN_URL` | no | DfT export URL | override for testing |

## Runtime settings

- **Runtime:** Python 3.12
- **Handler:** `lambda_function.handler`
- **Memory:** 512 MB (the national CSV is ~150 MB; raise if you hit memory limits)
- **Timeout:** 300 s (matches the in-code HTTP timeout)
- **Region:** `eu-west-2` (same region as the bucket)

## IAM (execution role)

The read side is already covered — `AIRBNB_S3_INT` / `snowflake-airbnb-s3-read`
grants Snowflake `GetObject`/`ListBucket` on `raw/*`. This Lambda only needs
**write** to the NaPTAN prefix:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "NaptanPutObject",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::airbnb-investment-app-988261629236-eu-west-2-an/raw/naptan/*"
    }
  ]
}
```
(plus the standard `AWSLambdaBasicExecutionRole` for CloudWatch logs).

## Deploy

```bash
cd aws/lambdas/naptan_ingest
zip function.zip lambda_function.py

aws lambda create-function \
  --function-name naptan_ingest \
  --runtime python3.12 \
  --handler lambda_function.handler \
  --timeout 300 --memory-size 512 \
  --role arn:aws:iam::988261629236:role/<naptan-ingest-exec-role> \
  --environment "Variables={BUCKET=airbnb-investment-app-988261629236-eu-west-2-an,PREFIX=raw/naptan}" \
  --zip-file fileb://function.zip \
  --region eu-west-2
```

`boto3` is provided by the Lambda runtime — no dependency packaging needed.

## Schedule (monthly, 03:00 UTC on the 1st)

```bash
aws scheduler create-schedule \
  --name naptan_ingest_monthly \
  --schedule-expression "cron(0 3 1 * ? *)" \
  --flexible-time-window "Mode=OFF" \
  --target '{"Arn":"arn:aws:lambda:eu-west-2:988261629236:function:naptan_ingest","RoleArn":"arn:aws:iam::988261629236:role/<scheduler-invoke-role>"}' \
  --region eu-west-2
```

NaPTAN changes slowly (stops/stations rarely move), so monthly captures new/closed
stops with negligible lag while keeping runs cheap. The Bronze loader always selects
the latest `snapshot_date=`, so re-runs are idempotent.

## Test

```bash
BUCKET=airbnb-investment-app-988261629236-eu-west-2-an python lambda_function.py
# then confirm the object landed:
aws s3 ls s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/naptan/ --recursive
```
