#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""moin2git.py

A tool to migrate the content of a MoinMoin wiki to a Git based system
like Waliki, Gollum or similar.

Usage:
  moin2git.py migrate <data_dir> <git_repo> [--convert-to-rst] [--users-file <users_file>]
  moin2git.py users <data_dir>
  moin2git.py attachments <data_dir> <dest_dir>

Arguments:
    data_dir  Path where your MoinMoin content are
    git_repo  Path to the target repo (created if it doesn't exist)
    dest_dir  Path to copy attachments (created if it doesn't exist)

Options:
    --convert-to-rst    After migrate, convert to reStructuredText
    --users-file        Use users_file to map wiki user to git commit author
"""
from sh import git, python, pandoc, ErrorReturnCode_1
import docopt
import os
import re
import json
from datetime import datetime
from urllib2 import unquote
import shutil

__version__ = "0.1"
PACKAGE_ROOT = os.path.abspath(os.path.dirname(__file__))
CONVERSION_BLACKLIST = ['']
HYPHEN_MANUAL_MAP = {'PythonOSOps' : "Python-OS-Ops", "GNUParallel" : "GNU-Parallel", "FrontPage" : "Home", "CWLMake" : "CWL-Make", "ITMistakes" : "IT-Mistakes", "MiscSysAdmin" : "Misc-SysAdmin", "AWSBackup" : "AWS-Backup"}


def _unquote(encoded):
    """
    >>> _unquote("Tom(c3a1)s(20)S(c3a1)nchez(20)Garc(c3ad)a")
    Tomás Sánchez García
    """
    chunks = re.findall('\(([a-f0-9]{2,4})\)', encoded)
    for chunk in chunks:
        encoded = encoded.replace('(' + chunk + ')', '%' + "%".join(re.findall('..', chunk)))
    return unquote(encoded)


def parse_users(data_dir=None):
    if not data_dir:
        data_dir = arguments['<data_dir>']
    users = {}
    users_dir = os.path.join(data_dir, 'user')
    for autor in os.listdir(users_dir):
        try:
            data = open(os.path.join(users_dir, autor)).read()
        except IOError:
            continue

        users[autor] = dict(re.findall(r'^([a-z_]+)=(.*)$', data, flags=re.MULTILINE))
    return users


def get_versions(page, users=None, data_dir=None, convert=False):
    if not data_dir:
        data_dir = arguments['<data_dir>']
    if not users:
        users = parse_users(data_dir)
    versions = []
    path = os.path.join(data_dir, 'pages', page)
    log = os.path.join(path, 'edit-log')
    if not os.path.exists(log):
        return versions
    log = open(log).read()
    if not log.strip():
        return versions

    if not convert:
        try:
            convert = arguments['--convert-to-rst']
        except NameError:
            convert = False

    logs_entries = [l.split('\t') for l in log.split('\n')]
    for entry in logs_entries:
        if len(entry) != 9:
            continue
        date = datetime.fromtimestamp(int(entry[0][:-6]))
        comment = entry[-1]
        email = users.get(entry[-3], {}).get('email', 'an@nymous.com')
        revision = entry[1]
        # look for name, username. default to IP
        name = users.get(entry[-3], {}).get('name', None) or users.get(entry[-3], {}).get('username', entry[-5])
        try:
            content = open(os.path.join(path, 'revisions', entry[1])).read()
        except IOError:
            # Append blank string to content to indicate that the file was removed.
            content = ''
        if convert and revision != '99999999':
            conversor = os.path.join(PACKAGE_ROOT, "moin2rst", "moin2rst.py")
            basedir = os.path.abspath(os.path.join(data_dir, '..', '..'))
            try:
                rst = python(conversor, _unquote(page), d=basedir, r=str(int(revision)))
                rst_content = rst.stdout
            except Exception as e:
                rst_content = ''
                print(e)
            #except ErrorReturnCode_1:
            #    print("Couldn't convert %s to rst" % page)
        else:
            rst_content = ''

        versions.append({'date': date, 'content': content, 'rst_content': rst_content,
                         'author': "%s <%s>" % (name, email),
                         'm': comment,
                         'revision': revision})

    return versions

def _hyphenize(page):
    '''
    Convert transitions from lower to uppercase to hyphen delimiters.
    '''
    page = str(page)
    if page in HYPHEN_MANUAL_MAP.keys():
        return HYPHEN_MANUAL_MAP[page]
    newpage = ''
    for idx, elm in enumerate(page):
        newpage+=page[idx]
        if idx != len(page) - 1:
            if (page[idx].islower() and page[idx+1].isupper()):
                newpage+='-'
    return newpage

def migrate_to_git():
    if arguments['--users-file']:
        users = json.loads(open(arguments['<users_file>']).read())
    else:
        users = parse_users()
    git_repo = arguments['<git_repo>']

    if not os.path.exists(git_repo):
        os.makedirs(git_repo)
    if not os.path.exists(os.path.join(git_repo, '.git')):
        git.init(git_repo)

    data_dir = os.path.abspath(arguments['<data_dir>'])
    root = os.path.join(data_dir, 'pages')
    pages = os.listdir(root)
    os.chdir(git_repo)
    for page in pages:
        if page in CONVERSION_BLACKLIST:
            continue
        versions = get_versions(page, users=users, data_dir=data_dir)
        if not versions:
            print("### ignoring %s (no revisions found)" % page)
            continue
        path = _hyphenize(_unquote(page)) + '.txt'
        print("### Creating %s\n" % path)
        dirname, basename = os.path.split(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)

        for version in versions:
            revision = version.pop('revision')
            # Handle attachment revisions
            if revision == '99999999':
                continue
            print("revision %s" % revision)
            try:
                if version['content']:
                    with open(path, 'w') as f:
                        print("Opening %s" % path)
                        f.write(version.pop('content'))
                    print("Adding %s" % path)
                    git.add(path)
                else:
                    print("Removing %s" % path)
                    git.rm(path)
                    version.pop('content')
                if version['rst_content']:
                    with open(path.replace('txt','rst'), 'w') as f:
                        print("Opening %s" % path.replace('txt','rst'))
                        f.write(version.pop('rst_content'))
                    pandoc(path.replace('txt','rst'), f="rst",t="markdown_github", o=path.replace('txt','md'))
                    print("Adding %s" % path.replace('txt','rst'))
                    git.add(path.replace('txt','rst'))
                    print("Adding %s" % path.replace('txt','md'))
                    git.add(path.replace('txt','md'))
                elif os.path.isfile(path.replace('txt','rst')):
                    print("Removing %s" % path.replace('txt','rst'))
                    git.rm(path.replace('txt','rst'))
                    print("Removing %s" % path.replace('txt','md'))
                    git.rm(path.replace('txt','md'))
                    version.pop('rst_content')
                else:
                    version.pop('rst_content')
                print("Committing %s" % path)
                print(version['m'])
                if not version['m'].strip():
                    version['m'] = "Change made on %s" % version['date'].strftime('%x')
                git.commit(path.replace('txt','*'), **version)
            except Exception as e:
                print(e)
                #pass


def copy_attachments():
    dest_dir = arguments['<dest_dir>']

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    root = os.path.abspath(os.path.join(arguments['<data_dir>'], 'pages'))
    pages = os.listdir(root)
    # os.chdir(dest_dir)
    for page in pages:
        attachment_dir = os.path.join(root, page, 'attachments')
        if not os.path.exists(attachment_dir):
            continue
        print("Copying attachments for %s" % page)
        path = _unquote(page)
        dest_path = os.path.join(dest_dir, path)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        for f in os.listdir(attachment_dir):
            print(".. %s" % f)
            full_file_name = os.path.join(attachment_dir, f)
            shutil.copy(full_file_name, dest_path)


if __name__ == '__main__':

    arguments = docopt.docopt(__doc__, version=__version__)

    if arguments['users']:
        print(json.dumps(parse_users(), sort_keys=True, indent=2))
    elif arguments['migrate']:
        migrate_to_git()
    elif arguments['attachments']:
        copy_attachments()
