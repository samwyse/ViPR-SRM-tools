#!/usr/bin/env python3

'''\
Read and manipulate a ViPR SRM alerting.xml file.

Tested with Python 2.7.9 and 3.4.3
'''

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function


__version__ = 1.1
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

# Python standard libraries
from collections import defaultdict, namedtuple
from functools import partial
from hashlib import md5  # deprecated, but we want speed, not security
from operator import attrgetter
from string import Template
from sys import platform, version_info, stdout

import argparse, cgi, os, string, sys, textwrap

PY2 = version_info.major == 2
if PY2:
    from StringIO import StringIO
    zip_longest = partial(map, None)
else:
    from io import StringIO
    from itertools import zip_longest
    basestring = str
    unicode = str

# Python site libraries
from graphviz import Digraph

# Python personal libraries
from AlertingConfig import AlertingConfig, getText
from htmltags import *

if 0:
    style = 'radial'
    fillcolor = [ '/pastel15/{0}:/set15/{0}'.format(i) for i in range(6) ]
else:
    style='filled'
    fillcolor = [ '/set15/{0:d}'.format(i) for i in range(6) ]

#
# Utilities
#

def parse_folders(path, sep='/', _cache={}):
    '''Split a path into flagged components.

>>> parse_folders('foo')
[(True, u'foo')]

>>> parse_folders('foo/bar')
[(False, u'foo'), (True, u'bar')]

>>> sorted('foo foo/bar foo/bar/baz bar bar/baz baz'.split(), key=parse_folders)
[u'bar/baz', u'foo/bar/baz', u'foo/bar', u'bar', u'baz', u'foo']
'''
    pieces = path.split(sep)
    n = len(pieces) - 1
    try:
        # Caching the flags speeds things up by about 27%
        flags = _cache[n]
    except KeyError:
        # Flag folders with False to get correct sort order
        flags = _cache[n] = [False] * n + [True]
    return list(zip(flags, pieces))


class MyFormatter(string.Formatter):
    def convert_field(self, value, conversion):
        if conversion == 'q':
            return cgi.escape(str(value), True)
        elif conversion == 'Q':
            return cgi.escape(str(value).title(), True)
        else:
            return super(MyFormatter, self).convert_field(value, conversion)
fmt = MyFormatter().format


pattern = r"""(
    \s+ |                                 # any whitespace
    [^\s\w]* \w+? (?:
        [-_] (?=\w) |           # hyphenated words
        [a-z] (?=[A-Z])         # CamelCase
        ) |
    (?<=[\w\!\"\'\&\.\,\?]) -{2,} (?=\w)  # em-dash
    )"""

textwrap.TextWrapper.wordsep_re = textwrap.re.compile(pattern, textwrap.re.X)
tw = textwrap.TextWrapper(width=16)
if isinstance('', bytes):
    tw.wordsep_re_uni = textwrap.re.compile(unicode(pattern), textwrap.re.X+textwrap.re.U)
else:
    tw.wordsep_re_uni = tw.wordsep_re
fill = tw.fill


leaving_corners = {
    1: 'e'.split(),
    2: 'ne se'.split(),
    3: 'ne e se'.split(),
    4: 'n ne se s'.split(),
    5: 'n ne e se s'.split(),
    }

entering_corners = {
    1: 'w'.split(),
    2: 'nw sw'.split(),
    3: 'nw w sw'.split(),
    4: 'n nw sw s'.split(),
    5: 'n nw w sw s'.split(),
    }


# UsefulInfo should really be a base class...
UsefulInfo = namedtuple('UsefulInfo', 'title, keyAttr, filter, key_is_path')


def always(*args, **keywords):
    return True


def DDTP(s):
    '''\
Dehyphenate a string,
Drop the last word,
Title-case the result,
Pluralize it.

>>> DDTP('adapter-list')
>>> DDTP('definition-list')
>>> DDTP('grouped-box-list')
>>> DDTP('component-template-list')
'''
    s = ' '.join(s.split('-')[:-1])
    s = s.title()
    return s + ('es' if s.endswith(('ch', 'x')) else 's')


#
# The main event...
#


