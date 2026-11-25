# CodeGuard gate for GitHub Actions

Reads the CodeGuard gate for a pull request, saves its findings as SARIF, and fails the job when the gate blocks.
CodeGuard ([codeguard.grcxai.com](https://codeguard.grcxai.com)) scans the pull request through its GitHub App; this
action reads that scan. It does not create scans, upload code or invent a verdict: a pending or unavailable gate fails.

The action installs the CodeGuard CLI wheel from `codeguard.grcxai.com/downloads/cli/` and refuses it unless its
SHA-256 matches the digest pinned in `action.yml`. Pin the action by **commit SHA**, and you pin the CLI too.

## Use

1. Install the CodeGuard GitHub App on the repository and add it to CodeGuard, so pull requests are scanned.
2. In CodeGuard create an API token with **read:findings** and **read:scans**, and save it as the repository secret
   `CODEGUARD_TOKEN`.
3. Add a workflow:

```yaml
name: CodeGuard gate
on: pull_request
permissions:
  contents: read
  checks: read
  # security-events: write   # only with code-scanning: 'true'
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - name: Wait for the CodeGuard scan of this commit
        id: scan
        env:
          GH_TOKEN: ${{ github.token }}
          SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          for i in $(seq 1 60); do
            read -r id status < <(gh api "repos/$GITHUB_REPOSITORY/commits/$SHA/check-runs?check_name=CodeGuard" \
              --jq '.check_runs | sort_by(.started_at) | last | "\(.external_id // "") \(.status // "")"')
            if [ -n "$id" ] && [ "$status" = completed ]; then echo "id=$id" >> "$GITHUB_OUTPUT"; exit 0; fi
            sleep 20
          done
          echo "No completed CodeGuard check on $SHA after 20 minutes" >&2; exit 1
      - uses: goldsbd/codeguard-action@<commit-sha>   # pin a full commit SHA, never a branch
        with:
          scan-id: ${{ steps.scan.outputs.id }}
        env:
          CODEGUARD_TOKEN: ${{ secrets.CODEGUARD_TOKEN }}
```

The token is read from the environment only; it is never an input and is never passed to `pip`.

## Inputs

| Input | Default | |
|---|---|---|
| `scan-id` | (required) | The CodeGuard scan UUID: the `external_id` of the `CodeGuard` check run |
| `api-url` | `https://codeguard.grcxai.com` | CodeGuard API origin (HTTPS) |
| `code-scanning` | `'false'` | `'true'` also uploads the SARIF to GitHub code scanning (needs `security-events: write`; private repositories need GitHub Advanced Security) |
| `cli-wheel-url` | the pinned release | Override only with another published wheel from `/downloads/cli/` |
| `cli-sha256` | the pinned release's digest | Must match `cli-wheel-url`; see the signed `manifest.json` beside the wheels |

The SARIF is written to `codeguard.sarif` and kept as a workflow artifact even when the gate blocks.

## Verify the pinned CLI yourself

`https://codeguard.grcxai.com/downloads/cli/manifest.json` lists every published wheel with its SHA-256;
`manifest.json.sig` is its Ed25519 signature. Published wheels are never replaced: a new CLI is a new version.

```sh
curl -fsSO https://codeguard.grcxai.com/downloads/cli/codeguard-0.2.44-py3-none-any.whl
shasum -a 256 codeguard-0.2.44-py3-none-any.whl   # 68960798247200a95fc38769e756287ae625d88d9da3fa8a0f63bf2e817b8b20
```

## Licence

Apache-2.0 (`LICENSE`, `NOTICE`). The CLI wheel it installs is Apache-2.0 as well.
