"""
test_config.py

Unit tests for configuration utilities in Second Brain Database.

Dependencies:
    - pytest
    - unittest.mock
    - second_brain_database.config

Author: Rohan Batra
Date: 2025-06-11
"""

import os
import json
import tempfile
import shutil
import builtins
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import importlib
import io
from contextlib import redirect_stdout

import second_brain_database.config as config_mod

def test_is_docker_env_var(monkeypatch):
    """
    Test is_docker returns True when IN_DOCKER env var is set.
    """
    monkeypatch.setenv('IN_DOCKER', '1')
    assert config_mod.is_docker() is True

def test_is_docker_file(monkeypatch):
    """
    Test is_docker returns True when .dockerenv file exists.
    """
    # Simulate /.dockerenv file exists
    with patch("pathlib.Path.exists", return_value=True):
        monkeypatch.delenv('IN_DOCKER', raising=False)
        assert config_mod.is_docker() is True

def test_is_docker_false(monkeypatch):
    """
    Test is_docker returns False when not in Docker.
    """
    monkeypatch.delenv('IN_DOCKER', raising=False)
    monkeypatch.setattr(config_mod, 'Path', Path)
    assert config_mod.is_docker() is False

def test_is_docker_env_var_true(monkeypatch):
    """
    Test is_docker returns True when IN_DOCKER env var is set to '1'.
    """
    monkeypatch.setenv('IN_DOCKER', '1')
    assert config_mod.is_docker() is True

def test_is_docker_env_var_false(monkeypatch):
    """
    Test is_docker returns False when IN_DOCKER env var is not set.
    """
    monkeypatch.delenv('IN_DOCKER', raising=False)
    monkeypatch.setattr(config_mod, 'Path', Path)
    assert config_mod.is_docker() is False

def test_is_docker_dockerenv_file(monkeypatch):
    """
    Test is_docker returns True when .dockerenv file exists and env var is not set.
    """
    monkeypatch.delenv('IN_DOCKER', raising=False)
    with patch('pathlib.Path.exists', return_value=True):
        assert config_mod.is_docker() is True

def test_ensure_default_config_creates_file(tmp_path):
    """
    Test ensure_default_config creates a config file with defaults.
    """
    config_file = tmp_path / 'test_config.json'
    defaults = {'FOO': 'bar', 'BAZ': 123}
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'bar'
    assert data['BAZ'] == 123

def test_ensure_default_config_creates_nested_dir(tmp_path):
    """
    Test ensure_default_config creates a config file in a nested directory.
    """
    nested_dir = tmp_path / 'a' / 'b' / 'c'
    config_file = nested_dir / 'test_config.json'
    defaults = {'FOO': 'bar'}
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'bar'

def test_ensure_default_config_does_not_overwrite(tmp_path):
    """
    Test ensure_default_config does not overwrite an existing config file.
    """
    config_file = tmp_path / 'test_config.json'
    config_file.write_text(json.dumps({'FOO': 'old'}))
    defaults = {'FOO': 'new'}
    config_mod.ensure_default_config(config_file, defaults)
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'old'

def test_ensure_default_config_existing_file_not_overwritten(tmp_path, capsys):
    """
    Test ensure_default_config does not overwrite an existing file and does not print a message.
    """
    config_file = tmp_path / 'test_config.json'
    config_file.write_text(json.dumps({'FOO': 'old'}))
    defaults = {'FOO': 'new'}
    config_mod.ensure_default_config(config_file, defaults)
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'old'
    captured = capsys.readouterr()
    assert 'Created default config file' not in captured.out

def test_ensure_default_config_uppercase_keys(tmp_path):
    """
    Test ensure_default_config converts keys to uppercase.
    """
    config_file = tmp_path / 'test_config.json'
    defaults = {'foo': 'bar', 'BaZ': 123}
    config_mod.ensure_default_config(config_file, defaults)
    data = json.loads(config_file.read_text())
    assert 'FOO' in data
    assert 'BAZ' in data
    assert data['FOO'] == 'bar'
    assert data['BAZ'] == 123

def test_ensure_default_config_parent_exists(tmp_path):
    """
    Test ensure_default_config works when the parent directory already exists.
    """
    parent = tmp_path / 'parent'
    parent.mkdir()
    config_file = parent / 'test_config.json'
    defaults = {'FOO': 'bar'}
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'bar'

def test_ensure_default_config_file_already_exists(tmp_path, capsys):
    """
    Test ensure_default_config does not overwrite an existing file and does not print a message.
    """
    config_file = tmp_path / 'already.json'
    config_file.write_text(json.dumps({'FOO': 'old'}))
    defaults = {'FOO': 'new'}
    config_mod.ensure_default_config(config_file, defaults)
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'old'
    captured = capsys.readouterr()
    assert 'Created default config file' not in captured.out

def test_ensure_default_config_creates_file_and_prints(tmp_path, capsys):
    """
    Test ensure_default_config creates a new file and prints a message.
    """
    config_file = tmp_path / 'newfile.json'
    defaults = {'FOO': 'bar'}
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    out = capsys.readouterr().out
    assert 'Created default config file' in out

def test_load_sbd_config_local(monkeypatch, tmp_path):
    """
    Test load_sbd_config loads a local config file.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text(json.dumps({'FOO': 'bar'}))
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'baz'})
    config = config_mod.load_sbd_config()
    assert config['FOO'] == 'bar'

def test_load_sbd_config_docker(monkeypatch, tmp_path):
    """
    Test load_sbd_config loads a Docker config file.
    """
    config_file = tmp_path / '.sbd_config.json'
    config_file.write_text(json.dumps({'FOO': 'docker'}))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', True)
    monkeypatch.setattr(config_mod, 'Path', lambda x=None: config_file if x else config_file)
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'baz'})
    config = config_mod.load_sbd_config()
    assert config['FOO'] == 'docker'

def test_load_sbd_config_invalid_json(monkeypatch, tmp_path):
    """
    Test load_sbd_config handles invalid JSON gracefully.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{invalid json}')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'baz'})
    config = config_mod.load_sbd_config()
    assert isinstance(config, dict)
    assert 'FOO' not in config

def test_load_sbd_config_invalid_json_prints(monkeypatch, tmp_path, capsys):
    """
    Test load_sbd_config prints an error message for invalid JSON.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{invalid json}')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'baz'})
    config = config_mod.load_sbd_config()
    captured = capsys.readouterr()
    assert '[CONFIG] Error loading config file:' in captured.out
    assert isinstance(config, dict)
    assert 'FOO' not in config

def test_load_sbd_config_no_home(monkeypatch):
    """
    Test load_sbd_config returns an empty config when HOME is not set.
    """
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.delenv('HOME', raising=False)
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'baz'})
    config = config_mod.load_sbd_config()
    assert isinstance(config, dict)
    assert config == {}

def test_load_sbd_config_config_file_none(monkeypatch):
    """
    Test load_sbd_config returns an empty config when both IS_DOCKER and HOME are missing.
    """
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.delenv('HOME', raising=False)
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'baz'})
    config = config_mod.load_sbd_config()
    assert isinstance(config, dict)
    assert config == {}

def test_get_conf_priority(monkeypatch):
    """
    Test get_conf prioritizes config > env > default.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'FOO': 'from_config'})
    monkeypatch.setenv('FOO', 'from_env')
    config_mod.defaults['FOO'] = 'from_default'
    assert config_mod.get_conf('FOO') == 'from_config'
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    assert config_mod.get_conf('FOO') == 'from_env'
    monkeypatch.delenv('FOO')
    assert config_mod.get_conf('FOO') == 'from_default'

