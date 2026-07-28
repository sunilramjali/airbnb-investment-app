# Databricks setup — S3 access for Bronze

Databricks equivalent of the Snowflake `STORAGE INTEGRATION` handshake documented at
`etl/ingestion_layer/01_bronze_ddl.sql:71-86`.

**The existing IAM role `snowflake-airbnb-s3-read` cannot be reused** — its trust policy names
Snowflake's IAM principal. Databricks needs its own role.

## Values (captured 2026-07-27, metastore `2013dd5c-9b50-4e38-b3bf-65790d6fe43e`)

| | |
|---|---|
| Unity Catalog principal | `arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL` |
| External ID | `d781b099-9a6d-4198-b415-98183d94803d` |
| New role name | `databricks-airbnb-s3-read` |
| AWS account | `988261629236` |
| Bucket | `airbnb-investment-app-988261629236-eu-west-2-an` (eu-west-2) |
| Databricks region | **us-east-2** — cross-region, see note below |

⚠️ These came from a probe credential that has since been deleted. The external ID appears to be
per-metastore (it matches the metastore's managed-storage path segment), so it should be stable —
but **re-check both values against the real credential** after step 3 and update the trust policy
if they differ.

## Steps

### 1. Create the IAM role — use `iam_trust_policy_step1.json`
IAM → Roles → Create role → **Custom trust policy**, and paste **`iam_trust_policy_step1.json`**
(Unity Catalog principal only). Name the role exactly **`databricks-airbnb-s3-read`**.

> ⚠️ **Do not paste `iam_trust_policy.json` here.** It names the role itself as a principal, and
> AWS validates principal ARNs at creation time — referencing a role that does not exist yet is
> rejected (`MalformedPolicyDocument: Invalid principal in policy`). The self-reference can only
> be added *after* the role exists. That is what step 3 is for.

Attach an inline policy using **`iam_permission_policy.json`**. This grants read-only access to
`raw/*` only — the same least-privilege posture as the Snowflake role.

### 2. Add the self-reference — use `iam_trust_policy.json`
Now that the role exists, edit its trust relationship and paste the full
**`iam_trust_policy.json`** (both principals).

> **The self-reference is required, not a typo.** Unity Catalog assumes the role and then
> re-assumes it. Without the role trusting itself, credential validation in step 3 fails with an
> `AssumeRole` error even though the policy looks correct.

### 3. Create the storage credential and external locations
> Order matters: the role must already trust itself (step 2) before this validates.

```bash
databricks storage-credentials create --profile airbnb --json '{
  "name": "airbnb_s3_cred",
  "aws_iam_role": {"role_arn": "arn:aws:iam::988261629236:role/databricks-airbnb-s3-read"}
}'
```

#### ⚠️ ONE EXTERNAL LOCATION PER PREFIX — a single `raw/` location does not work

Snowflake used **one** storage integration (`STORAGE_ALLOWED_LOCATIONS = '.../raw/'`) serving
three stages. The obvious Databricks mirror — one external location at `raw/` — **fails
validation**, even though the IAM policy in `iam_permission_policy.json` grants `s3:GetObject`
on `raw/*` and `s3:ListBucket` with `s3:prefix IN ('raw/*','raw')`:

```
$ databricks external-locations update airbnb_raw \
    --url 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/' --force --profile airbnb
Error: AWS IAM role does not have READ permissions on url
       s3://airbnb-investment-app-988261629236-eu-west-2-an/raw. PERMISSION_DENIED
```

Locations at the **child** prefixes validate fine against that same credential. So create one
per prefix (all three share `airbnb_s3_cred`, so no extra AWS work is involved):

```bash
databricks external-locations create airbnb_raw \
  "s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/" \
  airbnb_s3_cred --read-only --profile airbnb

databricks external-locations create airbnb_raw_lr \
  "s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry/" \
  airbnb_s3_cred --read-only --profile airbnb

databricks external-locations create airbnb_raw_ons \
  "s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/ons/" \
  airbnb_s3_cred --read-only --profile airbnb
```

| Location | Prefix | Serves |
|---|---|---|
| `airbnb_raw` | `raw/inside_airbnb` | Airbnb snapshots (`02_bronze_load.py`) |
| `airbnb_raw_lr` | `raw/hm_land_registry` | Land Registry (`03`/`04`) |
| `airbnb_raw_ons` | `raw/ons` | ONS private rents (`07`/`08`) and ONSPD (`06`) |

`airbnb_raw`'s URL points at the `inside_airbnb/` prefix so loader paths still begin at the
city, matching the Snowflake `RAW_STAGE` layout exactly.

IAM propagation can take a minute or two — if validation fails immediately, retry before debugging.

### 4. Verify
```bash
databricks external-locations validate --profile airbnb --json '{"external_location_name":"airbnb_raw"}'
```
Then confirm the `snapshot_date=` folders are visible — this is the Databricks analogue of
`LIST @BRONZE.RAW_STAGE/london/` and the precondition for `latest_snapshot()` to port:
```sql
LIST 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/london/'
```

## ⚠️ Cross-region note

Databricks Free Edition placed this workspace in **us-east-2**; the bucket is in **eu-west-2**.
Region is not selectable on Free Edition, so this cannot be fixed from the Databricks side.

Consequences: every read pays AWS inter-region egress (~$0.02/GB, billed to account `988261629236`,
not Databricks) and carries transatlantic latency. At Inside Airbnb volumes — a few hundred MB per
city-snapshot — a full Bronze rebuild costs pennies, so this is a latency and tidiness concern more
than a cost one. It only becomes a real cost if something re-scans the bucket repeatedly.

**Alternative worth considering:** skip S3 and IAM entirely by uploading raw files into a Unity
Catalog **Volume** (`/Volumes/airbnb_investment/bronze/raw/`). No IAM role, no cross-region egress,
no external location. The cost is losing the quarterly Lambda's automatic delivery — you would
upload manually or script it. Reasonable for a learning migration; wrong if the Lambda pipeline is
part of what you're demonstrating.
