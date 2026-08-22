# Security Policy

## Supported versions

Security fixes are evaluated for the latest commit on `main` and the latest tagged release. Older releases may receive guidance, but are not guaranteed to receive backported fixes.

## Reporting a vulnerability

**Do not report security vulnerabilities through public GitHub Issues.**

Use this repository's GitHub **Private Security Advisory** reporting form:

1. Open the repository's **Security** tab.
2. Open **Advisories**.
3. Select **Report a vulnerability**.

Include a clear summary, affected tag or commit, safe reproduction steps, impact, and any proposed mitigation. A minimal reproduction is preferred.

Do not include credentials, private keys, tokens, production-network details, sensitive packet captures, customer data, or information about real OT/ICS equipment.

## Scope and safe testing

Amenonuboco is intended for isolated, authorized laboratory use. Reports and reproductions must not require access to production systems, real industrial equipment, or networks that you do not explicitly control. Do not perform active testing against third-party systems.

If a report could affect real OT/ICS operations, stop testing and submit only the minimum sanitized information needed for assessment through the private reporting channel.

## Response and disclosure

We aim to acknowledge a valid private report within **7 days**. We will validate the report, assess affected versions, prepare a fix, and coordinate disclosure with the reporter when appropriate.

After a fix is available, we may publish a GitHub Security Advisory and release notes describing the affected scope, remediation, and credit. Please do not disclose the vulnerability publicly until a coordinated disclosure date has been agreed.

## Non-security issues

For reproducible defects that do not create a security risk, use the [bug report template](./.github/ISSUE_TEMPLATE/bug_report.md). For product ideas, use the [feature request template](./.github/ISSUE_TEMPLATE/feature_request.md).
