# Using app

- run app with uv run python app.py
- login with email volunteer@example.com and password
- user admin@example.com to view store manager page

# Developing

## Setup for local dev

In WSL Ubuntu, I set up from the repo on new machine using:

```
git clone git@github.com:FraserSingh/TNT_APP.git
pip  install uv
cd TNT_APP/
uv sync
pre-commit
pre-commit install
pre-commit autoupdate
pre-commit install-hooks
uv sync
```