class BaseAlertingConfig(AlertingConfig):
    '''\
The alerting.xml files define grouped boxes in a manner similar to the
alert definitions, enough so that we can use the AlertingConfig class to
handle both. This class encapsulates the common aspects.'''

    def get_basic_info(self, node, *tagNames):
        info = { '': tagNames }  # a bit of a hack
        for tagName in tagNames:
            child = node.getElementsByTagName(tagName)
            text = getText(child[0].childNodes) if child else ''
            info[tagName] = text
            if tagName == 'class':
                self.jclasses.add(text)
        return info

    def show_basic_info(self, info, **kwds):
        try:
            detail = self.detail
        except:
            detail = self.html
        bgcolor = kwds.pop('bgcolor', 'White')
        detail(fmt('<table bgcolor="{0!q}">', bgcolor))
        detail('<colgroup><col width=20%><col width=75%></colgroup>')
        detail('<tbody>')
        for tagName in info['']:
            detail(fmt('<tr><td>{0!q}</td><td>{1!q}</td></tr>', tagName, info[tagName]))
        detail('</tbody>')
        detail('</table>')
        return info

    def param_table(self, node, bgcolor='#F7F7FF'):
        try:
            detail = self.detail
        except:
            detail = self.html
        detail(fmt('<table bgcolor="{0!q}">', bgcolor))
        detail('<colgroup><col width=20%><col width=75%></colgroup>')
        detail('<thead><tr><th colspan="2">Parameters</th></tr></thead>')
        detail('<tbody>')
        for param in node.getElementsByTagName('param-list'):
            name = param.getAttribute('name')
            text = getText(param.childNodes)
            detail(fmt('<tr><td class="level{2}">{0!q}</td><td>{1!q}</td></tr>', name, text, self.depth))
        detail('</tbody>')
        detail('</table>')

    def prepare(self):
        self.digraph = Digraph(self.unique_name, format='svg')
        self.digraph.graph_attr.update(
            fontsize='30',
            labelloc='t',
            splines='True',
            overlap='False',
            rankdir='LR',
            id='${uniqueid}',  #fmt('graph-{0!q}', id(self)),
            )
        self.digraph.node_attr.update(
            style=style,
            fontcolor='white',)
        self.stringio = StringIO()
        self.detail = partial(print, file=self.stringio)
        self.node_keywords = {}
        self.edge_keywords = {}

    def cleanup(self):
        for node, keywords in sorted(self.node_keywords.items()):
            self.digraph.node(fmt("{0!q}", node), **keywords)

        leaving = defaultdict(set)
        entering = defaultdict(set)
        for from_node, from_port, to_node, to_port in self.edge_keywords:
            leaving[from_node].add(from_port)
            entering[to_node].add(to_port)
        leaving_mapping = {}
        for node, ports in sorted(leaving.items()):
            leaving_mapping[node] = {port: corner for port, corner in zip(sorted(ports), leaving_corners[len(ports)])}
        entering_mapping = {}
        for node, ports in sorted(entering.items()):
            entering_mapping[node] = {port: corner for port, corner in zip(sorted(ports), entering_corners[len(ports)])}
        # If multiple edges leave (or enter) via the same port, we only want to label the first one.
        from_seen = set()
        to_seen = set()
        for (from_node, from_port, to_node, to_port), keywords in sorted(self.edge_keywords.items()):
            javaclass = self.node_keywords.get(from_node).get('tooltip')
            from_nodeport = fmt("{0!q}:{1!q}", from_node, leaving_mapping[from_node][from_port])
            to_nodeport = fmt("{0!q}:{1!q}", to_node, entering_mapping[to_node][to_port])
            # Only label edges if they leave via multiple ports
            # or if the node is a a certain type.
            if len(leaving_mapping[from_node]) > 1 or (javaclass and javaclass.startswith((
                'com.watch4net.alerting.operation.comparator.',
                'com.watch4net.alerting.operation.window.'))):
                # Only label the first edge to leave via this port.
                if from_nodeport not in from_seen:
                    keywords['taillabel'] = from_port
                    from_seen.add(from_nodeport)
            # Only label edges if they enter via multiple ports
            if len(entering_mapping[to_node]) > 1:
                # Only label the first edge to enter via this port.
                if to_nodeport not in to_seen:
                    keywords['headlabel'] = to_port
                    to_seen.add(to_nodeport)
            self.digraph.edge(from_nodeport, to_nodeport, **keywords)

        source = self.digraph.source
        if getattr(self, 'debug', False):
            print(source)
        m = md5()
        m.update(source.encode() if isinstance(source, unicode) else source)
        cached_name = ".cache/%s-%d.svg" % (m.hexdigest(), len(source))
        if True:  ## args.inline:
            try:
                # See if we cached this earlier.
                with open(cached_name, 'r') as cached:
                    svg = cached.read()
            except IOError:
                try:
                    # Try to generate the data.
                    svg = self.digraph.pipe().decode('utf-8')
                except:
                    # Protect ourselves in case of problems.
                    svg = '[Graphviz not found, graphs will not be generated.]'
                else:
                    with open(cached_name, 'w') as cached:
                        cached.write(svg)
            finally:
                svg = Template(svg).safe_substitute(uniqueid=id(self))
            self.html(svg)
        else:
            # Someday we'll have a web service to generate the SVG files...
            self.html(fmt('<iframe src="{0!q}" width="100%" height="480"></iframe>', cached_name))
        self.html(self.stringio.getvalue())
        self.stringio.close()
        del self.unique_name, self.digraph, self.stringio, self.detail, self.node_keywords, self.edge_keywords


