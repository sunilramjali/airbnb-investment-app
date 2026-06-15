# Branches and File/Folder Naming Conventions

branches = hyphens
folders/files = underscores

Branch:
role/data-engineer/feature/data-ingestion

Folder:
setup/run_setup.py


----------------------------------------------------------



# Project Architecture Guide

This project follows a simple Medallion data pipeline structure based on the **Bronze → Silver → Gold** architecture.

The purpose of this structure is to keep the project organised, easy to understand, and easy for the team to collaborate on.

Current project structure:

```text
airbnb-investment-app/
├── CHEATSHEET.md
├── README.md
├── config/
│   ├── __init__.py/
│   ├── run_sql_file.py/
│   └── snowflake_context.py/
|── notebooks/
|   └── preprocessing_layer.ipynb
├── setup/
│   ├── run_setup.py/
│   ├── 00_setup_api_integration.sql/
│   └── 01_setup_database_and_warehouse.sql/
```

---

## What each folder is for

### `CHEATSHEET.md`

This file contains quick copy-and-paste commands for the team.

Use this file when you need commands for:

* setting up the project
* activating the virtual environment
* installing requirements
* running notebooks
* using Git
* pulling and pushing changes

The cheat sheet is for quick daily use.

---

### `README.md`

This is the main project guide.

It explains:

* what the project is about
* how the repository is structured
* how to set up the project
* how the data pipeline works
* how the team should collaborate

The README should be the first file a new team member reads.

---

## Data folder

The `data/` folder stores the datasets used and produced by the project.

This project uses three main data layers:

```text
data/
├── bronze/
├── silver/
└── gold/
```

---

## Bronze layer

```text
data/bronze/
```

The bronze layer stores the first official version of the data after loading it into the project.

This data is usually close to the original source, with only light changes such as:

* standardising column names
* adding ingestion dates
* converting files into a consistent format
* applying basic schema checks

Bronze data answers:

> What data did we receive from the original source?

Example files:

```text
data/bronze/airbnb_listings.csv
data/bronze/airbnb_reviews.csv
data/bronze/crime_data.csv
data/bronze/house_prices.csv
```

The bronze layer should not contain heavily cleaned or final analysis-ready data.

---

## Silver layer

```text
data/silver/
```

The silver layer stores cleaned and validated data.

This is where the main preprocessing work happens.

The silver layer may include:

* removed duplicates
* fixed missing values
* corrected data types
* cleaned date columns
* standardised area names
* cleaned location fields
* joined lookup tables
* created useful features

Silver data answers:

> Is the data clean and ready for analysis?

Example files:

```text
data/silver/listings_cleaned.csv
data/silver/reviews_cleaned.csv
data/silver/crime_cleaned.csv
data/silver/house_prices_cleaned.csv
```

The silver layer can be used for analysis, modelling, and enrichment.

---

## Gold layer

```text
data/gold/
```

The gold layer stores the final app-ready or dashboard-ready outputs.

This is the data that should be used by the final Airbnb Investment App or dashboard.

The gold layer may include:

* final joined datasets
* area-level summaries
* investment scores
* ranking tables
* final reporting CSV files
* app-ready datasets

Gold data answers:

> What data does the app need to show the user?

Example files:

```text
data/gold/app_ready_dataset.csv
data/gold/investment_scores.csv
data/gold/area_summary.csv
```

The app should mainly read from the gold layer, not from bronze or silver.

---

## Notebooks folder

```text
notebooks/
└── preprocessing_layer.ipynb
```

> **New to the project?** Read [docs/what_is_src.md](docs/what_is_src.md) for a beginner-friendly
> explanation of the `src/` folder and how it is used at each stage of the pipeline.

The `notebooks/` folder stores Jupyter notebooks used for data processing and analysis.

Currently, the project has one notebook:

```text
preprocessing_layer.ipynb
```

This notebook should contain the steps used to move data through the pipeline.

For example:

```text
bronze data → cleaning/preprocessing → silver data → aggregation/scoring → gold data
```

As the project grows, the team may split this into multiple notebooks:

```text
notebooks/
├── 01_ingestion_bronze.ipynb
├── 02_cleaning_silver.ipynb
├── 03_enrichment_silver.ipynb
└── 04_gold_export.ipynb
```

For now, keeping one `preprocessing_layer.ipynb` is fine if the project is still small.

---

## Recommended data flow

The project should follow this flow:

```text
Raw/source data
      ↓
Bronze layer
      ↓
Silver layer
      ↓
Gold layer
      ↓
App / dashboard / final analysis
```

In simple terms:

```text
bronze = original or lightly standardised data
silver = cleaned and validated data
gold = final app-ready data
```

---

## Team rule

Each team member should understand which layer they are working on before editing files.

A simple rule is:

```text
Do not overwrite bronze data.
Cleaned data goes into silver.
Final app-ready data goes into gold.
Temporary test files go into interim.
```

This keeps the project organised and prevents confusion when multiple people are working on the same repository.


------------------------------------------------------------------------------


# Airbnb Investment App - Repository Setup Guide

This repository is for the Airbnb Investment App project.

The purpose of this guide is to explain which files should be committed to GitHub and which files should be ignored using `.gitignore`.

## Why use `.gitignore`?

A `.gitignore` file tells Git which files and folders should **not** be uploaded to GitHub.

This is useful because some files are:

- temporary
- private
- too large
- automatically generated
- specific to your own laptop
- easy to recreate by running the code again

For this project, we should commit code, documentation, notebooks, and small reusable files. We should avoid committing private files, virtual environments, raw data, and temporary outputs.

---

## Python files and folders

### `__pycache__/`

