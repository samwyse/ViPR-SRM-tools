#!/usr/bin/env python

"""\
Read an SRM alerting.xml file, adding email actions to all enabled alerts.
"""

# Insure maximum compatibility between Python 2.7 and 3.x
from __future__ import absolute_import, division, print_function, unicode_literals

from functools import partial
from itertools import groupby
from operator import attrgetter
import sys

from AlertingConfig import *

class PathsToTree(object):
    def __init__(self):
        self.tree = {}
    def add(self, node):
        name = node.getAttribute('name')
        r = self.tree
        for branch in name.split('/'):
            r = r.setdefault(branch, {})
    def print(self, indent='\t'):
        def helper(r, depth=0):
            if r:
                for branch in sorted(r):
                    print(indent * depth + branch)
                    helper(r.get(branch), depth+1)
        helper(self.tree)
            
def getChildrenByTagName(node, tag):
    for child in node.childNodes:
        if node.tagName == tag:
            yield child

def hasMailAction(action):
    """Check if an action sends an email
Returns the action if so, else None."""
    for element in action.getElementsByTagName('class'):
        if getText(element) == MailAction:
            return action

def add_new_nodes(args, ac, origin, action_id, action, source):
    """add a condition node of type 'counter' and two action nodes of type 'email'"""

    new_name = getText(next(
        getChildren(action,
                    lambda node: node.tagName == 'name')
        )).replace('trap', 'counter')

    new_descr = getText(next(
        getChildren(action,
                    lambda node: node.tagName == 'description')
        )).replace('trap', 'counter')

    counter_node = ac.create_node(
        tag='operation-list',
        id=action_id + '-counter',
        components=(
            ('name', None, new_name),
            ('class', None, args.NewOperation),
            ('description', None, new_descr),
            ('param-list', 'time-range', args.time_range),
            ('param-list', 'counter', args.counter),
            ('param-list', 'time-based', args.time_based),
            )
        )

    ac.add_link(origin, counter_node, 'output', 'entry')

    new_name = getText(next(
        getChildren(action,
                    lambda node: node.tagName == 'name')
        )).replace('trap', 'email')

    new_descr = getText(next(
        getChildren(action,
                    lambda node: node.tagName == 'description')
        )).replace('trap', 'email')

    email_node = ac.create_node(
        tag='action-list',
        id=action_id + '-email-2',
        components=(
            ('name', None, new_name),
            ('class', None, args.NewAction),
            ('description', None, new_descr),
            ('param-list', 'to', args.to),
            ('param-list', 'subject', args.subject),
            ('param-list', 'message', args.message+'\n'+source),
            )
        )

    ac.add_link(counter_node, email_node, 'false', 'entry')

    email_node = ac.create_node(
        tag='action-list',
        id=action_id + '-email-1',
        components=(
            ('name', None, new_name),
            ('class', None, args.NewAction),
            ('description', None, new_descr),
            ('param-list', 'to', args.to),
            ('param-list', 'subject', args.subject+'.'),
            ('param-list', 'message', args.message+'\n'+source),
            )
        )

    ac.add_link(counter_node, email_node, 'true', 'entry')

def is_wanted(node):
##    return node.getAttribute('enabled') == 'true'
##    return node.getAttribute('enabled') == 'true' and not walkDefinition(node, hasMailAction)
    return node.getAttribute('name') == 'EMC M&R Health/Component Availability'

