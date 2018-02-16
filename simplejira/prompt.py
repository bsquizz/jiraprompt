from __future__ import print_function

import argparse

import cmd2
import prompter

from .common import editor_ignore_comments, sanitize_worklog_time
from .resource_collections import issue_collection, worklog_collection
from .wrapper import JiraWrapper


class BasePrompt(cmd2.Cmd):
    def input(self, *args, **kwargs):
        """
        Call prompter.prompt but allow for ctrl+c to cancel and return to base prompt
        """
        try:
            return prompter.prompt(*args, **kwargs)
        except KeyboardInterrupt:
            print("<cancelled>\n")
            return self.emptyline()


class Prompt(BasePrompt):
    def __init__(self, config_file):
        self.abbrev = True
        cmd2.Cmd.__init__(self, use_ipython=False)
        self.prompt = "(simplejira) "
        self.allow_cli_args = True
        self.exclude_from_help += [
            'do_load', 'do_py', 'do_pyscript', 'do_shell', 'do_set', 'do_shortcuts', 'do_history',
            'do_edit',
        ]

        self.issue_collection = None
        self._jw = JiraWrapper(config_file=config_file)
        self._jira = self._jw.jira
        print("\nWelcome to simplejira!  We hope you have a BLAST.\n")
        print("Type 'help' or '?' to get started.\n")

    # -----------------
    # ls
    # -----------------
    ls_parser = argparse.ArgumentParser()
    ls_parser.add_argument(
        '-u', '--user', type=str, default=None,
        help='Issue assignee. Default is yourself.')
    ls_parser.add_argument(
        '-s', '--sprint', type=str, default=None,
        help='Sprint name, sprint number, or "backlog". Default is current sprint.')
    @cmd2.with_argparser(ls_parser)
    def do_ls(self, args):
        issues = self._jw.search_issues(args.user, args.sprint)
        self.issue_collection = issue_collection(issues)
        self.issue_collection.print_table()

    # -----------------
    # card
    # -----------------
    card_parser = argparse.ArgumentParser()
    card_parser.add_argument('number', type=int, help="Card # from table to operate on")
    card_parser.add_argument('cmd', nargs=argparse.REMAINDER,
                             help="Command to pass on to card prompt (optional)")
    @cmd2.with_argparser(card_parser)
    def do_card(self, args):
        if not self.issue_collection:
            print("No issue table generated yet. Run 'ls' or 'search' first.")
            return
        ce = CardEditor(self._jw, self.issue_collection.select(args.number))
        if args.cmd:
            ce.onecmd(" ".join(args.cmd))
        else:
            ce.cmdloop()

    # -----------------
    # create
    # -----------------
    create_parser = argparse.ArgumentParser()
    create_parser.add_argument('-e', '--use-editor', default=False, action="store_true",
                               help="Open a text editor to fill out issue parameters")
    create_parser.add_argument('-s', '--summary', type=str, default=None, help='Issue summary')
    create_parser.add_argument('-d', '--details', type=str, default=None, help='Issue details')
    create_parser.add_argument('-c', '--component', type=str, default=None, help='Component')
    create_parser.add_argument('-l', '--label', type=str, default=None, help='Label')
    create_parser.add_argument('-a', '--assignee', type=str, default=None,
                               help='Assignee\'s user ID. Default=yourself')
    create_parser.add_argument('-S', '--sprint', type=str, default=None,
                               help='Sprint name, sprint number, or "blacklog". Default=current')
    create_parser.add_argument('-T', '--timeleft', type=str, default=None,
                               help='Estimated time remaining, e.g. "5h30m"')
    @cmd2.with_argparser(create_parser)
    def do_create(self, args):
        self._jw.create_issue(
            summary=args.summary,
            details=args.details,
            component=args.component,
            label=args.label,
            assignee=args.assignee,
            sprint=args.sprint,
            timeleft=args.timeleft,
        )

    # -----------------
    # edit
    # -----------------
    def do_edit(self, args):
        """edit card details (opens editor)"""
        print(editor_ignore_comments(self.issue_collection.to_yaml()))

    # -----------------
    # todayswork
    # -----------------
    def do_todayswork(self, args):
        """show all work log entries logged today for a generated issue table"""
        if not self.issue_collection:
            print("No issue table generated yet. Run 'ls' or 'search' first")
            return
        worklog_collection(
            self._jw.get_todays_worklogs(self.issue_collection.entries)).print_table()


