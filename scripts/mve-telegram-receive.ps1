# MVE capture receiver — long-polls Telegram for new messages, writes to inbox/q-NNN.json
# Usage:
#   .\scripts\mve-telegram-receive.ps1                 (one-shot drain)
#   .\scripts\mve-telegram-receive.ps1 -Loop           (continuous poll, Ctrl+C to stop)
# Env vars required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# State: scripts/.telegram-last-update-id (max update_id seen, to avoid replay)
# Output: inbox/q-NNN.json with shape:
#   { "id": "q-NNN", "received_at": "ISO8601", "from_chat": id, "type": "url|text", "body": "...", "raw": {...} }

param(
    [switch]$Loop,
    [int]$PollSeconds = 30
)

if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
    Write-Error "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars."
    exit 1
}

$repoRoot   = (git rev-parse --show-toplevel 2>$null) -replace "/", "\"
$inboxDir   = Join-Path $repoRoot "inbox"
$stateFile  = Join-Path $repoRoot "scripts\.telegram-last-update-id"
if (-not (Test-Path $inboxDir)) { New-Item -ItemType Directory -Path $inboxDir | Out-Null }

function Get-NextInboxId {
    $existing = Get-ChildItem $inboxDir -Filter "q-*.json" -ErrorAction SilentlyContinue |
                ForEach-Object { if ($_.BaseName -match '^q-(\d+)$') { [int]$Matches[1] } } |
                Sort-Object -Descending
    $next = if ($existing.Count -gt 0) { $existing[0] + 1 } else { 1 }
    return "q-{0:000}" -f $next
}

function Drain-Updates {
    $lastId = if (Test-Path $stateFile) { [int](Get-Content $stateFile) } else { 0 }
    $url = "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/getUpdates"
    $body = @{ offset = $lastId + 1; timeout = 0; allowed_updates = @("message") } | ConvertTo-Json

    try {
        $resp = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
    } catch {
        Write-Warning "Telegram getUpdates failed: $_"
        return 0
    }

    if (-not $resp.ok) {
        Write-Warning "Telegram returned ok=false"
        return 0
    }

    $count = 0
    foreach ($upd in $resp.result) {
        $lastId = [Math]::Max($lastId, [int]$upd.update_id)
        $msg = $upd.message
        if (-not $msg) { continue }

        # only accept from Aaron's chat_id
        if ("$($msg.chat.id)" -ne "$($env:TELEGRAM_CHAT_ID)") {
            Write-Warning "Rejected message from chat_id $($msg.chat.id) (not allowlisted)"
            continue
        }

        $text = $msg.text
        if (-not $text) { continue }  # skip non-text (no voice in MVP)

        $type = if ($text -match "^https?://") { "url" } else { "text" }
        $id   = Get-NextInboxId
        $payload = @{
            id           = $id
            received_at  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
            from_chat    = $msg.chat.id
            type         = $type
            body         = $text
            raw          = $msg
        } | ConvertTo-Json -Depth 10

        $outFile = Join-Path $inboxDir "$id.json"
        $payload | Out-File -FilePath $outFile -Encoding utf8
        Write-Host "[$id] type=$type len=$($text.Length)"
        $count++

        # ack back to Telegram
        $ackUrl = "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/sendMessage"
        $ackBody = @{ chat_id = $msg.chat.id; text = "Queued #$id - laptop drains on next /capture-meeting"; reply_to_message_id = $msg.message_id } | ConvertTo-Json
        try { Invoke-RestMethod -Uri $ackUrl -Method Post -Body $ackBody -ContentType "application/json" -TimeoutSec 10 | Out-Null } catch { }
    }

    $lastId | Out-File -FilePath $stateFile -Encoding ascii
    return $count
}

if ($Loop) {
    Write-Host "Polling every $PollSeconds s. Ctrl+C to stop."
    while ($true) {
        $n = Drain-Updates
        if ($n -gt 0) { Write-Host "  drained $n message(s)" }
        Start-Sleep -Seconds $PollSeconds
    }
} else {
    $n = Drain-Updates
    Write-Host "Drained $n message(s)."
}
