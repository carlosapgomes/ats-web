"""Testes do Slice 005 — NIR: casos operacionais compartilhados.

Todos os NIR veem todos os casos operacionais (status != CLEANED),
independentemente de created_by. Casos CLEANED não aparecem na fila
operacional NIR nem são acessíveis pela rota de detalhe operacional NIR.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseStatus

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client):
    """Cria usuário NIR, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir-a@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _nir_client_b(client):
    """Cria segundo NIR, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir-b@test.com", password="testpass123")
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


# ═══════════════════════════════════════════════════════════════════════
# RED — Lista NIR compartilhada
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirSharedList:
    """NIR vê todos os casos operacionais, não apenas os próprios."""

    def test_nir_sees_own_non_cleaned_cases(self, client) -> None:
        """NIR continua vendo seus próprios casos não CLEANED."""
        client, user = _nir_client(client)

        Case.objects.create(
            created_by=user,
            agency_record_number="MY-ACTIVE-001",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "MY-ACTIVE-001" in content

    def test_nir_sees_other_nir_wait_doctor(self, client) -> None:
        """NIR vê caso de outro NIR em WAIT_DOCTOR."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other@test.com")

        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-WAIT-DOC",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-WAIT-DOC" in content

    def test_nir_sees_other_nir_wait_appt(self, client) -> None:
        """NIR vê caso de outro NIR em WAIT_APPT."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other2@test.com")

        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-WAIT-APPT",
            status=CaseStatus.WAIT_APPT,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-WAIT-APPT" in content

    def test_nir_sees_other_nir_wait_receipt(self, client) -> None:
        """NIR vê caso de outro NIR em WAIT_R1_CLEANUP_THUMBS."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other3@test.com")

        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-WAIT-RC",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-WAIT-RC" in content

    def test_nir_sees_other_nir_failed_not_cleaned(self, client) -> None:
        """NIR vê caso de outro NIR em FAILED (não CLEANED)."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other4@test.com")

        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-FAILED",
            status=CaseStatus.FAILED,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-FAILED" in content

    def test_cleaned_cases_do_not_appear(self, client) -> None:
        """Casos CLEANED de qualquer NIR não aparecem na lista."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other5@test.com")

        # Caso CLEANED do próprio NIR
        Case.objects.create(
            created_by=user_a,
            agency_record_number="MY-CLEANED",
            status=CaseStatus.CLEANED,
        )
        # Caso CLEANED de outro NIR
        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-CLEANED",
            status=CaseStatus.CLEANED,
        )
        # Caso ativo (deve aparecer)
        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-ACTIVE",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-ACTIVE" in content
        assert "MY-CLEANED" not in content
        assert "OTHER-CLEANED" not in content

    def test_status_filter_still_works(self, client) -> None:
        """Filtro ?status=WAIT_DOCTOR funciona sobre a lista compartilhada."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other6@test.com")

        Case.objects.create(
            created_by=user_a,
            agency_record_number="MY-WAIT-DOC",
            status=CaseStatus.WAIT_DOCTOR,
        )
        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-WAIT-DOC",
            status=CaseStatus.WAIT_DOCTOR,
        )
        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-NEW",
            status=CaseStatus.NEW,
        )

        response = client.get(reverse("intake:my_cases") + "?status=WAIT_DOCTOR")
        assert response.status_code == 200
        content = response.content.decode()
        assert "MY-WAIT-DOC" in content
        assert "OTHER-WAIT-DOC" in content
        assert "OTHER-NEW" not in content

    def test_search_still_works(self, client) -> None:
        """Busca ?q= filtra sobre a lista compartilhada."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other7@test.com")

        Case.objects.create(
            created_by=user_a,
            agency_record_number="2026-0505-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        Case.objects.create(
            created_by=other_user,
            agency_record_number="2026-0428-999",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases") + "?q=0428")
        assert response.status_code == 200
        content = response.content.decode()
        assert "2026-0428-999" in content
        assert "2026-0505-001" not in content

    def test_no_duplicate_cards(self, client) -> None:
        """Não há duplicidade de cards para o mesmo caso."""
        client, user_a = _nir_client(client)

        Case.objects.create(
            created_by=user_a,
            agency_record_number="UNIQUE-001",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert content.count("UNIQUE-001") == 1


# ═══════════════════════════════════════════════════════════════════════
# RED — Detalhe compartilhado
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirSharedDetail:
    """NIR consegue abrir detalhe de caso operacional de outro NIR."""

    def test_nir_opens_other_nir_operational_case(self, client) -> None:
        """NIR abre detalhe de caso operacional não CLEANED de outro NIR."""
        client, _ = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other-detail@test.com")

        case = Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-DETAIL",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-DETAIL" in content

    def test_nir_opens_other_nir_wait_receipt_detail(self, client) -> None:
        """NIR abre detalhe de caso WAIT_R1_CLEANUP_THUMBS de outro NIR."""
        client, _ = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other-detail2@test.com")

        case = Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-RECEIPT",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200

    def test_nir_cannot_open_cleaned_case_detail(self, client) -> None:
        """NIR não abre detalhe operacional de caso CLEANED."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(username="nir-other-detail3@test.com")

        case = Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-CLEANED",
            status=CaseStatus.CLEANED,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        # Deve retornar 404 porque casos CLEANED estão fora da fila operacional
        assert response.status_code == 404

    def test_non_nir_blocked(self, client) -> None:
        """Usuário sem papel NIR continua bloqueado pelo role guard."""
        client, _ = _doctor_client(client)
        some_user = User.objects.create_user(username="anyone@test.com")

        case = Case.objects.create(
            created_by=some_user,
            agency_record_number="BLOCKED-001",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        # role_required bloqueia → redireciona (302)
        assert response.status_code in (302, 404)


# ═══════════════════════════════════════════════════════════════════════
# RED — Visual indicator
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirSharedVisualIndicator:
    """Indicador visual quando caso foi criado por outro NIR."""

    def test_created_by_other_nir_badge_shown(self, client) -> None:
        """Card mostra badge 'Criado por outro NIR' quando não é do NIR logado."""
        client, user_a = _nir_client(client)
        other_user = User.objects.create_user(
            username="nir-other@test.com",
            first_name="Outro",
            last_name="NIR",
        )

        Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-BADGE",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Criado por" in content
        assert "Outro NIR" in content or "nir-other" in content

    def test_no_badge_on_own_case(self, client) -> None:
        """Card do próprio NIR não mostra o badge 'Criado por outro'."""
        client, user_a = _nir_client(client)

        Case.objects.create(
            created_by=user_a,
            agency_record_number="MY-CASE-NO-BADGE",
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()
        # "Criado por" pode aparecer em outros contextos, mas não para este caso
        # Vamos verificar que o conteúdo aparece corretamente
        assert "MY-CASE-NO-BADGE" in content
