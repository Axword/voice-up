#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3.11+ is required"; exit 1; }
command -v npm >/dev/null || { echo "Node.js 22.12+ is required"; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
(cd webui && npm ci && npm run build)
printf '%s\n' '#!/usr/bin/env sh' 'cd "$(dirname "$0")"' 'exec .venv/bin/python main.py "$@"' > launch.sh
chmod +x launch.sh
echo "Installed. Start with ./launch.sh. System-wide game input is intended for Windows."
