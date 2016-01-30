from functools import partial


__all__ = [ 'Element', 'EmptyElement' ]


def import_all(cls, globals=globals()):
    try:
        for tagName in cls.__all__:
            globals.setdefault(tagName, partial(cls, tagName.lower()))
        __all__.extend(cls.__all__)
    except AttributeError:
        pass
    return cls


@import_all
class EmptyElement(object):
    __all__ = [
        'Area', 'Base', 'BaseFont', 'Br', 'Col', 'Frame', 'HR', 'Img',
        'Input', 'IsIndex', 'Link', 'Meta', 'Param']

    def __init__(self, tagName, **attributes):
        self.tagName = tagName
        self.attributes = attributes
        super().__init__()

    def __iter__(self):
        yield '<' + self.tagName
        for key, value in self.attributes.items():
            yield ' ' + key
            if value is not None:
                yield '=' + repr(value)
        yield '>'

    def __str__(self):
        return ''.join(self)

    def __bytes__(self):
        return str(self).encode()

    def getAttribute(self, name):
        return self.attributes[name]

    def hasAttribute(self, name):
        return name in self.attributes

    def removeAttribute(self, name):
        del self.attributes[name]

    def setAttribute(self, name, value):
        self.attributes[name] = value


@import_all
class Element(EmptyElement):
    __all__ = [
        'A', 'Abbr', 'Acronym', 'Address', 'Applet', 'B', 'Bdo', 'Big',
        'Blockquote', 'Body', 'Button', 'Caption', 'Center', 'Cite',
        'Code', 'Colgroup', 'Dd', 'Del', 'Dfn', 'Dir', 'Div', 'Dl',
        'Dt', 'Em', 'Fieldset', 'Font', 'Form', 'Frameset', 'H1', 'H2',
        'H3', 'H4', 'H5', 'H6', 'Head', 'Html', 'I', 'Iframe', 'Ins',
        'Kbd', 'Label', 'Legend', 'Li', 'Map', 'Menu', 'Noframes',
        'Noscript', 'Object', 'Ol', 'Optgroup', 'Option', 'P', 'Pre',
        'Q', 'S', 'Samp', 'Script', 'Select', 'Small', 'Span', 'Strike',
        'Strong', 'Style', 'Sub', 'Sup', 'Table', 'Tbody', 'Td',
        'Textarea', 'Tfoot', 'Th', 'Thead', 'Title', 'Tr', 'Tt', 'U',
        'Ul', 'Var']
    
    def __init__(self, tagName, *childNodes, **attributes):
        self.childNodes = list(childNodes )
        super().__init__(tagName, **attributes)
        
    def __iadd__(self, item):
        self.childNodes.append(item)
        return self
    
    def __iter__(self):
        yield '<' + self.tagName
        for key, value in self.attributes.items():
            yield ' ' + key
            if value is not None:
                yield '=' + repr(value)
        if not self.childNodes:
            yield ' />'
        else:
            yield '>'
            for item in self.childNodes:
                yield str(item)
            yield '</' + self.tagName+'>'
