#!/usr/bin/env python3
"""Read-only, secret-free host inventory. Never starts or approves a staging deployment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
STAGING_PORTS = (13000, 18001)
CONTAINERS = ("tls-mongodb", "tls-backend", "tls-frontend", "tls-staging-mongodb", "tls-staging-backend", "tls-staging-frontend")


def read_command(*args: str) -> str | None:
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # Error output may contain connection details; do not forward it to the report.
    return result.stdout.strip() if result.returncode == 0 else None


def memory_mib(meminfo: str) -> dict:
    values = {}
    for line in meminfo.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in ("MemTotal:", "MemAvailable:") and parts[1].isdigit() and parts[2] == "kB":
            values[parts[0].rstrip(":")] = int(parts[1]) // 1024
    return {"total_mib": values.get("MemTotal"), "available_mib": values.get("MemAvailable")}


def port_status(socket_output: str | None) -> dict:
    if socket_output is None:
        return {str(port): "unknown" for port in STAGING_PORTS}
    listening = set()
    for line in socket_output.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[0] != "LISTEN":
            return {str(port): "unknown" for port in STAGING_PORTS}
        port = fields[3].rsplit(":", 1)[-1]
        if not port.isdigit():
            return {str(port): "unknown" for port in STAGING_PORTS}
        listening.add(int(port))
    return {str(port): "occupied" if port in listening else "free_at_check_time" for port in STAGING_PORTS}


def collect_report() -> dict:
    report = {
        "schema": "tls.staging-host-preflight.v1",
        "read_only": True,
        "decision": "manual_review_required",
        "platform": platform.system(),
        "required_tools": {name: shutil.which(name) is not None for name in ("docker", "python3", "openssl", "curl", "ss", "git")},
    }
    if report["platform"] != "Linux":
        report["host_checks"] = "run_on_the_linux_server_not_on_the_windows_workstation"
        return report

    report["cpu_count"] = os.cpu_count()
    report["load_average"] = list(os.getloadavg())
    try:
        report["memory"] = memory_mib(Path("/proc/meminfo").read_text())
        disk = shutil.disk_usage(ROOT)
        report["checkout_disk"] = {"total_gib": round(disk.total / 2**30, 1), "free_gib": round(disk.free / 2**30, 1)}
    except OSError:
        report["resource_check"] = "incomplete"

    report["staging_ports"] = port_status(read_command("ss", "-H", "-ltn"))
    status = read_command("git", "status", "--porcelain")
    report["checkout_clean"] = None if status is None else status == ""
    report["commit"] = read_command("git", "rev-parse", "--short", "HEAD")
    report["compose_version"] = read_command("docker", "compose", "version", "--short")

    # Do not combine local resource numbers with an unrelated remote Docker host.
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        report["docker_target"] = "explicit_override_not_inspected"
        return report
    endpoint = read_command("docker", "context", "inspect", "--format", '{{(index .Endpoints "docker").Host}}')
    if not endpoint or not endpoint.startswith("unix:///"):
        report["docker_target"] = "remote_or_unknown_not_inspected"
        return report
    report["docker_target"] = "local_unix_socket"
    report["docker_server_version"] = read_command("docker", "version", "--format", "{{.Server.Version}}")
    docker_root = read_command("docker", "info", "--format", "{{.DockerRootDir}}")
    if docker_root and Path(docker_root).is_absolute():
        try:
            disk = shutil.disk_usage(docker_root)
            report["docker_disk_free_gib"] = round(disk.free / 2**30, 1)
        except OSError:
            report["docker_disk_free_gib"] = None
    report["containers"] = {
        name: read_command("docker", "inspect", "--format", '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}', name)
        for name in CONTAINERS
    }
    return report


if __name__ == "__main__":
    print(json.dumps(collect_report(), indent=2))