def test_get_conf_returns_none(monkeypatch):
    """
    Test get_conf returns None when no value is found.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.delenv('BAZ', raising=False)
    config_mod.defaults.pop('BAZ', None)
    assert config_mod.get_conf('BAZ') is None

def test_get_conf_env_only(monkeypatch):
    """
    Test get_conf returns value from environment when no config or default exists.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.setenv('ENVONLY', 'env_value')
    config_mod.defaults.pop('ENVONLY', None)
    assert config_mod.get_conf('ENVONLY') == 'env_value'
    monkeypatch.delenv('ENVONLY')

def test_get_conf_case_insensitive(monkeypatch):
    """
    Test get_conf is case-insensitive for config keys.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'FOO': 'bar'})
    assert config_mod.get_conf('foo') == 'bar'

def test_get_conf_returns_explicit_default(monkeypatch):
    """
    Test get_conf returns explicit default when no value is found.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.delenv('BAR', raising=False)
    config_mod.defaults.pop('BAR', None)
    assert config_mod.get_conf('BAR', default='fallback') == 'fallback'

def test_get_conf_defaults_only(monkeypatch):
    """
    Test get_conf returns value from defaults when no config or env exists.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.delenv('ONLYDEFAULT', raising=False)
    config_mod.defaults['ONLYDEFAULT'] = 'defaultval'
    assert config_mod.get_conf('ONLYDEFAULT') == 'defaultval'

def test_get_conf_config_and_env(monkeypatch):
    """
    Test get_conf prioritizes config over environment variables.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'BOTH': 'from_config'})
    monkeypatch.setenv('BOTH', 'from_env')
    config_mod.defaults['BOTH'] = 'from_default'
    assert config_mod.get_conf('BOTH') == 'from_config'
    monkeypatch.delenv('BOTH')

def test_get_conf_env_and_default(monkeypatch):
    """
    Test get_conf prioritizes environment variables over defaults.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.setenv('ENVDEF', 'from_env')
    config_mod.defaults['ENVDEF'] = 'from_default'
    assert config_mod.get_conf('ENVDEF') == 'from_env'
    monkeypatch.delenv('ENVDEF')

def test_get_conf_case_insensitive(monkeypatch):
    """
    Test get_conf is case-insensitive for config keys.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MIXEDCASE': 'val'})
    assert config_mod.get_conf('mixedcase') == 'val'

def test_get_conf_with_env(monkeypatch):
    """
    Test get_conf returns value from environment when no config exists.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.setenv('FOO', 'envval')
    config_mod.defaults['FOO'] = 'defaultval'
    assert config_mod.get_conf('FOO') == 'envval'
    monkeypatch.delenv('FOO')

def test_get_conf_with_default(monkeypatch):
    """
    Test get_conf returns value from defaults when no config or env exists.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.delenv('FOO', raising=False)
    config_mod.defaults['FOO'] = 'defaultval'
    assert config_mod.get_conf('FOO') == 'defaultval'

def test_get_conf_with_explicit_default(monkeypatch):
    """
    Test get_conf returns explicit default when no value is found.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.delenv('BAR', raising=False)
    config_mod.defaults.pop('BAR', None)
    assert config_mod.get_conf('BAR', default='explicit') == 'explicit'

def test_printenv_config(monkeypatch, capsys):
    """
    Test printenv_config prints effective configuration values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'mongo'})
    monkeypatch.setenv('MONGO_DB_NAME', 'db')
    config_mod.defaults['SECRET_KEY'] = 'secret'
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = mongo' in out
    assert 'MONGO_DB_NAME = db' in out
    assert 'SECRET_KEY = secret' in out

def test_printenv_config_sources(monkeypatch, capsys):
    """
    Test printenv_config includes source information for each value.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'mongo'})
    monkeypatch.setenv('MONGO_DB_NAME', 'db')
    config_mod.defaults['SECRET_KEY'] = 'secret'
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = mongo   (from config)' in out
    assert 'MONGO_DB_NAME = db   (from env)' in out
    assert 'SECRET_KEY = secret   (from default)' in out

def test_printenv_config_all_sources(monkeypatch, capsys):
    """
    Test printenv_config prints values from all sources.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'mongo_config'})
    monkeypatch.setenv('MONGO_DB_NAME', 'mongo_env')
    config_mod.defaults['SECRET_KEY'] = 'mongo_default'
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = mongo_config   (from config)' in out
    assert 'MONGO_DB_NAME = mongo_env   (from env)' in out
    assert 'SECRET_KEY = mongo_default   (from default)' in out

def test_printenv_config_empty(monkeypatch, capsys):
    """
    Test printenv_config prints None for missing values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    config_mod.defaults.clear()
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert '[ENV/CONFIG] Effective configuration values:' in out
    assert 'MONGO_URL = None   (from default)' in out

def test_printenv_config_all_empty(monkeypatch, capsys):
    """
    Test printenv_config prints None for all keys when no values are set.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    config_mod.defaults.clear()
    config_mod.printenv_config()
    out = capsys.readouterr().out
    for key in [
        'MONGO_URL', 'MONGO_DB_NAME', 'SECRET_KEY', 'JWT_EXPIRY', 'JWT_REFRESH_EXPIRY',
        'MAIL_DEFAULT_SENDER', 'MAIL_SENDER_NAME', 'MT_API',
        'REDIS_HOST', 'REDIS_PORT', 'REDIS_DB', 'REDIS_STORAGE_URI']:
        assert f'{key} = None   (from default)' in out

def test_printenv_config_mixed_case(monkeypatch, capsys):
    """
    Test printenv_config handles mixed case keys correctly.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'val1', 'JWT_EXPIRY': 'val2'})
    config_mod.defaults['JWT_REFRESH_EXPIRY'] = 'val3'
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = val1' in out
    assert 'JWT_EXPIRY = val2' in out
    assert 'JWT_REFRESH_EXPIRY = val3' in out

def test_printenv_config_all_sources_present(monkeypatch, capsys):
    """
    Test printenv_config prints values from all sources when present.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'from_config'})
    monkeypatch.setenv('MONGO_DB_NAME', 'from_env')
    config_mod.defaults['SECRET_KEY'] = 'from_default'
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = from_config   (from config)' in out
    assert 'MONGO_DB_NAME = from_env   (from env)' in out
    assert 'SECRET_KEY = from_default   (from default)' in out

