# Credential exposure remediation checklist

This checklist records the response for the credential-like value found in historical request material. The value is intentionally omitted. Its validity has not been tested.

- [ ] Credential owner identifies the provider/account without copying the value into an issue, log, or chat.
- [ ] Owner revokes or rotates the credential through the provider's trusted account interface.
- [ ] Owner confirms revocation and checks recent provider activity for unexpected use.
- [ ] Search current files, Git history, generated artifacts, and backups using redacted findings only; do not print matches.
- [ ] Replace retained examples with an environment-variable or secret-store reference.
- [ ] Record completion date and credential category here without recording the secret or a reversible fingerprint.
- [ ] Decide separately whether any history rewrite is needed; do not rewrite Git history as part of this checklist.

Status: owner verification and revocation are pending.
