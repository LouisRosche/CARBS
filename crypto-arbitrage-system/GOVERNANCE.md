# Project Governance

## Project Status

**Status:** Active Development
**Version:** 1.0.0
**Maturity:** Stable (initial release)
**Primary Maintainer:** Louis Rosche (@LouisRosche)

---

## Project Goals

### Primary Goals

1. **Education**: Provide a reference implementation of production-grade arbitrage trading system
2. **Research**: Enable academic and personal research into cryptocurrency arbitrage strategies
3. **Safety-First**: Demonstrate proper risk management and security practices in trading systems

### Non-Goals

- **Not a get-rich-quick scheme**: No guarantees of profitability
- **Not financial advice**: Educational and research purposes only
- **Not enterprise-ready out-of-box**: Requires customization for specific use cases

---

## Maintenance Commitment

### Current Commitment (as of 2025-12-17)

- **Security updates**: High priority, addressed within 72 hours
- **Critical bugs**: Addressed within 1 week
- **Feature requests**: Evaluated on case-by-case basis
- **Documentation**: Maintained and kept current
- **Dependencies**: Updated quarterly for security, annually for features

### Response Times (Target)

| Issue Type | Response Time | Resolution Time |
|------------|---------------|-----------------|
| Security vulnerability | 24 hours | 72 hours |
| Critical bug (system crash) | 48 hours | 1 week |
| Major bug (functionality broken) | 1 week | 2 weeks |
| Minor bug | 2 weeks | 1 month |
| Feature request | 1 week (evaluation) | Variable |
| Documentation | 1 week | 2 weeks |

**Note:** These are targets, not guarantees. This is a volunteer-maintained project.

---

## Decision-Making Process

### Maintainer Authority

The primary maintainer (Louis Rosche) has final decision authority on:
- Code merges
- Release timing
- Project direction
- Breaking changes

### Community Input

Community input is valued through:
- GitHub Issues for bug reports and feature requests
- GitHub Discussions for general questions and ideas
- Pull Requests for code contributions
- Issue voting (👍 reactions) to gauge interest

### Major Decisions

For major decisions (breaking changes, architecture shifts, license changes):
1. **Proposal**: Maintainer or contributor opens Discussion
2. **Community Feedback**: 2-week minimum feedback period
3. **Decision**: Maintainer makes final decision considering feedback
4. **Announcement**: Decision announced with rationale

---

## Contribution Process

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Acceptance Criteria for Pull Requests

✅ **Will be accepted** if:
- Solves a real problem
- Includes tests
- Passes CI (lint, type-check, tests, security)
- Documented (code comments, docstrings, README/docs updated)
- Follows project coding standards
- Reviewed and approved by maintainer

❌ **Will be rejected** if:
- Breaks existing functionality without good reason
- Lacks tests
- Poorly documented
- Violates security best practices
- Out of scope for project goals
- Code quality below project standards

### Stale Pull Requests

PRs without activity for 60 days may be closed with a note:
- "Closing due to inactivity. Please reopen if you'd like to continue this work."
- Can be reopened if contributor becomes active again

---

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):
- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (1.X.0): New features, backwards-compatible
- **PATCH** (1.0.X): Bug fixes, backwards-compatible

### Release Cadence

- **No fixed schedule**: Releases when meaningful changes accumulated
- **Security patches**: Released as soon as validated
- **Estimated**: 1-3 releases per quarter (highly variable)

### Release Checklist

Before each release:
- [ ] All tests pass
- [ ] CHANGELOG.md updated
- [ ] Version bumped in setup.py, __init__.py
- [ ] Security scan clean
- [ ] Documentation updated
- [ ] Tagged in git: `git tag v1.X.X`
- [ ] GitHub Release created with notes

---

## Conflict Resolution

### Code Review Disagreements

1. Reviewer requests changes
2. Author discusses and either implements or provides rationale
3. If unresolved, maintainer makes final decision
4. Maintainer's decision is final

### Community Disagreements

1. Respectful discussion in appropriate forum (Issue, Discussion, PR)
2. If heated, moderator (maintainer) will request cooling-off period
3. If behavior violates Code of Conduct, see enforcement process
4. Goal: Technical merit-based decisions, not politics

---

## Project Succession

### Bus Factor Risk

**Current bus factor: 1** (single primary maintainer)

### Succession Plan

If primary maintainer is unable to continue:

1. **Short-term (<3 months unavailable)**:
   - Project enters "maintenance mode"
   - Security updates only
   - PRs reviewed on return

2. **Long-term (>3 months unavailable)**:
   - Maintainer will announce unavailability in README
   - Community members can fork and continue development
   - Maintainer may transfer ownership to trusted contributor

3. **Permanent departure**:
   - Maintainer will clearly announce in README
   - Project may be archived or transferred
   - Forks encouraged to continue development

### Co-Maintainer Criteria

To reduce bus factor, co-maintainers may be added who demonstrate:
- **Technical competence**: 10+ merged PRs of high quality
- **Commitment**: Active for 6+ months
- **Judgment**: Good decision-making in reviews and discussions
- **Alignment**: Understands and supports project goals
- **Trust**: Earned through sustained positive contribution

---

## Project Archival Conditions

This project will be archived if:
1. **No activity** for 12+ months (no commits, no maintainer response)
2. **Maintainer departure** without successor
3. **Technology obsolescence** (Python EOL, exchanges deprecated)
4. **Fundamental business model broken** (arbitrage opportunities vanish)

### Archival Process

1. README updated with **"⚠️ ARCHIVED"** banner
2. Explanation of why archived
3. Pointers to active forks (if any)
4. Repository set to read-only

---

## Funding and Sponsorship

### Current Funding

**No external funding.** This is a volunteer project.

### Future Sponsorship

If sponsorship is offered:
- **Transparency**: All sponsorships publicly disclosed
- **No influence on roadmap**: Sponsors do not get special features
- **Security audits**: Funds may be used for professional security audits
- **Infrastructure**: May be used for CI/CD costs, hosting, etc.
- **No ads/tracking**: Will not add advertising or tracking for funding

---

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

---

## License

This project is licensed under the MIT License. All contributions must be compatible with this license.

---

## Contact

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: General questions, ideas
- **Security Issues**: See [SECURITY.md](SECURITY.md) for responsible disclosure
- **Email**: (Primary maintainer may provide if desired)

---

## Changes to Governance

This governance document may be updated by the primary maintainer with:
1. Announcement in GitHub Discussions
2. 2-week feedback period
3. Update committed with summary of changes

**Last Updated:** 2025-12-17
**Version:** 1.0
