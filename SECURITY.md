# Security Policy

PIZARRO is experimental software and is **not production-ready**.

## Reporting

Do not disclose an unpatched vulnerability in a public issue. Report security findings privately to the repository owner through an appropriate private GitHub security channel.

## Release gate

A production release requires, at minimum:

1. deterministic consensus tests;
2. real multi-process/multi-node network tests;
3. fork and reorganization tests;
4. persistence and recovery tests;
5. adversarial input and fuzz testing;
6. dependency and supply-chain review;
7. independent security review/audit;
8. documented recovery and backup procedures.

Passing CI alone never constitutes production approval.
