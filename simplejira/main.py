from __future__ import print_function

import argparse
import os
import sys

import prompter
import yaml

from .common import editor_ignore_comments, PkgResource
from .prompt import Prompt

CONFIG_FILE = os.path.expanduser('~/.simplejira.yml')


def _create_config_file():
    new_config = editor_ignore_comments(PkgResource.read(PkgResource.DEFAULT_CONFIG))

    filename = prompter.prompt("Enter path for saving config", default=CONFIG_FILE)
    print("Writing config to {}".format(filename))
    with open(filename, 'w') as f:
        f.write(new_config)
    return filename


def _setup_config():
    filename = None
    print("It looks like you have no config created.\n")
    if prompter.yesno("Create one now?"):
        filename = _create_config_file()
    return filename


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file', type=str)
    args, unknown_args = parser.parse_known_args()
    if args.config_file:
        filename = args.config_file
    elif os.path.exists(CONFIG_FILE):
        filename = CONFIG_FILE
    else:
        filename = _setup_config()

    if not filename:
        print("No valid config file found.")
        sys.exit(0)

    # print welcome msg
    print(PkgResource.read(PkgResource.ASCII_ART))

    sys.argv = sys.argv[:1] + unknown_args
    Prompt(config_file=filename).cmdloop()


if __name__ == '__main__':
    main()
