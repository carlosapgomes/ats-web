#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "classify_risk.py"


class ClassifyRiskTests(unittest.TestCase):
    def test_non_bugfix_description_is_promoted_to_professional(self) -> None:
        run = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "Adicionar campo opcional no formulario de cadastro",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, msg=run.stderr)
        payload = json.loads(run.stdout)
        self.assertEqual(payload["risk_assessment"]["level"], "PROFESSIONAL")
        self.assertTrue(payload["artifact_policy"]["design_required"])
        self.assertIn("promotion_reason", payload["risk_assessment"])

    def test_simple_bugfix_keeps_essential_and_no_design_required(self) -> None:
        run = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "Bug fix simples: corrigir typo no label do botao",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, msg=run.stderr)
        payload = json.loads(run.stdout)
        self.assertEqual(payload["risk_assessment"]["level"], "ESSENTIAL")
        self.assertFalse(payload["artifact_policy"]["design_required"])

    def test_context_adjustment_uses_security_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PROJECT_CONTEXT.md").write_text(
                "Projeto do governo com dados sensiveis LGPD.\n",
                encoding="utf-8",
            )
            run = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "Implementar security hardening para autenticacao",
                    "--format",
                    "json",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn(run.returncode, (0, 2), msg=run.stderr)
            payload = json.loads(run.stdout)
            adjustments = payload["risk_assessment"].get("adjustment_factors", [])
            self.assertTrue(any("segurança" in item or "seguranca" in item for item in adjustments))

    def test_professional_default_exit_code_is_zero(self) -> None:
        run = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "Implementar integração com API externa",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, msg=run.stderr)

    def test_professional_strict_exit_code_is_one(self) -> None:
        run = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "Implementar integração com API externa",
                "--strict-exit-codes",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(run.returncode, 1, msg=run.stderr)


if __name__ == "__main__":
    unittest.main()
