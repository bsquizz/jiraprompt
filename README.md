# jiraprompt

A CLI-based tool that gives quick access to basic agile workflows for a JIRA board. jiraprompt
requires Python 3.6 or higher.

Working on the JIRA UI can be cumbersome. Many tasks related to agile boards are repeated
requently and can be handled more efficiently via the CLI instead. So we began to write a tool
to allow us to do just that. You might find this tool useful too.

## Dependencies
You'll need the Python headers and the Kerberos headers installed in order to install jiraprompt's
dependencies.

### Fedora

```
$ sudo dnf install gcc redhat-rpm-config python3-devel krb5-devel which binutils
```

### Debian

```
$ sudo apt install build-essential python3-dev libkrb5-dev
```

## Installing

To install jiraprompt and the rest of its dependencies, it is recommended you set up a virtual environment

```
$ python3 -m venv /path/to/env
$ . /path/to/env/bin/activate
```

The package is available on pypi, so you can simply run:

```
$ pip install jiraprompt
```

Alternatively, you can install from source with:

```
$ pip install -r requirements.txt
```

## Running

To run jiraprompt, just run the `jiraprompt` command from within your virtual environment.

```
$ jiraprompt
```

The first time you run jiraprompt, it will set up a new configuration for you and allow you to edit
the configuration file.

## SSL Validation

If you have issues with SSL validation, the config supplies a field for the CA trust cert path. You
can also comment out this line to use your system default. On Fedora, you can run
`dnf install python-requests` to install a patched version of requests that is already pointed
toward the Fedora CA cert bundle by default.
