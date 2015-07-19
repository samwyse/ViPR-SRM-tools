#!/usr/bin/python

"""\
Create an Excel spreadsheet for the customer to fill in.

This runs on the SRM server wherre the alerting backend is installed
and creates a list of Python instructions to create the spreadsheet.
This allows us to avoid installing extraneous modules on the
SRM server."""

# Insure maximum compatibility between Python 2.6 (installed on the
# SRM servers) and Python 3 (which may become the default someday).
from __future__ import absolute_import, division, print_function, unicode_literals

from contextlib import contextmanager
from glob import glob
from os import chdir, getcwd
from os.path import join

import re

root = "/opt/APG/Web-Servers/Tomcat/Default/webapps/centralized-management/solutionpacks"

@contextmanager
def pushd(dirname=None):
    curdir = getcwd()
    try:
        if dirname:
            chdir(dirname)
        yield
    finally:
        chdir(curdir)

def interpret(
    q, section, prefix="",
    elsefi_re = re.compile(r"\s*(else|fi)\s*$"),
    star_re = re.compile(r"\s*(\w+(?:\.\w+)*)(\s+\*)?\s*$"),
    decl_re = re.compile(r"\s*(\w+)\s*\=\s*(.*?)\s*$"),
    ):
    # TODO: Look into Oracle's 'database' section and IBM XIV's 'ibmxiv.array'
    seen = set()
    try:
        iterator = q[section]
    except KeyError:
        return
    for line in iterator:
        match = elsefi_re.match(line)
        if match:
            continue
        match = decl_re.match(line)
        if match:
            var, type = match.groups()
            if prefix:
                var = prefix + "." + var
            if var not in seen:
                if prefix:
                    yield var
                seen.add(var)
            continue
        match = star_re.match(line)
        if match:
            section, flag = match.groups()
            if flag or prefix:
                if prefix:
                    new_prefix = prefix + "." + section
                else:
                    new_prefix = section
                if section not in seen:
                    seen.add(section)
                    for xxx in interpret(q, section, prefix=new_prefix):
                        yield xxx
            continue

def load_properties(fname):
    """Load a simplified Java-style properties file."""
    properties = {}
    try:
        with open(fname) as pfile:
            for line in pfile:
                try:
                    key, value = map(unicode.strip, line.split("=", 2))
                    properties[key] = value
                except ValueError:
                    pass
    except IOError:
        pass
    return properties

def load_dialog(fname,
    section_re = re.compile(r"\s*\[\s*(\W)?(\w+(?:\.\w+)*)\s*\]\s*$"),
    blank_re = re.compile(r"\s*$"),
    ):
    """Load a dialog description file."""
    dialog = { "": [] }
    with open(fname) as dfile:
        section = ""
        for line in dfile:
            match = blank_re.match(line)
            if match:
                continue
            match = section_re.match(line)
            if match:
                section = match.group(2)
                dialog.setdefault(section, [])
                continue
            dialog[section].append(line)
    return dialog

def main():
    print("import xlwt")
    print("wb = xlwt.Workbook()")
    families = set(["Application", "Networking", "Infrastructure", "Storage"])
    families = set(["Storage"])
    chdir(root)
    for dir in glob("*"):  # TODO: replace with opendir(".")?
        ##if not dir.startswith("emc-vnx"):
            ##continue
        with pushd(dir):
            meta = load_properties("meta.properties")
            if meta.get("family") in families:
                with pushd(join("blocks", "extracted")):
                    collect = glob("*collect*")
                    if len(collect):
                        name = meta["name"]
                        for char in ":\\/?*[]":
                            name = name.replace(char, "")
                        name = name[:31]
                        print("ws = wb.add_sheet(%r)" % name)
                        with pushd(collect[0]):
                            xlate = load_properties("questions.properties")
                            questions = load_dialog("questions.txt")
                            try:
                                for col, xxx in enumerate(interpret(questions, "main")):
                                    caption = xlate.get(xxx)
                                    if not caption:
                                        caption = xlate.get(xxx.split(".")[-1], xxx)
                                    print("ws.write(0, %d, %r)" % (col, caption))
                            except:
                                from traceback import print_exc
                                print_exc()
                                print(join(root, dir, "blocks", "extracted", collect[0]))
                                pass
    print("wb.save(%r)" % "device-discovery.xls")

if __name__ == "__main__":
    main()
