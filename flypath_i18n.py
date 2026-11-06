"""Qt translation helpers shared by every FlyPath module.

The source language is English.  Catalogs live in ``i18n/FlyPath_<locale>.ts``
(Qt's XML format).  ``tools/update_translations.py`` extracts the sources and
``tools/update_translations.py --compile`` builds the ``.qm`` files with Qt's
``lrelease``.

When no compiled catalog is available (for example in a source checkout) the
plugin reads the XML catalog directly, so translations still work without Qt's
build tools.  Importing this module never imports QGIS or Qt at module level,
which keeps the pure-Python modules testable outside a QGIS runtime.
"""

import os
import xml.etree.ElementTree as ET  # nosec B405 - catalogs ship with the plugin

CONTEXT = 'FlyPath'

_translator = None
_translate = None


def tr(text, **values):
    """Translate an English source string and fill ``{name}`` fields."""
    translate = _translate
    if translate is not None:
        text = translate(CONTEXT, text)
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def trn(singular, plural, count, **values):
    """Translate the source form that matches ``count``.

    English falls back to the singular/plural source strings.  Translations
    provide the two source messages separately in the catalog, so languages
    with more than two plural forms need their own convention later.
    """
    values.setdefault('n', count)
    return tr(singular if count == 1 else plural, **values)


def _locale_name():
    from qgis.PyQt.QtCore import QLocale, QSettings
    try:
        name = str(QSettings().value('locale/userLocale', '') or '')
    except Exception:
        name = ''
    return name or QLocale().name() or QLocale.system().name()


def _load_ts(path):
    """Return translated ``source -> text`` entries from one Qt ``.ts`` file."""
    try:
        root = ET.parse(path).getroot()  # nosec B314 - local, trusted catalog
    except (ET.ParseError, OSError):
        return {}
    catalog = {}
    for context in root.findall('context'):
        if (context.findtext('name') or '') != CONTEXT:
            continue
        for message in context.findall('message'):
            source = message.findtext('source')
            node = message.find('translation')
            if source is None or node is None:
                continue
            if node.get('type') in ('unfinished', 'vanished', 'obsolete'):
                continue
            value = node.text or ''
            if value:
                catalog[source] = value
    return catalog


def _install_xml(plugin_dir, locale_name):
    from qgis.PyQt.QtCore import QTranslator
    names = [locale_name]
    language = locale_name.split('_', 1)[0]
    if language and language != locale_name:
        names.append(language)
    for name in names:
        catalog = _load_ts(os.path.join(plugin_dir, 'i18n', 'FlyPath_%s.ts' % name))
        if not catalog:
            continue

        class _CatalogTranslator(QTranslator):
            def __init__(self, entries):
                super().__init__()
                self._entries = entries

            def translate(self, context, source_text, disambiguation=None, n=-1):
                if context != CONTEXT:
                    return ''
                return self._entries.get(source_text, '')

        return _CatalogTranslator(catalog)
    return None


def install(plugin_dir):
    """Install the catalog for the QGIS user locale, once per process."""
    global _translator, _translate
    if _translator is not None:
        return _translator
    try:
        from qgis.PyQt.QtCore import QCoreApplication, QLocale, QTranslator
    except ImportError:
        return None

    locale_name = _locale_name()
    translator = QTranslator()
    i18n_dir = os.path.join(plugin_dir, 'i18n')
    if translator.load(QLocale(locale_name), 'FlyPath', '_', i18n_dir):
        _translator = translator
    else:
        _translator = _install_xml(plugin_dir, locale_name)

    if _translator is not None:
        QCoreApplication.installTranslator(_translator)
        _translate = QCoreApplication.translate
    return _translator


def uninstall():
    """Remove the catalog, for example when the plugin is reloaded."""
    global _translator, _translate
    if _translator is None:
        return
    try:
        from qgis.PyQt.QtCore import QCoreApplication
    except ImportError:
        QCoreApplication = None
    if QCoreApplication is not None:
        QCoreApplication.removeTranslator(_translator)
    _translator = None
    _translate = None
