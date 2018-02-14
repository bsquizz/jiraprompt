import copy
from inspect import isclass, isfunction

import attr
import yaml
from attr.validators import optional, instance_of
from jira.resources import Resource, Issue, Worklog
from prettytable import PrettyTable

from .common import iso_to_ctime_str, friendly_worklog_time, iso_to_datetime


@attr.s
class PrintableTable(object):
    """
    Represents an ordered set of entries as a table whose rows give details on each entry
    """

    entry_type = attr.ib(
        validator=lambda _, __, value: isclass(value) and isinstance(value, Resource)
    )

    entries = attr.ib(
        type=list,
        validator=lambda self, __, value: all(isinstance(v, self.entry_type) for v in value)
    )

    field_names = attr.ib(type=list)

    align_left = attr.ib(
        type=list,
        validator=lambda self, _, value: all(v in self.field_names for v in value)
    )

    row_builder = attr.ib()
    @row_builder.validator
    def test_row(self, attribute, value):
        valid = False
        if isfunction(value):
            try:
                value(self.entries[0])
                valid = True
            except Exception:
                print("ERROR: provided row_builder failed to build a row from entry 0")
                raise
        return valid

    updater = attr.ib()

    totals_row_builder = attr.ib(default=None)
    @totals_row_builder.validator
    def test_totaler(self, attribute, value):
        valid = False
        if isfunction(value):
            try:
                totals_row = value(self.entries)
                if len(totals_row) != len(self.field_names):
                    raise TypeError("ERROR: totals row does not match len of other rows")
            except Exception:
                print("ERROR: provided totals_row_builder failed validation")
                raise

            valid = True
        return valid

    sorter = attr.ib(
        default=None,
        validator=optional(lambda _, __, value: isfunction(value))
    )

    _table = attr.ib(default=None, validator=optional(instance_of(PrettyTable)))
    _table_with_totals = attr.ib(default=None, validator=optional(instance_of(PrettyTable)))


    @property
    def table(self):
        if not self._table:
            t = PrettyTable()
            t.field_names = ["no."] + self.field_names
            for idx, entry in enumerate(self.entries):
                new_row = self.row_builder(entry)
                new_row = [idx + 1] + new_row
                t.add_row(new_row)
            for field in self.align_left:
                t.align[field] = "l"

            self._table = t
        return self._table

    @property
    def table_with_totals(self):
        if self.table:
            if self.totals_row_builder:
                self._table_with_totals = copy.deepcopy(self.table)
                totals_row = self.totals_row_builder(self.entries)
                totals_row = ["total"] + totals_row
                self._table_with_totals.add_row(totals_row)
            else:
                self._table_with_totals = self.table
        return self._table_with_totals

    def __attrs_post_init__(self):
        if self.sorter:
            self.entries.sort(key=self.sorter)

    def print_table(self, show_totals=True):
        if show_totals:
            # A hacky way to add the totals row w/ a line divider before it
            table_lines = str(self.table_with_totals).splitlines()
            divider = table_lines[-1]
            table_lines.insert(-2, divider)
            print("\n".join(table_lines))
        else:
            print(self.table)

    def to_yaml(self, specific_entry=None):
        if specific_entry:
            entry_data_list = [specific_entry]
        else:
            entry_data_list = self.entries

        filtered_data_list = []
        for entry in entry_data_list:
            filtered_data = {
                self.field_names[i]: data for i, data in enumerate(self.row_builder(entry))
            }
            filtered_data_list.append(filtered_data)
        return yaml.safe_dump(filtered_data_list, default_flow_style=False)

    def select(self, number):
        return self.entries[number - 1]

def create_issue_table(issue_list):
    def row_builder(issue):
        f = issue.fields
        # Truncate the summary if too long
        summary = f.summary[:49] + "..." if len(f.summary) > 50 else f.summary
        row = [
            issue.key,
            summary,
            f.components[0].name if len(f.components) else "",
            f.labels[0] if len(f.labels) else "",
            f.status.name,
            friendly_worklog_time(f.timespent),
            friendly_worklog_time(f.timeestimate),
        ]
        return row

    def updater(issue, new_data):
        '''
        issue.update(
            key=new_data['key'],
            summary=new_data['summary'],
            fields={
                'components': [{'name': new_data['component']}],
                'labels': [new_data['label']],
                'status': {'name': new_data['status']},
                'timespent': new_data['timeSpent'],
                'timeestimate': new_data['timeEstimate']
            }
        )
        TODO: transition status
        '''

    def totals_row_builder(issue_list):
        total_timespent = friendly_worklog_time(
            sum(issue.fields.timespent for issue in issue_list if issue.fields.timespent)
        )
        total_timeest = friendly_worklog_time(
            sum(issue.fields.timeestimate for issue in issue_list if issue.fields.timeestimate)
        )
        return ["", "", "", "", "", total_timespent, total_timeest]

    return PrintableTable(
        entry_type=Issue,
        entries=issue_list,
        field_names=["key", "summary", "component", "label", "status", "timeSpent", "timeLeft"],
        align_left=["summary"],
        row_builder=row_builder,
        updater=updater,
        totals_row_builder=totals_row_builder,
        sorter=lambda issue: issue.fields.status.name
    )


def create_worklog_table(worklog_list):
    def row_builder(wl):
        # Truncate comment if too long
        comment = wl.comment[:79] + "..." if len(wl.comment) > 80 else wl.comment
        row = [friendly_worklog_time(wl.timeSpentSeconds), iso_to_ctime_str(wl.started), comment]
        return row

    def totals_row_builder(wl_list):
        total_timespent = friendly_worklog_time(sum(wl.timeSpentSeconds for wl in wl_list))
        return [total_timespent, "", ""]

    return PrintableTable(
        entry_type=Worklog,
        entries=worklog_list,
        field_names=["timeSpent", "started", "comment"],
        align_left=["comment"],
        row_builder=row_builder,
        updater=None,
        totals_row_builder=totals_row_builder,
        sorter=lambda worklog: iso_to_datetime(worklog.started)
    )