class GroupedBoxReporter(BaseAlertingConfig):

    def prolog(self):
        self.prepare()

    def do_internal_operation_list(self, operations):
        self.depth += 1
        for operation in operations:
            info = self.get_basic_info(operation, 'name', 'class', 'description')
            pname = operation.getAttribute('id')
            nname = fill(info['name'])
            if nname not in self.node_keywords:
                javaclass = info['class']
                if not javaclass.startswith('com.'):
                    shape, fllclr = 'rectangle', 1
                elif javaclass.startswith('com.watch4net.alerting.operation.comparator.'):
                    shape, fllclr = 'diamond', 5
                else:
                    shape, fllclr = 'rectangle', 2
                self.node_keywords[pname] = {
                    'label': nname,
                    'shape': shape,
                    'fillcolor': fillcolor[fllclr],
                    'tooltip': javaclass,
                    'URL': '#' + operation.getAttribute('id'),
                    }

                self.detail(fmt('<div class="level{0}">', self.depth))
                self.detail('<div class="dialog">')
                self.detail(fmt('<h2><a name="{0!q}">Operation</a></h2>', pname))
                self.show_basic_info(info)
                self.param_table(operation)
##                self.operations(operation, [{
##                    'id': getText(element.childNodes),
##                    'from': element.getAttribute('from'),
##                    'to': element.getAttribute('to'),
##                    } for element in operation.getElementsByTagName('operation-list')])
                for element in operation.getElementsByTagName('operation-list'):
                    edge = (pname, element.getAttribute('from'), getText(element.childNodes), element.getAttribute('to'))
                    if edge not in self.edge_keywords:
                        self.edge_keywords[edge] = {}
##                self.actions(operation, [{
##                    'id': getText(element.childNodes),
##                    'from': element.getAttribute('from'),
##                    'to': element.getAttribute('to'),
##                    } for element in operation.getElementsByTagName('action-list')])
                for element in operation.getElementsByTagName('action-list'):
                    edge = (pname, element.getAttribute('from'), getText(element.childNodes), element.getAttribute('to'))
                    if edge not in self.edge_keywords:
                        self.edge_keywords[edge] = {}
                self.detail('</div>')
                self.detail('</div>')
        self.depth -= 1

    def do_internal_action_list(self, actions):
        self.depth += 1
        for action in actions:
            info = self.get_basic_info(action, 'name', 'class', 'description')
            pname = action.getAttribute('id')
            nname = fill(info['name'])
            if nname not in self.node_keywords:
                javaclass = info['class']
                self.node_keywords[pname] = {
                    'label': nname,
                    'shape': 'ellipse',
                    'fillcolor': fillcolor[3],
                    'tooltip': javaclass,
                    'URL': '#' + action.getAttribute('id'),
                    }

                self.detail(fmt('<div class="level{0}">', self.depth))
                self.detail('<div class="dialog">')
                self.detail(fmt('<h2><a name="{0!q}">Action</a></h2>', pname))
                self.show_basic_info(info)
                self.param_table(action)
                for element in action.getElementsByTagName('action-list'):
                    edge = (pname, element.getAttribute('from'), getText(element.childNodes), element.getAttribute('to'))
                    if edge not in self.edge_keywords:
                        self.edge_keywords[edge] = {}
                self.detail('</div>')
                self.detail('</div>')
        self.depth -= 1

    def epilog(self):
        self.cleanup()


