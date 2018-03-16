from __future__ import print_function

import argparse
import difflib
import os
import sys

import prompter
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO

from .common import editor_preserve_comments
from .prompt import MainPrompt

from .res import get_default_config, get_ascii_art

CONFIG_FILE = os.path.expanduser('~/.simplejira.yml')


def _create_config_file():
    new_config = editor_preserve_comments(get_default_config())

    filename = prompter.prompt(
        "Enter path for saving config", default=CONFIG_FILE)
    print("Writing config to {}".format(filename))
    with open(filename, 'w') as f:
        f.write(new_config)
    os.chmod(filename, 0o600)
    return filename


def _setup_config():
    filename = None
    print("It looks like you have no config created.\n")
    if prompter.yesno("Create one now?"):
        filename = _create_config_file()
    return filename


def _compare_config(filename):
    """
    Compare components/labels map in template config to that of current config

    Prompt user to update if diffs are noticed.

    Uses ruamel so comments are preserved.
    """
    yml = YAML()

    with open(filename, 'r') as f:
        current_cfg = yml.load(f)

    # Bail here if the option to sync defaults is explicitly disabled
    if current_cfg.get('sync_to_defaults', None) is False:
        return

    default_cfg = yml.load(get_default_config())

    current_map = current_cfg['components_labels_map']
    default_map = default_cfg['components_labels_map']

    if current_map != default_map:
        # convert these values out of their ruamel objects into strings
        # so we can run them through difflib
        str1 = StringIO()
        str2 = StringIO()
        yml.dump(current_map, str1)
        yml.dump(default_map, str2)

        # Run the diff on the 2 blocks of text, and strip out
        # the '- ' from the YAML list entries for easier readabilty
        diffs = difflib.unified_diff(
            str1.getvalue().replace('- ', '   ').splitlines(),
            str2.getvalue().replace('- ', '   ').splitlines(),
            fromfile='current', tofile='defaults', n=9999
        )

        print(
            '{}\n\n'
            'Diffs were found in the components_labels_map between your '
            'config and the default config in the above '
            'areas'.format('\n'.join(diffs))
        )

        print(
            '\nThis check can be disabled by adding \'sync_to_defaults: false\''
            ' to your config file.\n'
        )
        yes = prompter.yesno(
            'Do you want to update your config to match defaults now?'
        )

        if yes:
            current_cfg['components_labels_map'].update(default_map)
            with open(filename, 'w') as f:
                yml.dump(current_cfg, f)


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
        print('No valid config file found.')
        sys.exit(0)

    # print welcome msg
    print(get_ascii_art())

    _compare_config(filename)

    sys.argv = sys.argv[:1] + unknown_args
    MainPrompt(config_file=filename).cmdloop()


if __name__ == '__main__':
    main()
