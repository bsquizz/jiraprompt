import editor
import re

def editor_ignore_comments(default_text):
    """
    Open pyeditor but ignore lines starting with "#" when text is returned.

    :param default_text:
    :return:
    """
    edited_text = editor.edit(contents=default_text)
    lines = edited_text.split('\n')
    return "\n".join([line for line in lines if not line.startswith("#")])


def sanitize_worklog_time(s):
    """
    Convert a time string entered by user to jira-acceptable format for issue time tracking
    """
    s = s.replace(' ', '')

    def get_number_before(letter):
        number = 0
        try:
            regex_str = '\D*(\d*)\s*{}.*'.format(letter)
            number = re.findall(regex_str, s)[0]
        except (AttributeError, IndexError):
            pass
        return number

    days = get_number_before('d')
    hours = get_number_before('h')
    mins = get_number_before('m')
    secs = get_number_before('s')

    new_s = ""
    new_s += days + "d " if days else ""
    new_s += hours + "h " if hours else ""
    new_s += mins + "m " if mins else ""
    new_s += secs + "s " if secs else ""
    if new_s:
        return new_s
    else:
        # user might not have specified any strings at all, just pass along the int
        return s