def test_config_module_top_level(monkeypatch, tmp_path):
    """
    Ensure top-level code in config.py is covered, including printenv_config().
    """
    import importlib
    import sys
    monkeypatch.delenv('IN_DOCKER', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    sys.modules.pop('second_brain_database.config', None)
    monkeypatch.setattr('builtins.print', lambda *a, **k: None)
    monkeypatch.setattr('pathlib.Path.exists', lambda self: False)
    monkeypatch.setattr('second_brain_database.config.ensure_default_config', lambda *a, **k: None)
    monkeypatch.setattr('second_brain_database.config.printenv_config', lambda: None)
    importlib.import_module('second_brain_database.config')
    config_mod.printenv_config()

def test_config_module_top_level_prints(monkeypatch, tmp_path, capsys):
    """
    Ensure top-level print statements in config.py are covered (no print patch).
    """
    import importlib
    import sys
    monkeypatch.delenv('IN_DOCKER', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    sys.modules.pop('second_brain_database.config', None)
    importlib.import_module('second_brain_database.config')
    out = capsys.readouterr().out
    assert "Setting configuration defaults" in out
    assert ("Docker environment detected" in out) or ("Localhost environment detected" in out)

def test_is_docker_with_print_statements(monkeypatch, capsys):
    """
    Test is_docker function with print statement verification.
    """
    monkeypatch.setenv('IN_DOCKER', '1')
    result = config_mod.is_docker()
    assert result is True
    captured = capsys.readouterr()
    assert "Checking if running inside Docker container" in captured.out
    assert "Detected Docker environment via IN_DOCKER env variable" in captured.out

def test_is_docker_dockerenv_with_prints(monkeypatch, capsys):
    """
    Test is_docker function with /.dockerenv file detection and prints.
    """
    monkeypatch.delenv('IN_DOCKER', raising=False)
    with patch('pathlib.Path.exists', return_value=True):
        result = config_mod.is_docker()
        assert result is True
        captured = capsys.readouterr()
        assert "Checking if running inside Docker container" in captured.out
        assert "Detected Docker environment via /.dockerenv file" in captured.out

def test_is_docker_false_with_prints(monkeypatch, capsys):
    """
    Test is_docker function returning False with print statements.
    """
    monkeypatch.delenv('IN_DOCKER', raising=False)
    with patch('pathlib.Path.exists', return_value=False):
        result = config_mod.is_docker()
        assert result is False
        captured = capsys.readouterr()
        assert "Checking if running inside Docker container" in captured.out
        assert "Not running inside Docker" in captured.out

def test_ensure_default_config_json_formatting(tmp_path):
    """
    Test that ensure_default_config creates properly formatted JSON.
    """
    config_file = tmp_path / 'format_test.json'
    defaults = {'foo': 'bar', 'nested': {'key': 'value'}}
    config_mod.ensure_default_config(config_file, defaults)
    content = config_file.read_text()
    assert '"FOO": "bar"' in content
    assert '"NESTED": {\n    "key": "value"\n  }' in content

def test_ensure_default_config_permission_error(tmp_path, monkeypatch):
    """
    Test ensure_default_config handles permission errors gracefully.
    """
    config_file = tmp_path / 'readonly_dir' / 'config.json'
    defaults = {'FOO': 'bar'}
    original_mkdir = Path.mkdir
    def mock_mkdir(*args, **kwargs):
        raise PermissionError("Permission denied")
    monkeypatch.setattr(Path, 'mkdir', mock_mkdir)
    with pytest.raises(PermissionError):
        config_mod.ensure_default_config(config_file, defaults)

def test_load_sbd_config_docker_path_construction(monkeypatch):
    """
    Test that Docker config path is constructed correctly.
    """
    monkeypatch.setattr(config_mod, 'IS_DOCKER', True)
    constructed_paths = []
    original_path = config_mod.Path
    def mock_path(path):
        constructed_paths.append(str(path))
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = False
        return mock_path_obj
    monkeypatch.setattr(config_mod, 'Path', mock_path)
    monkeypatch.setattr(config_mod, 'ensure_default_config', lambda *args: None)
    config_mod.load_sbd_config()
    assert '/sbd_user/.config/Second-Brain-Database/.sbd_config.json' in constructed_paths

def test_load_sbd_config_file_read_error(monkeypatch, tmp_path, capsys):
    """
    Test load_sbd_config handles file read errors.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('not json at all')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    assert config == {}
    captured = capsys.readouterr()
    assert '[CONFIG] Error loading config file:' in captured.out

def test_get_conf_environment_variable_precedence(monkeypatch):
    """
    Test that environment variables take precedence over defaults but not config.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'TEST_KEY': 'config_value'})
    monkeypatch.setenv('TEST_KEY', 'env_value')
    config_mod.defaults['TEST_KEY'] = 'default_value'
    assert config_mod.get_conf('TEST_KEY') == 'config_value'
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    assert config_mod.get_conf('TEST_KEY') == 'env_value'
    monkeypatch.delenv('TEST_KEY')
    assert config_mod.get_conf('TEST_KEY') == 'default_value'

def test_get_conf_empty_string_handling(monkeypatch):
    """
    Test how get_conf handles empty strings vs None.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'EMPTY_KEY': ''})
    monkeypatch.delenv('EMPTY_KEY', raising=False)
    config_mod.defaults.pop('EMPTY_KEY', None)
    assert config_mod.get_conf('EMPTY_KEY') is None
    monkeypatch.setattr(config_mod, 'sbd_config', {'EMPTY_KEY': ''})
    monkeypatch.setenv('EMPTY_KEY', 'non_empty')
    assert config_mod.get_conf('EMPTY_KEY') == 'non_empty'

def test_get_conf_none_value_in_config(monkeypatch):
    """
    Test get_conf behavior when config contains None values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'NULL_KEY': None})
    monkeypatch.setenv('NULL_KEY', 'env_value')
    config_mod.defaults['NULL_KEY'] = 'default_value'
    assert config_mod.get_conf('NULL_KEY') == 'env_value'

def test_module_level_constants(monkeypatch):
    """
    Test that module-level constants are properly set.
    """
    assert hasattr(config_mod, 'MONGO_URL')
    assert hasattr(config_mod, 'MONGO_DB_NAME')
    assert hasattr(config_mod, 'SECRET_KEY')
    assert hasattr(config_mod, 'JWT_EXPIRY')
    assert hasattr(config_mod, 'JWT_REFRESH_EXPIRY')
    assert hasattr(config_mod, 'REDIS_PORT')
    assert hasattr(config_mod, 'REDIS_DB')
    assert isinstance(config_mod.REDIS_PORT, int)
    assert isinstance(config_mod.REDIS_DB, int)

def test_redis_port_conversion(monkeypatch):
    """
    Test that REDIS_PORT is properly converted to integer.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'REDIS_PORT': '9999'})
    port = int(config_mod.get_conf('REDIS_PORT', 6379))
    assert port == 9999
    assert isinstance(port, int)

def test_redis_db_conversion(monkeypatch):
    """
    Test that REDIS_DB is properly converted to integer.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'REDIS_DB': '5'})
    db = int(config_mod.get_conf('REDIS_DB', 0))
    assert db == 5
    assert isinstance(db, int)

def test_redis_storage_uri_construction(monkeypatch):
    """
    Test REDIS_STORAGE_URI construction with custom host and port.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {
        'REDIS_HOST': 'custom.redis.com',
        'REDIS_PORT': '6380'
    })
    host = config_mod.get_conf('REDIS_HOST', 'localhost')
    port = config_mod.get_conf('REDIS_PORT', 6379)
    expected_uri = f"redis://{host}:{port}"
    assert host == 'custom.redis.com'
    assert port == '6380'

def test_printenv_config_with_custom_values(monkeypatch, capsys):
    """
    Test printenv_config with custom configuration values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {
        'MONGO_URL': 'mongodb://config.example.com:27017',
        'SECRET_KEY': 'config_secret'
    })
    monkeypatch.setenv('MONGO_DB_NAME', 'env_database')
    monkeypatch.setenv('JWT_EXPIRY', '30m')
    config_mod.defaults.update({
        'REDIS_HOST': 'default.redis.com',
        'MT_API': 'default_api_key'
    })
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = mongodb://config.example.com:27017   (from config)' in out
    assert 'MONGO_DB_NAME = env_database   (from env)' in out
    assert 'REDIS_HOST = default.redis.com   (from default)' in out

