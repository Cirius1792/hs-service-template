#!/usr/bin/env bash
# Deploy a SWAG nginx site configuration to a remote host over SSH.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/deploy_swag_config.sh [local-config] [remote-path]

If local-config is omitted, the script searches for a single file named
  *.subdomain.conf or *.subfolder.conf under SWAG_LOCAL_CONFIG_DIR (default: swag/proxy-confs).
If remote-path is omitted, SWAG_REMOTE_CONFIG_PATH must be set.

Required environment variables:
  DEPLOY_SSH_HOST       SSH host for the SWAG machine
  DEPLOY_SSH_USER       SSH user allowed to manage SWAG
Optional environment variables:
  DEPLOY_SSH_PORT           SSH port (default: 22)
  SWAG_CONTAINER_NAME       Docker container name (default: swag)
  SWAG_REMOTE_CONFIG_PATH   Default remote path when second argument is omitted
  SWAG_LOCAL_CONFIG_DIR     Directory to search when auto-detecting configs (default: swag/proxy-confs)
EOF
}

# Print the help message when -h/--help is passed.
if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

# Determine the local config file, either from the first argument or by auto-detecting it.
CONFIG_ARG=${1:-}
if [[ -n "$CONFIG_ARG" ]]; then
  LOCAL_CONFIG="$CONFIG_ARG"
  if [[ ! -f "$LOCAL_CONFIG" ]]; then
    echo "Local config file '$LOCAL_CONFIG' not found" >&2
    exit 1
  fi
else
  SEARCH_DIR=${SWAG_LOCAL_CONFIG_DIR:-swag/proxy-confs}
  if [[ ! -d "$SEARCH_DIR" ]]; then
    echo "Config directory '$SEARCH_DIR' not found; nothing to deploy."
    exit 0
  fi
  shopt -s nullglob
  CANDIDATES=()
  for candidate in "$SEARCH_DIR"/*.subdomain.conf "$SEARCH_DIR"/*.subfolder.conf; do
    if [[ -f "$candidate" ]]; then
      CANDIDATES+=("$candidate")
    fi
  done
  shopt -u nullglob
  if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
    echo "No *.subdomain.conf or *.subfolder.conf files found in '$SEARCH_DIR'; nothing to deploy."
    exit 0
  fi
  if [[ ${#CANDIDATES[@]} -gt 1 ]]; then
    echo "Multiple config files found in '$SEARCH_DIR'; ensure only one exists:" >&2
    for file in "${CANDIDATES[@]}"; do
      echo "  - $file" >&2
    done
    exit 1
  fi
  LOCAL_CONFIG="${CANDIDATES[0]}"
  echo "Auto-detected config file: $LOCAL_CONFIG"
fi

# Use the second argument or the SWAG_REMOTE_CONFIG_PATH env var for the remote location.
REMOTE_PATH=${2:-${SWAG_REMOTE_CONFIG_PATH:-}}
if [[ -z "$REMOTE_PATH" ]]; then
  echo "Remote path missing. Pass it as the second argument or set SWAG_REMOTE_CONFIG_PATH." >&2
  exit 1
fi

LOCAL_BASENAME=$(basename "$LOCAL_CONFIG")

# Ensure the required SSH target variables are set (shell will abort if missing).
: "${DEPLOY_SSH_HOST:?Set DEPLOY_SSH_HOST}"
: "${DEPLOY_SSH_USER:?Set DEPLOY_SSH_USER}"

# Fill in optional parameters with defaults when not explicitly set.
SSH_PORT=${DEPLOY_SSH_PORT:-22}
SWAG_CONTAINER=${SWAG_CONTAINER_NAME:-swag}
SSH_TARGET="${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST}"

# Create temporary filenames to avoid clobbering the final destination during upload.
TMP_NAME="swag-config.$(date +%s).$$.conf"
REMOTE_TMP="/tmp/${TMP_NAME}"

# Copy the config file to the remote host using scp, placing it in a temporary location.
echo "Uploading ${LOCAL_CONFIG} to ${SSH_TARGET}:${REMOTE_PATH}"
scp -P "$SSH_PORT" "$LOCAL_CONFIG" "${SSH_TARGET}:${REMOTE_TMP}"

# Execute a guarded install script on the remote side to swap in the config atomically.
ssh -p "$SSH_PORT" "$SSH_TARGET" \
  "REMOTE_TMP='${REMOTE_TMP}' REMOTE_PATH='${REMOTE_PATH}' LOCAL_BASENAME='${LOCAL_BASENAME}' SWAG_CONTAINER='${SWAG_CONTAINER}' bash -s" <<'REMOTE'
set -euo pipefail

# Ensure the temporary file is deleted no matter how the script exits.
trap 'rm -f "$REMOTE_TMP"' EXIT

# Determine the final destination path, allowing REMOTE_PATH to point to a directory.
TARGET_PATH="$REMOTE_PATH"
DEST_PATH="$TARGET_PATH"

if [[ "$TARGET_PATH" == */ ]]; then
  DEST_PATH="${TARGET_PATH%/}/${LOCAL_BASENAME}"
elif [ -d "$TARGET_PATH" ]; then
  DEST_PATH="${TARGET_PATH%/}/${LOCAL_BASENAME}"
fi

REMOTE_BACKUP="${DEST_PATH}.bak"

# Back up the current config, if it exists, so we can roll back on failure.
echo "Preparing to install config to $DEST_PATH"
if [ -f "$DEST_PATH" ]; then
  cp "$DEST_PATH" "$REMOTE_BACKUP"
fi

# Move the uploaded file into the final destination with correct permissions.
install -Dm644 "$REMOTE_TMP" "$DEST_PATH"

# Validate the nginx configuration before reloading SWAG.
echo "Validating nginx configuration inside $SWAG_CONTAINER"
if docker exec "$SWAG_CONTAINER" nginx -t; then
  # Remove the backup once we know the new config is valid.
  if [ -f "$REMOTE_BACKUP" ]; then
    rm -f "$REMOTE_BACKUP"
  fi
  # Reload nginx so the new virtual host is live immediately.
  echo "Reloading nginx"
  docker exec "$SWAG_CONTAINER" nginx -s reload
else
  # Restore the previous config if validation fails and propagate the error.
  echo "nginx -t failed; restoring previous config" >&2
  if [ -f "$REMOTE_BACKUP" ]; then
    mv "$REMOTE_BACKUP" "$DEST_PATH"
  fi
  exit 1
fi
REMOTE

# Let the user know everything completed successfully.
echo "Deployment completed"
