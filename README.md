
---

# pw-mcp-py/README.md

```markdown
# Playwright MCP (Python, FastAPI)

MCP-style HTTP server exposing tools to generate and execute Playwright UI tests.

## Tools
- `launch_browser { headless: bool }`
- `goto { url: string }`
- `snapshot_dom {} -> { html }`
- `generate_playwright_test { testsRoot, name?, scenario, steps[] }`
- `run_tests { testsRoot }`
- `git_push { projectRoot, remoteUrl, branch? }`

## Repo Layout
pw-mcp-py/
├─ pyproject.toml
├─ requirements.txt
├─ src/pw_mcp/server.py
└─ scripts/
├─ publish_twine.sh
└─ publish_twine.ps1


## Prereqs
- Python 3.10+
- Node.js + npm
- Playwright browsers (installed via command below)

## Install & Run
```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.\.venv\Scripts\activate

pip install -r requirements.txt
python -m playwright install
uvicorn pw_mcp.server:app --host 0.0.0.0 --port 7010

Quick Test (manual)
# Launch browser
curl -X POST http://localhost:7010/tool -H "Content-Type: application/json" \
  -d '{"tool":"launch_browser","input":{"headless":true}}'
  
#Windows
Invoke-WebRequest -Uri "http://localhost:7010/tool" `
-Method POST `
-Headers @{ "Content-Type" = "application/json" } `
-Body '{"tool":"launch_browser","input":{"headless":false}}'

# Navigate and snapshot DOM
curl -X POST http://localhost:7010/tool -H "Content-Type: application/json" \
  -d '{"tool":"goto","input":{"url":"https://example.org"}}'
curl -X POST http://localhost:7010/tool -H "Content-Type: application/json" \
  -d '{"tool":"snapshot_dom","input":{}}'

Generate & Run Tests
# Generate a test under ./demo-tests
curl -X POST http://localhost:7010/tool -H "Content-Type: application/json" \
  -d '{"tool":"generate_playwright_test","input":{
        "testsRoot":"./demo-tests",
        "name":"generated.spec.ts",
        "scenario":"Open homepage and verify heading",
        "steps":[{"action":"open","value":"https://example.org"}]
      }}'

# Execute
curl -X POST http://localhost:7010/tool -H "Content-Type: application/json" \
  -d '{"tool":"run_tests","input":{"testsRoot":"./demo-tests"}}'

Publish to Artifactory (PyPI)
pip install build twine
python -m build
twine upload --repository-url https://<ARTIFACTORY-PYPI-URL> -u $ARTIFACTORY_USER -p $ARTIFACTORY_API_KEY dist/*

Notes

First test run in a fresh folder automatically does npm i -D @playwright/test and npx playwright install.

Windows shells: add --% if needed to pass JSON to curl without escaping issues, or use PowerShell’s Invoke-RestMethod.
