"""AIGuard storage CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .manager import StorageManager
from .migrations import migrate_backend


DOCKER_TEMPLATE = """version: '3.9'
services:
  postgres:
    image: postgres:15
    container_name: aiguard-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "54329:5432"
    volumes:
      - aiguard_data:/var/lib/postgresql/data
volumes:
  aiguard_data:
"""


def cmd_init(args):
    if args.docker:
        target = Path("docker-compose.aiguard.yml")
        if target.exists():
            print(f"Refusing to overwrite existing {target}")
            return 1
        target.write_text(DOCKER_TEMPLATE)
        print(f"Docker template written to {target}")
    return 0


def cmd_project(args):
    mgr = StorageManager()
    if args.subcommand == "list":
        for p in mgr.list_projects():
            print(p)
    elif args.subcommand == "delete":
        if not args.force:
            confirm = input(f"Type the project name '{args.project}' to confirm deletion: ")
            if confirm != args.project:
                print("Aborted")
                return 1
        mgr.delete_project(args.project)
        print(f"Deleted project {args.project}")
    elif args.subcommand == "export":
        data = mgr.export_project(args.project)
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2))
            print(f"Exported to {args.output}")
        else:
            print(json.dumps(data, indent=2))
    return 0


def cmd_migrate(args):
    migrate_backend(args.to)
    print(f"Migration to {args.to} completed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiguard", description="AIGuard storage CLI")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize assets")
    p_init.add_argument("--docker", action="store_true", help="Generate docker-compose template")
    p_init.set_defaults(func=cmd_init)

    p_proj = sub.add_parser("project", help="Project operations")
    proj_sub = p_proj.add_subparsers(dest="subcommand", required=True)

    proj_list = proj_sub.add_parser("list", help="List projects")
    proj_list.set_defaults(func=cmd_project)

    proj_del = proj_sub.add_parser("delete", help="Delete project (requires confirmation)")
    proj_del.add_argument("project")
    proj_del.add_argument("--force", action="store_true", help="Skip confirmation")
    proj_del.set_defaults(func=cmd_project)

    proj_exp = proj_sub.add_parser("export", help="Export project data to JSON")
    proj_exp.add_argument("project")
    proj_exp.add_argument("--output", help="Output file path")
    proj_exp.set_defaults(func=cmd_project)

    p_mig = sub.add_parser("migrate", help="Migrate between backends")
    p_mig.add_argument("--to", choices=["sqlite", "postgres"], required=True)
    p_mig.set_defaults(func=cmd_migrate)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
