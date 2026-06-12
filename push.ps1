Set-Location -Path "c:\bot_2\telegram_bot2\Admin_SITE"
npx vite build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Vite build failed"
    exit $LASTEXITCODE
}
Set-Location -Path "c:\bot_2\telegram_bot2"
git add .
git commit -F commit_msg.txt
git push