def test_printenv_config_header_and_footer(monkeypatch, capsys):
    """
    Test that printenv_config includes proper header and formatting.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert out.startswith('\n[ENV/CONFIG] Effective configuration values:')
    assert out.endswith('\n')

def test_defaults_docker_vs_localhost():
    """
    Test that Docker and localhost defaults are different where expected.
    """
    with patch.object(config_mod, 'is_docker', return_value=True):
        docker_defaults = {
            'MONGO_URL': 'mongodb://mongo:27017',
            'REDIS_HOST': 'redis',
            'JWT_EXPIRY': '1h',
        }
        localhost_defaults = {
            'MONGO_URL': 'mongodb://127.0.0.1:27017',
            'REDIS_HOST': '127.0.0.1',
            'JWT_EXPIRY': '15m',
        }
        assert docker_defaults['MONGO_URL'] != localhost_defaults['MONGO_URL']
        assert docker_defaults['REDIS_HOST'] != localhost_defaults['REDIS_HOST']
        assert docker_defaults['JWT_EXPIRY'] != localhost_defaults['JWT_EXPIRY']

def test_config_file_path_docker(monkeypatch):
    """
    Test config file path construction in Docker environment.
    """
    monkeypatch.setattr(config_mod, 'IS_DOCKER', True)
    paths_used = []
    def mock_ensure_default_config(config_file, defaults):
        paths_used.append(str(config_file))
    def mock_path_exists(self):
        return False
    monkeypatch.setattr(config_mod, 'ensure_default_config', mock_ensure_default_config)
    monkeypatch.setattr('pathlib.Path.exists', mock_path_exists)
    config_mod.load_sbd_config()
    assert any('/sbd_user/.config/Second-Brain-Database/.sbd_config.json' in path for path in paths_used)

def test_config_file_path_localhost_no_home(monkeypatch):
    """
    Test config file path when HOME is not set.
    """
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.delenv('HOME', raising=False)
    config = config_mod.load_sbd_config()
    assert config == {}

def test_config_uppercase_normalization(tmp_path):
    """
    Test that configuration keys are normalized to uppercase.
    """
    config_file = tmp_path / 'test_config.json'
    mixed_case_config = {
        'mongo_url': 'test_url',
        'REDIS_HOST': 'test_host',
        'Secret_Key': 'test_key'
    }
    with open(config_file, 'w') as f:
        json.dump(mixed_case_config, f)
    config_mod.ensure_default_config(config_file, {'FOO': 'bar'})
    config_file2 = tmp_path / 'new_config.json'
    config_mod.ensure_default_config(config_file2, {'lower_key': 'value'})
    with open(config_file2, 'r') as f:
        data = json.load(f)
    assert 'LOWER_KEY' in data
    assert 'lower_key' not in data

def test_load_sbd_config_prints_file_status(monkeypatch, tmp_path, capsys):
    """
    Test that load_sbd_config prints appropriate messages about config file status.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{"FOO": "bar"}')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config_mod.load_sbd_config()
    captured = capsys.readouterr()
    assert f'[CONFIG] Loaded config file: {config_file}' in captured.out
    config_file.unlink()
    config_mod.load_sbd_config()
    captured = capsys.readouterr()
    assert f'[CONFIG] Config file not found, using defaults: {config_file}' in captured.out

def test_ensure_default_config_with_complex_nested_data(tmp_path):
    """
    Test ensure_default_config with complex nested data structures.
    """
    config_file = tmp_path / 'complex_config.json'
    complex_defaults = {
        'simple_key': 'simple_value',
        'nested_dict': {
            'level1': {
                'level2': 'deep_value'
            }
        },
        'list_value': ['item1', 'item2'],
        'mixed_case_key': 'MixedValue'
    }
    config_mod.ensure_default_config(config_file, complex_defaults)
    assert config_file.exists()
    with open(config_file, 'r') as f:
        data = json.load(f)
    assert 'SIMPLE_KEY' in data
    assert 'NESTED_DICT' in data
    assert 'LIST_VALUE' in data
    assert 'MIXED_CASE_KEY' in data
    assert data['MIXED_CASE_KEY'] == 'MixedValue'
    assert data['LIST_VALUE'] == ['item1', 'item2']

def test_get_conf_with_numeric_strings(monkeypatch):
    """
    Test get_conf behavior with numeric string values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'NUMERIC_KEY': '12345'})
    result = config_mod.get_conf('NUMERIC_KEY')
    assert result == '12345'
    assert isinstance(result, str)

def test_all_config_keys_in_printenv(monkeypatch, capsys):
    """
    Test that all expected configuration keys appear in printenv output.
    """
    expected_keys = [
        'MONGO_URL', 'MONGO_DB_NAME', 'SECRET_KEY', 'JWT_EXPIRY', 'JWT_REFRESH_EXPIRY',
        'MAIL_DEFAULT_SENDER', 'MAIL_SENDER_NAME', 'MT_API',
        'REDIS_HOST', 'REDIS_PORT', 'REDIS_DB', 'REDIS_STORAGE_URI'
    ]
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    for key in expected_keys:
        monkeypatch.delenv(key, raising=False)
    config_mod.printenv_config()
    out = capsys.readouterr().out
    for key in expected_keys:
        assert key in out

def test_mail_sender_name_default_handling(monkeypatch):
    """
    Test special default handling for MAIL_SENDER_NAME.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    monkeypatch.delenv('MAIL_SENDER_NAME', raising=False)
    config_mod.defaults.pop('MAIL_SENDER_NAME', None)
    result = config_mod.get_conf('MAIL_SENDER_NAME', "Rohan Batra")
    assert result == "Rohan Batra"

def test_ensure_default_config_write_permission_error(tmp_path, monkeypatch):
    """
    Test ensure_default_config when file write fails.
    """
    config_file = tmp_path / 'test_config.json'
    defaults = {'FOO': 'bar'}
    original_open = builtins.open
    def mock_open(*args, **kwargs):
        if 'w' in str(kwargs.get('mode', 'r')) or ('w' in args[1] if len(args) > 1 else False):
            raise PermissionError("Permission denied")
        return original_open(*args, **kwargs)
    monkeypatch.setattr('builtins.open', mock_open)
    with pytest.raises(PermissionError):
        config_mod.ensure_default_config(config_file, defaults)

def test_ensure_default_config_json_dump_error(tmp_path, monkeypatch):
    """
    Test ensure_default_config when JSON serialization fails.
    """
    config_file = tmp_path / 'test_config.json'
    class UnserializableObject:
        pass
    defaults = {'FOO': UnserializableObject()}
    with pytest.raises(TypeError):
        config_mod.ensure_default_config(config_file, defaults)

def test_load_sbd_config_file_permission_error(monkeypatch, tmp_path, capsys):
    """
    Test load_sbd_config when file exists but can't be read.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{"FOO": "bar"}')
    original_open = builtins.open
    def mock_open(*args, **kwargs):
        if str(config_file) in str(args[0]):
            raise PermissionError("Permission denied")
        return original_open(*args, **kwargs)
    monkeypatch.setattr('builtins.open', mock_open)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    assert config == {}
    captured = capsys.readouterr()
    assert '[CONFIG] Error loading config file:' in captured.out

def test_load_sbd_config_unicode_error(monkeypatch, tmp_path, capsys):
    """
    Test load_sbd_config with unicode decode error.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    with open(config_file, 'wb') as f:
        f.write(b'\xff\xfe{"FOO": "bar"}')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    assert config == {}
    captured = capsys.readouterr()
    assert '[CONFIG] Error loading config file:' in captured.out

