from __future__ import print_function

import attr
import yaml
from jira import JIRA


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
            auth_cfg = self.config['auth']
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

    @staticmethod
    def edit_remaining_time(issue, time_string):
        """
        Set remaining time estimate on an issue.

        Keep originalEstimate and only edit remainingEstimate
        We need to pass both of them as not passing originalEstimate zeroes it.
        """
        t = convert_time_string(str(time_string))
        issue.update(
            fields={
                'timetracking': {
                    'remainingEstimate': t,
                    'originalEstimate': issue.fields.timeoriginalestimate
                }
            }
        )

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
    def update_labels(issue, labels):
        issue.update(
            fields={
                'labels': label_list
            }
        )

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