important_basic_information = {
    'adapter-list': UsefulInfo(
        'Adapters',
        'name',
        always,
        False,
        ),
    'definition-list': UsefulInfo(
        'Definitions',
        'name',
        always,
        True,
        ),
    'grouped-box-list': UsefulInfo(
        'Grouped Boxes',
        'id',
        always,
        False,
        ),
    'component-template-list': UsefulInfo(
        'Component Templates',
        'name',
        always,
        False,
        ),
    }
show_disabled_defs = UsefulInfo(
        'Definitions',
        'name',
        always,
        True,
        )
hide_disabled_defs = UsefulInfo(
        'Definitions',
        'name',
        lambda node: node.getAttribute('enabled') != 'false',
        True,
        )


class ConfigReporter(BaseAlertingConfig):

    def table_of_contents(self, tagName):
        try:
            info = important_basic_information[tagName]
        except KeyError:
            # Must not have been that important.  :)
            return
        self.html(fmt('<li><h2>{0!q}</h2><ul>', info.title))
        nodes = self.list_by_tagname[tagName]
        seen = set()
        if info.key_is_path:
            nodes.sort(
                key=lambda node: parse_folders(node.getAttribute(info.keyAttr))
                )
            previous = []
            previous_level, level = 0, 0
            for node in nodes:
                if not info.filter(node):
                    continue
                unique_name = node.getAttribute(info.keyAttr)
                if unique_name in seen:
                    continue
                seen.add(unique_name)
                path = parse_folders(unique_name)
                changed = False
                for old, new, level in zip_longest(
                    previous,
                    path,
                    range(max(len(previous), len(path)))):
                    if new and (changed or old != new):
                        if level > previous_level:
                            self.html('<ul>')
                            previous_level += 1
                        else:
                            while level < previous_level:
                                self.html('</ul>')
                                previous_level -= 1
                        if new[0]:
                            self.html(fmt('<li><a href="#{0!q}">{1!q}</a></li>',
                                          unique_name, new[1]))
                        else:
                            self.html(fmt('<li>{0!q}</li>', new[1]))
                        changed = True
                previous = path
            while previous_level > 0:
                self.html('</ul>')
                previous_level -= 1
        else:
            nodes.sort(
                key=lambda node: node.getAttribute(info.keyAttr)
                )
            for node in nodes:
                unique_name = node.getAttribute(info.keyAttr)
                if unique_name in seen:
                    continue
                info2 = self.get_basic_info(node, 'name')
                seen.add(unique_name)
                self.html(fmt('<li><a href="#{0!q}">{1!q}</a></li>',
                              unique_name,
                              info2.get('name') or unique_name))
        self.html('</ul></li>')

    def prolog(self):
        # Begin creating our report.
        self.html = partial(print, file=self.args.output)
        self.html('''\
<!DOCTYPE html>
<html><head>
  <meta content="text/html; charset=utf-8" http-equiv="Content-Type">''')
        self.html('''\
  <meta name="generator" content="AlertingConfig/report.py {__version__}">'''.format(**globals()))
        self.html('''\
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alerting Configuration</title>''')
##        # Alternate stylesheets are fun, but these conflict with my CSS...
##        for include in 'Chocolate', 'Midnight', 'Modernist', 'Oldstyle', 'Steely', 'Swiss', 'Traditional', 'Ultramarine':
##            self.html('  <link rel="alternate stylesheet" title="%s" href="http://www.w3.org/StyleSheets/Core/%s" type="text/css">'
##                      % (include, include))
        for include, media in (
            ('mobile', 'screen and (max-width: 768px)'),
            ('desktop', 'screen and (min-width: 769px)'),
            ('print', 'print'),
            ('common', ''),
            ):
            css_name = "static/%s.css" % include
            if self.args.inline:
                with open(css_name) as css:
                    self.html('  <style>')
                    if media:
                        self.html('    @media ' + media + ' {')
                    self.html(css.read())
                    if media:
                        self.html('    }')
                    self.html('  </style>')
            else:
                self.html('  <link rel="stylesheet" type="text/css" media="%s" href="%s">'
                          % (media, css_name))
            
        self.html('</head><body>')

        # First section...
        self.html('<nav><ul>')
        for tagName in important_basic_information.keys():
            self.table_of_contents(tagName)
        self.html('</ul></nav>')
        self.jclasses = set()
        self.html('<article>')

    def do_adapter_list(self, adapters):
        self.depth = 0
        info = important_basic_information['adapter-list']
        self.html(fmt('<h1>{0!q}</h1>', info.title))
        for adapter in adapters:
            if not info.filter(adapter):
                continue
            self.unique_name = adapter.getAttribute('name')
            self.html(fmt('<h2><a name="{0!q}">{0!q}</a></h2>', self.unique_name))
            self.html(fmt('<div class="level{0}">', 1))
            self.html('<div class="dialog">')
            info2 = self.get_basic_info(adapter, 'class',)
            self.show_basic_info(info2)
            self.param_table(adapter)
            self.html('</div>')
            self.html('</div>')

    def do_component_template_list(self, component_templates):
        self.depth = 0
        info = important_basic_information['component-template-list']
        self.html(fmt('<h1>{0!q}</h1>', info.title))
        for component_template in component_templates:
            if not info.filter(component_template):
                continue
            self.unique_name = component_template.getAttribute('name')
            self.html(fmt('<h2><a name="{0!q}">{0!q}</a></h2>', self.unique_name))
            self.html('<div class="level1">')
            self.html('<div class="dialog">')
            info2 = self.get_basic_info(component_template, 'class', 'description')
            self.show_basic_info(info2)
            self.param_table(component_template)
            self.html('</div>')
            self.html('</div>')

    def do_grouped_box_list(self, grouped_boxes):
        self.depth = 0
        self.html('<hr>')
        info = important_basic_information['grouped-box-list']
        self.html(fmt('<h1>{0!q}</h1>', info.title))
        seen = set()
        for grouped_box in grouped_boxes:
            if not info.filter(grouped_box):
                continue
            self.unique_name = grouped_box.getAttribute(info.keyAttr)
            if self.unique_name in seen:
                continue
            seen.add(self.unique_name)
            info2 = self.get_basic_info(grouped_box, 'name', 'description')
            self.html(fmt('<h2><a name="{0!q}">{1!q}</a></h2>', self.unique_name, info2['name']))
            self.show_basic_info(info2)
            nested = GroupedBoxReporter(grouped_box,
                                        html=self.html,
                                        unique_name=self.unique_name,
                                        jclasses=self.jclasses,
                                        depth=0,
                                        )
            nested.generate()

    def do_definition_list(self, definitions):
        self.html('<hr>')
        try:
            info = important_basic_information['definition-list']
        except KeyError:
            return
        self.html(fmt('<h1>{0!q}</h1>', info.title))
        seen = set()
        for definition in definitions:
            self.unique_name = definition.getAttribute(info.keyAttr)
            if not info.filter(definition):
                continue
            if self.unique_name in seen:
                continue
            self.depth = 0
            self.debug = self.unique_name == '...'
            seen.add(self.unique_name)
            self.html(fmt('<h2><a name="{0!q}">{0!q}</a></h2>', self.unique_name))
            self.prepare()
            self.entry_points([
                getText(element.childNodes)
                for element in definition.getElementsByTagName('entry-point-list')])
            self.cleanup()

    def entry_points(self, entry_points):
        self.depth += 1
        for entry_point_proxy in entry_points:
            entry_point = self.index_by_tagname['entry-point-list'][entry_point_proxy]
            self.detail(fmt('<div class="level{0}">', self.depth))
            self.detail('<div class="dialog">')
            self.detail(fmt('<h2><a name="{0!q}">Entry Point</a></h2>', entry_point.getAttribute('id')))
            info = self.get_basic_info(entry_point, 'name', 'class', 'description', 'filter')
            self.show_basic_info(info)
            nname = fill(info['name'])
            if nname not in self.node_keywords:
                javaclass = info['class']
                self.node_keywords[nname] = {
                    'shape': 'ellipse',
                    'fillcolor': fillcolor[4],
                    'tooltip': javaclass,
                    'URL': '#' + entry_point.getAttribute('id'),
                    }
