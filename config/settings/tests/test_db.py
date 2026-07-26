"""Testes unitários para get_db_config()."""

import os
import tempfile

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.db import get_db_config


class TestGetDbConfig:
    """Cobre ambos os caminhos: DATABASE_URL e variáveis individuais."""

    # ── Caminho DATABASE_URL ──────────────────────────────────────────

    def test_database_url_takes_precedence(self, monkeypatch):
        """DATABASE_URL presente → ignora variáveis individuais."""
        monkeypatch.setenv("DATABASE_URL", "postgres://url_user:url_pass@url_host:9999/url_db")
        monkeypatch.setenv("DB_HOST", "individual_host")
        monkeypatch.setenv("DB_NAME", "individual_db")
        monkeypatch.setenv("DB_USER", "individual_user")
        monkeypatch.setenv("DB_PASSWORD", "individual_pass")

        config = get_db_config()

        assert config["HOST"] == "url_host"
        assert config["PORT"] == 9999
        assert config["NAME"] == "url_db"
        assert config["USER"] == "url_user"
        assert config["PASSWORD"] == "url_pass"

    # ── Caminho variáveis individuais (dict direto) ───────────────────

    def test_individual_vars_dict_direct(self, monkeypatch):
        """DB_HOST + DB_NAME + DB_USER + DB_PASSWORD → dict Django direto."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")
        monkeypatch.setenv("DB_PORT", "5433")

        config = get_db_config()

        assert config["ENGINE"] == "django.db.backends.postgresql"
        assert config["HOST"] == "myhost"
        assert config["PORT"] == "5433"  # str, pois é o que Django espera
        assert config["NAME"] == "mydb"
        assert config["USER"] == "myuser"
        assert config["PASSWORD"] == "mypass"

    def test_password_special_chars_preserved(self, monkeypatch):
        """Senha com @:;/% → preservada intacta (prova que não passou por URL)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        special_password = "p@ss:word/with%special;chars"
        monkeypatch.setenv("DB_PASSWORD", special_password)

        config = get_db_config()

        assert config["PASSWORD"] == special_password

    # ── DB_PASSWORD_FILE ──────────────────────────────────────────────

    def test_password_file_read(self, monkeypatch):
        """DB_PASSWORD_FILE → senha lida do arquivo."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("secret-from-file\n")
            tmp_path = f.name

        try:
            monkeypatch.setenv("DB_PASSWORD_FILE", tmp_path)
            config = get_db_config()
            assert config["PASSWORD"] == "secret-from-file"
        finally:
            os.unlink(tmp_path)

    def test_password_file_precedence_over_password(self, monkeypatch):
        """DB_PASSWORD_FILE + DB_PASSWORD → arquivo vence."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "ignored-pass")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("file-pass\n")
            tmp_path = f.name

        try:
            monkeypatch.setenv("DB_PASSWORD_FILE", tmp_path)
            config = get_db_config()
            assert config["PASSWORD"] == "file-pass"
        finally:
            os.unlink(tmp_path)

    def test_password_file_not_found_raises(self, monkeypatch):
        """DB_PASSWORD_FILE inexistente → ImproperlyConfigured."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD_FILE", "/tmp/does-not-exist-12345")

        with pytest.raises(ImproperlyConfigured):
            get_db_config()

    def test_password_file_empty_raises(self, monkeypatch):
        """DB_PASSWORD_FILE aponta para arquivo vazio → ImproperlyConfigured."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            # arquivo vazio — não escreve nada
            tmp_path = f.name

        try:
            monkeypatch.setenv("DB_PASSWORD_FILE", tmp_path)
            with pytest.raises(ImproperlyConfigured):
                get_db_config()
        finally:
            os.unlink(tmp_path)

    # ── Defaults ──────────────────────────────────────────────────────

    def test_default_port_5432(self, monkeypatch):
        """DB_PORT não setado → default 5432 como str."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")

        config = get_db_config()
        assert config["PORT"] == "5432"

    def test_default_host_db(self, monkeypatch):
        """DB_HOST não setado → default 'db'."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")

        config = get_db_config()
        assert config["HOST"] == "db"

    def test_missing_password_raises_when_no_default(self, monkeypatch):
        """Sem DATABASE_URL, sem DB_PASSWORD, sem DB_PASSWORD_FILE, sem default → erro."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        monkeypatch.delenv("DB_USER", raising=False)

        # default_db_password=None (padrão) → deve falhar
        with pytest.raises(ImproperlyConfigured):
            get_db_config()

    # ── DB_CONN_MAX_AGE ───────────────────────────────────────────────

    def test_conn_max_age_from_env_overrides_param(self, monkeypatch):
        """DB_CONN_MAX_AGE setado → sobrescreve param."""
        monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
        monkeypatch.setenv("DB_CONN_MAX_AGE", "30")

        config = get_db_config(conn_max_age=600)
        assert config["CONN_MAX_AGE"] == 30

    def test_conn_max_age_defaults_to_param(self, monkeypatch):
        """DB_CONN_MAX_AGE não setado → usa param."""
        monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")

        config = get_db_config(conn_max_age=600)
        assert config["CONN_MAX_AGE"] == 600

    # ── DB_APPLICATION_NAME ───────────────────────────────────────────

    def test_application_name_from_env(self, monkeypatch):
        """DB_APPLICATION_NAME setado → OPTIONS.application_name."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")
        monkeypatch.setenv("DB_APPLICATION_NAME", "myapp")

        config = get_db_config()
        assert config["OPTIONS"]["application_name"] == "myapp"

    # ── Cenário dev ───────────────────────────────────────────────────

    def test_dev_defaults_scenario(self, monkeypatch):
        """Simula ambiente dev: sem DATABASE_URL, com defaults de dev."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Não seta DB_HOST, DB_NAME, DB_USER, DB_PASSWORD — usa defaults

        config = get_db_config(
            default_db_host="localhost",
            default_db_port="5432",
            default_db_name="ats_web_dev",
            default_db_password="ats_web_dev",
            conn_max_age=0,
            conn_health_checks=False,
        )

        assert config["HOST"] == "localhost"
        assert config["PORT"] == "5432"
        assert config["NAME"] == "ats_web_dev"
        assert config["USER"] == "ats_web"
        assert config["PASSWORD"] == "ats_web_dev"
        assert config["CONN_MAX_AGE"] == 0
        assert config["CONN_HEALTH_CHECKS"] is False
