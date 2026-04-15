from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def detect_codex_home(override: str = "") -> Path:
    if override:
        return Path(override).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def copy_item(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install job-apply-assistant into the local Codex skills directory.")
    parser.add_argument("--codex-home", default="", help="Optional CODEX_HOME override.")
    parser.add_argument("--skill-name", default="job-apply-assistant", help="Installed skill directory name.")
    parser.add_argument("--force", action="store_true", help="Replace an existing installed skill directory.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    install_items = [
        "SKILL.md",
        "agents",
        "examples",
        "references",
        "scripts",
    ]

    codex_home = detect_codex_home(args.codex_home)
    skills_dir = codex_home / "skills"
    target_root = skills_dir / args.skill_name

    if target_root.exists():
        if not args.force:
            raise SystemExit(
                f"Target already exists: {target_root}\n"
                "Re-run with --force to replace the existing installation."
            )
        shutil.rmtree(target_root)

    target_root.mkdir(parents=True, exist_ok=True)

    for name in install_items:
        src = skill_root / name
        if not src.exists():
            raise SystemExit(f"Missing expected install item: {src}")
        copy_item(src, target_root / name)

    print(f"Installed skill to: {target_root}")


if __name__ == "__main__":
    main()
