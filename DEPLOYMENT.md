# Deployment

The dev bot is deployed as one prebuilt Docker container. The server does not
build Python dependencies and only pulls the image produced by GitHub Actions.

## Server requirements

- 1 CPU, 1 GiB RAM, and 10 GiB storage
- Docker Engine with the Compose plugin
- Deployment directory created at `DEV_SERVER_APP_DIR`
- Application secrets in `DEV_SERVER_APP_DIR/.env`
- Persistent application files in `DEV_SERVER_APP_DIR/data`

No swap is required. The bot container is limited to 512 MiB and Docker logs
are limited to three 10 MiB files.

## GitHub Actions secrets

- `DEV_SERVER_HOST`
- `DEV_SERVER_USER`
- `DEV_SERVER_SSH_KEY`
- `DEV_SERVER_APP_DIR`
- `TELEGRAM_BOT_TOKEN`
- `SPREADSHEET_ID`
- `OPENAI_API_KEY`
- `GOOGLE_CREDENTIALS_B64`

`GOOGLE_CREDENTIALS_B64` contains the base64-encoded `data/creds.json` file.
The workflow uses its short-lived `GITHUB_TOKEN` to pull the private container
image and logs the server out of GHCR immediately afterwards.

## Deployment flow

Every push to `dev` performs these steps:

1. Build the Docker image in GitHub Actions.
2. Publish immutable commit and mutable `dev` tags to GHCR.
3. Upload the current Docker Compose configuration.
4. Recreate `.env` and Google credentials from GitHub Actions Secrets.
5. Connect to the server and pull the immutable commit image.
6. Restart only the bot container and remove obsolete services.
7. Verify that the bot process remains running.
8. Roll back to the previous image if startup fails.
9. Delete unused Docker images older than seven days.

The `.env` and `data` directory stay on the server and are not included in the
image.