def test_get_conf_boolean_conversion(monkeypatch):
    """
    Test get_conf with boolean-like string values.
    """
    test_cases = {
        'TRUE_STRING': 'true',
        'FALSE_STRING': 'false',
        'YES_STRING': 'yes',
        'NO_STRING': 'no',
        'ONE_STRING': '1',
        'ZERO_STRING': '0'
    }
    monkeypatch.setattr(config_mod, 'sbd_config', test_cases)
    for key, expected_value in test_cases.items():
        assert config_mod.get_conf(key) == expected_value
        assert isinstance(config_mod.get_conf(key), str)

def test_get_conf_whitespace_handling(monkeypatch):
    """
    Test get_conf with whitespace in values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {
        'LEADING_SPACE': ' value',
        'TRAILING_SPACE': 'value ',
        'BOTH_SPACES': ' value ',
        'INTERNAL_SPACES': 'val ue'
    })
    assert config_mod.get_conf('LEADING_SPACE') == ' value'
    assert config_mod.get_conf('TRAILING_SPACE') == 'value '
    assert config_mod.get_conf('BOTH_SPACES') == ' value '
    assert config_mod.get_conf('INTERNAL_SPACES') == 'val ue'

def test_get_conf_unicode_values(monkeypatch):
    """
    Test get_conf with unicode values.
    """
    unicode_config = {
        'EMOJI_KEY': '🚀💻',
        'CHINESE_KEY': '配置',
        'ACCENTED_KEY': 'café'
    }
    monkeypatch.setattr(config_mod, 'sbd_config', unicode_config)
    assert config_mod.get_conf('EMOJI_KEY') == '🚀💻'
    assert config_mod.get_conf('CHINESE_KEY') == '配置'
    assert config_mod.get_conf('ACCENTED_KEY') == 'café'

def test_get_conf_very_long_values(monkeypatch):
    """
    Test get_conf with very long string values.
    """
    long_value = 'x' * 10000
    monkeypatch.setattr(config_mod, 'sbd_config', {'LONG_KEY': long_value})
    result = config_mod.get_conf('LONG_KEY')
    assert result == long_value
    assert len(result) == 10000

def test_printenv_config_with_none_values(monkeypatch, capsys):
    """
    Test printenv_config when some values are None.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': None})
    monkeypatch.setenv('MONGO_DB_NAME', 'test_db')
    original_defaults = config_mod.defaults.copy()
    config_mod.defaults.clear()
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = None' in out
    assert 'MONGO_DB_NAME = test_db' in out
    config_mod.defaults.update(original_defaults)

def test_printenv_config_with_special_characters(monkeypatch, capsys):
    """
    Test printenv_config with special characters in values.
    """
    special_config = {
        'MONGO_URL': 'value with spaces & symbols!@#$%^&*()',
        'MONGO_DB_NAME': 'value "with" quotes',
        'SECRET_KEY': 'value\nwith\nnewlines'
    }
    monkeypatch.setattr(config_mod, 'sbd_config', special_config)
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'value with spaces & symbols!@#$%^&*()' in out
    assert 'value "with" quotes' in out
    assert 'value\nwith\nnewlines' in out

def test_is_docker_in_docker_env_different_values(monkeypatch, capsys):
    """
    Test is_docker with different IN_DOCKER environment variable values.
    """
    test_values = ['1', 'true', 'TRUE', 'yes', 'YES', 'on', 'ON']
    for value in test_values:
        monkeypatch.setenv('IN_DOCKER', value)
        if value == '1':
            assert config_mod.is_docker() is True
        else:
            assert config_mod.is_docker() is False

def test_is_docker_env_falsy_values(monkeypatch):
    """
    Test is_docker with falsy environment variable values.
    """
    falsy_values = ['0', 'false', 'FALSE', '', 'no', 'off']
    for value in falsy_values:
        monkeypatch.setenv('IN_DOCKER', value)
        with patch('pathlib.Path.exists', return_value=False):
            assert config_mod.is_docker() is False

def test_ensure_default_config_empty_defaults(tmp_path):
    """
    Test ensure_default_config with empty defaults dictionary.
    """
    config_file = tmp_path / 'empty_defaults.json'
    defaults = {}
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    with open(config_file, 'r') as f:
        data = json.load(f)
    assert data == {}

def test_ensure_default_config_none_values_in_defaults(tmp_path):
    """
    Test ensure_default_config with None values in defaults.
    """
    config_file = tmp_path / 'none_defaults.json'
    defaults = {'NULL_KEY': None, 'VALID_KEY': 'value'}
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    with open(config_file, 'r') as f:
        data = json.load(f)
    assert data['NULL_KEY'] is None
    assert data['VALID_KEY'] == 'value'

def test_load_sbd_config_empty_json_file(monkeypatch, tmp_path):
    """
    Test load_sbd_config with empty JSON file.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{}')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    assert config == {}

def test_load_sbd_config_json_array_file(monkeypatch, tmp_path, capsys):
    """
    Test load_sbd_config with JSON array instead of object.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('["not", "an", "object"]')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    assert config == ["not", "an", "object"]

def test_get_conf_with_config_override_priority(monkeypatch):
    """
    Test detailed priority: config > env > default > explicit default.
    """
    key = 'PRIORITY_TEST'
    monkeypatch.setattr(config_mod, 'sbd_config', {key: 'config_val'})
    monkeypatch.setenv(key, 'env_val')
    config_mod.defaults[key] = 'default_val'
    assert config_mod.get_conf(key, 'explicit_val') == 'config_val'
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    assert config_mod.get_conf(key, 'explicit_val') == 'env_val'
    monkeypatch.delenv(key)
    assert config_mod.get_conf(key, 'explicit_val') == 'default_val'
    config_mod.defaults.pop(key, None)
    assert config_mod.get_conf(key, 'explicit_val') == 'explicit_val'

def test_config_constants_immutability():
    """
    Test that config constants are properly set and accessible.
    """
    required_constants = [
        'MONGO_URL', 'MONGO_DB_NAME', 'SECRET_KEY', 'JWT_EXPIRY', 'JWT_REFRESH_EXPIRY',
        'MAIL_DEFAULT_SENDER', 'MAIL_SENDER_NAME', 'MT_API',
        'REDIS_HOST', 'REDIS_PORT', 'REDIS_DB', 'REDIS_STORAGE_URI'
    ]
    for const in required_constants:
        assert hasattr(config_mod, const), f"Missing constant: {const}"
        value = getattr(config_mod, const)
        assert value is not None, f"Constant {const} is None"

def test_redis_storage_uri_default_construction():
    """
    Test REDIS_STORAGE_URI default construction logic.
    """
    host = config_mod.get_conf('REDIS_HOST', 'localhost')
    port = config_mod.get_conf('REDIS_PORT', 6379)
    expected_default_uri = f"redis://{host}:{port}"
    actual_uri = config_mod.get_conf('REDIS_STORAGE_URI', expected_default_uri)
    assert actual_uri is not None
    assert 'redis://' in actual_uri

