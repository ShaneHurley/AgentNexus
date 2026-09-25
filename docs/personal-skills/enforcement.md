# Hard vs soft enforcement

| Surface | Write / side effect | Soft or hard | Authority |
|---------|---------------------|--------------|-----------|
| Personal skills / router | Drafts, checklists, emails | Soft | User accepts; skill must not claim persistence |
| `personal-store` CLI | Append/apply/export/delete career files | Soft-confirm | Visible diff + explicit confirmation; schema validate |
| `writing-lint` | Em dash / repetition / structure | Deterministic soft gate | Fail-closed: `writing_result.status` cannot be `COMPLETE` if lint fails (documented exemptions only) |
| Browser everyday | Drafts only | Soft | `persisted: false`; never writes career store |
| Agent Dashboard | Observe DC/RF | Soft | No personal-data view in v1 |
| Cursor/IDE hooks | Assist / warn | Soft | Not authoritative |
| Daily Coder / RF mutations | Repo writes, tools | Hard | PolicyGateway + ide-bridge + ledger |
| Changing skill library / schemas in git | Code change | Hard | `daily-coder` via ide-bridge |

Soft ≠ hard: hooks assist only. Audited engineering writes go through [`agents/ide/bridge`](../../agents/ide/bridge/README.md).
