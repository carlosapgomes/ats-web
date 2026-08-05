"""Testes da view my_cases — lista com filtros — Slice 4."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseStatus, ExamType

User = get_user_model()
PAGE_URL = reverse("intake:my_cases")


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client):
    """Cria usuário NIR, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    """Cria usuário doctor, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMyCasesList:
    """GET /intake/my-cases/ — renderização da lista de casos do NIR."""

    def test_my_cases_shows_all_operational_cases(self, client) -> None:
        """NIR vê todos os casos operacionais, incluindo de outros NIR (continuidade de plantão)."""
        client, user = _nir_client(client)

        # Caso do NIR logado
        Case.objects.create(
            created_by=user,
            agency_record_number="NIR-001",
            status=CaseStatus.NEW,
        )

        # Caso de outro NIR
        other_user = User.objects.create_user(username="other@test.com")
        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-999",
            status=CaseStatus.NEW,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "NIR-001" in content
        assert "OTHER-999" in content

    def test_my_cases_excludes_cleaned(self, client) -> None:
        """Casos com status CLEANED não devem aparecer na lista."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="ACTIVE-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        Case.objects.create(
            created_by=user,
            agency_record_number="CLEANED-999",
            status=CaseStatus.CLEANED,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "ACTIVE-001" in content
        assert "CLEANED-999" not in content

    def test_my_cases_filter_by_status(self, client) -> None:
        """Filtro ?status=WAIT_DOCTOR mostra apenas casos naquele estado."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="WAITING-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        Case.objects.create(
            created_by=user,
            agency_record_number="NEW-001",
            status=CaseStatus.NEW,
        )

        response = client.get(reverse("intake:my_cases") + "?status=WAIT_DOCTOR")
        assert response.status_code == 200
        content = response.content.decode()
        assert "WAITING-001" in content
        assert "NEW-001" not in content

    def test_my_cases_search_by_record(self, client) -> None:
        """Busca ?q=2026-0428 filtra por número de registro."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="2026-0428-001",
            status=CaseStatus.NEW,
        )
        Case.objects.create(
            created_by=user,
            agency_record_number="2026-0505-002",
            status=CaseStatus.NEW,
        )

        response = client.get(reverse("intake:my_cases") + "?q=0428")
        assert response.status_code == 200
        content = response.content.decode()
        assert "2026-0428-001" in content
        assert "2026-0505-002" not in content

    def test_my_cases_order_by_newest(self, client) -> None:
        """Casos devem ser ordenados por created_at decrescente."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="OLDEST",
            status=CaseStatus.NEW,
        )
        Case.objects.create(
            created_by=user,
            agency_record_number="NEWEST",
            status=CaseStatus.NEW,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        # NEWEST deve aparecer antes de OLDEST no HTML
        pos_newest = content.index("NEWEST")
        pos_oldest = content.index("OLDEST")
        assert pos_newest < pos_oldest

    def test_my_cases_shows_status_label(self, client) -> None:
        """HTML deve conter o label em português do status."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="LABEL-001",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        # Label em português: "Aguardando médico"
        assert "Aguardando médico" in content

    def test_my_cases_has_htmx_polling_container(self, client) -> None:
        """Full my-cases page polls the partial endpoint with current filters."""
        client, _ = _nir_client(client)
        response = client.get(reverse("intake:my_cases") + "?q=0428")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'hx-get="/cases/my-cases/partial/?q=0428"' in content
        assert 'hx-trigger="every 20s"' in content

    def test_my_cases_partial_renders_without_layout(self, client) -> None:
        """HTMX partial returns list content without the full base layout."""
        client, user = _nir_client(client)
        Case.objects.create(created_by=user, agency_record_number="PARTIAL-001", status=CaseStatus.NEW)
        response = client.get(reverse("intake:my_cases_partial"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "<!DOCTYPE html>" not in content
        assert "PARTIAL-001" in content

    def test_my_cases_requires_nir_role(self, client) -> None:
        """Usuário com role doctor deve ser bloqueado."""
        client, _ = _doctor_client(client)
        response = client.get(reverse("intake:my_cases"))
        # role_required redireciona para /
        assert response.status_code == 302

    def test_my_cases_has_closed_cases_link(self, client) -> None:
        """Página 'Meus Casos' renderiza link para Casos Encerrados."""
        client, _ = _nir_client(client)
        response = client.get(PAGE_URL)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Casos Encerrados" in content
        assert reverse("intake:closed_cases_search") in content

    def test_my_cases_status_filter_excludes_cleaned(self, client) -> None:
        """O select de status de my_cases não inclui 'Concluído' (CLEANED)."""
        client, _ = _nir_client(client)
        response = client.get(PAGE_URL)
        assert response.status_code == 200
        content = response.content.decode()
        # 'Concluído' é o label de CLEANED — não deve aparecer no select
        assert "Concluído" not in content
        # 'Todos os status' e outros labels operacionais devem aparecer
        assert "Aguardando médico" in content
        assert "Aceito pelo médico" in content

    def test_my_cases_shows_doctor_with_crm(self, client) -> None:
        """Card do NIR mostra nome do médico e CRM quando preenchido."""
        client, user = _nir_client(client)
        doctor_user = User.objects.create_user(
            username="doc.crm@test.com",
            password="pass123",
            first_name="Maria",
            last_name="Silva",
        )
        doctor_user.professional_council = "CRM"
        doctor_user.professional_council_number = "12345"
        doctor_user.save()

        Case.objects.create(
            created_by=user,
            agency_record_number="DOC-CRM-001",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor_user,
            doctor_decision="accept",
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Silva" in content
        assert "CRM 12345" in content

    def test_my_cases_shows_doctor_without_crm(self, client) -> None:
        """Card do NIR mostra ao menos o nome do médico quando não há CRM."""
        client, user = _nir_client(client)
        doctor_user = User.objects.create_user(
            username="doc.nocrm@test.com",
            password="pass123",
            first_name="João",
            last_name="Souza",
        )

        Case.objects.create(
            created_by=user,
            agency_record_number="DOC-NOCRM-001",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor_user,
            doctor_decision="accept",
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "João Souza" in content

    def test_my_cases_shows_doctor_observation_badge_only_for_filled_observation(self, client) -> None:
        """Card do NIR mostra badge apenas para casos com observação médica preenchida."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="OBS-FILLED-001",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_observation="Observação importante para logística",
        )
        Case.objects.create(
            created_by=user,
            agency_record_number="OBS-EMPTY-001",
            status=CaseStatus.DOCTOR_ACCEPTED,
        )
        Case.objects.create(
            created_by=user,
            agency_record_number="OBS-SPACES-001",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_observation="   ",
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OBS-FILLED-001" in content
        assert "OBS-EMPTY-001" in content
        assert "OBS-SPACES-001" in content
        assert content.count("Orientação médica") == 1
        assert "Observação importante para logística" not in content


# ── Slice 007 — R1: filtro por tipo de exame em Meus Casos ──────────────


@pytest.mark.django_db
class TestMyCasesExamTypeFilter:
    """R1: NIR compõe tipo de exame (Todos/EDA/Colonoscopia) com status e busca."""

    def _make(self, user, exam_type: str, record: str, status: str = CaseStatus.NEW) -> Case:
        return Case.objects.create(
            created_by=user,
            exam_type=exam_type,
            agency_record_number=record,
            status=status,
        )

    def test_default_todos_shows_both_types(self, client) -> None:
        """Sem parâmetro, Todos default mostra EDA e Colonoscopia."""
        client, user = _nir_client(client)
        self._make(user, ExamType.EDA, "EDA-001")
        self._make(user, ExamType.COLONOSCOPY, "COL-001")

        response = client.get(PAGE_URL)
        assert response.status_code == 200
        content = response.content.decode()
        assert "EDA-001" in content
        assert "COL-001" in content

    def test_filter_eda(self, client) -> None:
        """?exam_type=eda lista somente casos EDA."""
        client, user = _nir_client(client)
        self._make(user, ExamType.EDA, "EDA-001")
        self._make(user, ExamType.COLONOSCOPY, "COL-001")

        response = client.get(PAGE_URL + "?exam_type=eda")
        content = response.content.decode()
        assert "EDA-001" in content
        assert "COL-001" not in content

    def test_filter_colonoscopy(self, client) -> None:
        """?exam_type=colonoscopy lista somente casos Colonoscopia."""
        client, user = _nir_client(client)
        self._make(user, ExamType.EDA, "EDA-001")
        self._make(user, ExamType.COLONOSCOPY, "COL-001")

        response = client.get(PAGE_URL + "?exam_type=colonoscopy")
        content = response.content.decode()
        assert "COL-001" in content
        assert "EDA-001" not in content

    def test_invalid_exam_type_falls_back_to_all(self, client) -> None:
        """Tipo inválido cai para Todos (default), sem erro."""
        client, user = _nir_client(client)
        self._make(user, ExamType.EDA, "EDA-001")
        self._make(user, ExamType.COLONOSCOPY, "COL-001")

        response = client.get(PAGE_URL + "?exam_type=cpre")
        content = response.content.decode()
        assert "EDA-001" in content
        assert "COL-001" in content

    def test_composes_with_status(self, client) -> None:
        """Tipo compõe com status (conjunção)."""
        client, user = _nir_client(client)
        self._make(user, ExamType.EDA, "EDA-WAIT", status=CaseStatus.WAIT_DOCTOR)
        self._make(user, ExamType.EDA, "EDA-NEW", status=CaseStatus.NEW)
        self._make(user, ExamType.COLONOSCOPY, "COL-WAIT", status=CaseStatus.WAIT_DOCTOR)

        response = client.get(PAGE_URL + "?exam_type=eda&status=WAIT_DOCTOR")
        content = response.content.decode()
        assert "EDA-WAIT" in content
        assert "EDA-NEW" not in content
        assert "COL-WAIT" not in content

    def test_composes_with_search_term(self, client) -> None:
        """Tipo compõe com busca por ocorrência (conjunção)."""
        client, user = _nir_client(client)
        self._make(user, ExamType.COLONOSCOPY, "2026-COL-001")
        self._make(user, ExamType.EDA, "2026-COL-002")
        self._make(user, ExamType.COLONOSCOPY, "2026-EDA-001")

        response = client.get(PAGE_URL + "?exam_type=colonoscopy&q=COL")
        content = response.content.decode()
        assert "2026-COL-001" in content
        assert "2026-EDA-001" not in content
        assert "2026-COL-002" not in content

    def test_partial_polling_preserves_exam_type(self, client) -> None:
        """Polling partial preserva tipo, status e termo na query string."""
        client, _ = _nir_client(client)
        response = client.get(PAGE_URL + "?exam_type=colonoscopy&q=0428&status=WAIT_DOCTOR")
        content = response.content.decode()
        # Atributo HTML escapa "&": o navegador recebe a query original
        assert 'hx-get="/cases/my-cases/partial/?exam_type=colonoscopy&amp;q=0428&amp;status=WAIT_DOCTOR"' in content
        assert 'hx-trigger="every 20s"' in content

    def test_template_has_exam_type_select_with_todos_default(self, client) -> None:
        """Controle acessível de tipo com default Todos."""
        client, _ = _nir_client(client)
        response = client.get(PAGE_URL)
        content = response.content.decode()
        assert 'name="exam_type"' in content
        assert "Todos os tipos" in content
        assert "Colonoscopia" in content
        assert '<option value="all" selected' in content or 'value="all"' in content

    def test_clear_button_resets_all_filters(self, client) -> None:
        """Botão Limpar aponta para my_cases sem filtros (restaura Todos)."""
        client, _ = _nir_client(client)
        response = client.get(PAGE_URL + "?exam_type=colonoscopy&q=0428")
        content = response.content.decode()
        assert f'href="{PAGE_URL}"' in content

    def test_cards_show_exam_type_badge(self, client) -> None:
        """Cards exibem badge persistido do tipo de exame."""
        client, user = _nir_client(client)
        self._make(user, ExamType.COLONOSCOPY, "COL-BADGE")

        response = client.get(PAGE_URL)
        content = response.content.decode()
        assert "exam-type-colonoscopy" in content
        assert "Colonoscopia" in content
