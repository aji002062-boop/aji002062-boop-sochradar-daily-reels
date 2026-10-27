# SOCHRADAR INDIA — Automatic Daily Trading Reel

**What this kit really does:** Makes a short original-graphics 720×1280 (9:16) Hindi market-news explainer (~18s) from fresh Google News RSS headlines + Gemini, generates a Hindi voice with Edge TTS, produces original instrumental background music, saves MP4 + caption + hashtags + source links in year/month/date folders on Google Drive, optionally publishes via the official Instagram Graph API using **Facebook Login for Business**. Runs in the GitHub cloud even if your computer is OFF.

**This is NOT the Google Flow website or Veo video generation**. Flow free credits cannot currently be reliably controlled by a supported public scheduled API; this is a low-cost/no-cost practical alternative. This kit produces slightly moving infographic/slideshow reels (4 scenes), NOT AI-generated photographic cinema. The included demo is strictly a sample.

## Beginner steps (Windows PC, one-time)

### 1 — GitHub and repository
1. Make account at https://github.com (if not already).
2. Click `+` > `New repository`; name `sochradar-daily-reels`; select **Private**; Create.
3. Unzip this package. Go into unzipped folder; ensure you can see `.github` (hidden folder).
4. GitHub repository > **Add file** > **Upload files**, drag the content of the unzipped folder (including `.github`) and commit. Some browsers may omit hidden folders: if `.github/workflows/daily-reel.yml` is missing, use GitHub `Add file > Create new file` and enter that complete path, paste YAML from this package. Do **NOT** upload your `rclone.conf` or passwords.

### 2 — Gemini free API key
1. Go to https://aistudio.google.com/app/apikey and create an API key in an eligible **free-tier** project (avoid enabling billing unless you want paid usage).
2. In GitHub repo go to Settings > Secrets and variables > Actions > New repository secret.
3. Name `GEMINI_API_KEY` and paste your key. Never publish your key.
4. If a model is unavailable in your free tier, change `GEMINI_MODEL` in `content.py` or set a GitHub Action secret/env accordingly. Current default: `gemini-2.5-flash-lite`.

### 3 — Drive unattended upload (one-time OAuth authorization)
1. Open Google Cloud Console https://console.cloud.google.com/ and create a personal project.
2. Enable **Google Drive API** under APIs & Services > Library.
3. Go to Google Auth Platform / OAuth consent screen. Set audience **External**, fill required fields, and preferably move to **In production** when permitted: an external app still in Testing generally receives **refresh tokens valid for 7 days only**, so unattended daily sync breaks after a week.
4. Under Clients / Credentials create OAuth client with **Desktop app** application type, note its Client ID and Secret.
5. Install rclone on Windows: https://rclone.org/downloads/ . Open PowerShell: `rclone config`
6. Choose **n** (new remote), name it EXACTLY `gdrive`, storage `drive`, fill your OWN Client ID and Client Secret (2026 rclone is retiring its shared Google Drive client ID), choose full Drive scope (`drive`) or appropriate supported scope. Use browser authorization, log into the Google Account with your intended Drive. Shared Drive: answer no unless yours is shared.
7. Test `rclone lsd gdrive:` .
8. Make your secret by running this exact PowerShell snippet:

```powershell
$config = rclone config file
# Read the path printed by that command, usually $env:APPDATA\rclone\rclone.conf
$p = Join-Path $env:APPDATA 'rclone\rclone.conf'
[Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) | Set-Clipboard
```

9. In GitHub > Settings > Secrets and variables > Actions > **New repository secret**, name `RCLONE_CONFIG_B64`, paste what is on clipboard. It is sensitive: NEVER paste into code, logs, public chats or public repositories. Your **Google Drive ChatGPT connection is separate from this server OAuth step**.
10. Go to Settings > Secrets and variables > Actions > **Variables** tab > New repository variable `DRIVE_ENABLED` with value `true`.

### 4 — Instagram Professional setup
1. In Instagram `@sochradarindia`, go to Profile > Settings and activity > Account type and tools. Switch to **Business/Creator (Professional)** if necessary.
2. Connect it to a **Facebook Page** you manage; for this exact sample flow choose **Facebook Login for Business**.
3. Visit https://developers.facebook.com/apps/ and create a Meta Developer app for Business with Instagram API / Facebook Login setup (UI labels may differ).
4. Give your app role/admin permission on the Facebook Page/Instagram account. For your *own* linked account Standard Access is normally sufficient; other users require App Review/Advanced Access.
5. Obtain a valid Facebook Page access token with `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list` as relevant; use the official Graph API Explorer: https://developers.facebook.com/tools/explorer/ . User token and Page token are NOT interchangeable.
6. To find your IG professional ID: Using a valid user/page token, check `GET /me/accounts?fields=name,access_token,instagram_business_account` on Graph API Explorer. The `instagram_business_account.id` is your `IG_USER_ID`; the selected page `access_token` is `IG_PAGE_ACCESS_TOKEN`.
7. Add both as GitHub repository **Secrets** named `IG_USER_ID` and `IG_PAGE_ACCESS_TOKEN`. Don't share with anyone. Token validity/permissions are essential; long-lived / system-user options require Meta configuration and maintenance. Do not assume tokens never expire.