##                self.digraph.node(nname, **self.node_keywords[nname])
                self.detail('</div>')
                self.operations(entry_point, [{
                    'id': getText(element.childNodes),
                    'from': element.getAttribute('from'),
                    'to': element.getAttribute('to'),
                    } for element in entry_point.getElementsByTagName('operation-list')])
                self.actions(entry_point, [{
                    'id': getText(element.childNodes),
                    'from': element.getAttribute('from'),
                    'to': element.getAttribute('to'),
                    } for element in entry_point.getElementsByTagName('action-list')])
                self.detail('</div>')
        self.depth -= 1

    def operations(self, predecessor, operations):
        self.depth += 1
        pname = fill(getText(predecessor.getElementsByTagName('name')[0].childNodes))
        for operation_proxy in operations:
            id = operation_proxy['id']
            from_port = operation_proxy['from']
            to_port = operation_proxy['to']
            operation = self.index_by_tagname['operation-list'][id]
            info = self.get_basic_info(operation, 'name', 'class', 'description')
            nname = fill(info['name'])
            if nname not in self.node_keywords:
                javaclass = info['class']
                if not javaclass.startswith('com.'):
                    shape, fllclr = 'rectangle', 1
                elif javaclass.startswith('com.watch4net.alerting.operation.comparator.'):
                    shape, fllclr = 'diamond', 5
                else:
                    shape, fllclr = 'rectangle', 2
                self.node_keywords[nname] = {
                    'shape': shape,
                    'fillcolor': fillcolor[fllclr],
                    'tooltip': javaclass,
                    'URL': '#' + operation.getAttribute('id'),
                    }
