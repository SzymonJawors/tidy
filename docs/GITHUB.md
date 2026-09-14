# Publish to GitHub

Replace `YOUR_USERNAME` and `REPO_NAME` (e.g. `tidy`) with your GitHub user and repository name.

## 1. Create an empty repo on GitHub

On [github.com/new](https://github.com/new): name the repo, leave it **empty** (no README, no `.gitignore` — this project already has them).

## 2. First push from your PC

Open PowerShell in the project folder:

```powershell
cd $env:USERPROFILE\Desktop\porzadek

git init
git add .
git status
git commit -m "Initial commit: Tidy file organizer for Windows"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
git push -u origin main
```

If GitHub asks you to log in, use a [Personal Access Token](https://github.com/settings/tokens) as the password, or sign in with `gh auth login`.

## 3. Using GitHub CLI (optional)

```powershell
cd $env:USERPROFILE\Desktop\porzadek
gh repo create REPO_NAME --public --source=. --remote=origin --push
```

(`gh` creates the repo and pushes in one step; run `git init` and an initial commit first if the folder is not a repo yet.)

## 4. Later updates

```powershell
git add .
git commit -m "Describe your change"
git push
```

## 5. Before the first commit — checklist

- [ ] Remove local secrets (none expected in this project).
- [ ] Do not commit `Tidy.exe`, `build/`, `dist/` (listed in `.gitignore`).
- [ ] Add screenshots under `docs/screenshots/` when ready, then uncomment the image blocks in `README.md`.
