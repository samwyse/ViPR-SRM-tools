#!/usr/bin/env python

"""\
Read an SRM alerting.xml file, adding email actions to all enabled alerts.
"""

# Insure maximum compatibility between Python 2.7 and 3.x
from __future__ import absolute_import, division, print_function, unicode_literals

from functools import partial
from itertools import groupby
from operator import attrgetter

__all__ = [
    'AlertingConfig', 'getChildren', 'getText', 'walkDefinition',
    'DataCounterOperation', 'MailAction', 'SNMPTrapAction'
    ]

DataCounterOperation = "com.watch4net.alerting.operation.window.DataCounterOperation"
MailAction = 'com.watch4net.alerting.action.MailAction'
SNMPTrapAction = "com.watch4net.alerting.action.SNMPTrapAction"

def getChildren(node, *predicates):
    for child in node.childNodes:
        if child.nodeType == child.ELEMENT_NODE and all(f(child) for f in predicates):
            yield child

def getText(node):
    """Returns the concatenation of all nested text nodes."""
    rc = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            rc.append(child.data)
    return ''.join(rc)

def walkDefinition(definition, predicate):
    """Walks a definition, looking for the first node that satisfies the
predicate. If found, returns that node."""
    assert definition.tagName == 'definition-list'
    if hasattr(predicate, '__call__'):
        predicate = predicate.__call__
    try:
       predicate_1 = predicate if predicate.func_code.co_argcount == 1 else None
    except AttributeError:
        predicate_1 = predicate
    if predicate_1:
        predicate = lambda node, parent: predicate_1(node)
    getById = definition.ownerDocument.getElementById
    seen = set()

    def helper(node):
        """Checks all actions in an element, looking for one that
satisfies the predicate. If none do, recursively checks all nested
operations."""
        for action in node.getElementsByTagName('action-list'):
            element = getById(getText(action))
            if element not in seen:
                seen.add(element)
                result = predicate(element, node)
                if result is not None:
                    return result
        for operation in node.getElementsByTagName('operation-list'):
            element = getById(getText(operation))
            if element not in seen:
                seen.add(element)
                result = predicate(element, node) or helper(element)
                if result is not None:
                    return result

    for entry_point in definition.getElementsByTagName('entry-point-list'):
        element = getById(getText(entry_point))
        if element not in seen:
            seen.add(element)
            result = predicate(element, definition) or helper(element)
            if result is not None:
                return result

class AlertingConfig(object):
    # The alerting config contains the following.
    # They must appear in exactly this order.
    allowed_subelements = [
        'adapter-list',
        'definition-list',
        'entry-point-list',
        'operation-list',
        'action-list',
        'grouped-box-list',
        'component-template-list',
        ]

    def __init__(self, doc):
        self.toc = self.refChild = None
        self.doc = doc
        self.root = doc.documentElement
        assert self.root.tagName == 'AlertingConfig'
        self.writexml = self.doc.writexml
        self.toxml = self.doc.toxml
        self.getElementById = self.doc.getElementById

        # This is insane.  Apparently, you need to walk the document and, on a
        # node-by-node basis, declare which attribute(s) to be used as the index.
        # I suspect that there's a shortcut, but I haven't figured it out.
        # Augmenting the element info doesn't seem to work.

##        class IndexedElementInfo(ElementInfo):
##            def isId(self, aname):
##                """Returns true iff the named attribute is a DTD-style ID."""
##                return aname == 'id'
##
##        for tag in 'entry-point-list', 'operation-list', 'action-list':
##            doc._elem_info[tag] = IndexedElementInfo(tag)

        # In our case, the only indexed nodes are in the top level, so we
        # don't need to walk the entire tree.
        for node in self.root.childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                id = node.getAttribute('id')
                if id:
                    node.setIdAttribute('id')

    def __del__(self):
        """\
Unlink the doc object so everything will be garbage collected."""
        self.doc.unlink()

    @classmethod
    def parse(self, filename_or_file, parser=None, bufsize=None):
        """\
parse() is a class method that returns a new AlertingConfig object."""
        from xml.dom.minidom import parse
        return self(parse(filename_or_file, parser, bufsize))

    @classmethod
    def parseString(self, string, parser=None):
        """\
parseString() is a class method that returns a new AlertingConfig object."""
        from xml.dom.minidom import parseString
        return self(parseString(string, parser))