##                self.digraph.node(nname, **self.node_keywords[nname])

                self.detail(fmt('<div class="level{0}">', self.depth))
                self.detail('<div class="dialog">')
                self.detail(fmt('<h2><a name="{0!q}">Operation</a></h2>', operation.getAttribute('id')))
                self.show_basic_info(info)
                self.param_table(operation)
                self.detail('</div>')
                self.operations(operation, [{
                    'id': getText(element.childNodes),
                    'from': element.getAttribute('from'),
                    'to': element.getAttribute('to'),
                    } for element in operation.getElementsByTagName('operation-list')])
                self.actions(operation, [{
                    'id': getText(element.childNodes),
                    'from': element.getAttribute('from'),
                    'to': element.getAttribute('to'),
                    } for element in operation.getElementsByTagName('action-list')])
                self.detail('</div>')

            edge = (pname, from_port, nname, to_port)
            if edge not in self.edge_keywords:
##                self.digraph.edge(pname, nname)
                self.edge_keywords[edge] = {}
        self.depth -= 1

    def actions(self, predecessor, actions):
        self.depth += 1
        pname = fill(getText(predecessor.getElementsByTagName('name')[0].childNodes))
        for action_proxy in actions:
            id = action_proxy['id']
            from_port = action_proxy['from']
            to_port = action_proxy['to']
            action = self.index_by_tagname['action-list'][id]
            info = self.get_basic_info(action, 'name', 'class', 'description')

            nname = fill(info['name'])
            if nname not in self.node_keywords:
                javaclass = info['class']
                self.node_keywords[nname] = {
                    'shape': 'ellipse',
                    'fillcolor': fillcolor[3],
                    'tooltip': javaclass,
                    'URL': '#' + action.getAttribute('id'),
                    }

                self.detail(fmt('<div class="level{0}">', self.depth))
                self.detail('<div class="dialog">')
                self.detail(fmt('<h2><a name="{0!q}">Action</a></h2>', action.getAttribute('id')))
                self.show_basic_info(info)
                self.param_table(action)
                self.detail('</div>')
                self.detail('</div>')

            edge = (pname, from_port, nname, to_port)
            if edge not in self.edge_keywords:
                self.edge_keywords[edge] = {}
        self.depth -= 1

    def epilog(self):
        self.html('</article></body></html>')
        del self.html
        if not isinstance(self.args.output, StringIO):
            self.args.output.close()

