# Deploying the demo (GitHub + Render)

The app runs as one Docker container: the Python server, the built web app and the
LibreDWG converter. Render builds it from the GitHub repository and gives it an https
address such as `https://factory-consultant-demo.onrender.com`.

## 1. Put the code on GitHub (private)

1. On github.com, create a **new private repository** (for example under the company
   organisation), named `factory-consultant-agent`. Do not add a README or .gitignore.
2. In the VS Code terminal, in the project folder:

   ```powershell
   git remote add origin https://github.com/<organisation>/factory-consultant-agent.git
   git branch -M main
   git push -u origin main --tags
   ```

   Drawings, projects, `.venv` and `tools` are excluded by `.gitignore` and are not uploaded.

## 2. Create the service on Render

1. Sign in at render.com and connect your GitHub account (allow access to this repository).
2. Choose **New → Blueprint**, pick the repository, and confirm. Render reads `render.yaml`.
3. The first build takes about 10 minutes (it compiles the DWG converter). Later builds are
   faster.
4. Open the service URL. The demo starts with three sample projects.

Every push to `main` redeploys automatically.

## Plans

| Plan | Cost | Behaviour |
| --- | --- | --- |
| Starter + 1 GB disk (render.yaml) | paid monthly | Always on; projects are kept |
| Free (change `plan: free`, remove `disk`) | free | Sleeps after 15 min idle (about a minute to wake); saved projects are lost on sleep, restart or redeploy; sample projects are recreated |

## Settings (Render → service → Environment)

| Variable | Meaning |
| --- | --- |
| `FCA_DEMO=1` | Demo banner and sample projects when empty |
| `FCA_DEMO_PASSWORD` | Optional: set to require a shared password for the whole site (any user name). Not set = open |
| `FCA_DATA_DIR` | Where projects are stored (the disk) |

## Notes

- The site sends `noindex` headers and a `robots.txt`, so search engines do not list it, but
  anyone with the link can open it. Use sample data only.
- VR on a standalone headset works on the https address.
- LibreDWG is GPL-3.0 and runs as a separate program inside the container; confirm licensing
  before any commercial distribution.
