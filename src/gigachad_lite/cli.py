from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from gigachad_lite import __version__
from gigachad_lite.adapters import AGENTS
from gigachad_lite.env import current_depth, max_depth, reset_warnings
from gigachad_lite.jobs import DEFAULT_TIMEOUT, Job, JobStore
from gigachad_lite.models import list_models

EXIT_USAGE = 2
EXIT_NOT_FINISHED = 3
STATE_EXIT_CODES = {"succeeded": 0, "failed": 1, "timed_out": 124, "cancelled": 130}


def job_to_dict(job: Job) -> dict:
    data = asdict(job)
    data["job_dir"] = str(job.job_dir)
    return data


def header(job: Job) -> str:
    duration = (job.finished_at or 0) - job.started_at if job.started_at and job.finished_at else 0.0
    if job.killed_by:
        outcome = f"killed by {job.killed_by} via {job.signal}"
    else:
        outcome = f"exit {'-' if job.exit_code is None else job.exit_code}"
    return f"{job.id} {job.state} ({job.agent}/{job.model}, {duration:.1f}s, {outcome})"


def format_result(job: Job) -> str:
    lines = [header(job)]
    if job.final_message:
        lines += ["", job.final_message]
    elif job.error:
        lines += ["", f"error: {job.error}"]
    return "\n".join(lines)


def format_row(job: Job) -> str:
    return f"{job.id}  {job.state:<9}  {job.agent}/{job.model}  {job.cwd}"


def emit(job: Job, as_json: bool) -> None:
    print(json.dumps(job_to_dict(job), indent=2) if as_json else format_result(job))


def check_depth() -> str | None:
    depth, limit = current_depth(), max_depth()
    if depth >= limit:
        return f"delegation depth {depth} reached GIGACHAD_LITE_MAX_DEPTH={limit}; refusing to start a job"
    return None


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file == "-":
        return sys.stdin.read()
    return Path(args.prompt_file).read_text(encoding="utf-8")


def create_and_start(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> Job:
    job = store.create(
        agent=args.agent,
        model=args.model,
        prompt=read_prompt(args),
        cwd=Path(args.cwd).resolve(),
        mode=args.mode,
        timeout=args.timeout,
        extra_args=extra_args,
    )
    return store.start(job)


def cmd_start(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    error = check_depth()
    if error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    job = create_and_start(store, args, extra_args)
    if args.json:
        print(json.dumps({"id": job.id, "state": job.state, "job_dir": str(job.job_dir)}))
    else:
        print(job.id)
    return 0


def cmd_run(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    error = check_depth()
    if error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    job = store.wait(create_and_start(store, args, extra_args).id)
    emit(job, args.json)
    return STATE_EXIT_CODES[job.state]


def cmd_status(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    if args.job_id:
        job = store.get(args.job_id)
        print(json.dumps(job_to_dict(job), indent=2) if args.json else format_row(job))
        return 0
    return print_jobs(store.list(Path.cwd()), args.json)


def cmd_list(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    return print_jobs(store.list(None if args.all else Path.cwd()), args.json)


def print_jobs(jobs: list[Job], as_json: bool) -> int:
    if as_json:
        print(json.dumps([job_to_dict(job) for job in jobs], indent=2))
    else:
        for job in jobs:
            print(format_row(job))
    return 0


def cmd_wait(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    try:
        job = store.wait(args.job_id, args.timeout)
    except TimeoutError as exc:
        print(exc, file=sys.stderr)
        return EXIT_NOT_FINISHED
    emit(job, args.json)
    return STATE_EXIT_CODES[job.state]


def cmd_result(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    job = store.get(args.job_id)
    if not job.is_terminal:
        print(f"job {job.id} is still {job.state}", file=sys.stderr)
        return EXIT_NOT_FINISHED
    emit(job, args.json)
    return STATE_EXIT_CODES[job.state]


def cmd_logs(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    job_dir = store.get(args.job_id).job_dir

    def read(name: str) -> str:
        path = job_dir / name
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    lines = read("transcript.log").splitlines()
    stderr = read("stderr.log")
    if stderr.strip():
        lines += ["--- stderr ---", *stderr.splitlines()]
    if args.tail is not None:
        lines = lines[-args.tail :] if args.tail > 0 else []
    if lines:
        print("\n".join(lines))
    return 0


def cmd_cancel(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    job = store.cancel(args.job_id)
    print(f"cancel requested for {job.id}" if not job.is_terminal else f"{job.id} already {job.state}")
    return 0


def cmd_models(store: JobStore, args: argparse.Namespace, extra_args: list[str]) -> int:
    entries = [entry for entry in list_models() if args.agent in (None, entry["agent"])]
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    current_agent = None
    for entry in entries:
        if entry["agent"] != current_agent:
            current_agent = entry["agent"]
            print(f"{current_agent}:")
        print(f"  {'*' if entry['default'] else ' '} {entry['id']}")
    return 0


def add_job_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("job_id")


def add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="machine-readable output")


def add_launch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent", required=True, choices=AGENTS)
    parser.add_argument("--model", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="prompt text")
    source.add_argument("--prompt-file", help="file containing the prompt ('-' for stdin)")
    parser.add_argument("--cwd", default=".", help="worker working directory (default: current)")
    parser.add_argument("--mode", choices=("write", "read-only"), default="write")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="worker timeout in seconds")
    add_json(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gigachad-lite", epilog="Arguments after `--` are passed through to the worker CLI."
    )
    parser.add_argument("--version", action="version", version=f"gigachad-lite {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func, help_text in (
        ("start", cmd_start, "start a background job and print its id"),
        ("run", cmd_run, "start a job, wait, and print the result"),
    ):
        add_launch_options(sub.add_parser(name, help=help_text))
        sub.choices[name].set_defaults(func=func)

    status = sub.add_parser("status", help="show one job, or the jobs of the current directory")
    status.add_argument("job_id", nargs="?")
    add_json(status)
    status.set_defaults(func=cmd_status)

    listing = sub.add_parser("list", help="list jobs of the current directory")
    listing.add_argument("--all", action="store_true", help="list jobs from every directory")
    add_json(listing)
    listing.set_defaults(func=cmd_list)

    wait = sub.add_parser("wait", help="wait for a job and print its result")
    add_job_id(wait)
    wait.add_argument("--timeout", type=float, help="give up waiting after this many seconds")
    add_json(wait)
    wait.set_defaults(func=cmd_wait)

    result = sub.add_parser("result", help="print the result of a finished job")
    add_job_id(result)
    add_json(result)
    result.set_defaults(func=cmd_result)

    logs = sub.add_parser("logs", help="print a job's transcript and stderr")
    add_job_id(logs)
    logs.add_argument("--tail", type=int, help="only the last N lines")
    logs.set_defaults(func=cmd_logs)

    cancel = sub.add_parser("cancel", help="cancel a running job")
    add_job_id(cancel)
    cancel.set_defaults(func=cmd_cancel)

    models = sub.add_parser("models", help="list models available for delegation")
    models.add_argument("--agent", choices=AGENTS, help="only list models for this agent")
    add_json(models)
    models.set_defaults(func=cmd_models)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra_args: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, extra_args = argv[:split], argv[split + 1 :]
    reset_warnings()
    args = build_parser().parse_args(argv)
    store = JobStore()
    try:
        return args.func(store, args, extra_args)
    except KeyError as exc:
        print(f"unknown job: {exc.args[0]}", file=sys.stderr)
        return EXIT_USAGE
