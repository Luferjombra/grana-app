"""Exige atualização do CLAUDE.md quando o commit toca código.

O CLAUDE.md deste projeto define um fluxo obrigatório de duas partes:

  1. rodar `/code-review` antes de qualquer commit;
  2. atualizar a seção "Status atual" ao commitar.

Só a segunda é verificável por máquina, e é o que este hook faz: se o commit
mexe em `apps/`, `etl/` ou `infra/` e não mexe no CLAUDE.md, algo foi esquecido.

A primeira **não tem como ser verificada** — não existe artefato que prove que a
revisão rodou. O hook aproveita o bloqueio pra lembrar, mas quem garante isso é
disciplina, não automação. Dizer o contrário seria vender garantia que não existe.

O CLAUDE.md é o handoff entre sessões: se ele desatualiza, a próxima sessão
reabre decisão já fechada ou reimplementa o que existe.
"""

import json
import subprocess
import sys

# Onde mora código de produto. Mexer aqui muda o que a próxima sessão precisa
# saber; mexer em protótipo, doc ou config, não necessariamente.
CODE_PREFIXES = ("apps/", "etl/", "infra/")

HANDOFF = "CLAUDE.md"

MESSAGE = """BLOQUEADO: commit toca código sem atualizar o {handoff}.

Arquivos de código no commit:
{files}

O fluxo obrigatório deste projeto (está no {handoff}) tem duas partes:

  1. rodar `/code-review` antes do commit — e corrigir o que for relevante
  2. atualizar a seção "Status atual" do {handoff}

Este hook checa a parte 2, que é a única verificável: o {handoff} é o handoff
entre sessões, e desatualizado ele faz a próxima reabrir decisão já fechada.

A parte 1 nenhum hook consegue verificar, porque não deixa artefato. Se ainda não
rodou o `/code-review`, rode antes de commitar."""


def staged_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    if "git commit" not in command:
        return 0

    files = staged_files()
    if not files:
        # Nada staged: é `--amend` só de mensagem, ou o commit vai falhar sozinho
        # por outro motivo. Não é assunto deste hook.
        return 0

    code = [path for path in files if path.startswith(CODE_PREFIXES)]
    if not code:
        return 0  # protótipo, doc, config: não exige nota de status
    if HANDOFF in files:
        return 0

    listed = "\n".join(f"  - {path}" for path in code[:10])
    if len(code) > 10:
        listed += f"\n  ... e outros {len(code) - 10}"

    print(MESSAGE.format(handoff=HANDOFF, files=listed), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