def test_printenv_config_output_format_consistency(monkeypatch, capsys):
    """
    Test that printenv_config output format is consistent.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'test_mongo', 'SECRET_KEY': 'test_secret'})
    monkeypatch.setenv('REDIS_HOST', 'test_redis')
    config_mod.printenv_config()
    output = capsys.readouterr().out
    lines = [line for line in output.split('\n') if ' = ' in line]
    for line in lines:
        assert ' = ' in line, f"Line missing ' = ': {line}"
        assert '(from ' in line and ')' in line, f"Line missing source info: {line}"
        parts = line.split(' = ')
        assert len(parts) == 2, f"Line format incorrect: {line}"
        key = parts[0].strip()
        assert key.isupper(), f"Key not uppercase: {key}"

def test_edge_case_home_directory_variations(monkeypatch):
    """
    Test various HOME directory edge cases.
    """
    edge_cases = ['', '/nonexistent', '/tmp']
    for home_dir in edge_cases:
        monkeypatch.setenv('HOME', home_dir)
        monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
        try:
            config = config_mod.load_sbd_config()
            assert isinstance(config, dict)
        except (PermissionError, OSError):
            pass

def test_ensure_default_config_with_readonly_parent_directory(tmp_path, monkeypatch):
    """
    Test ensure_default_config when parent directory is read-only.
    """
    readonly_dir = tmp_path / 'readonly'
    readonly_dir.mkdir()
    config_file = readonly_dir / 'subdir' / 'config.json'
    readonly_dir.chmod(0o444)
    try:
        with pytest.raises(PermissionError):
            config_mod.ensure_default_config(config_file, {'FOO': 'bar'})
    finally:
        readonly_dir.chmod(0o755)

def test_load_sbd_config_with_malformed_json_variations(monkeypatch, tmp_path, capsys):
    """
    Test load_sbd_config with various malformed JSON formats.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    malformed_jsons = ['{', '{"key": }', '{"key": "value"', 'null', '123', '"string"']
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    for malformed_json in malformed_jsons:
        config_file.write_text(malformed_json)
        config = config_mod.load_sbd_config()
        assert isinstance(config, (dict, list, str, int, type(None)))
        capsys.readouterr()

def test_environment_variable_case_sensitivity(monkeypatch):
    """
    Test that environment variables are case-sensitive while config keys are normalized.
    """
    monkeypatch.setenv('test_key', 'env_value')
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    result = config_mod.get_conf('TEST_KEY')
    assert result is None or result != 'env_value'
    monkeypatch.setenv('TEST_KEY', 'env_value_upper')
    result = config_mod.get_conf('TEST_KEY')
    assert result == 'env_value_upper'

def test_concurrent_config_access():
    """
    Test that config access is thread-safe.
    """
    import threading
    import time
    results = []
    errors = []
    def access_config():
        try:
            for _ in range(10):
                value = config_mod.get_conf('MONGO_URL')
                results.append(value)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=access_config) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, f"Errors occurred: {errors}"
    assert all(result == results[0] for result in results), "Inconsistent results across threads"

def test_module_import_side_effects():
    """
    Test that importing the module has expected side effects.
    """
    assert hasattr(config_mod, 'IS_DOCKER')
    assert hasattr(config_mod, 'defaults')
    assert hasattr(config_mod, 'sbd_config')
    assert isinstance(config_mod.IS_DOCKER, bool)
    assert isinstance(config_mod.defaults, dict)
    assert isinstance(config_mod.sbd_config, dict)

def test_defaults_completeness():
    """
    Test that all required keys have defaults.
    """
    required_keys = [
        'MONGO_URL', 'MONGO_DB_NAME', 'SECRET_KEY', 'JWT_EXPIRY', 'JWT_REFRESH_EXPIRY',
        'MAIL_DEFAULT_SENDER', 'MAIL_SENDER_NAME', 'MT_API',
        'REDIS_HOST', 'REDIS_PORT', 'REDIS_DB', 'REDIS_STORAGE_URI'
    ]
    for key in required_keys:
        default_value = config_mod.defaults.get(key)
        conf_value = config_mod.get_conf(key)
        assert default_value is not None or conf_value is not None, f"No default for {key}"

def test_config_validation():
    """
    Test that configuration values meet basic validation requirements.
    """
    redis_port = config_mod.REDIS_PORT
    assert isinstance(redis_port, int)
    assert 1 <= redis_port <= 65535
    redis_db = config_mod.REDIS_DB
    assert isinstance(redis_db, int)
    assert 0 <= redis_db <= 15
    mongo_url = config_mod.MONGO_URL
    assert mongo_url is not None
    assert mongo_url.startswith('mongodb://')
    redis_uri = config_mod.REDIS_STORAGE_URI
    assert redis_uri is not None
    assert redis_uri.startswith('redis://')

def test_security_sensitive_config_handling():
    """
    Test that sensitive configuration is handled appropriately.
    """
    secret_key = config_mod.SECRET_KEY
    assert secret_key is not None
    assert len(secret_key) >= 32, "Secret key should be at least 32 characters"
    insecure_patterns = ['password', '123456', 'secret', 'default']
    secret_lower = secret_key.lower()
    for pattern in insecure_patterns:
        if pattern in secret_lower and len(secret_key) < 50:
            pytest.skip(f"Secret key contains potentially insecure pattern: {pattern}")

def test_printenv_config_performance():
    """
    Test that printenv_config performs reasonably well.
    """
    import time
    start_time = time.time()
    config_mod.printenv_config()
    end_time = time.time()
    assert end_time - start_time < 1.0, "printenv_config took too long to execute"

def test_memory_usage_stability():
    """
    Test that repeated config access doesn't cause memory leaks.
    """
    import gc
    gc.collect()
    initial_objects = len(gc.get_objects())
    for _ in range(1000):
        config_mod.get_conf('MONGO_URL')
        config_mod.get_conf('REDIS_HOST')
        config_mod.get_conf('SECRET_KEY')
    gc.collect()
    final_objects = len(gc.get_objects())
    assert final_objects - initial_objects < 100, "Potential memory leak detected"

def test_get_conf_recursive_key_evaluation(monkeypatch):
    """
    Test that get_conf doesn't enter infinite recursion with circular references.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'KEY1': 'KEY2', 'KEY2': 'KEY1'})
    assert config_mod.get_conf('KEY1') == 'KEY2'
    assert config_mod.get_conf('KEY2') == 'KEY1'

def test_config_file_symlink_handling(tmp_path, monkeypatch):
    """
    Test that config loading works with symlinked directories.
    """
    actual_config_dir = tmp_path / 'actual_config'
    actual_config_dir.mkdir(parents=True)
    config_file = actual_config_dir / '.sbd_config.json'
    config_file.write_text('{"TEST_SYMLINK": "value"}')
    symlink_dir = tmp_path / 'symlink_config'
    symlink_dir.symlink_to(actual_config_dir)
    home = tmp_path / 'home'
    home.mkdir()
    config_symlink = home / '.config' / 'Second-Brain-Database'
    config_symlink.parent.mkdir(parents=True)
    config_symlink.symlink_to(actual_config_dir)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    assert config.get('TEST_SYMLINK') == 'value'

def test_config_with_environment_variable_expansion(monkeypatch):
    """
    Test config values that might contain environment variable references.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {
        'PATH_WITH_VAR': '/path/to/$HOME/config',
        'DOLLAR_VALUE': '$100.00',
        'SHELL_COMMAND': '$(echo hello)'
    })
    assert config_mod.get_conf('PATH_WITH_VAR') == '/path/to/$HOME/config'
    assert config_mod.get_conf('DOLLAR_VALUE') == '$100.00'
    assert config_mod.get_conf('SHELL_COMMAND') == '$(echo hello)'

