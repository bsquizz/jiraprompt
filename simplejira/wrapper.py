from __future__ import print_function

import attr
import yaml
from jira import JIRA

from .common import iso_time_is_today, sanitize_worklog_time


class JiraClientOverride(JIRA):
    def _create_kerberos_session(self, *args, **kwargs):
        """
        Little hack to get auth cookies from JIRA when using kerberos, otherwise
        queries to other URLs hit a 401 and are not handled properly for some
        reason

        https://stackoverflow.com/questions/21578699/jira-rest-api-and-kerberos-authentication
        """
        super(JiraClientOverride, self)._create_kerberos_session(*args, **kwargs)
        print("Attempting to authticate with kerberos...")
        r = self._session.get("{}/step-auth-gss".format(self._options['server']))
        if r.status_code == 200:
            print("Authenticated successfully")


class IssueFields(object):
    """
    Class which holds builders for various jira field data

    Build multiple field sections and then pass in the entire kwarg without having to remember the
    json variations.
    Example:

    f = IssueFields().labels(['something1', 'something2']).component("LOL").summary("my summary")
    issue.update(**f.kwarg)
    """
    def __init__(self):
        self._base = {'fields': {}}
        self.fields = self._base['fields']

    @property
    def kwarg(self):
        return self._base

    def timetracking(self, remaining, original):
        self.fields.update({
            'timetracking': {
                'remainingEstimate': sanitize_worklog_time(remaining),
                'originalEstimate': sanitize_worklog_time(original)
            }
        })
        return self

    def component(self, component_name):
        self.fields.update({
            'components': [
                {'name': component_name}
            ]
        })
        return self

    def labels(self, label_list):
        self.fields.update({
            'labels': label_list
        })
        return self

    def summary(self, summary_text):
        self.fields.update({
            'summary': summary_text
        })
        return self

    def assignee(self, name):
        self.fields.update({
            'assignee': {
                'name': name
            }
        })
        return self


@attr.s
class JiraWrapper(object):
    """
    Provides utils for storing config and interacting with python-jira
    """
    config_file = attr.ib()
    config = attr.ib(default=attr.Factory(dict))
    _jira = attr.ib(default=None)
    _current_sprint_id = attr.ib(default=0)

    def load_config(self, filename):
        with open(filename, 'r') as f:
            self.config = yaml.safe_load(f)

    def __attrs_post_init__(self):
        self.load_config(self.config_file)

    @property
    def jira_url(self):
        return self.config['url']

    @property
    def jira(self):
        if not self._jira:
            print("Connecting to jira at", self.jira_url)
            kwargs = {}
            cfg = self.config
            auth_cfg = cfg['auth']
            try:
                kwargs['validate'] = auth_cfg['validate']
            except KeyError:
                kwargs['validate'] = True

            if 'basic_auth' in auth_cfg and auth_cfg['basic_auth'] is True:
                print("Using basic authentication")
                kwargs['basic_auth'] = (auth_cfg['username'], auth_cfg['password'])
            else:
                print("Using kerberos authentication")
                kwargs['kerberos'] = True
                kwargs['kerberos_options'] = {'mutual_authentication': "DISABLED"}

            kwargs['options'] = {}
            if 'verify_ssl' in cfg and cfg['verify_ssl'] is False:
                print("Warning: SSL certificate verification is disabled!")
                kwargs['options']['verify'] = False
                # Disable ssl validation warnings, we gave one warning already ...
                from urllib3.exceptions import InsecureRequestWarning
                from requests.packages.urllib3 import disable_warnings
                disable_warnings(category=InsecureRequestWarning)

            self._jira = JiraClientOverride(self.jira_url, **kwargs)
        return self._jira

    @property
    def current_sprint_id(self):
        if not self._current_sprint_id:
            active_sprints = (
                sprint for sprint
                in self.jira.sprints(board_id=self.config['board_id'], state='active')
                if sprint.state.lower() == 'active'
            )
            self._current_sprint_id = sorted(active_sprints, key=lambda sprint: sprint.id)[-1].id
        return self._current_sprint_id

    def search_issues(self, sprint=None, assignee=None):
        if not sprint:
            sprint = self.current_sprint_id
        if not assignee:
            assignee = "currentUser()"
        return self.jira.search_issues('sprint = {} AND assignee = {}'.format(sprint, assignee))

    def get_my_issues(self):
        return self.search_issues()

    def get_worklog(self, issue):
        return self.jira.worklogs(issue.key)

    def get_todays_worklogs(self, issue_list):
        worklogs = []

        for issue in issue_list:
            for wl in self.get_worklog(issue):
                if iso_time_is_today(wl.created) or iso_time_is_today(wl.started):
                    worklogs.append(wl)
        return worklogs

    @staticmethod
    def edit_remaining_time(issue, time_string):
        """
        Set remaining time estimate on an issue.

        Keep originalEstimate and only edit remainingEstimate
        We need to pass both of them as not passing originalEstimate zeroes it.
        """
        f = IssueFields().timetracking(time_string, issue.fields.timeoriginalestimate)
        issue.update(**f.kwarg)

    @staticmethod
    def zero_remaining_time(issue):
        self.edit_remaining_time(issue, 0)

    def zero_remaining_work_done(self):
        issues = self.jira.search_issues(
            'sprint = {} AND assignee = currentUser() AND '
            'status = "Done" AND remainingEstimate > 0'.format(self.current_sprint_id)
        )

        for issue in issues:
            self.zero_remaining_time(issue)

    @staticmethod
    def update_component(issue, component_name):
        f = IssueFields().component(component_name)
        issue.update(**f.kwarg)

    @staticmethod
    def update_labels(issue, labels):
        f = IssueFields().labels(labels)
        issue.update(**f.kwarg)

    @staticmethod
    def normalize_status_name(txt):
        return txt.replace(' ', '').lower()

    def get_avail_statuses(self, issue):
        avail_statuses = [
            {
                'name': JiraWrapper.normalize_status_name(t['name']),  # used for name matching
                'id': t['id'],
                'friendly_name': t['name'],
            } for t in self.jira.transitions(issue) if 'Parallel Team' not in t['name']
        ]
        avail_statuses.sort(key=lambda s: s['name'])
        for idx, status in enumerate(avail_statuses):
            status['local_num'] = idx + 1
        return avail_statuses

    @staticmethod
    def get_avail_status_id(avail_statuses, txt):
        for s in avail_statuses:
            normalized_name = JiraWrapper.normalize_status_name(txt)
            if normalized_name == s['name'] or (txt.isdigit() and int(txt) == s['local_num']):
                return s['id']
        return None