Reference for Meta's server publishing: https://github.com/fbsamples/reels_publishing_apis/tree/main/insta_reels_publishing_api_sample

### 5 — First safe test
1. In GitHub repository > **Actions** > SochRadar Daily Trading Reel > **Run workflow**.
2. Keep the **demo** checkbox ON and start. Wait for completion.
3. Open that workflow run > `Artifacts` > download `sochradar-reel-result` and watch `reel.mp4`. It is DEMO with no news fetching, no Instagram publishing, and no Google Drive upload.
4. Edit `prompts/YOUR_MASTER_PROMPT.txt` to describe the style from your own video-to-code master prompt. The prompt is used as creative direction; code execution from generative AI is intentionally disabled for security.
5. **Second test:** Go to Actions > Run workflow, untick Demo. This fetches real recent headlines, creates one Reel, and copies files to Drive; with `AUTO_PUBLISH` not set it will **NOT** post to Instagram. Open Google Drive > SochRadarIndia > YYYY > MM > YYYY-MM-DD and inspect movie, caption and sources.
6. Review source headlines/facts, dates, voiceover, music copyright and hashtags before enabling autopost. Never set publishing until first Meta token has been independently tested.
7. After successful tests, Settings > Secrets and variables > Actions > Variables > New repository variable: `AUTO_PUBLISH` = `true`.
8. Scheduled workflow fires at **6:30 PM India time**, although GitHub Actions scheduling is best-effort and can be delayed or skipped. GitHub can disable public repo scheduled workflows after 60 days of repository inactivity. This setup uses a private repo with free quota, but check failures periodically.

### 6 — Date-wise output

```text
Google Drive/
  SochRadarIndia/
    2026/
      10/
        2026-10-27/
          reel.mp4
          post_caption.txt
          source_links.txt
          content.json
          status.json
          card_1.png ... card_4.png
          original_music.wav
          hindi_voice.mp3
```

The code tries to create **maximum 1 reel per India-local date** using `status.json` on Drive as a ledger. If Meta submission status is uncertain it blocks auto retries to reduce duplicate posts. A truly guaranteed exactly-once system would need an external transactional store and reconciliation.

## Known limitations / security
- This is an **18-second motion-graphic explainer**, not a Veo/Flow generated cinematic AI video; Google Flow's 50 free daily credits are separate from Gemini API's free tier.
- On a day with no safe current headlines or Gemini/API errors, one of several rotating educational evergreen topics is used instead. It is not mislabeled as current/trending.
- Fresh Google News RSS **does not prove** a particular topic is viral on Instagram, and titles alone cannot fully establish financial facts. This is a best-effort current-events selection. Only publish after human review until accuracy is reliable.
- The Edge TTS service is unofficial, so rate limits/outages can stop TTS. On failure the script stops rather than publishing a silent video.
- Original instrumental generated by the code is used automatically. Instagram **trending copyrighted music** cannot be reliably chosen and embedded automatically under its music licensing and API rules. For popular song overlays, use Instagram licensed music manually where available and permitted.
- Long lived Google OAuth tokens and Meta access tokens still need occasional renewal, unless your configured authorization scheme supports durable refresh and remains valid.
- Gemini Free tier and GitHub monthly limits are subject to change. GitHub scheduling may occasionally skip a run.
- For stock-market content, **educational news only**; avoid fake returns, guaranteed profits, target/stop loss recommendations, specific stock tips, unverified live prices and unattributed numbers. Videos should say if they are AI-generated where applicable, consistent with Meta platform requirements.
- Unlike user phone sessions, official Instagram publishing requires no login password and works unattended *once all credentials and permissions have been configured*.
- Do not give GitHub Actions arbitrary executable code returned by the AI. This kit deliberately limits AI to storyboard text + captions.

## Troubleshooting
- `Missing GEMINI_API_KEY`: check repository secret.
- `not enough fresh headlines`: an educational evergreen fallback Reel is made instead; it is NOT described as trending news.
- `rclone error`: check OAuth client, Drive API, secret, publishing status, token freshness, and `gdrive` remote name.
- `403` Meta API: ensure IG Professional account linked to Page and Page access token has correct permissions/role.
- `upload error`: verify server uploaded valid 720×1280 H.264 AAC MP4.
- `publishing_pending`: do NOT blindly rerun. Inspect Instagram and Meta media before resetting status in Drive.
- `scheduled did not run`: check workflow enabled, schedule in default branch, GitHub Actions quota and GitHub status; GitHub schedules are not guaranteed exactly on time.
