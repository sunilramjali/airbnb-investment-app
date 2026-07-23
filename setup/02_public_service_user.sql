-- Creates the read-only key-pair service user, role, and GOLD grants for the public Streamlit (Community Cloud) deployment.
-- Co-authored with CoCo
--
-- Run as ACCOUNTADMIN (or a role that can create users/roles and grant on AIRBNB_INVESTMENT_DB).
-- The RSA_PUBLIC_KEY below is the PUBLIC half of the key pair — safe to commit.
-- The matching PRIVATE key (deploy_secrets/rsa_key.p8) is git-ignored and goes ONLY into
-- the Streamlit Community Cloud "Secrets" panel, never into git.

USE ROLE ACCOUNTADMIN;

-- 1. Read-only role -----------------------------------------------------------
CREATE ROLE IF NOT EXISTS AIRBNB_APP_PUBLIC_ROLE
  COMMENT = 'Read-only role for the public Airbnb Streamlit app (Community Cloud). SELECT on GOLD only.';

-- 2. Service user (key-pair auth, no password) --------------------------------
CREATE USER IF NOT EXISTS AIRBNB_APP_SVC
  TYPE = SERVICE
  RSA_PUBLIC_KEY = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3zuG/mzp6E10Bon5swIq1g28mP/hRgG2VCi7Jh1ocOOLAG9346a9wXO9SBYWMHCJLB852SE/DQ0VCXUQYmKPGs/WMCbo3+mCEsiPUiLWpLiGiLhpD+Ws3UOEpi6o3ZPzoKAzwqzrMEmlwOkfrgibCMjLW3R2eSP/wSu1ePowbX49+kAB9uxeCipe6vOd5r6rHOm/5X/ehEuJLeZc/b+YXAaiWUnvbISKva2DS1Hi/unS/qO4cjQ3AZMxXy66QNDsaNe0/9GLCuS21xa+4l+Y/Uj96IH7QGBs4K/SM77HEB34ZWwv2tK3eQrfHRkO8p47CroAXcHIldAoEThKIv+w3QIDAQAB'
  DEFAULT_ROLE = AIRBNB_APP_PUBLIC_ROLE
  DEFAULT_WAREHOUSE = AIRBNB_APP_WH
  DEFAULT_NAMESPACE = 'AIRBNB_INVESTMENT_DB.GOLD'
  COMMENT = 'Service user for the public Airbnb Streamlit app on Community Cloud. Key-pair auth, read-only.';

-- 3. Read-only grants ---------------------------------------------------------
GRANT USAGE ON WAREHOUSE AIRBNB_APP_WH TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT USAGE ON DATABASE AIRBNB_INVESTMENT_DB TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT USAGE ON SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;

-- The GOLD marts are dynamic tables; DIM_DATE is a base table. Grant all object
-- classes now, and FUTURE grants so teammate-added objects (e.g. INVESTMENT_SCORES,
-- AI_OUTPUTS) are readable automatically without re-granting.
GRANT SELECT ON ALL TABLES         IN SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT SELECT ON ALL VIEWS          IN SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT SELECT ON ALL DYNAMIC TABLES IN SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT SELECT ON FUTURE TABLES         IN SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT SELECT ON FUTURE VIEWS          IN SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;
GRANT SELECT ON FUTURE DYNAMIC TABLES IN SCHEMA AIRBNB_INVESTMENT_DB.GOLD TO ROLE AIRBNB_APP_PUBLIC_ROLE;

-- 3b. AI cache write exception -------------------------------------------------
-- The role is otherwise read-only, but the ST vs LT AI comparison persists its
-- generated narratives to this table so future sessions reuse them instead of
-- re-calling Gemini. That requires INSERT on this one table.
GRANT INSERT ON TABLE AIRBNB_INVESTMENT_DB.GOLD.ST_VS_LT_COMPARISON_CACHE TO ROLE AIRBNB_APP_PUBLIC_ROLE;

-- 4. Bind role to the service user --------------------------------------------
GRANT ROLE AIRBNB_APP_PUBLIC_ROLE TO USER AIRBNB_APP_SVC;

-- 5. Verify -------------------------------------------------------------------
SHOW GRANTS TO ROLE AIRBNB_APP_PUBLIC_ROLE;

-- To rotate the key later:
--   ALTER USER AIRBNB_APP_SVC SET RSA_PUBLIC_KEY = '<new public key body>';
-- To disable access immediately:
--   ALTER USER AIRBNB_APP_SVC SET DISABLED = TRUE;
