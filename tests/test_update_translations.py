"""Checks for the translation catalog maintenance tool."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import update_translations as update


def _catalog(tmp_path, monkeypatch, entries):
    monkeypatch.setattr(update, 'ROOT', tmp_path)
    (tmp_path / 'i18n').mkdir()
    path = tmp_path / 'i18n' / 'FlyPath_zh_CN.ts'
    path.write_text(update._render(['Hello', 'World'], entries, 'zh_CN'),
                    encoding='utf-8')
    return path


def test_check_allows_unfinished_by_default(tmp_path, monkeypatch):
    _catalog(tmp_path, monkeypatch, {'Hello': ('你好', None)})
    assert update._check(['Hello', 'World'], 'zh_CN') == []


def test_strict_check_reports_unfinished(tmp_path, monkeypatch):
    _catalog(tmp_path, monkeypatch, {'Hello': ('你好', None)})
    problems = update._check(['Hello', 'World'], 'zh_CN', strict=True)
    assert any('unfinished translation' in problem for problem in problems)
    assert any('World' in problem for problem in problems)


def test_list_unfinished_includes_missing_sources(tmp_path, monkeypatch):
    _catalog(tmp_path, monkeypatch, {'Hello': ('你好', None)})
    (tmp_path / 'i18n' / 'FlyPath_zh_CN.ts').write_text(
        update._render(['Hello'], {'Hello': ('你好', None)}, 'zh_CN'),
        encoding='utf-8')
    _path, pending = update._unfinished(['Hello', 'World'], 'zh_CN')
    assert pending == ['World']


def test_strict_requires_check_flag():
    with pytest.raises(SystemExit):
        update.main(['--strict'])
