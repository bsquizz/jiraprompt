from setuptools import setup

setup(
    name='simplejira',
    version='1.0',
    description='simplejira',
    author='Brandon Squizzato',
    author_email='bsquizza@redhat.com',
    url='https://www.github.com/bsquizz/simplejira',
    packages=['simplejira'],
    install_requires=[
        'jira',
        'pyyaml',
        'prompter',
        'python-editor',
        'attrs',
        'prettytable',
        'cmd2',
        'iso8601',
        'six',
        'pykerberos',
        'python-dateutil',
        'requests',
        'pbr',
        'requests-kerberos',
    ],
    scripts=['bin/simplejira']
)
