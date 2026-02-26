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

# TNT App Charity Runbook (UK)

This guide is for non-technical admins to keep the app running safely.

## What this app uses

- App hosting: Fly.io
- Database: Supabase Postgres
- Region: Fly `lhr` and nearest Supabase EU/UK region

## One-time setup (done once)

1. Install Fly CLI (`flyctl`) on your computer.
2. Create a Supabase project and copy the Postgres connection string.
3. Set Fly secrets:

```bash
fly secrets set DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>:5432/postgres?sslmode=require"
fly secrets set SECRET_KEY="<strong-random-secret>"
```

Purpose:
- `DATABASE_URL`: tells the app where the database lives.
- `SECRET_KEY`: secures login sessions and cookies.

## Deploy updates

From the project folder:

```bash
fly deploy
```

Purpose:
- Deploys the latest app version.
- Automatically runs database migrations via Fly release command.

## Check app health

```bash
fly status
fly logs
```

Purpose:
- `fly status`: confirms app machine is running.
- `fly logs`: shows startup errors and migration results.

## If deployment fails

1. Run `fly logs` and look for database/auth errors.
2. Re-check secrets (especially `DATABASE_URL` and `SECRET_KEY`).
3. Re-run `fly deploy` after fixing secrets.

## Safe routine for changes

1. Developer makes code changes.
2. Developer deploys with `fly deploy`.
3. Admin verifies basic login and rota page load.
4. Admin checks `fly logs` for clean startup.

## Backup and recovery policy (recommended)

- Keep Supabase automated backups enabled.
- Keep one secure record of:
  - Supabase project URL
  - Fly app name (`tnt-volunteers`)
  - Who has admin access
- If serious issue occurs, contact your developer and provide:
  - Approximate time issue started
  - Recent deploy time
  - Relevant `fly logs` output
