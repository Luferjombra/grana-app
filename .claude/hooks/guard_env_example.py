"""Bloqueia escrita em `*.env.example`.

Este hook existe por causa de um incidente real neste repositório: credenciais
de verdade (Supabase service key, Mindee, Pluggy) foram colar em
`apps/backend/.env.example`. Os quatro `.env.example` são **rastreados** no git —
e precisam ser, porque documentam as variáveis esperadas — num repositório
**público**. O `.gitignore` corretamente não os ignora, então a porta pela qual o
incidente passou continua aberta.

Na ocasião as chaves não entraram em commit nenhum, o que foi verificado com
`git log --all -p`. Mas foi sorte, não processo.

Lê o `file_path` do JSON em vez de dar grep no stdin inteiro: o próprio CLAUDE.md
menciona `.env.example` em texto, e grep cru bloquearia editar a documentação.

Saída 2 bloqueia a chamada da ferramenta e devolve a mensagem ao agente.
"""

import json
import sys
from pathlib import PurePosixPath

# Ferramentas que escrevem arquivo. Se aparecer uma nova, ela passa batida —
# o hook é uma trava a mais, não a única linha de defesa.
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

MESSAGE = """BLOQUEADO: {path}

`.env.example` é rastreado no git e este repositório é público. Ele documenta
QUAIS variáveis existem, nunca os valores.

Se a intenção era guardar uma credencial, o arquivo é `.env` (gitignored).
Se era mesmo documentar uma variável nova, use um placeholder — `SUA_CHAVE_AQUI`
— e nunca o valor real.

Contexto: neste repo, chaves reais já foram colar num `.env.example`. Elas não
chegaram a entrar em commit, mas por verificação manual, não por processo."""


def main() -> int:
    raw_stdin = sys.stdin.read()

    try:
        payload = json.loads(raw_stdin)
    except (json.JSONDecodeError, ValueError):
        # Payload ilegível não pode virar passe livre num hook de segurança, nem
        # travar o projeto inteiro por mudança de formato. O meio honesto: se o
        # texto bruto menciona `.env.example`, bloqueia; se não menciona, deixa
        # passar, porque aí não havia nada a proteger de todo modo.
        if ".env.example" in raw_stdin:
            print(MESSAGE.format(path="(payload ilegível mencionando .env.example)"), file=sys.stderr)
            return 2
        return 0

    if payload.get("tool_name") not in WRITE_TOOLS:
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw:
        return 0

    # Compara só o nome do arquivo: o caminho vem absoluto e com separador de
    # Windows, e o que importa é o sufixo.
    name = PurePosixPath(raw.replace("\\", "/")).name
    if name == ".env.example" or name.endswith(".env.example"):
        print(MESSAGE.format(path=raw), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
