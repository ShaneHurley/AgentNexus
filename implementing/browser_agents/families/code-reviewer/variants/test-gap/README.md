# Variant `test-gap` — Code Reviewer

Narrows review to **coverage and observability** vs packet acceptance criteria. Emits a test gap matrix; de-emphasizes style unless it blocks testability.

Use when craft output already looks correct but you need proof tests match behavior changes, or to audit author `TESTS_MISSING` / `SELF_REVIEW` honestly.

Packet: `browser_variant: "test-gap"`.
