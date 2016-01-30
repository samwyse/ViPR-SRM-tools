#!/usr/bin/env python

'''\
This file provides common tools used by other scripts that manipulate
and/or report on alerting configuration files in ViPR SRM.  You probably
want to run one of them.'''

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = 1.0
__copyright__ = "Copyright 2015, Sam Denton"
__author__ = "Sam Denton <sam.denton@emc.com>"
__contributors__ = []

__license__ = """
Copyright (c) 2015, Sam Denton <sam.denton@emc.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from collections import defaultdict, OrderedDict

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

class OrderedDefaultDict(OrderedDict, defaultdict):
    def __init__(self, default_factory=None, *args, **kwds):
        super(OrderedDefaultDict, self).__init__(*args, **kwds)
        self.default_factory = default_factory

class AlertingConfig(object):

    def __init__(self, root, **keywords):
        '''\
Create an index of the alerting.xml file.

The current alerting module requires all top-level children of a particular
type to be contiguous, and for the element types to appear in a particular
order.  This routine relaxes those constraints a bit, only requiring the
first occurance of an element type to appear in the order needed by the
alerting module.'''
        self.__dict__.update(keywords)        
        list_by_tagname = self.list_by_tagname = OrderedDefaultDict(list)
        index_by_tagname = self.index_by_tagname = defaultdict(dict)
        ELEMENT_NODE = root.ELEMENT_NODE
        for child in root.childNodes:
            if child.nodeType == ELEMENT_NODE:
                tagName = child.tagName
                list_by_tagname[tagName].append(child)
                for attr in 'id', 'name':
                    id = child.getAttribute(attr)
                    if id:
                        index_by_tagname[tagName][id] = child
                        break

    def generate(self):
        '''\
Check for and invoke methods that can be defined by sub-classes.

prolog -- called to prepare for processing.
epilog -- called to clean up afterwards
do_XXX -- called once for each distinct top level element type, and
passed a list of all elements of that type.'''
        try:
            func = getattr(self, 'prolog')
        except AttributeError:
            pass
        else:
            func()

        for tagName, listing in self.list_by_tagname.items():
            try:
                func = getattr(self, 'do_' + tagName.replace('-', '_'))
            except AttributeError:
                pass
            else:
                func(listing)

        try:
            func = getattr(self, 'epilog')
        except AttributeError:
            pass
        else:
            func()

if __name__ == '__main__':
    print(__doc__)

def _test():
    import doctest
    doctest.testmod()

    # The following provides a quick check that everything works.
    # It is not intended to be particularly useful.

    class PrintOutline(AlertingConfig):

        def prolog(self):
            self.depth = 0

        def epilog(self):
            assert self.depth == 0

        def do_definition_list(self, definitions):
            for definition in definitions:
                self.depth += 1
                print(self.depth * '  ' + 'definition:', definition)
                self.entry_points([
                    getText(element.childNodes)
                    for element in definition.getElementsByTagName('entry-point-list')])
                self.depth -= 1

        def entry_points(self, entry_points):
            for entry_point_id in entry_points:
                entry_point = self.index_by_tagname['entry-point-list'][entry_point_id]
                self.depth += 1
                print(self.depth * '  ' + 'entry_point:', entry_point)
                self.operations([
                    getText(element.childNodes)
                    for element in entry_point.getElementsByTagName('operation-list')])
                self.actions([
                    getText(element.childNodes)
                    for element in entry_point.getElementsByTagName('action-list')])
                self.depth -= 1

        def operations(self, operations):
            for operation_id in operations:
                operation = self.index_by_tagname['operation-list'][operation_id]
                self.depth += 1
                print(self.depth * '  ' + 'operation:', operation)
                self.operations([
                    getText(element.childNodes)
                    for element in operation.getElementsByTagName('operation-list')])
                self.actions([
                    getText(element.childNodes)
                    for element in operation.getElementsByTagName('action-list')])
                self.depth -= 1

        def actions(self, actions):
            for action_id in actions:
                action = self.index_by_tagname['action-list'][action_id]
                self.depth += 1
                print(self.depth * '  ' + 'action:', action)
                self.depth -= 1

    import xml.dom.minidom
    dom = xml.dom.minidom.parse('alerting.xml')
    root = dom.childNodes[0]
    PrintOutline(root).generate()