class CardEditor(BasePrompt):
    def __init__(self, jira_wrapper, issue):
        self.abbrev = True
        self.cmd_shortcuts = {
            'do_1': 'do_ls',
            'do_2': 'do_logwork',
            'do_3': 'do_lswork',
            'do_4': 'do_component',
            'do_5': 'do_addlabels',
            'do_6': 'do_rmlabels',
            'do_7': 'do_status',
            'do_8': 'do_exit',
        }
        self.shortcuts.update(self.cmd_shortcuts)

        cmd2.Cmd.__init__(self, use_ipython=False)

        self.prompt = "(card {}) ".format(issue.key)
        self.exclude_from_help += ["do_quit"]

        self._jw = jira_wrapper
        self._jira = self._jw.jira
        self.issue = issue
        self._issue_collection = issue_collection([issue])

    def _print_cmds(self):
        # Print all the commands that can be run against a card
        # We build this list dynamically, based on what shortcuts are defined in self.cmd_shortcuts
        print(
            "\nEditing card {}, select what you want to do (enter number or command):".format(
                self.issue.key)
        )

        for shortcut_num in range(1, len(self.cmd_shortcuts) + 1):
            full_cmd_name = self.cmd_shortcuts["do_" + str(shortcut_num)]

            # Get the description for this cmd
            docstring = getattr(self, full_cmd_name).__doc__
            if "usage" in docstring:
                # This method is using argparse decorator, which adds additional docstring text,
                # so just pull the short description out
                docstring = docstring.split('\n')[2]

            print("  {} / {}\t -- {}".format(shortcut_num, full_cmd_name.lstrip("do_"), docstring))

        print("\nUse 'exit' to get back to main prompt\n")

    def cmdloop(self, *args, **kwargs):
        """
        Print cmd list before entering prompt mode.

        If we enter cmdloop, args weren't passed in from main prompt, so cmd list is printed for
        helpful reference.
        """
        self._print_cmds()
        cmd2.Cmd.cmdloop(self, *args, **kwargs)

    def do_exit(self, args):
        """return to main prompt"""
        return self.do_quit(args)

    # -----------------
    # logwork
    # -----------------
    log_parser = argparse.ArgumentParser()
    log_parser.add_argument('timespent', const=None, nargs='?', help="Time spent, e.g. 2h30m")
    log_parser.add_argument('comment', const=None, nargs='*', help="Comment for the work done")
    @cmd2.with_argparser(log_parser)
    def do_logwork(self, args):
        """log work"""
        if not args.timespent:
            args.timespent = self.input("Enter time spent (e.g. 2h30m):")
        if not args.comment:
            args.comment = self.input("Enter comment:")
        else:
            args.comment = " ".join(args.comment)

        self._jira.add_worklog(
            self.issue.key,
            timeSpent=sanitize_worklog_time(args.timespent),
            comment=args.comment
        )

    # -----------------
    # ls
    # -----------------
    def do_ls(self, args):
        """re-load this issue from server and show it"""
        self.issue = self._jira.issue(self.issue.key)
        issue_collection([self.issue]).print_table(show_totals=False)

    # -----------------
    # lswork
    # -----------------
    def do_lswork(self, args):
        """show work log"""
        worklogs = self._jw.get_worklog(self.issue)
        worklog_collection(worklogs).print_table()

    # -----------------
    # status
    # -----------------
    status_parser = argparse.ArgumentParser()
    status_parser.add_argument('new_status', const=None, type=str, nargs='*',
                               help="Name of new status (e.g. in progress or inprogress)")
    @cmd2.with_argparser(status_parser)
    def do_status(self, args):
        """change status"""
        avail_statuses = self._jw.get_avail_statuses(self.issue)

        args.new_status = " ".join(args.new_status)

        new_id = self._jw.get_avail_status_id(avail_statuses, args.new_status)
        if not new_id:
            if args.new_status:
                print('"{}" is an invalid status for this issue.'.format(args.new_status))

            print("Available statuses:\n\n")
            for status in avail_statuses:
                print("  {}) {}".format(status['number'], status['friendly_name']))
            while True:
                new_id = self._jw.get_avail_status_id(
                    avail_statuses,
                    self.input("Select new status (enter number from above):")
                )
                if new_id:
                    break

        self._jira.transition_issue(self.issue, new_id)

    # -----------------
    # component
    # -----------------
    component_parser = argparse.ArgumentParser()
    component_parser.add_argument('component_name', const=None, type=str, nargs=1)
    @cmd2.with_argparser(component_parser)
    def do_component(self, args):
        """set component"""
        name = " ".join(args.component_name)
        if not name:
            name = self.input("Enter component name:")

        self._jw.update_component(issue, name)

    # -----------------
    # addlabels
    # -----------------
    label_parser = argparse.ArgumentParser()
    label_parser.add_argument('label_names', const=None, type=str, nargs='*')
    @cmd2.with_argparser(label_parser)
    def do_addlabels(self, args):
        """add label(s)"""
        if not args.label_names:
            args.label_names = self.input("Enter label names (separated by space):").split(' ')
        self._jw.update_labels(self.issue, args.label_names)

    # -----------------
    # rmlabels
    # -----------------
    @cmd2.with_argparser(label_parser)
    def do_rmlabels(self, args):
        """remove label(s)"""
        if not args.label_names:
            args.label_names = self.input("Enter label names (separated by space):").split(' ')
        new_labels = [l for l in self.issue.fields.labels if l not in args.label_names]
        self._jw.update_labels(self.issue, new_labels)

    '''
    TODO
    def do_edit(self, args):
        #TODO
        self._issue_collection.updater(
            self.issue, yaml.safe_load(
                editor_ignore_comments(
                    self._issue_collection.to_yaml(
                        self.issue)))[0])

    def do_editwork(self, args):
        """edit full work log (opens editor)"""
        #TODO
        worklogs = self._jw.get_worklog(self.issue)
        collection = worklog_collection(worklogs)
        print(editor_ignore_comments(collection.to_yaml()))
    '''
