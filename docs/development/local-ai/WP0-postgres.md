# WP0 PostgreSQL and pgvector feasibility

T13 / POC-05 tests the proposed Windows binary pair in a disposable native runner. The fixture uses neither an installer nor Windows service registration. PostgreSQL is CPU-only and independent of accelerator inventory or model selection.

| Input | Candidate |
| --- | --- |
| PostgreSQL | EDB x64 PostgreSQL 17.12 binary ZIP, publisher package 17.12-2, 386,262,342 bytes. The [published SHA-256](https://get.enterprisedb.com/postgresql/postgresql-17.12-2-windows-x64-binaries.zip.sha256) matched the downloaded bytes. The ZIP contains the server DLLs, executable tools, headers and import library. |
| pgvector | v0.8.7, commit `f37c13f68b57d2c3472b2214fbcff699d6d34876`. Compile with the pinned PostgreSQL headers and import library, using the upstream Windows Makefile and the runner's x64 compiler. |
| Scope | Only the required binary, include, library, share and notice paths are extracted from the published ZIP. The build writes its extension into this private PostgreSQL copy. The database test runs with a Windows Basic User token, two separate, temporary clusters and synthetic vector rows. It uses loopback SCRAM and an application role with limited privileges. |

The acceptance probe checks administrator status, exact server and extension versions, known vector distance order, SQL application-role isolation, restart and logical dump/restore into a fresh cluster, and an unchanged Windows service inventory. It closes both owned servers and retains only a non-sensitive test receipt in the job log. The dump has no Engram, PeerHub or private user data.

[Native Windows job 140939976804](https://github.com/greatgc-flow/Engram/actions/runs/46132318927/job/140939976804) passed against commit `8eafc49a58a82e4b28bb1cd0275dc5fe3b0c61f9`. The effective token was non-admin, PostgreSQL reported 17.12, pgvector reported 0.8.7, the listener was 127.0.0.1, and the role, restart, fresh-cluster restore and service-inventory assertions passed. An extension build and SQL fixture qualify only this artifact pair. Redistribution, offline packaged delivery, database file ACLs for multi-user workstations, Hindsight local-provider behavior, Knowledge Bank provenance and Engram coordinated backup remain open. No production memory profile is enabled.

[PostgreSQL Windows distribution](https://www.postgresql.org/download/windows/) · [pgvector Windows build](https://github.com/pgvector/pgvector/tree/f37c13f68b57d2c3472b2214fbcff699d6d34876#windows).