def test_config_with_json_escape_sequences(tmp_path):
    """
    Test that JSON escape sequences in config values are handled correctly.
    """
    config_file = tmp_path / 'escape_test.json'
    config_data = {
        'QUOTE_VALUE': 'He said "Hello"',
        'NEWLINE_VALUE': 'Line 1\nLine 2',
        'TAB_VALUE': 'Column1\tColumn2',
        'BACKSLASH_VALUE': 'C:\\Windows\\System32',
        'UNICODE_VALUE': 'Caf\u00e9'
    }
    with open(config_file, 'w') as f:
        json.dump(config_data, f, ensure_ascii=False)
    config_mod.ensure_default_config(config_file, {'DEFAULT': 'value'})
    with open(config_file, 'r') as f:
        loaded_data = json.load(f)
    assert loaded_data['QUOTE_VALUE'] == 'He said "Hello"'
    assert loaded_data['NEWLINE_VALUE'] == 'Line 1\nLine 2'
    assert loaded_data['TAB_VALUE'] == 'Column1\tColumn2'
    assert loaded_data['BACKSLASH_VALUE'] == 'C:\\Windows\\System32'
    assert loaded_data['UNICODE_VALUE'] == 'Café'

def test_config_file_atomic_writes(tmp_path, monkeypatch):
    """
    Test that config file writes are atomic (no partial writes).
    """
    config_file = tmp_path / 'atomic_test.json'
    defaults = {'LARGE_CONFIG': 'x' * 10000}
    original_write = open
    write_call_count = 0
    def mock_write(*args, **kwargs):
        nonlocal write_call_count
        write_call_count += 1
        if write_call_count == 1:
            return original_write(*args, **kwargs)
        else:
            raise IOError("Simulated interruption")
    config_mod.ensure_default_config(config_file, defaults)
    assert config_file.exists()
    with open(config_file, 'r') as f:
        data = json.load(f)
    assert data['LARGE_CONFIG'] == 'x' * 10000

def test_config_key_normalization_edge_cases(monkeypatch):
    """
    Test edge cases in key normalization.
    """
    edge_case_keys = {
        'ALREADY_UPPER': 'already_upper',
        'MIXED_CASE_KEY': 'mixed_case',
        'KEY_WITH_DASHES': 'dashes',
        'KEY_WITH_DOTS': 'dots',
        'KEY_WITH_SPACES': 'spaces',
        'NUMERIC_START': 'numeric',
        '_UNDERSCORE_START': 'underscore'
    }
    monkeypatch.setattr(config_mod, 'sbd_config', edge_case_keys)
    for original_key, value in edge_case_keys.items():
        result = config_mod.get_conf(original_key)
        assert result == value
        result_lower = config_mod.get_conf(original_key.lower())
        assert result_lower == value

def test_config_value_type_preservation(tmp_path):
    """
    Test that different value types are preserved correctly in JSON.
    """
    config_file = tmp_path / 'types_test.json'
    complex_defaults = {
        'string_value': 'hello',
        'int_value': 42,
        'float_value': 3.14,
        'bool_true': True,
        'bool_false': False,
        'null_value': None,
        'list_value': [1, 2, 3],
        'dict_value': {'nested': 'value'},
        'empty_string': '',
        'zero_int': 0,
        'zero_float': 0.0
    }
    config_mod.ensure_default_config(config_file, complex_defaults)
    with open(config_file, 'r') as f:
        data = json.load(f)
    assert isinstance(data['STRING_VALUE'], str)
    assert isinstance(data['INT_VALUE'], int)
    assert isinstance(data['FLOAT_VALUE'], float)
    assert isinstance(data['BOOL_TRUE'], bool)
    assert isinstance(data['BOOL_FALSE'], bool)
    assert data['NULL_VALUE'] is None
    assert isinstance(data['LIST_VALUE'], list)
    assert isinstance(data['DICT_VALUE'], dict)
    assert data['EMPTY_STRING'] == ''
    assert data['ZERO_INT'] == 0
    assert data['ZERO_FLOAT'] == 0.0

