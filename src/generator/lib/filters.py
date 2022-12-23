import os
import subprocess
import re


import inflect

inflection = inflect.engine()

SPACES_PER_TAB = 4


re_first_4_spaces = re.compile('^ {1,4}', flags=re.MULTILINE)
re_spaces_after_newline = re.compile('^ {4}', flags=re.MULTILINE)
re_linestart = re.compile('^', flags=re.MULTILINE)
re_desc_parts = re.compile(
    r"((the part (names|properties) that you can include in the parameter value are)|(supported values are ))(.*?)\.",
    flags=re.IGNORECASE | re.MULTILINE)

re_find_replacements = re.compile(r"\{[/\+]?\w+\*?\}")

# ==============================================================================
## @name Filters
# ------------------------------------------------------------------------------
## @{

# rust module doc comment filter
def rust_module_doc_comment(s):
    return re_linestart.sub('//! ', s)


# rust doc comment filter
def rust_doc_comment(s):
    return re_linestart.sub('/// ', s)


# returns true if there is an indication for something that is interpreted as doc comment by rustdoc
def has_markdown_codeblock_with_indentation(s):
    return re_spaces_after_newline.search(s) != None


def preprocess(s):
    p = subprocess.Popen([os.environ['PREPROC']], close_fds=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    res = p.communicate(s.encode('utf-8'))
    return res[0].decode('utf-8')


# runs the preprocessor in case there is evidence for code blocks using indentation
def rust_doc_sanitize(s):
    if has_markdown_codeblock_with_indentation(s):
        return preprocess(s)
    else:
        return s


# rust comment filter
def rust_comment(s):
    return re_linestart.sub('// ', s)


# hash-based comment filter
def hash_comment(s):
    return re_linestart.sub('# ', s)


# hides lines in rust examples, if not already hidden, or empty.
def hide_rust_doc_test(s):
    return re.sub('^[^#\n]', lambda m: '# ' + m.group(), s, flags=re.MULTILINE)


# remove the first indentation (must be spaces !)
def unindent(s):
    return re_first_4_spaces.sub('', s)


# don't do anything with the passed in string
def pass_through(s):
    return s


# tabs: 1 tabs is 4 spaces
def unindent_first_by(tabs):
    def unindent_inner(s):
        return re_linestart.sub(' ' * tabs * SPACES_PER_TAB, s)

    return unindent_inner


# filter to remove empty lines from a string
def remove_empty_lines(s):
    return re.sub("^\n", '', s, flags=re.MULTILINE)


# Prepend prefix  to each line but the first
def prefix_all_but_first_with(prefix):
    def indent_inner(s):
        try:
            i = s.index('\n')
        except ValueError:
            f = s
            p = None
        else:
            f = s[:i + 1]
            p = s[i + 1:]
        if p is None:
            return f
        return f + re_linestart.sub(prefix, p)

    return indent_inner


# tabs: 1 tabs is 4 spaces
def indent_all_but_first_by(indent, indent_in_tabs=True):
    if indent_in_tabs:
        indent *= SPACES_PER_TAB
    spaces = ' ' * indent
    return prefix_all_but_first_with(spaces)


# add 4 spaces to the beginning of a line.
# useful if you have defs embedded in an unindent block - they need to counteract.
# It's a bit itchy, but logical
def indent(s):
    return re_linestart.sub(' ' * SPACES_PER_TAB, s)


# indent by given amount of spaces
def indent_by(n):
    def indent_inner(s):
        return re_linestart.sub(' ' * n, s)

    return indent_inner


# return s, with trailing newline
def trailing_newline(s):
    if not s.endswith('\n'):
        return s + '\n'
    return s


# a rust test that doesn't run though
def rust_doc_test_norun(s):
    return "```test_harness,no_run\n%s```" % trailing_newline(s)


# a rust code block in (github) markdown
def markdown_rust_block(s):
    return "```Rust\n%s```" % trailing_newline(s)


# wraps s into an invisible doc test function.
def rust_test_fn_invisible(s):
    return "# async fn dox() {\n%s# }" % trailing_newline(s)


# markdown comments
def markdown_comment(s):
    return "<!---\n%s-->" % trailing_newline(s)


# escape each string in l with "s" and return the new list
def estr(l):
    return ['"%s"' % i for i in l]


# escape all '"' with '\"'
def escape_rust_string(s):
    return s.replace('"', '\\"')


## -- End Filters -- @}

# ==============================================================================
## @name Natural Language Utilities
# ------------------------------------------------------------------------------
## @{

# l must be a list, if it is more than one, 'and' will before last item
# l will also be coma-separtated
# Returns string
def put_and(l):
    if len(l) < 2:
        return l[0]
    return ', '.join(l[:-1]) + ' and ' + l[-1]


# ['foo', ...] with e == '*' -> ['*foo*', ...]
def enclose_in(e, l):
    return ['%s%s%s' % (e, s, e) for s in l]


def md_italic(l):
    return enclose_in('*', l)


def singular(s):
    if s.lower().endswith('data'):
        return s

    single_noun = inflection.singular_noun(s)

    if single_noun is False:
        return s
    else:
        return single_noun


def split_camelcase_s(s):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1).lower()


def camel_to_under(s):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# there are property descriptions from which parts can be extracted. Regex is based on youtube ... it's sufficiently
# easy enough to add more cases ...
# return ['part', ...] or []
def extract_parts(desc):
    res = []
    m = re_desc_parts.search(desc)
    if m is None:
        return res
    for part in m.groups()[-1].split(' '):
        part = part.strip(',').strip()
        if not part or part == 'and':
            continue
        res.append(part)
    return res


## -- End Natural Language Utilities -- @}
