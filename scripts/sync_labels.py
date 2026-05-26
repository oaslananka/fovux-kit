#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def main() -> None:
    repos = os.environ["REPOS"].split()
    labels = yaml.safe_load(Path(".github/labels.yml").read_text()) or []

    for repo in repos:
        for label in labels:
            name = label["name"]
            color = str(label.get("color", "ededed")).lstrip("#")
            description = label.get("description", "")
            result = gh("api", f"repos/{repo}/labels/{name}", check=False)
            if result.returncode == 0:
                gh(
                    "api",
                    "-X",
                    "PATCH",
                    f"repos/{repo}/labels/{name}",
                    "-f",
                    f"new_name={name}",
                    "-f",
                    f"color={color}",
                    "-f",
                    f"description={description}",
                )
            else:
                gh(
                    "api",
                    "-X",
                    "POST",
                    f"repos/{repo}/labels",
                    "-f",
                    f"name={name}",
                    "-f",
                    f"color={color}",
                    "-f",
                    f"description={description}",
                )


if __name__ == "__main__":
    main()
