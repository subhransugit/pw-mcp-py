from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
import subprocess, json, pathlib, os
from git import Repo

app = FastAPI()
_state = {"browser": None, "context": None, "page": None, "pctx": None}

class ToolCall(BaseModel):
    tool: str
    input: dict | None = None

def _ensure_node_setup(tests_root: str):
    """Make sure package.json and Playwright test deps exist."""
    pkg_json = os.path.join(tests_root, "package.json")
    if not os.path.exists(pkg_json):
        subprocess.run(["npm", "init", "-y"],
                       cwd=tests_root, capture_output=True, text=True, shell=(os.name == "nt"))
    pw_cli = os.path.join(tests_root, "node_modules", ".bin",
                          "playwright.cmd" if os.name == "nt" else "playwright")
    if not os.path.exists(pw_cli):
        subprocess.run(["npm", "i", "-D", "@playwright/test@^1.48.0"],
                       cwd=tests_root, capture_output=True, text=True, shell=(os.name == "nt"))
    # Ensure Chromium browser is installed
    subprocess.run(["npx", "playwright", "install", "chromium"],
                   cwd=tests_root, capture_output=True, text=True, shell=(os.name == "nt"))

def _gen_spec_code(scenario: str, steps: list[dict]) -> str:
    # Translate “steps” to Playwright code
    body_lines: list[str] = []
    for s in steps or []:
        a = (s.get("action") or "").lower()
        sel = s.get("selector")
        tgt = s.get("target")
        val = s.get("value")
        q = sel or (f"#{tgt}" if tgt else None)

        if a == "open" and val:
            body_lines.append(f'await page.goto("{val}");')
        elif a == "click" and q:
            body_lines.append(f'await page.click("{q}");')
        elif a == "type" and q is not None and val is not None:
            body_lines.append(f'await page.fill("{q}", "{val}");')
        elif a == "asserttext" and q is not None and val is not None:
            body_lines.append(f'await expect(page.locator("{q}")).toContainText("{val}");')
        elif a == "custom" and isinstance(val, str) and val.lower().startswith("wait "):
            ms = "".join(ch for ch in val if ch.isdigit()) or "500"
            body_lines.append(f'await page.waitForTimeout({ms});')
        else:
            body_lines.append(f'// TODO: unsupported step: {s}')

    body = "\n  ".join(body_lines) or "// TODO"
    return f"""import {{ test, expect }} from '@playwright/test';

test('{scenario.replace("'", "\\'")}', async ({{ page }}) => {{
  {body}
}});
"""

@app.post("/tool")
def tool(call: ToolCall):
    i = call.input or {}; t = call.tool

    # ---- Browser session management
    if t == "launch_browser":
        headless = i.get("headless", True)
        # Close existing
        if _state.get("page"):
            try: _state["page"].context.browser.close()
            except: pass
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        _state.update({"pctx": p, "browser": browser, "context": context, "page": page})
        return {"ok": True}

    if t == "goto":
        if not _state.get("page"):
            return {"error": "No browser/page. Call launch_browser first."}
        _state["page"].goto(i["url"])
        return {"ok": True}

    if t == "snapshot_dom":
        if not _state.get("page"):
            return {"error": "No page. Call launch_browser and goto first."}
        html = _state["page"].content()
        return {"html": html}

    # ---- Code generation & execution
    if t == "generate_playwright_test":
        tests_root = pathlib.Path(i["testsRoot"]).resolve()
        tests_root.mkdir(parents=True, exist_ok=True)
        name = i.get("name") or "generated.spec.ts"
        scenario = i.get("scenario") or "Generated scenario"
        steps = i.get("steps") or []

        spec_code = _gen_spec_code(scenario, steps)
        spec_path = tests_root / name
        spec_path.write_text(spec_code, encoding="utf-8")

        # Initialize Node+PW deps if needed
        pkg = tests_root / "package.json"
        if not pkg.exists():
            pkg.write_text(json.dumps({
                "name": "pw-tests",
                "private": True,
                "scripts": {"test": "playwright test"},
                "devDependencies": {"@playwright/test": "^1.48.0"}
            }, indent=2))
        return {"path": str(spec_path)}

    if t == "run_tests":
        tests_root = i["testsRoot"]
        _ensure_node_setup(tests_root)
        proc = subprocess.run(["npx", "playwright", "test"],
                              cwd=tests_root, capture_output=True, text=True, shell=(os.name == "nt"))
        return {"code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}

    if t == "git_push":
        project_root = i["projectRoot"]; remote = i["remoteUrl"]; branch = i.get("branch","main")
        if not (pathlib.Path(project_root) / ".git").exists():
            Repo.init(project_root)
        repo = Repo(project_root)
        repo.git.add(A=True)
        try:
            repo.index.commit("chore: add generated PW tests")
        except Exception:
            pass
        try:
            repo.delete_remote("origin")
        except Exception:
            pass
        repo.create_remote("origin", remote)
        repo.git.push("-u", "origin", branch, "--force")
        return {"ok": True}

    return {"error": f"unknown tool {t}"}

def main():
    import uvicorn
    uvicorn.run("pw_mcp.server:app", host="0.0.0.0", port=7010, reload=False)
