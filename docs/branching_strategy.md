# Branching Strategy

## Purpose

This document explains how branches should be used in this project so the team can work safely without overwriting each other’s work.

For this project, branches are organised by **role first**, then by the **specific feature or task** being worked on.

This makes it clear:

* who is responsible for each branch
* what area of the project the branch belongs to
* what feature or task is being developed
* which work is ready to be reviewed and merged

---

## Core Rule

No one should push directly to `main`.

All changes should be made on a separate branch and merged into `main` through a Pull Request.

This helps us:

* avoid breaking the project
* review changes before they are merged
* keep a clear history of who changed what
* reduce merge conflicts
* make sure `main` always contains the latest stable version of the project

---

## Main Branch

The `main` branch is the stable version of the project.

It should contain:

* the latest working version of the app
* approved documentation
* tested code
* agreed project structure
* stable data pipeline scripts
* final or near-final outputs

The `main` branch should not contain:

* unfinished code
* broken notebooks
* experimental work
* personal test files
* API keys, passwords, or secrets
* raw large datasets

---

## Branch Protection

The `main` branch should be protected on GitHub.

Recommended settings:

* require a Pull Request before merging
* require at least 1 approval before merging
* require conversations to be resolved before merging
* block force pushes
* do not allow direct pushes to `main`

This means all work must go through a review process before becoming part of the stable project.

---

## Branch Naming Structure

Branches should follow this structure:

```text
role/<role-name>/<task-type>/<task-name>
```

Example:

```text
role/data-engineer/feature/ingestion
```

This means:

```text
role/              = the branch belongs to a project role
data-engineer/     = the person or role responsible
feature/           = the type of work
ingestion          = the specific task
```

---

## Role Branches

The first layer of branching should be based on roles.

Recommended role groups for this project:

```text
role/data-architect
role/data-engineer
role/data-analyst
role/ai-engineer
role/ui-developer
role/qa-tester
```

These role branches help separate responsibilities across the project.

However, team members should usually create a more specific task branch under their role instead of working directly on the general role branch.

For example, instead of working directly on:

```text
role/data-engineer
```

use:

```text
role/data-engineer/feature/preprocessing
```

---

## Task Types

After the role name, use a task type.

Recommended task types:

```text
feature/
fix/
test/
docs/
experiment/
```

### Feature Branches

Use `feature/` when adding a new part of the project.

Examples:

```text
role/data-engineer/feature/data-ingestion
role/data-engineer/feature/data-cleaning
role/data-engineer/feature/data-enrichment
role/data-analyst/feature/exploratory-analysis
role/data-analyst/feature/investment-metrics
role/ai-engineer/feature/review-sentiment-analysis
role/ai-engineer/feature/investment-scoring-model
role/frontend-developer/feature/streamlit-dashboard
role/backend-developer/feature/api-endpoints
```

### Fix Branches

Use `fix/` when correcting an error or bug.

Examples:

```text
role/data-engineer/fix/file-path-error
role/data-engineer/fix/null-handling
role/ai-engineer/fix/model-output-format
role/frontend-developer/fix/dashboard-filter-error
role/qa-tester/fix/test-failures
```

### Testing Branches

Use `test/` when adding or improving tests.

Examples:

```text
role/qa-tester/test/data-validation
role/qa-tester/test/unit-tests
role/qa-tester/test/integration-tests
role/data-engineer/test/pipeline-validation
role/ai-engineer/test/model-validation
```

### Documentation Branches

Use `docs/` when changing documentation.

Examples:

```text
role/documentation/docs/update-readme
role/documentation/docs/add-architecture-guide
role/documentation/docs/branching-strategy
role/documentation/docs/testing-validation
role/project-manager/docs/project-plan
```

### Experiment Branches

Use `experiment/` for work that may not be included in the final project.

Examples:

```text
role/ai-engineer/experiment/new-model
role/data-analyst/experiment/airbnb-review-clustering
role/frontend-developer/experiment/alternative-dashboard-design
```

Experimental branches should only be merged into `main` if the team agrees that the work is useful and stable.

---

## Recommended Branches for This Project

For the Airbnb Investment Intelligence App, recommended branches could include:

