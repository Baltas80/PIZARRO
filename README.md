# PIZARRO

PIZARRO is an experimental proof-of-work blockchain implementation focused on deterministic consensus, explicit chain identity, multi-node development networking, persistence, and security testing.

## Development status

**Production readiness: NO.**

This repository is being built from a clean bootstrap. Production release requires reproducible tests, real multi-node testing, security review/audit, recovery testing, and documented operational procedures.

## Security rule

Do not use this software for real funds or production networks until an independent security review and real-network test program have been completed.

## Initial scope

- deterministic block/header validation
- cumulative-work chain selection
- transaction validation with `chain_id`
- persistent local state
- development P2P network
- fork/reorganization testing
- adversarial and fuzz testing
- CI and backup/recovery checks
