#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "generate_agents_md.py"


class GenerateAgentsMdTests(unittest.TestCase):
    def test_generates_agents_for_django_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manage.py").write_text("print('django')\n", encoding="utf-8")
            (root / "requirements.txt").write_text("Django==5.0.6\n", encoding="utf-8")
            (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

            run = subprocess.run(
                ["python3", str(SCRIPT), "--project-root", str(root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)

            content = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## 2. Comandos de Validacao", content)
            self.assertIn("python3 manage.py check", content)
            self.assertIn("python3 -m pytest -q", content)
            self.assertIn("TDD obrigatorio: RED (teste falha) -> GREEN (minimo para passar) -> REFACTOR (limpeza sem quebrar).", content)
            self.assertIn("Follow TDD cycle: RED (failing test) -> GREEN (minimal pass) -> REFACTOR (clean safely).", content)
            self.assertIn("Implementar uma task slice vertical por vez (end-to-end).", content)
            self.assertIn("Nao quebrar o trabalho em slice horizontal por camada sem entrega de fluxo completo.", content)
            self.assertIn("Planejar slices enxutos: tocar poucos arquivos (ideal <= 5) e so o necessario para entregar valor.", content)
            self.assertIn("Cada slice deve incluir handoff + prompt pronto para implementador LLM com contexto zero.", content)
            self.assertIn("No REFACTOR, reforcar clean code: nomes claros, funcoes coesas, baixo acoplamento e remocao de codigo morto.", content)
            self.assertIn("design.md e obrigatorio, exceto QUICK de bugfix simples e reversivel.", content)
            self.assertIn("Gerar relatorio detalhado do slice com snippets antes/depois e salvar em markdown temporario.", content)
            self.assertIn("REPORT_PATH informado para avaliacao do planner", content)
            self.assertIn("Fazer commit com mensagem rastreavel e dar push para branch remota.", content)
            self.assertIn("Nao iniciar o proximo slice sem confirmacao explicita do usuario.", content)
            self.assertIn("Push realizado para branch remota", content)

    def test_includes_markdown_and_hook_commands_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            (root / ".githooks").mkdir(parents=True, exist_ok=True)
            (root / "scripts/markdown-format.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / "scripts/markdown-lint.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / ".githooks/pre-commit").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            run = subprocess.run(
                ["python3", str(SCRIPT), "--project-root", str(root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)

            content = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("./scripts/markdown-format.sh", content)
            self.assertIn("./scripts/markdown-lint.sh", content)
            self.assertIn("git config core.hooksPath .githooks", content)
            self.assertIn("Markdown lint sem erros", content)

    def test_check_mode_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("Django==5.0.6\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("old-content\n", encoding="utf-8")

            run = subprocess.run(
                ["python3", str(SCRIPT), "--project-root", str(root), "--check"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 2, msg=run.stderr)


if __name__ == "__main__":
    unittest.main()
