import re
import urllib2
from os import path as op

from cssmin import cssmin
from jsmin import jsmin
import scss

from zetalibrary.settings import LIBDIR

scss.LOAD_PATHS = LIBDIR

class Parser(object):

    import_re = None
    comment_re = None

    def __init__(self, basedir, compress=False):
        self.compress = compress
        self.basedir = basedir

    @staticmethod
    def read(path, savedir):
        " Read file from path "
        if path.startswith('http://'):
            name = op.basename(path)
            save_path = op.join(savedir, name)
            if not op.exists(save_path):
                src = urllib2.urlopen(path).read()
                try:
                    open(save_path, 'w').write(src)
                except IOError:
                    return src
            path = save_path
        return open(path, 'r').read()

    def parse_path(self, path, parent=None):
        curdir = op.dirname(parent) if parent else self.basedir
        return self.parse_imports(self.read(path, curdir))

    def parse_imports(self, src):
        " Parse imports from source. "
        result = []
        def child(obj):
            result.append(obj.group(1))
        src = self.import_re.sub(child, src)
        return src, result

    def parse_src(self, src, path=None):
        if self.compress:
            src = self.comment_re.sub('', src)
        return src.strip()


class CSSParser(Parser):
    import_re = re.compile(r'^\s*@import +url\(\s*["\']?([^\)\'\"]+)["\']?\s*\)\s*;?\s*$', re.MULTILINE)
    comment_re = re.compile(r'/\*(?:[^*]|\*+[^*/])*\*+/')
    comment_template = '/* %s */\n'
    link_re = re.compile(r'url\(\s*["\']?([^\)\'\"]+)["\']?\)')

    def parse_src(self, src, path=None):
        src = super(CSSParser, self).parse_src(src)
        def links(obj):
            link_path = obj.group(1)
            for ignore in ('data:image', 'http://', 'https://'):
                if link_path.startswith(ignore):
                    return "url(%s)" % link_path
            try:
                url = "url(%s)" % op.relpath(op.join(op.dirname(path), link_path), self.basedir)
                url = url.replace("\\", "/")
                return url
            except OSError:
                return "url(%s)" % link_path

        src = self.link_re.sub(links, src)
        if self.compress:
            src = cssmin(src)
        return src


class SCSSParser(CSSParser):

    def __init__(self, *args, **kwargs):
        super(SCSSParser, self).__init__(*args, **kwargs)
        self.parser = scss.Scss()
        self.parser._scss_opts['compress'] = self.compress

    def parse_src(self, src, path=None):
        src = super(SCSSParser, self).parse_src(src)
        self.parser._scss_files[path] = self.parser.parse_scss_string(path, src)
        self.parser.parse_children()
        self.parser.parse_extends()
        self.parser.manage_order()
        self.parser.parse_properties()
        src = self.parser.create_css(path)
        src = self.parser.post_process(src)
        return src.strip()


class JSParser(Parser):
    import_re = re.compile(r'^require\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)\s*;?\s*$', re.MULTILINE)
    comment_re = re.compile(r'/\*(?:[^*]|\*+[^*/])*\*+/')
    comment_template = '// %s\n'

    def parse_src(self, src, path=None):
        src = super(JSParser, self).parse_src(src)
        if self.compress:
            src = jsmin(src)
        return src