Python automatically creates `__pycache__` folders when you run `.py` files.

These folders contain compiled versions of your Python code. They help Python run files slightly faster, but they are not needed in GitHub.

They can be safely ignored because Python will recreate them automatically.

```gitignore
__pycache__/
```

---

### `.venv/`

The `.venv` folder is your local Python virtual environment.

It contains installed packages such as:

- pandas
- numpy
- streamlit
- scikit-learn
- matplotlib

This folder can become very large and may only work properly on your own laptop.

Instead of uploading `.venv`, we should upload a `requirements.txt` file so other team members can recreate the environment.

Example:

```bash
pip install -r requirements.txt
```

Ignore:

```gitignore
.venv/
```

Commit instead:

```text
requirements.txt
```

---

### `.env`

The `.env` file is used to store private information such as:

- API keys
- passwords
- database URLs
- secret tokens

Example:

```env
OPENAI_API_KEY=your_api_key_here
DATABASE_PASSWORD=your_password_here
```

This should **never** be committed to GitHub, even if the repository is private.

Ignore:

```gitignore
.env
```

A safer option is to commit a template file called:

```text
.env.example
```

Example `.env.example`:

```env
OPENAI_API_KEY=add_your_key_here
DATABASE_URL=add_database_url_here
```

---

## Data files and folders

### `data/`

The `data/` folder should store original downloaded datasets.

Examples:

```text
data/bronze/airbnb_listings.csv
data/bronze/airbnb_reviews.csv
data/bronze/crime_data.csv
data/bronze/house_prices.csv
```

Raw data can be large and may not need to be stored in GitHub.

Instead, we should document where the data came from in:

```text
docs/data_sources.md
```

Ignore:

```gitignore
data/
```


---

### CSV files

CSV files are common data files.

Examples:

```text
airbnb_reviews.csv
crime_data.csv
final_output.csv
```

Be careful with ignoring all CSV files.

This rule ignores every CSV file in the repository:

```gitignore
*.csv
```

For this project, that may be too broad because we may want to commit a small sample CSV or final app-ready CSV.

A better approach is to only ignore CSV files in raw and interim folders:

```gitignore
data/raw/*.csv
data/interim/*.csv
```

This means raw and temporary CSV files are ignored, but useful sample files can still be committed elsewhere.

---

### Parquet files

Parquet is a data storage format often used for processed datasets.

Examples:

```text
crime_cleaned.parquet
reviews_processed.parquet
airbnb_features.parquet
```

Parquet files are often generated outputs and can be large.

A sensible rule is:

```gitignore
data/raw/*.parquet
data/interim/*.parquet
```

This ignores raw and temporary Parquet files while still allowing the team to commit small selected files if needed.



## Recommended project folders to commit

These folders should usually be committed to GitHub:

```text
notebooks/
src/
docs/
app/
tests/
requirements.txt
README.md
.gitignore
```

These contain the important project work: code, documentation, notebooks, tests, and setup files.

---

## Recommended project folders to ignore

These should usually be ignored:

```text
.venv/
.env
__pycache__/
data/
.DS_Store
```

These are local, private, temporary, or generated files.

---

## Suggested workflow for the team

1. Keep source code in `src/`
2. Keep notebooks in `notebooks/`
3. Keep documentation in `docs/`
4. Keep raw downloaded data in `data/bronze/`
5. Keep temporary processed data in `data/silver/`
6. Keep final selected outputs in `data/gold/`
7. Do not commit API keys, passwords, or virtual environments
8. Use branches for separate work
9. Merge work into `main` using pull requests

---

## If a folder was already committed before being ignored

Adding a folder to `.gitignore` does not automatically remove it from Git tracking if it was already committed.

To stop tracking a folder without deleting it from your laptop:

```bash
git rm -r --cached folder_name/
```

Example:

```bash
git rm -r --cached .venv/
```

Then commit the change:

```bash
git add .gitignore
git commit -m "Add gitignore rules"
git push
```

---

## Summary

The main rule is:

> Commit files that help the team understand, run, and improve the project. Ignore files that are private, temporary, large, or automatically generated.

For this Airbnb Investment App, the most important files to commit are the app code, notebooks, documentation, requirements file, README, and `.gitignore`.


------------------------------------------------------------------------------


# Team Cheat Sheet

This project includes a separate Markdown file called:

```text
CHEATSHEET.md
```

The cheat sheet is designed to help team members quickly copy and paste the most common commands needed to run and work on the project.

Instead of searching through the full README every time, team members can open `CHEATSHEET.md` and find the essential commands for:

* cloning the repository
* creating and activating the virtual environment
* installing requirements
* running notebooks
* running the Streamlit app
* using Git branches
* pulling the latest changes
* committing work
* pushing work to GitHub


## When to use the cheat sheet

Use `CHEATSHEET.md` when you just need a quick command to copy and paste.

For example:

```bash
git pull origin main
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
streamlit run app/main.py
```

## Important

The cheat sheet should only contain commands that are safe and useful for the team.

Avoid adding commands that could accidentally delete work, reset branches, remove files, or overwrite someone else’s changes unless they are clearly explained.

For example, be careful with commands such as:

```bash
git reset --hard
```

```bash
git clean -fd
```

```bash
rm -rf
```

These commands can permanently remove local changes or files if used incorrectly.

## Recommended file structure

```text
airbnb-investment-app/
├── README.md
├── CHEATSHEET.md
├── requirements.txt
├── .gitignore
├── notebooks/
├── src/
├── app/
├── data/
└── docs/
```

## Summary

The cheat sheet is the quick copy-and-paste command guide.

Both files should be kept updated as the project changes.
