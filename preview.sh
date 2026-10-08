#!/usr/bin/env bash
# Renderiza o README com a API de Markdown do GitHub e serve em http://localhost:8000/.preview.html
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8000}"

body="$(gh api markdown -f mode=gfm -f text="$(cat README.md)")"
cat > .preview.html <<EOF
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Prévia README</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-dark.min.css" />
  <style>
    body { background: #0D1117; margin: 0; }
    .markdown-body { box-sizing: border-box; max-width: 1012px; margin: 32px auto; padding: 32px; border: 1px solid #30363D; border-radius: 6px; }
  </style>
</head>
<body>
  <article class="markdown-body">
$body
  </article>
</body>
</html>
EOF

echo "Prévia em http://localhost:${PORT}/.preview.html"
python3 -m http.server "$PORT"
