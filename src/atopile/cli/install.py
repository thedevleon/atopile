import logging
import os
import sys
from pathlib import Path

import click
import yaml
from git import Repo
import subprocess

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@click.command()
@click.argument("component_id")
def install(component_id: str):
    # Example of running a simple command like 'ls' on Unix or 'dir' on Windows
    # check that component id is valid, must start with a C and then be all numbers
    if not component_id.startswith('C'):
        log.error(f"Component id {component_id} is invalid. Aborting.")
        sys.exit(1)
    if not component_id[1:].isdigit():
        log.error(f"Component id {component_id} is invalid. Aborting.")
        sys.exit(1)

    # Get the top level of the git module the user is currently within
    repo = Repo('.', search_parent_directories=True)
    top_level_path = Path(repo.working_tree_dir)

    # Get the remote URL
    remote_url = repo.remote().url

    # Set the footprints_dir based on the remote URL
    if remote_url == "git@gitlab.atopile.io:atopile/modules.git":
        footprints_dir = top_level_path / "footprints"
    else:
        footprints_dir = top_level_path / "elec/lib/lib"


    log.info(f"Footprints directory: {footprints_dir}")

    command = ["easyeda2kicad", "--full", f"--lcsc_id={component_id}", f"--output={footprints_dir}", "--overwrite"]
    result = subprocess.run(command, capture_output=True, text=True)

    # The stdout and stderr are captured due to 'capture_output=True'
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    # Check the return code to see if the command was successful
    if result.returncode == 0:
        print("Command executed successfully")
    else:
        print("Command failed")
