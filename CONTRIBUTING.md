# Contributing to Amenonuboco

Thank you for improving Amenonuboco. Because this project models OT/ICS environments, contributions must be safe, reviewable, and reproducible. These are acceptance requirements, not suggestions.

## Safety and scope

- Use only isolated, authorized local laboratory environments. Never target production systems, real OT/ICS equipment, or networks you do not explicitly control.
- Do not commit credentials, private keys, tokens, customer data, sensitive packet captures, or environment-specific configuration.
- Describe any network-facing behavior and its intended lab-only scope in the pull request.

## Change process

- Do not push directly to `main`. Create a focused branch and submit a pull request.
- Keep one logical purpose per pull request. Do not mix feature work with unrelated formatting, dependency updates, or generated-file churn.
- State the purpose, affected components, risks, and exact validation commands in the PR description.
- Address review feedback with follow-up commits; do not weaken unrelated checks to make a change pass.

## Tests and generated artifacts

- Add or update automated tests for behavior, schema, manifest, provisioner, or scenario changes.
- Run the relevant test suite before review. The baseline check is:

  ```bash
  pip install -r requirements-dev.txt
  pytest
  ```

- Do not hand-edit generated samples, diagrams, or catalogs. Regenerate them from documented inputs and include the generation command in the PR.
- Preserve backward compatibility unless the PR explicitly documents a migration and has approval for the breaking change.

## Performance and security claims

- A performance, SLO, arrival-rate, loss, or capacity claim must include raw results, command, environment, duration, settling rule, and known limitations.
- Do not present a one-off result, an exploratory screen, or a selected configuration as a general or externally confirmed performance value.
- Link public performance claims to [`docs/performance/`](./docs/performance/); do not duplicate metrics in a README.
- Describe ambiguous results honestly. Do not remove outliers or failed trials without a documented, pre-specified reason.

## Documentation and review

- `README.md` is the English canonical README. If its meaning changes, update `README.ja.md` in the same PR.
- Keep both README files concise and link them to the same authoritative evidence and detailed documentation.
- Keep the diff minimal, ensure CI succeeds, and leave reviewers commands that reproduce the verification.

## Required checklist

- [ ] The change is safe for an isolated laboratory and contains no secrets.
- [ ] The branch and PR have one clear purpose.
- [ ] Tests were added or updated where behavior changed, and relevant tests pass.
- [ ] Generated artifacts were regenerated from documented inputs.
- [ ] Performance or security claims have reproducible evidence and limitations.
- [ ] English and Japanese README content remains semantically aligned.
- [ ] The PR body includes validation commands and results.

Contributions that do not meet these conditions will be returned for revision before review.
