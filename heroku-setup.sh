#!/usr/bin/env bash
# Auto-detect Heroku app name + set ffmpeg/python buildpacks
# Usage:
#   bash heroku-setup.sh           # auto-detect from git remote
#   bash heroku-setup.sh myapp     # explicit name
set -e

detect_app() {
  if [ -n "$1" ]; then
    echo "$1"
    return
  fi
  if [ -n "$HEROKU_APP_NAME" ]; then
    echo "$HEROKU_APP_NAME"
    return
  fi
  # git remote: https://git.heroku.com/APP.git  or  https://git.heroku.com/APP.git/
  local url
  url=$(git remote get-url heroku 2>/dev/null || true)
  if [ -n "$url" ]; then
    echo "$url" | sed -E 's#.*heroku\.com/([^\./]+).*#\1#'
    return
  fi
  # fallback: heroku CLI default app (from git remote / cwd)
  heroku apps:info -j 2>/dev/null | sed -n 's/.*"name":"\([^"]*\)".*/\1/p' | head -1
}

APP=$(detect_app "$1")
if [ -z "$APP" ] || [ "$APP" = "$url" ]; then
  echo "ERROR: Heroku app name nahi mila."
  echo "  1) pehle: heroku git:remote -a YOUR_APP_NAME"
  echo "  2) ya:    bash heroku-setup.sh YOUR_APP_NAME"
  exit 1
fi

echo "==> Detected Heroku app: $APP"
echo "==> Setting buildpacks (ffmpeg + apt + python)..."

heroku buildpacks:clear -a "$APP" || true
heroku buildpacks:add --index 1 https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git -a "$APP"
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-apt.git -a "$APP"
heroku buildpacks:add --index 3 heroku/python -a "$APP"

echo ""
echo "==> Current buildpacks:"
heroku buildpacks -a "$APP"
echo ""
echo "==> Done for app: $APP"
echo "    Ab code push / redeploy karo, phir:"
echo "    heroku run \"ffmpeg -version\" -a $APP"
