"""
run_demo.py

`python3 run_demo.py` and, per the brief: Kafka starts, simulators start,
agents start, events flow, traces appear, and a report is generated at the
end -- automatically, no manual setup beyond having Docker available.

Every process below is a REAL, separate OS process (subprocess.Popen), not
a thread or an in-process shortcut -- everything really does talk only
through Kafka, exactly as required. This script's only job is process
lifecycle: start them, let them run for --duration seconds (or until
Ctrl+C), stop them cleanly, then call failure_report.py.

Usage:
    python3 run_demo.py                      # 60s demo run, default scenario mix
    python3 run_demo.py --duration 120
    python3 run_demo.py --skip-infra          # Kafka/Redis already running, just run the demo
    python3 run_demo.py --recreate-topics     # wipe and recreate demo topics first
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import harness_config as cfg
import event_logger

HARNESS_DIR = cfg.HARNESS_DIR
PY = sys.executable


def sh(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)


def wait_for_broker(timeout_s: float = 60.0) -> bool:
    from confluent_kafka.admin import AdminClient
    admin = AdminClient({"bootstrap.servers": cfg.KAFKA_BOOTSTRAP_SERVERS})
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            admin.list_topics(timeout=3)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return False


def start_infra() -> None:
    if shutil.which("docker") is None:
        print("docker not found on PATH -- skipping infra startup. If Kafka/Redis are already "
              "running elsewhere, pass --skip-infra. Otherwise install Docker and re-run.",
              file=sys.stderr)
        return
    compose_files = ["-f", str(cfg.DEV_ENV_COMPOSE), "-f", str(HARNESS_DIR / "docker-compose.yml")]
    sh(["docker", "compose", *compose_files, "up", "-d"], cwd=str(HARNESS_DIR))


def stop_infra() -> None:
    if shutil.which("docker") is None:
        return
    compose_files = ["-f", str(cfg.DEV_ENV_COMPOSE), "-f", str(HARNESS_DIR / "docker-compose.yml")]
    sh(["docker", "compose", *compose_files, "down"], cwd=str(HARNESS_DIR))


def spawn(*args: str) -> subprocess.Popen:
    cmd = [PY, *args]
    print(f"spawning: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=str(HARNESS_DIR))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=60.0, help="seconds to let the demo run")
    parser.add_argument("--skip-infra", action="store_true", help="assume Kafka/Redis already running")
    parser.add_argument("--recreate-topics", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--data-source", choices=["random", "data-engine"], default="random",
                         help="'random': this harness's own 3 simulators. "
                              "'data-engine': one process driven by Sentinel_Data_Engine "
                              "(requires DATA_ENGINE_ROOT -- see README).")
    args = parser.parse_args()

    print("=" * 70)
    print("SENTINEL Integration Demo")
    print("=" * 70)

    event_logger.reset_db()
    print("[1/6] Trace store reset.")

    if not args.skip_infra:
        print("[2/6] Starting infra (Kafka, Redis, Postgres) via docker compose...")
        start_infra()
        print("      Waiting for broker to accept connections...")
        if not wait_for_broker():
            print("FAILED: Kafka broker never became reachable. Check `docker compose logs kafka`.",
                  file=sys.stderr)
            return 1
    else:
        print("[2/6] --skip-infra set, assuming Kafka/Redis already running.")
        if not wait_for_broker(timeout_s=10):
            print(f"FAILED: cannot reach Kafka at {cfg.KAFKA_BOOTSTRAP_SERVERS}.", file=sys.stderr)
            return 1

    print("[3/6] Ensuring topics exist...")
    reset_args = [PY, "reset_topics.py"] + (["--recreate"] if args.recreate_topics else [])
    result = sh(reset_args, cwd=str(HARNESS_DIR))
    if result.returncode != 0:
        print("FAILED: topic setup failed.", file=sys.stderr)
        return 1

    print("[4/6] Starting agent workers and simulators as real subprocesses...")
    procs: list[subprocess.Popen] = []
    try:
        procs.append(spawn("environmental_agent_worker.py"))
        procs.append(spawn("zone_agent_worker.py"))
        time.sleep(2.0)  # let both agents finish subscribing before traffic starts
        if args.data_source == "data-engine":
            procs.append(spawn("fake_data_engine_simulator.py"))
        else:
            procs.append(spawn("fake_sensor_simulator.py"))
            procs.append(spawn("fake_worker_simulator.py"))
            procs.append(spawn("fake_permit_simulator.py"))
        sh([PY, "fake_equipment_simulator.py"], cwd=str(HARNESS_DIR))  # logs the gap and exits immediately

        print(f"[5/6] Demo running for {args.duration}s. Live view: "
              f"`python3 pipeline_visualizer.py` in another terminal.")
        print("      Ctrl+C to stop early.")
        try:
            time.sleep(args.duration)
        except KeyboardInterrupt:
            print("\nStopping early on Ctrl+C...")
    finally:
        print("[6/6] Stopping subprocesses...")
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    if not args.no_report:
        sh([PY, "failure_report.py"], cwd=str(HARNESS_DIR))
        print(f"\nReport: {cfg.REPORT_OUTPUT_PATH}")
        print("Per-trace detail: python3 trace_dashboard.py --list")

    return 0


if __name__ == "__main__":
    sys.exit(main())
