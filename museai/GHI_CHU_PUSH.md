# Ghi chú push code

- Repo: https://github.com/3tmerfast-ui/MuseAI (nhánh `main`)
- Token GitHub lưu trong `.env` (biến `GITHUB_TOKEN`), file này đã nằm trong `.gitignore` — **không commit**.
- Không ghi token vào remote URL; dùng header tạm:

```bash
set -a; . ./.env; set +a
AUTH="Authorization: Basic $(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64)"
git -c http.extraHeader="$AUTH" pull origin main
git -c http.extraHeader="$AUTH" push origin main
```