```text
main

role/project-manager/docs/project-plan
role/project-manager/docs/task-allocation

role/documentation/docs/update-readme
role/documentation/docs/architecture-guide
role/documentation/docs/branching-strategy
role/documentation/docs/testing-validation

role/data-engineer/feature/data-ingestion
role/data-engineer/feature/data-cleaning
role/data-engineer/feature/data-enrichment
role/data-engineer/feature/final-dataset-export

role/data-analyst/feature/exploratory-analysis
role/data-analyst/feature/price-analysis
role/data-analyst/feature/location-analysis
role/data-analyst/feature/investment-metrics

role/ai-engineer/feature/review-sentiment-analysis
role/ai-engineer/feature/review-topic-modelling
role/ai-engineer/feature/investment-scoring-model

role/backend-developer/feature/api-endpoints
role/backend-developer/feature/database-connection

role/frontend-developer/feature/streamlit-app
role/frontend-developer/feature/dashboard-layout
role/frontend-developer/feature/user-filters

role/qa-tester/test/data-validation
role/qa-tester/test/unit-tests
role/qa-tester/test/integration-tests
role/qa-tester/test/final-output-checks
```

---

## Recommended Workflow

Before starting work, always update your local `main` branch:

```bash
git checkout main
git pull origin main
```

Create a new branch for your role and task:

```bash
git checkout -b role/data-engineer/feature/data-ingestion
```

Work on your files, then check what changed:

```bash
git status
```

Add only the files you want to commit:

```bash
git add path/to/file
```

Commit your work with a clear message:

```bash
git commit -m "Add Airbnb data ingestion script"
```

Push your branch to GitHub:

```bash
git push origin role/data-engineer/feature/data-ingestion
```

Then open a Pull Request on GitHub:

```text
role/data-engineer/feature/data-ingestion → main
```

Another team member should review the Pull Request before it is merged.

---

## Example Workflows by Role

### Data Architect

```bash
git checkout main
git pull origin main
git checkout -b role/data-architect/docs/architecture-guide

### Data Engineer

```bash
git checkout main
git pull origin main
git checkout -b role/data-engineer/feature/data-cleaning
```

This branch would be used for cleaning raw Airbnb data, handling missing values, standardising columns, and preparing data for analysis.

### Data Analyst

```bash
git checkout main
git pull origin main
git checkout -b role/data-analyst/feature/price-analysis
```

This branch would be used for analysing Airbnb prices, occupancy patterns, location trends, and investment indicators.

### AI Engineer

```bash
git checkout main
git pull origin main
git checkout -b role/ai-engineer/feature/review-sentiment-analysis
```

This branch would be used for analysing Airbnb guest reviews using AI or NLP techniques.

### UI Developer

```bash
git checkout main
git pull origin main
git checkout -b role/ui-developer/feature/streamlit-dashboard
```

This branch would be used for building the user-facing dashboard or app interface.

### QA Tester

```bash
git checkout main
git pull origin main
git checkout -b role/qa-tester/test/data-validation
```

This branch would be used for checking that the data, pipeline outputs, and app features work correctly.

---

## Pull Request Rules

Every Pull Request should include:

* a clear title
* a short description of what was changed
* the role responsible for the work
* any files or notebooks affected
* any tests or checks completed
* any known issues or limitations

Example Pull Request description:

```text
## Role
Data Engineer

## What changed
Added the first version of the data ingestion pipeline.

## Files changed
- etl/01_bronze_ddl.sql
- etl/02_bronze_load.py
- config/ingestion_manifest.py

## Checks completed
- confirmed the raw file loads correctly
- checked column names
- checked row count
- confirmed rows landed in the BRONZE schema with audit metadata

## Notes
Further validation may be needed after cleaning is completed.
```

---

## Commit Message Style

Commit messages should be short but clear.

Good examples:

```text
Add Airbnb data ingestion script
Clean missing values in listings dataset
Update README with setup instructions
Fix file path error in cleaning notebook
Add validation checks for final dataset
```

Avoid vague messages like:

```text
update
changes
fixed stuff
new work
final version
```

---

## Handling Merge Conflicts

Merge conflicts can happen when two people edit the same part of the same file.

To reduce conflicts:

* pull the latest version of `main` before starting work
* avoid multiple people editing the same notebook at the same time
* communicate before changing shared files
* keep Pull Requests small and focused
* merge work regularly instead of leaving branches too long
* separate tasks clearly by role and feature

If a conflict happens, do not guess. Read the conflicting sections carefully and decide which version should be kept.

---

## Files That Should Not Be Committed

Do not commit:

```text
.env
API keys
passwords
tokens
large raw datasets
__pycache__/
.venv/
.ipynb_checkpoints/
personal test files
```

These should be ignored using `.gitignore`.

---

## Final Rule

The `main` branch should always represent the best working version of the project.

All team members should work on branches that follow this structure:

```text
role/<role-name>/<task-type>/<task-name>
```

For example:

```text
role/data-engineer/feature/data-cleaning
```

Work should be reviewed through Pull Requests and only merged into `main` when it is stable.

