USE ROLE ACCOUNTADMIN;

---------------------------------------------------------------------
-- Create Datawarehouses for the development and quering of the app
---------------------------------------------------------------------

CREATE WAREHOUSE IF NOT EXISTS AIRBNB_DEV_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Small development warehouse for Airbnb investment project';

CREATE WAREHOUSE IF NOT EXISTS AIRBNB_APP_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Small querying warehouse for Airbnb investment project';

------------------------------------------------------------------------
-- 1. Create database following Medallion architecture
---------------------------------------------------------------------=--
CREATE DATABASE IF NOT EXISTS AIRBNB_INVESTMENT_DB;

-- 2. Use the database
USE DATABASE AIRBNB_INVESTMENT_DB;

-- 3. Create schemas for each data layer
CREATE SCHEMA IF NOT EXISTS BRONZE;
CREATE SCHEMA IF NOT EXISTS SILVER;
CREATE SCHEMA IF NOT EXISTS GOLD;