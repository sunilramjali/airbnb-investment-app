-- Sets up secure external access to the Gemini API for the Streamlit app: network rule, secret, EAI, and app binding.
-- Co-authored with CoCo
--
-- Run this as ACCOUNTADMIN (or a role owning AIRBNB_INVESTMENT_DB.GOLD and able to
-- create integrations). Paste your real Gemini API key where indicated below.
-- Objects use CREATE OR REPLACE so the script is safe to re-run.

USE ROLE ACCOUNTADMIN;
USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- 1. Egress network rule: allow outbound HTTPS to the Gemini API host only.
CREATE OR REPLACE NETWORK RULE AIRBNB_INVESTMENT_DB.GOLD.GEMINI_EGRESS_RULE
    MODE = EGRESS
    TYPE = HOST_PORT
    VALUE_LIST = ('generativelanguage.googleapis.com');

-- 2. Secret holding the Gemini API key.
--    Replace <PASTE_YOUR_GEMINI_API_KEY> with your real key before running.
CREATE OR REPLACE SECRET AIRBNB_INVESTMENT_DB.GOLD.GEMINI_API_KEY
    TYPE = GENERIC_STRING
    SECRET_STRING = '<PASTE_YOUR_GEMINI_API_KEY>';

-- 3. (Optional) Secret to override the Gemini model name at runtime.
--    Leave commented to use the app default (gemini-3.1-flash-lite).
-- CREATE OR REPLACE SECRET AIRBNB_INVESTMENT_DB.GOLD.GEMINI_MODEL
--     TYPE = GENERIC_STRING
--     SECRET_STRING = 'gemini-3.1-flash';

-- 4. External Access Integration binding the network rule and the secret.
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION AIRBNB_GEMINI_EAI
    ALLOWED_NETWORK_RULES = (AIRBNB_INVESTMENT_DB.GOLD.GEMINI_EGRESS_RULE)
    ALLOWED_AUTHENTICATION_SECRETS = (AIRBNB_INVESTMENT_DB.GOLD.GEMINI_API_KEY)
    ENABLED = TRUE;

-- 5. Attach the EAI and secret(s) to the Streamlit app.
--    The left-hand names ('gemini_api_key', 'gemini_model') are how the app
--    code reads them via st.secrets in the container runtime.
ALTER STREAMLIT AIRBNB_INVESTMENT_DB.GOLD.AIRBNB_APP
    SET EXTERNAL_ACCESS_INTEGRATIONS = (AIRBNB_GEMINI_EAI)
        SECRETS = ('gemini_api_key' = AIRBNB_INVESTMENT_DB.GOLD.GEMINI_API_KEY);
        -- To also expose the model override, add it to the SECRETS list above:
        -- SECRETS = ('gemini_api_key' = AIRBNB_INVESTMENT_DB.GOLD.GEMINI_API_KEY,
        --            'gemini_model'   = AIRBNB_INVESTMENT_DB.GOLD.GEMINI_MODEL);

-- Grants (only needed if a non-owner role runs/owns the app; ACCOUNTADMIN owns
-- these objects here, so these are informational):
-- GRANT USAGE ON INTEGRATION AIRBNB_GEMINI_EAI TO ROLE <app_owner_role>;
-- GRANT READ  ON SECRET AIRBNB_INVESTMENT_DB.GOLD.GEMINI_API_KEY TO ROLE <app_owner_role>;