def popattr(*args):
    value = getattr(*args)
    try:
        delattr(*args[:2])
    except AttributeError:
        pass
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Produce an HTML report from a ViPR SRM alerting.xml file.',
        epilog='Please be patient.  This program can take a minute or two to run.')
    parser.add_argument('--show_disabled', '-d', action='store_true',
                        help='Show disabled, as well as enabled, alert definitionss.')
    parser.add_argument('--inline', '-i', action='store_true',
                        help='Use inline CSS instead of external links.')
    parser.add_argument('input',
                        nargs='?', type=argparse.FileType('r'),
                        default=sys.stdin,
                        help='An alerting.xml file downloaded from ViPR SRM.')
    parser.add_argument('output',
                        nargs='?', type=argparse.FileType('w'),
                        default=None,
                        help='The HTML report to generate.')
    group1 = parser.add_argument_group('server configuration',
                        description='Information not needed when running as a web client.')
    group1.add_argument('--dialog', '-D', action='store_true',
                        help='Interactively ask for all parameters.')
    group1.add_argument('--wsgi', '-W', action='store_true',
                        help='Start as a web service.')
    group1.add_argument('--host', '-H',
                        default='0.0.0.0')
    group1.add_argument('--port', '-P',
                        type=int, default=0)
    group1.add_argument('--profile', action='store_true',
                        help='Run the Python profiler.')
    group1.add_argument('--graphviz_path', '-G',
                        nargs=1, type=str,
                        # http://enterprise-architecture.org/downloads?id=208
                        default=None if os.name == 'posix' else r'C:\Program Files (x86)\Graphviz2.38\bin',
                        help='The path to the graphviz executable.')
    args = parser.parse_args(argv)

    if args.graphviz_path and os.path.isdir(args.graphviz_path):
        syspath = os.getenv('PATH', os.path.defpath)
        os.environ['PATH'] = os.pathsep.join([args.graphviz_path, syspath])

    #from time import localtime, strftime

    if args.dialog:
        print('Enter values, or press <Enter> to accept the default.')
        for key, value in sorted(args.__dict__.items()):
            while True:
                s = raw_input('  {} (default: {}) > '.format(key, value))
                if not s:
                    break
                try:
                    s = type(value)(s)
                    setattr(args, key, s)
                except:
                    pass
                else:
                    break

    if args.wsgi:
        from wsgiref.simple_server import make_server, demo_app
        from wsgiapp import ArgParser, WSGIdispatcher

        srv = make_server(
            args.host, args.port, WSGIdispatcher(
                (r'demo_app$', demo_app),
                (r'$', ArgParser(
                    parser, args, run,
                    headers=[('Content-Type', 'text/html')],
                    skip_groups={'server configuration'})),
                static_path='static'))
        print('listening on %s:%d...' % srv.server_address)
        srv.serve_forever()
        # never returns...

    if not args.output:
        if args.input.name and args.input.name != sys.stdin.name:
            output = os.path.splitext(name)[0] + '.html'
            args.output = open(output, 'w')
        else:
            args.output = sys.stdout
    print('input from %s' % args.input.name)
    print('output to %s' % args.output.name)
    run(args)

def run(args):
    import xml.dom.minidom

    try:
        dom = xml.dom.minidom.parse(args.input)
    except xml.parsers.expat.ExpatError:
        return

    if args.show_disabled:
        important_basic_information['definition-list'] = show_disabled_defs
    else:
        important_basic_information['definition-list'] = hide_disabled_defs

    root = dom.childNodes[0]
    
    if popattr(args, 'profile'):
        import cProfile
        cProfile.run('ConfigReporter(root, args).generate()', sort='time')
    else:
        cr = ConfigReporter(root, args=args)
        cr.generate()


if __name__ == '__main__':
##    main(r'C:\Users\dentos\Documents\GitHub\ViPR-SRM-tools\AlertingConfig\alerting-grouped-boxes.xml nul'.split())
    main()
