# Using app

- run app locally with `uv run flask --app app:create_app --debug run --host 0.0.0.0 --port 8080`
    - or `uv run gunicorn "app:create_app()" --bind 0.0.0.0:8080 --workers 1 --threads 2` for production like runs
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


## Run with Gunicorn

`uv run gunicorn "app:create_app()" --bind 0.0.0.0:8080 --workers 1 --threads 2`

admin password is "admin_pass"
