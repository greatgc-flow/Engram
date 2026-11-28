"""Prove a native PostgreSQL/pgvector pair with synthetic data and a limited token."""
import argparse
from contextlib import contextmanager
import ctypes
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
from tempfile import TemporaryDirectory
import time
import winreg

LOOPBACK = "127.0.0.1"
ADMIN = "probe_owner"
APP = "probe_app"
DATABASE = "probe_memory"


def service_names():
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services") as key:
        count, _, _ = winreg.QueryInfoKey(key)
        return {winreg.EnumKey(key, index) for index in range(count)}


def child_env():
    return {key: value for key, value in os.environ.items() if not key.upper().startswith("PG")}


def command(binaries, name, *args, env=None, sql=None, report_error=True, timeout=45):
    result = subprocess.run(
        [str(binaries / (name + ".exe")), *map(str, args)],
        env=env if env is not None else child_env(), input=sql, text=True, encoding="utf-8",
        capture_output=True, timeout=timeout, check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() if report_error else "redacted setup command"
        raise RuntimeError(f"{name} exited {result.returncode}: {detail}")
    return result.stdout.strip()


def client_env(port, password):
    return {**child_env(), "PGHOST": LOOPBACK, "PGPORT": str(port),
            "PGPASSWORD": password, "PGCONNECT_TIMEOUT": "2", "PGCLIENTENCODING": "UTF8",
            "PGSSLMODE": "disable"}


def query(binaries, env, user, database, sql, *, sensitive=False):
    return command(binaries, "psql", "-X", "-w", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                   "-U", user, "-d", database, "-f", "-", env=env, sql=sql,
                   report_error=not sensitive)


def reserve_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind((LOOPBACK, 0))
        return candidate.getsockname()[1]


@contextmanager
def server(binaries, cluster, password):
    port = reserve_port()
    log = cluster.parent / (cluster.name + ".log")
    with log.open("wb") as output:
        owned = subprocess.Popen(
            [str(binaries / "postgres.exe"), "-D", str(cluster), "-h", LOOPBACK, "-p", str(port)],
            env=child_env(), stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
        )
        env = client_env(port, password)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and owned.poll() is None:
                try:
                    identity = query(binaries, env, ADMIN, "postgres",
                                     "SELECT current_setting('data_directory');")
                except RuntimeError:
                    time.sleep(0.25)
                    continue
                if not cluster.samefile(identity):
                    raise RuntimeError("A different cluster answered the readiness query.")
                break
            else:
                raise RuntimeError(f"Owned PostgreSQL cluster failed to start: {log.read_bytes()[-4000:]!r}")
            yield port
        finally:
            if owned.poll() is None:
                try:
                    command(binaries, "pg_ctl", "-D", cluster, "-m", "fast", "-w", "-t", "20", "stop")
                    owned.wait(timeout=5)
                finally:
                    if owned.poll() is None:
                        owned.terminate()
                        owned.wait(timeout=10)


def initialize(binaries, root, password_file):
    command(binaries, "initdb", "-D", root, "-U", ADMIN, "--auth=scram-sha-256",
            "--encoding=UTF8", "--locale=C", f"--pwfile={password_file}", timeout=90)


def create_database(binaries, env, password):
    query(binaries, env, ADMIN, "postgres",
          f"CREATE ROLE {APP} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{password}';\n"
          f"CREATE DATABASE {DATABASE};", sensitive=True)


def verify(binaries, port, app_password):
    app_env = client_env(port, app_password)
    result = query(binaries, app_env, APP, DATABASE, """
        SELECT id FROM memories ORDER BY embedding <-> '[1,0,0]'::vector, id LIMIT 2;
        SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole FROM pg_roles
        WHERE rolname = current_user;
        SELECT NOT has_schema_privilege(current_user, 'owner_only', 'USAGE');
        SELECT NOT has_table_privilege(current_user, 'memories', 'INSERT');
        SELECT extversion FROM pg_extension WHERE extname = 'vector';
        SELECT inet_server_addr() = '127.0.0.1'::inet;
    """).splitlines()
    if result != ["1", "3", "t", "t", "t", "0.8.7", "t"]:
        raise RuntimeError(f"Unexpected vector query or role evidence: {result!r}")


def probe(binaries, workspace, postgres_version):
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("A Windows Basic User token is required.")
    version = command(binaries, "postgres", "--version")
    if version != f"postgres (PostgreSQL) {postgres_version}":
        raise RuntimeError(f"Unexpected server version: {version}")
    before = service_names()
    source, destination = workspace / "source data", workspace / "restored data"
    backup = workspace / "synthetic.pgdump"
    admin_password, app_password = secrets.token_hex(32), secrets.token_hex(32)
    password_file = workspace / "bootstrap-password.txt"
    try:
        password_file.write_text(admin_password + "\n", encoding="ascii")
        initialize(binaries, source, password_file)
        initialize(binaries, destination, password_file)
    finally:
        password_file.unlink(missing_ok=True)

    with server(binaries, source, admin_password) as port:
        admin_env = client_env(port, admin_password)
        create_database(binaries, admin_env, app_password)
        query(binaries, admin_env, ADMIN, DATABASE, f"""
            CREATE EXTENSION vector;
            CREATE SCHEMA owner_only;
            CREATE TABLE owner_only.restricted (id integer);
            CREATE TABLE memories (id integer PRIMARY KEY, embedding vector(3) NOT NULL);
            INSERT INTO memories VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0.8,0.2,0]');
            GRANT SELECT ON memories TO {APP};
        """)
        verify(binaries, port, app_password)
        command(binaries, "pg_dump", "-w", "-U", ADMIN, "-Fc", "-f", backup, DATABASE,
                env=admin_env)
    with server(binaries, source, admin_password) as port:
        verify(binaries, port, app_password)
    with server(binaries, destination, admin_password) as port:
        admin_env = client_env(port, admin_password)
        create_database(binaries, admin_env, app_password)
        command(binaries, "pg_restore", "-w", "-U", ADMIN, "--exit-on-error", "--no-owner",
                "-d", DATABASE, backup, env=admin_env)
        verify(binaries, port, app_password)
    if service_names() != before:
        raise RuntimeError("Windows service inventory changed during the probe.")
    with backup.open("rb") as stream:
        dump_digest = file_digest(stream, sha256).hexdigest()
    return {"status": "PASS", "effective_admin": False, "postgresql": postgres_version,
            "pgvector": "0.8.7", "listener": LOOPBACK, "service_inventory_equal": True,
            "role_isolation": "PASS", "restart": "PASS", "fresh_cluster_restore": "PASS",
            "fixture_dump_sha256": dump_digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binaries", type=Path)
    parser.add_argument("postgres_version")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="engram pgvector ") as temporary:
        result = probe(args.binaries.resolve(strict=True), Path(temporary).resolve(), args.postgres_version)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
