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

## Migrations

- create migrations once: `uv run flask --app app:create_app db init`
- create a new migration after model changes: `uv run flask --app app:create_app db migrate -m "describe change"`
- apply migrations: `uv run flask --app app:create_app db upgrade`

## Fly.io deployment

1. Create app and Postgres:
    - `fly launch --no-deploy`
    - `fly postgres create`
    - `fly postgres attach <postgres-app-name>`
2. Set required secrets:
    - `fly secrets set SECRET_KEY="<strong-random-secret>"`
3. Deploy (runs migrations automatically via Fly release command):
    - `fly deploy`
