"""Extract FlyPath's tr()/trn() sources into Qt .ts catalogs.

Usage:
    python tools/update_translations.py --lang zh_CN
    python tools/update_translations.py --check
    python tools/update_translations.py --check --strict
    python tools/update_translations.py --list-unfinished
    python tools/update_translations.py --compile

The generated .ts files are normal Qt Linguist XML, so Weblate, Crowdin and
Qt Linguist can edit them.  ``--compile`` turns them into .qm files with
lrelease; the plugin also reads .ts directly when no .qm is present.
"""

import argparse
import ast
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = 'FlyPath'
EXCLUDED = {'.github', 'build', 'dist', 'docs', 'tests', 'tools', '__pycache__'}
PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)(?:![rsa])?(?::[^{}]*)?\}')


def _python_files():
    try:
        output = subprocess.run(
            ['git', '-c', 'safe.directory=%s' % ROOT, 'ls-files', '-z'],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout
        paths = [Path(value.decode()) for value in output.split(b'\0') if value]
    except (OSError, subprocess.CalledProcessError):
        paths = [path.relative_to(ROOT) for path in ROOT.rglob('*.py')]
    return [
        path for path in paths
        if path.suffix == '.py'
        and path.parts
        and path.parts[0] not in EXCLUDED
        and path.name != 'flypath_i18n.py'
        and 'flypath_engine' not in path.parts
        and (ROOT / path).is_file()
    ]


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    return None


def extract(path):
    """Return (sources, problems) for one Python file."""
    sources = []
    problems = []
    try:
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    except (OSError, SyntaxError) as exc:
        return sources, ['%s: %s' % (path, exc)]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name not in ('tr', 'trn'):
            continue
        wanted = 1 if name == 'tr' else 2
        for index, arg in enumerate(node.args[:wanted]):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                sources.append(arg.value)
            else:
                problems.append(
                    '%s:%s: %s() argument %d is not a string literal'
                    % (path, getattr(node, 'lineno', '?'), name, index + 1)
                )
    return sources, problems


def _read_ts(path):
    """Return ``source -> (translation, type)`` from an existing catalog."""
    if not path.is_file():
        return {}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise SystemExit('%s: %s' % (path, exc))
    entries = {}
    for context in root.findall('context'):
        if (context.findtext('name') or '') != CONTEXT:
            continue
        for message in context.findall('message'):
            source = message.findtext('source')
            node = message.find('translation')
            if source is None or node is None:
                continue
            entries[source] = (node.text or '', node.get('type'))
    return entries


def _placeholders(text):
    return {match.group(1) for match in PLACEHOLDER.finditer(text)}


def _render(sources, existing, language):
    root = ET.Element('TS', {'version': '2.1', 'language': language})
    context = ET.SubElement(root, 'context')
    ET.SubElement(context, 'name').text = CONTEXT
    for source in sorted(set(sources), key=lambda value: (value.casefold(), value)):
        message = ET.SubElement(context, 'message')
        ET.SubElement(message, 'source').text = source
        translation = ET.SubElement(message, 'translation')
        text, kind = existing.get(source, ('', None))
        if text:
            translation.text = text
            if kind:
                translation.set('type', kind)
        else:
            translation.set('type', 'unfinished')
    ET.indent(root, space='    ')
    body = ET.tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n' + body + '\n'


def _catalog_path(language):
    return ROOT / 'i18n' / ('FlyPath_%s.ts' % language)


def _languages(values):
    if values:
        return list(values)
    found = sorted(path.stem.split('_', 1)[1] for path in (ROOT / 'i18n').glob('FlyPath_*.ts'))
    return found or ['zh_CN']


def _find_lrelease():
    names = [
        os.environ.get('LRELEASE'), 'lrelease', 'lrelease6', 'lrelease-qt6',
        'lrelease-qt5', 'pyside6-lrelease', 'pyside2-lrelease',
    ]
    for name in names:
        if name and shutil.which(name):
            return shutil.which(name)
    for name in ('/usr/lib/qt6/bin/lrelease', '/usr/lib/qt5/bin/lrelease',
                 '/usr/lib/x86_64-linux-gnu/qt6/bin/lrelease',
                 '/usr/lib/x86_64-linux-gnu/qt5/bin/lrelease'):
        if os.path.isfile(name):
            return name
    return None


def _unfinished(sources, language):
    path = _catalog_path(language)
    existing = _read_ts(path)
    pending = []
    for source in sorted(set(sources), key=lambda value: (value.casefold(), value)):
        text, kind = existing.get(source, ('', None))
        if not text or kind == 'unfinished':
            pending.append(source)
    return path, pending


def _check(sources, language, strict=False):
    problems = []
    path = _catalog_path(language)
    existing = _read_ts(path)
    missing = sorted(set(sources) - set(existing))
    extra = sorted(set(existing) - set(sources))
    if missing:
        problems.append('%s: %d source(s) missing from the catalog' % (path, len(missing)))
        for source in missing[:10]:
            problems.append('  + %s' % source)
    if extra:
        problems.append('%s: %d obsolete source(s) in the catalog' % (path, len(extra)))
        for source in extra[:10]:
            problems.append('  - %s' % source)
    unfinished = []
    for source, (text, kind) in existing.items():
        if text and _placeholders(text) != _placeholders(source):
            problems.append(
                '%s: placeholder mismatch for %r' % (path, source)
            )
        if strict and (not text or kind == 'unfinished'):
            unfinished.append(source)
    if unfinished:
        problems.append('%s: %d unfinished translation(s)' % (path, len(unfinished)))
        for source in sorted(unfinished)[:20]:
            problems.append('  ? %s' % source)
        if len(unfinished) > 20:
            problems.append('  ...')
    return problems


def _compile():
    lrelease = _find_lrelease()
    if lrelease is None:
        print('lrelease was not found; .ts catalogs remain usable directly.',
              file=sys.stderr)
        return 1
    failed = 0
    for path in sorted((ROOT / 'i18n').glob('FlyPath_*.ts')):
        result = subprocess.run([lrelease, str(path)], cwd=ROOT)
        if result.returncode:
            failed += 1
        else:
            print('compiled %s' % path.with_suffix('.qm'))
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', action='append', help='language code, for example zh_CN')
    parser.add_argument('--check', action='store_true', help='fail if catalogs are out of date')
    parser.add_argument('--strict', action='store_true',
                        help='with --check, also fail on unfinished or empty translations')
    parser.add_argument('--list-unfinished', action='store_true',
                        help='list sources without a finished translation')
    parser.add_argument('--compile', action='store_true', help='run lrelease after updating')
    parser.add_argument('--compile-only', action='store_true', help='only run lrelease')
    args = parser.parse_args(argv)

    if args.strict and not args.check:
        parser.error('--strict requires --check')

    if args.compile_only:
        return _compile()

    sources = []
    problems = []
    for path in _python_files():
        found, warnings = extract(path)
        sources.extend(found)
        problems.extend(warnings)

    if args.check:
        for language in _languages(args.lang):
            problems.extend(_check(sources, language, strict=args.strict))
        if problems:
            print('\n'.join(problems), file=sys.stderr)
            return 1
        print('Translations are up to date.')
        return 0

    if args.list_unfinished:
        if problems:
            print('\n'.join(problems), file=sys.stderr)
            return 1
        for language in _languages(args.lang):
            path, pending = _unfinished(sources, language)
            if not pending:
                print('%s: all messages are translated.' % path)
                continue
            print('%s: %d untranslated message(s)' % (path, len(pending)))
            for source in pending:
                print('  %s' % source)
        return 0

    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1

    (ROOT / 'i18n').mkdir(exist_ok=True)
    for language in _languages(args.lang):
        path = _catalog_path(language)
        existing = _read_ts(path)
        path.write_text(_render(sources, existing, language), encoding='utf-8')
        print('wrote %s (%d messages)' % (path, len(set(sources))))

    if args.compile:
        return _compile()
    return 0


if __name__ == '__main__':
    sys.exit(main())
