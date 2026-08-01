# Model Gateway Secret Deployment

## Scenario: Deploy code that reads encrypted provider credentials

### 1. Scope / Trigger

Apply to any release adding or changing the Model Gateway master key, provider
secret encryption format, migration `0010` or later, or API startup wiring.

### 2. Signatures

`scripts/server/deploy.sh --target-ref <full-origin-main-sha>
--allow-migrations --execute` adds the marker-tracked
`model-gateway-key` stage after `git-sync` and before tests/migration/finalize.

### 3. Contracts

- Target is fixed under the service-owned `/var/lib/mediaops` secrets area.
- Remote user is exactly `mediaops`; no sudo/root helper is used.
- Directory mode is 0700; key file mode is 0600 and exactly 32 bytes.
- Absent key uses OS randomness plus exclusive/no-follow creation.
- Existing key is validated, never read, printed, backed up, or replaced.
- Key is outside Git, SQLite, `.env`, logs, database backups, static output,
  and deployment reports. Stage output is only created/present and modes.
- Stage writes `model-gateway-key=done` only after all checks pass.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Wrong SSH user | stage fails before mutation |
| Secret directory is symlink/non-directory/wrong owner | fail closed |
| Existing key symlink/non-file/wrong owner/wrong length | fail closed |
| New exclusive create races | fail; retry revalidates actual state |
| SSH 255 with done marker | reconnect recognizes completion |
| Migration diff without `--allow-migrations` | preflight stops before backup |

### 5. Good / Base / Bad Cases

- Good: first release creates the key, runs tests, migrates, then restarts API.
- Base: later releases validate the existing key and continue idempotently.
- Bad: put provider keys in systemd env, print a key/hash/path in a report,
  overwrite malformed state, use a root shell, or include the key in backup.

### 6. Tests Required

- `bash -n` for all server scripts and the release-script regression suite.
- Assert stage ordering, marker presence, resume skip, and SSH-255 semantics.
- Before activation, review migration/downgrade and create SQLite backup.
- After activation, verify DB head/integrity, API + Worker, SNI loopback,
  secret-free APIs, zero active tasks, and clean production worktree.

### 7. Wrong vs Correct

#### Wrong

```bash
echo "$MASTER_KEY" > /tmp/model-key
sudo cp /tmp/model-key /var/lib/mediaops/
```

#### Correct

Use the fixed deployment stage: exclusive OS-random creation as `mediaops`,
permission validation, no secret output, then a completion marker.
