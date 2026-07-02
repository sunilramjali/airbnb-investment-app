CREATE OR REPLACE NETWORK RULE muscache_network_rule
    MODE = EGRESS
    TYPE = HOST_PORT
    VALUE_LIST = ('a0.muscache.com');

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION muscache_access_int
    ALLOWED_NETWORK_RULES = (muscache_network_rule)
    ENABLED = TRUE;

GRANT USAGE ON INTEGRATION muscache_access_int TO ROLE sysadmin;

ALTER STREAMLIT user$andrewlawrence22.public."airbnb-investment-app"
    SET EXTERNAL_ACCESS_INTEGRATIONS = (muscache_access_int);

SHOW STREAMLITS IN ACCOUNT;