##    def writexml(self, writer):
##        """Write XML to the writer object."""
##        self.doc.writexml(writer)
##
##    def toxml(self, encoding=None):
##        """Return the XML that represents this object."""
##        return self.doc.toxml(encoding)

    def mk_toc(self):
        # The implemenation I'm working with requires the top-level nodes
        # to be in a particular order.  I maintain this by inserting new
        # nodes at the proper location, as tracked by self.insertBefore.
        self.toc = dict((k, next(g))
                   for k, g in groupby((
                            child for child in self.root.childNodes
                                  if child.nodeType == child.ELEMENT_NODE),
                            attrgetter('tagName')))
        self.refChild, child = {}, None
        for tag in reversed(self.allowed_subelements):
            self.refChild[tag], child = child, self.toc.get(tag, child)

    def findChildren(self, *predicates):
        for child in self.root.childNodes:
            if child.nodeType == child.ELEMENT_NODE and all(f(child) for f in predicates):
                yield child

    def create_node(self, tag, id, components):
        """Create a node within AlertingConfig."""
        doc = self.doc
        new_node = doc.createElement(tag)
        new_node.setAttribute('id', id)
        new_node.appendChild(doc.createTextNode('\n    '))
        for key, name, value in components:
            element = doc.createElement(key)
            if name:
                element.setAttribute('name', name)
            element.appendChild(
                doc.createTextNode(value)
                )
            new_node.appendChild(doc.createTextNode('    '))
            new_node.appendChild(element)
            new_node.appendChild(doc.createTextNode('\n    '))
        refChild = self.refChild[tag]
        if not refChild:
            self.root.insertBefore(doc.createTextNode('    '), refChild)
        self.root.insertBefore(new_node, refChild)
        self.root.insertBefore(doc.createTextNode('\n    ' if refChild else '\n'), refChild)
        return new_node

    def add_link(self, source, dest, from_attr, to_attr):
        """add a link from the 'source' definition pointing to the 'dest_id' definition"""
        createElement = self.doc.createElement
        createTextNode = self.doc.createTextNode

        link = createElement(dest.tagName)
        link.setAttribute('from', from_attr)
        link.setAttribute('to', to_attr)
        link.appendChild(
            createTextNode(dest.getAttribute('id'))
            )
        source.appendChild(createTextNode('    '))
        source.appendChild(link)
        source.appendChild(createTextNode('\n    '))


if __name__ == "__main__":
    from xml.dom.minidom import parseString
    ac = AlertingConfig.parseString("""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<AlertingConfig xmlns="http://www.watch4net.com/Alerting">
    <definition-list name="example" enabled="true">
        <description>An example alert.</description>
        <entry-point-list>my-entry-point</entry-point-list>
    </definition-list>
    <entry-point-list id="my-entry-point">
        <name>example entry point</name>
        <class>com.watch4net.alerting.operation.FilteredEntryPoint</class>
        <filter>Source='Example'</filter>
        <description>example entry point</description>
        <action-list from="output" to="entry">my-action</action-list>
    </entry-point-list>
    <action-list id="my-action">
        <name>example trap action</name>
        <class>com.watch4net.alerting.action.SNMPTrapAction</class>
        <description>send a trap somewhere</description>
        <param-list name="host">localhost</param-list>
    </action-list>
</AlertingConfig>""")
    ac.mk_toc()

    my_entry = ac.doc.getElementById("my-entry-point")
    assert(my_entry)

    my_action = ac.doc.getElementById("my-action")
    assert(my_action)

    new_name = getText(next(
        getChildren(my_action,
                    lambda node: node.tagName == 'name')
        )).replace('trap', 'email')

    new_descr = getText(next(
        getChildren(my_action,
                    lambda node: node.tagName == 'description')
        )).replace('trap', 'email')

    new_action = ac.create_node(
        tag='action-list',
        id='new-action',
        components=(
            ('name', None, new_name),
            ('class', None, "com.watch4net.alerting.action.MailAction"),
            ('description', None, new_descr),
            ('param-list', 'to', 'john.doe@example.com'),
            ('param-list', 'subject', 'foo'),
            ('param-list', 'message', 'bar'),
            )
        )
    assert(new_action)
    ac.add_link(my_entry, new_action, 'output', 'entry')
    print(ac.doc.toxml())