def process(args):
    # load the document
    ac = AlertingConfig.parse(args.alerting)

    # Find all definitions that meet our criteria.
    wanted, unwanted = set(), set()
    # TODO: Use the toc?
    for node in ac.findChildren(lambda node: node.tagName == 'definition-list'):
        (wanted if is_wanted(node) else unwanted).add(node)
        node.setAttribute('enabled', 'false')
    print('keeping', len(wanted), 'of', len(wanted) + len(unwanted), 'definitions')
    if not wanted:
        return

    class CheckOperationClass(object):
        def __init__(self, *functions):
            self.functions = functions
        def __call__(self, node):
            for function in self.functions:
                function(node)
            if node.tagName == 'operation-list':
                grouped_box = ac.getElementById(getText(node.getElementsByTagName('class')[0]))
                if grouped_box:
                    for function in self.functions:
                        function(grouped_box)

    discard = set()
    for node in unwanted:
        walkDefinition(node, discard.add)

    for node in unwanted | discard:
        previous = node.previousSibling
        ac.root.removeChild(node)
        node.unlink()
        if previous.nodeType == previous.TEXT_NODE:
            ac.root.removeChild(previous)
            previous.unlink()
    print('removed', len(unwanted) + len(discard), 'nodes')

    ac.mk_toc()

    class do_stuff(object):
        def __init__(self, **kwds):
            self.new_name = kwds['new_name']
        def __call__(self, node, parent):
            print('>>>', node, 'from', parent)
            for child in node.childNodes:
                if child.nodeType == child.ELEMENT_NODE and child.tagName == 'class' and getText(child) == args.OldAction:
                    print('ac', ac)
                    print('parent', parent)
                    print('action_id', node.getAttribute('id'))
                    print('action', node)
                    print('new_name', self.new_name)
                    add_new_nodes(args, ac, parent, node.getAttribute('id'), node, new_name)

    # Duplicate all SNMP Trap actions as Mail actions.
    changed_definitions = PathsToTree()
    for node in wanted:
        print('node', node)
        changed_definitions.add(node)

        old_name = node.getAttribute('name')
        new_name = old_name + ' ' + args.suffix
        node.setAttribute('name', new_name)
        print_name = do_stuff(new_name=new_name)
        walkDefinition(node, print_name)

##        for entry_point in getChildrenByTagName(node, 'entry-point-list'):
##            print('entry_point', entry_point, getText(entry_point))
##            ep = ac.getElementById(getText(entry_point))
##            print('ep', ep)
##            for node in getChildren(ep, lambda node: node.tagName.endswith('-list')):
##                action_id = getText(node)
##                if action_id.endswith('counter'):
##                    continue
##                action = ac.getElementById(action_id)
##                if action and getText(next(getChildrenByTagName(action, 'class'))) == args.OldAction:
##                    add_new_nodes(args, ac, ep, action_id, action, new_name)

    # Write the new alert definitions.
    with open('alerting-email.xml', 'w') as writer:
        ac.writexml(writer)

    changed_definitions.print()

