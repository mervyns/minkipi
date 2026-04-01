#!/usr/bin/env bash

set -euo pipefail

# Resolve project root relative to this script's location
SCRIPT_DIR=$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Versions
SELECT2_VERSION="4.1.0-beta.1"
FULLCALENDAR_VERSION="6.1.17"
JQUERY_VERSION="3.6.0"

# Define vendor files: name | url | output path (relative to project root)
declare -a VENDORS=(
  "Select2 CSS|https://cdnjs.cloudflare.com/ajax/libs/select2/${SELECT2_VERSION}/css/select2.min.css|${PROJECT_ROOT}/src/static/styles/select2.min.css"
  "Select2 JS|https://cdnjs.cloudflare.com/ajax/libs/select2/${SELECT2_VERSION}/js/select2.min.js|${PROJECT_ROOT}/src/static/scripts/select2.min.js"
  "jQuery|https://code.jquery.com/jquery-${JQUERY_VERSION}.min.js|${PROJECT_ROOT}/src/static/scripts/jquery.min.js"
  "Chart JS|https://cdn.jsdelivr.net/npm/chart.js|${PROJECT_ROOT}/src/static/scripts/chart.js"
  "Fullcalendar JS|https://cdn.jsdelivr.net/npm/fullcalendar@${FULLCALENDAR_VERSION}/index.global.min.js|${PROJECT_ROOT}/src/static/scripts/calendar.min.js"
)

# Download each vendor file
for vendor in "${VENDORS[@]}"; do
  IFS='|' read -r name url output <<< "$vendor"
  mkdir -p "$(dirname "$output")"
  echo "Updating $name..."
  if curl -sfL "$url" -o "$output"; then
    echo "  ✓ Downloaded to $output"
  else
    echo "  ✗ Failed to download $name" >&2
    exit 1
  fi
done

echo "All vendor files updated."
