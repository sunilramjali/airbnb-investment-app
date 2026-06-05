# Team Cheatsheet

## Setup Using Terminal

Use these commands when setting up the project for the first time.

```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install project requirements
pip install -r requirements.txt
```

## Daily start

```bash
# Pull the latest version of the project
git checkout main
git pull origin main

# Activate virtual environment
source .venv/bin/activate
```

## Create a New Branch

```bash
git checkout main
git pull origin main
git checkout -b role/your-role/feature/your-task-name
```

## Save your Work

```bash
git status
git add .
git commit -m "Describe what you changed"
git push origin your-branch-name
```

## Check Installed Packages

```bash
pip freeze
```

## Update Requirements File

```bash
pip freeze > requirements.txt
```

## Run Python Script

```bash
python path/to/script.py
```

## Run Tests

```bash
pytest
```

## Deactivate Virtual Environment

```bash
deactivate
```