def main(argv=None):
    """
>>> 42
42

"""

    import argparse

    class UpdateAction(argparse.Action):
        from copy import copy as _copy
        _copy = staticmethod(_copy)

        def setattrdefault(self, namespace, name, factory):
            if getattr(namespace, name, None) is None:
                setattr(namespace, name, factory())
            return getattr(namespace, name)

        def __init__(self,
                     option_strings,
                     dest,
                     nargs=None,
                     const=None,
                     default=None,
                     type=None,
                     choices=None,
                     required=False,
                     help=None,
                     metavar=None):
            if nargs == 0:
                raise ValueError('nargs for update actions must be > 0; if arg '
                                 'strings are not supplying the value with which to update, '
                                 'the update const action may be more appropriate')
            if const is not None and nargs != OPTIONAL:
                raise ValueError('nargs must be %r to supply const' % OPTIONAL)
            super(UpdateAction, self).__init__(
                option_strings=option_strings,
                dest=dest,
                nargs=nargs,
                const=const,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            items = UpdateAction._copy(self.setattrdefault(namespace, self.dest, dict))
            if len(values) != 2:
                raise ValueError('update actions require a pair of values')
            items[values[0]] = values[1]
            setattr(namespace, self.dest, items)

    key_eq_value = lambda s: s.split('=', 1)

    parser = argparse.ArgumentParser(
        description='Process some integers.',
##        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

##    parser.add_argument('--test', action='store_true',
##                        help='run doctest.testmod')
##    parser.add_argument('-p', '--param', action=UpdateAction,
##                        type=key_eq_value, metavar='KEY=VALUE',
##                        help='set a parameter')
    parser.add_argument('-o', '--output', metavar='FILENAME',
                        default=None,
                        help='Where to write the output.  Default: the input file name, with "-email" appended.')
    parser.add_argument('--suffix', metavar='STRING',
                        default="(with email)",
                        help='A suffix to add to definition names, to not conflict with existing names.\n(Default: %(default)r)')
    group1 = parser.add_argument_group('Email related settings', 'Settings used for sending emails.  Note that "--to" is a required argument.')
    group1.add_argument('--to', metavar='RECIPIENT',
                        help='The list of recipients separated by a comma (,).')
    group1.add_argument('--subject',
                        default="SRM-ALERT - Sev-PROP.'severity' PROP.'category' alert received for PROP.'devtype'-PROP.'device' is now PROP.'eventstate'",
                        help='The subject of the email.')
    group1.add_argument('--message', metavar='BODY',
                        default="""\
An PROP.'eventstate' alert has been received with the following attributes:

Message: PROP.'fullmsg'
Device: PROP.'device'
Device Type: PROP.'devtype'
Severity: PROP.'severity'
Source: PROP.'Source'
Source IP: PROP.'sourceip'
Part Type: PROP.'parttype'
Part: PROP.'part'
Category: PROP.'category'

This is an auto-generated email. To change the notification settings, consult the site administrator.""",
                        help="The specific content of the email. To add the value, the date, the Unix timestamps or the ID of the current data, use either the keyword VALUE, TMST, UNIX_TMST or ID in the field. To add a property of the current data, use the keyword PROP.'propertyName'.")
    group2 = parser.add_argument_group('Counter related settings', 'settings for the "counter" comparison object.')
    group2.add_argument('--time-range', metavar='MINUTES',
                        default="1440",
                        help='The time window boundary of the collected values in minutes.\n(Default: %(default)r)')
    group2.add_argument('--counter', metavar='INTEGER',
                        default="1",
                        help='The desired counter.\n(Default: %(default)r)')
    group2.add_argument('--time-based', action='store_const', const='true',
                        default="false",
                        help='If set, the condition will send its result for each received data, otherwise it will only send them when the state change for a given ID.')
##    parser.add_argument('--behavior',
##                        default="false",
##                        help='Select how this condition handles the time range: Expiration only: the time range will only serve as a personal reset for each counter in order to invalidate it if values are coming separated by a too long period. Release at period: the counter check will be made only when the range expires instead of when a data is coming in the condition with a maximum delta of 59 seconds. Be aware that this behavior requires more resources. Window expiration: Each time the time range expires based on when the Alerting Backend was started, all the counters will be reset.')
    group3 = parser.add_argument_group('miscellaneous arguments', 'these should not be changed at the current time')
    group3.add_argument('--OldAction', metavar='CLASS_NAME',
                        default=SNMPTrapAction,
                        help='The action to locate in the XML file')
    group3.add_argument('--NewOperation', metavar='CLASS_NAME',
                        default=DataCounterOperation,
                        help='The operation to add to the XML file')
    group3.add_argument('--NewAction', metavar='CLASS_NAME',
                        default=MailAction,
                        help='The action to add to the XML file')
    parser.add_argument('alerting', metavar='FILENAME',
                        nargs='?', type=argparse.FileType('r'), default='alerting.xml',
                        help='$APG_HOME/Backends/Alerting-Backend/Default/conf/alerting.xml\nor an exported SRM alert definition xml file.\n(Default: %(default)r)')

    args = parser.parse_args(argv)
##    if args.test:
##        import doctest
##        doctest.testmod()
##        return
    process(args)

# If writing a program...
if __name__ == "__main__":
    sys.exit(main('--to sam.denton@emc.com'.split()))