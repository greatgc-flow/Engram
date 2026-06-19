"""Quick diagnostic: test agy subprocess capture behavior."""
import subprocess, sys, time, shutil

agy = shutil.which("agy")
print(f"agy path: {agy}")

cmd = [agy, "--dangerously-skip-permissions", "-p", "say: OK"]
print(f"cmd: {cmd}")

t0 = time.monotonic()
proc = subprocess.Popen(
    cmd,
    stdin=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
print(f"PID: {proc.pid}, spawned in {time.monotonic()-t0:.2f}s")

try:
    out, err = proc.communicate(timeout=10)
    elapsed = time.monotonic() - t0
    print(f"Exited in {elapsed:.2f}s, returncode={proc.returncode}")
    print(f"stdout ({len(out)} bytes): {out[:500]}")
    print(f"stderr ({len(err)} bytes): {err[:500]}")
except subprocess.TimeoutExpired:
    elapsed = time.monotonic() - t0
    print(f"TimeoutExpired after {elapsed:.2f}s (process still running)")
    proc.kill()
    out, err = proc.communicate()
    print(f"After kill - stdout ({len(out)} bytes): {out[:500]}")
    print(f"After kill - stderr ({len(err)} bytes): {err[:500]}")