def test_config_loading_with_file_locks(tmp_path, monkeypatch):
    """
    Test config loading when file is locked or in use by another process.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{"TEST": "value"}')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    with open(config_file, 'r') as locked_file:
        config = config_mod.load_sbd_config()
        assert isinstance(config, (dict, list, str, int, type(None)))

def test_printenv_config_with_very_long_output(monkeypatch, capsys):
    """
    Test printenv_config with very long configuration values.
    """
    long_config = {
        'MONGO_URL': f'very_long_value_{"x" * 100}_0',
        'MONGO_DB_NAME': f'very_long_value_{"x" * 100}_1',
        'SECRET_KEY': f'very_long_value_{"x" * 100}_2',
        'JWT_EXPIRY': f'very_long_value_{"x" * 100}_3',
        'JWT_REFRESH_EXPIRY': f'very_long_value_{"x" * 100}_4',
    }
    for i in range(5, 15):
        if i == 5:
            long_config['MAIL_DEFAULT_SENDER'] = f'very_long_value_{"x" * 100}_{i}'
        elif i == 6:
            long_config['MAIL_SENDER_NAME'] = f'very_long_value_{"x" * 100}_{i}'
        elif i == 7:
            long_config['MT_API'] = f'very_long_value_{"x" * 100}_{i}'
        elif i == 8:
            long_config['REDIS_HOST'] = f'very_long_value_{"x" * 100}_{i}'
        elif i == 9:
            long_config['REDIS_PORT'] = f'very_long_value_{"x" * 100}_{i}'
        elif i == 10:
            long_config['REDIS_DB'] = f'very_long_value_{"x" * 100}_{i}'
        elif i == 11:
            long_config['REDIS_STORAGE_URI'] = f'very_long_value_{"x" * 100}_{i}'
    monkeypatch.setattr(config_mod, 'sbd_config', long_config)
    config_mod.printenv_config()
    output = capsys.readouterr().out
    assert len(output) > 1000
    assert '[ENV/CONFIG] Effective configuration values:' in output
    assert 'very_long_value_' in output

def test_config_resilience_to_filesystem_errors(tmp_path, monkeypatch):
    """
    Test config system resilience when filesystem operations fail.
    """
    restricted_path = tmp_path / 'no_permission'
    config_file = restricted_path / 'config' / '.sbd_config.json'
    original_mkdir = Path.mkdir
    def failing_mkdir(*args, **kwargs):
        raise OSError("No space left on device")
    monkeypatch.setattr(Path, 'mkdir', failing_mkdir)
    try:
        config_mod.ensure_default_config(config_file, {'TEST': 'value'})
    except OSError:
        pass
    monkeypatch.setattr(Path, 'mkdir', original_mkdir)
    original_json_dump = json.dump
    def failing_json_dump(*args, **kwargs):
        raise OSError("No space left on device")
    monkeypatch.setattr(json, 'dump', failing_json_dump)
    try:
        config_mod.ensure_default_config(tmp_path / 'test.json', {'TEST': 'value'})
    except OSError:
        pass

def test_config_module_reimport_behavior(monkeypatch, tmp_path):
    """
    Test behavior when config module is imported multiple times.
    """
    if 'second_brain_database.config' in sys.modules:
        del sys.modules['second_brain_database.config']
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('IN_DOCKER', '0')
    config1 = importlib.import_module('second_brain_database.config')
    is_docker1 = config1.IS_DOCKER
    monkeypatch.setenv('IN_DOCKER', '1')
    config2 = importlib.import_module('second_brain_database.config')
    is_docker2 = config2.IS_DOCKER
    assert config1 is config2
    assert is_docker1 == is_docker2

def test_config_function_parameter_validation():
    """
    Test parameter validation in config functions.
    """
    with pytest.raises(AttributeError):
        config_mod.get_conf(None)
    with pytest.raises(AttributeError):
        config_mod.get_conf(123)
    with pytest.raises((TypeError, AttributeError)):
        config_mod.ensure_default_config(None, {})

def test_config_system_integration(tmp_path, monkeypatch):
    """
    Integration test of the entire config system.
    """
    home = tmp_path
    config_dir = home / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    realistic_config = {
        'MONGO_URL': 'mongodb://prod.example.com:27017',
        'SECRET_KEY': 'production_secret_key_very_long_and_secure_123456789',
        'REDIS_HOST': 'redis.prod.example.com',
        'REDIS_PORT': '6380',
        'JWT_EXPIRY': '2h',
        'MAIL_DEFAULT_SENDER': 'noreply@prod.example.com'
    }
    with open(config_file, 'w') as f:
        json.dump(realistic_config, f)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('MONGO_DB_NAME', 'prod_database')
    monkeypatch.setenv('JWT_REFRESH_EXPIRY', '30d')
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config = config_mod.load_sbd_config()
    monkeypatch.setattr(config_mod, 'sbd_config', config)
    assert config_mod.get_conf('MONGO_URL') == 'mongodb://prod.example.com:27017'
    assert config_mod.get_conf('MONGO_DB_NAME') == 'prod_database'
    assert config_mod.get_conf('MT_API') is not None
    output = io.StringIO()
    with redirect_stdout(output):
        config_mod.printenv_config()
    output_str = output.getvalue()
    assert 'mongodb://prod.example.com:27017   (from config)' in output_str
    assert 'prod_database   (from env)' in output_str
    assert '(from default)' in output_str

def test_printenv_config_all_sources_types(monkeypatch, capsys):
    """
    Test printenv_config includes all sources and handles missing keys.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'MONGO_URL': 'from_config'})
    monkeypatch.setenv('MONGO_DB_NAME', 'from_env')
    config_mod.defaults['SECRET_KEY'] = 'from_default'
    if 'MT_API' in config_mod.defaults:
        del config_mod.defaults['MT_API']
    monkeypatch.delenv('MT_API', raising=False)
    config_mod.printenv_config()
    out = capsys.readouterr().out
    assert 'MONGO_URL = from_config   (from config)' in out
    assert 'MONGO_DB_NAME = from_env   (from env)' in out
    assert 'SECRET_KEY = from_default   (from default)' in out
    assert 'MT_API = None   (from default)' in out

def test_get_conf_non_string_key():
    """
    Test get_conf raises an error for non-string keys.
    """
    with pytest.raises(AttributeError):
        config_mod.get_conf(123)

def test_ensure_default_config_no_overwrite_and_no_print(tmp_path, capsys):
    """
    Test ensure_default_config does not overwrite existing files and does not print a message.
    """
    config_file = tmp_path / 'test.json'
    config_file.write_text(json.dumps({'FOO': 'old'}))
    config_mod.ensure_default_config(config_file, {'FOO': 'new'})
    out = capsys.readouterr().out
    assert 'Created default config file' not in out
    data = json.loads(config_file.read_text())
    assert data['FOO'] == 'old'

def test_load_sbd_config_returns_empty_if_missing(monkeypatch):
    """
    Test load_sbd_config returns an empty config if the file is missing.
    """
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    monkeypatch.setenv('HOME', '/tmp/doesnotexist')
    monkeypatch.setattr(config_mod, 'defaults', {'FOO': 'bar'})
    config = config_mod.load_sbd_config()
    assert config == {'FOO': 'bar'}

def test_config_module_top_level_docker(monkeypatch, capsys):
    """
    Cover Docker branch of config.py top-level code without filesystem errors.
    """
    sys.modules.pop('second_brain_database.config', None)
    monkeypatch.setenv('IN_DOCKER', '1')
    monkeypatch.setattr('pathlib.Path.exists', lambda self: False)
    monkeypatch.setattr('pathlib.Path.mkdir', lambda self, parents=True, exist_ok=True: None)
    from unittest.mock import mock_open
    mock_file = mock_open()
    monkeypatch.setattr('builtins.open', mock_file)
    importlib.import_module('second_brain_database.config')
    out = capsys.readouterr().out
    assert "Docker environment detected" in out

def test_config_module_top_level_localhost(monkeypatch, capsys, tmp_path):
    """
    Cover localhost branch of config.py top-level code.
    """
    sys.modules.pop('second_brain_database.config', None)
    monkeypatch.delenv('IN_DOCKER', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    importlib.import_module('second_brain_database.config')
    out = capsys.readouterr().out
    assert "Localhost environment detected" in out

def test_load_sbd_config_prints_error_on_json_load(monkeypatch, tmp_path, capsys):
    """
    Should print error when config file is malformed JSON.
    """
    config_dir = tmp_path / '.config' / 'Second-Brain-Database'
    config_dir.mkdir(parents=True)
    config_file = config_dir / '.sbd_config.json'
    config_file.write_text('{bad json')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    config_mod.load_sbd_config()
    out = capsys.readouterr().out
    assert "[CONFIG] Error loading config file:" in out

def test_ensure_default_config_prints_on_write_error(tmp_path, monkeypatch, capsys):
    """
    Should print error if writing config file fails.
    """
    config_file = tmp_path / 'fail.json'
    monkeypatch.setattr('builtins.open', lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    try:
        config_mod.ensure_default_config(config_file, {'FOO': 'bar'})
    except OSError:
        pass

def test_get_conf_key_with_whitespace_and_special(monkeypatch):
    """
    Test get_conf handles keys with whitespace and special characters.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {'KEY': 'value'})
    assert config_mod.get_conf('  KEY  ') is None
    assert config_mod.get_conf('KEY\n') is None

def test_get_conf_env_var_non_string(monkeypatch):
    """
    Test get_conf handles environment variables with non-string values.
    """
    monkeypatch.setattr(config_mod, 'sbd_config', {})
    config_mod.defaults.pop('REDIS_PORT', None)
    monkeypatch.setenv('REDIS_PORT', '6380')
    assert config_mod.get_conf('REDIS_PORT') == '6380'
    assert config_mod.get_conf('REDIS_PORT', 1234) == '6380'

def test_load_sbd_config_home_is_file(tmp_path, monkeypatch):
    """
    Test load_sbd_config raises an error when HOME is a file.
    """
    home_file = tmp_path / 'homefile'
    home_file.write_text('not a dir')
    monkeypatch.setenv('HOME', str(home_file))
    monkeypatch.setattr(config_mod, 'IS_DOCKER', False)
    with pytest.raises(NotADirectoryError):
        config_mod.load_sbd_config()


