git pull || exit /b 1
git add -A
git commit --amend --no-edit || exit /b 1
git push --force