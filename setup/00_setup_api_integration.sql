USE ROLE ACCOUNTADMIN;

-- Set up API integration for all users
CREATE OR REPLACE API INTEGRATION github_oauth_integration
  API_PROVIDER = git_https_api
  API_ALLOWED_PREFIXES = ('https://github.com/sunilramjali')
  API_USER_AUTHENTICATION = (TYPE = SNOWFLAKE_GITHUB_APP)
  ENABLED = TRUE;

GRANT USAGE ON INTEGRATION github_oauth_integration TO ROLE PUBLIC;