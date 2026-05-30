# MVE briefing sender — pipes /start-day output to Telegram via Bot API
# Usage:
#   .\scripts\mve-telegram-send.ps1 -Body (Get-Content logs/2026-05-13.md -Raw)
#   echo "test" | .\scripts\mve-telegram-send.ps1
# Env vars required (set in .secrets/telegram.env, source before invoking):
#   $env:TELEGRAM_BOT_TOKEN   = "123456:ABC-XYZ..."   (from @BotFather)
#   $env:TELEGRAM_CHAT_ID     = "987654321"           (your user ID — get from @userinfobot)

param(
    [Parameter(ValueFromPipeline=$true)]
    [string]$Body
)

begin {
    if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
        Write-Error "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars. Source .secrets/telegram.env first."
        exit 1
    }
    $buf = New-Object System.Text.StringBuilder
}

process {
    if ($Body) { [void]$buf.AppendLine($Body) }
}

end {
    $text = $buf.ToString().Trim()
    if (-not $text) {
        Write-Error "Empty body — nothing to send."
        exit 1
    }

    # Telegram limit is 4096 chars per message; chunk if needed
    $chunkSize = 3800  # leave headroom for MarkdownV2 escapes
    $chunks = @()
    for ($i = 0; $i -lt $text.Length; $i += $chunkSize) {
        $end = [Math]::Min($i + $chunkSize, $text.Length)
        $chunks += $text.Substring($i, $end - $i)
    }

    $url = "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/sendMessage"
    $sent = 0
    foreach ($chunk in $chunks) {
        $payload = @{
            chat_id    = $env:TELEGRAM_CHAT_ID
            text       = $chunk
            parse_mode = "Markdown"
            disable_web_page_preview = $true
        } | ConvertTo-Json

        try {
            $resp = Invoke-RestMethod -Uri $url -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 30
            if ($resp.ok) { $sent++ } else { Write-Warning "Telegram returned ok=false: $($resp | ConvertTo-Json -Compress)" }
        } catch {
            Write-Error "Telegram send failed: $_"
            exit 1
        }
    }
    Write-Host "Sent $sent / $($chunks.Count) chunks to chat $($env:TELEGRAM_CHAT_ID)"
}
