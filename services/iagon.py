"""IAGON — assistente de IA do painel de pavimentos.

Orquestra a conversa com a OpenAI (streaming + function calling), mantém memória
de longo prazo em arquivo e expõe as ferramentas que a UI executa (exportar/lembrar).
A geração de arquivos e o contexto de dados ficam na app (onde vivem os helpers);
aqui é só a camada de IA.
"""
from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterator

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_BASE = Path(__file__).resolve().parent.parent
_PROMPT_PATH = _BASE / "prompts" / "iagon_system_prompt.md"
_MEMORY_PATH = _BASE / "data" / "iagon_memory.json"

IAGON_MODEL = os.getenv("IAGON_MODEL", "gpt-4.1")


@lru_cache(maxsize=1)
def system_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return "Você é o IAGON, assistente de pavimentos do DNIT. Responda em português."


def is_configured() -> bool:
    return bool(os.getenv("API_OPENAI_KEY"))


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("API_OPENAI_KEY"))


# ──────────────────────────── memória de longo prazo ────────────────────────────
def load_memory() -> list[dict]:
    try:
        data = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_memory(items: list[dict]) -> None:
    _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def remember(fato: str, categoria: str = "geral") -> dict:
    fato = (fato or "").strip()
    item = {"fato": fato, "categoria": (categoria or "geral").strip(), "ts": time.strftime("%Y-%m-%d %H:%M")}
    if fato:
        items = load_memory()
        # evita duplicar o mesmo fato
        if not any(m.get("fato", "").lower() == fato.lower() for m in items):
            items.append(item)
            save_memory(items)
    return item


def forget_all() -> None:
    save_memory([])


def memory_text() -> str:
    items = load_memory()
    if not items:
        return "(ainda sem memórias — aprenda com a conversa usando a ferramenta lembrar)"
    return "\n".join(f"- [{m.get('categoria', 'geral')}] {m.get('fato', '')}" for m in items[-40:])


# ──────────────────────────── ferramentas ────────────────────────────
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "exportar_relatorio",
            "description": (
                "Gera um arquivo REAL (PDF, Excel ou CSV) a partir dos dados verdadeiros do relatório "
                "e mostra o botão de download para o usuário. Use quando pedirem exportar/baixar/gerar "
                "relatório ou planilha, ou quando você sugerir e o usuário aceitar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "escopo": {
                        "type": "string",
                        "description": "'rede' para toda a malha, ou o código/nome de uma rodovia (ex.: '364', 'BR-364/RO').",
                    },
                    "formato": {"type": "string", "enum": ["pdf", "excel", "csv"]},
                    "titulo": {"type": "string", "description": "Título opcional do relatório."},
                },
                "required": ["escopo", "formato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lembrar",
            "description": (
                "Salva um aprendizado ou preferência na memória de longo prazo do IAGON, para reusar em "
                "conversas futuras (ex.: 'o diretor foca na BR-364', 'prefere relatórios em PDF'). Use só o útil."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fato": {"type": "string", "description": "O que aprender, em uma frase."},
                    "categoria": {"type": "string", "description": "Ex.: preferência, foco, decisão."},
                },
                "required": ["fato"],
            },
        },
    },
]


def _build_messages(context_text: str, history: list[dict]) -> list[dict]:
    sys = (
        system_prompt()
        + "\n\n═══ MEMÓRIA DE LONGO PRAZO (o que você já aprendeu) ═══\n"
        + memory_text()
    )
    messages = [
        {"role": "system", "content": sys},
        {
            "role": "system",
            "content": (
                "DADOS DO RELATÓRIO — use SOMENTE estes números, não invente:\n\n" + context_text
            ),
        },
    ]
    messages.extend(history)
    return messages


def run_chat(
    context_text: str,
    history: list[dict],
    on_tool: Callable[[str, dict], str],
    *,
    max_rounds: int = 4,
) -> Iterator[str]:
    """Conversa com tools. Faz streaming do texto (yield) e executa tool calls via `on_tool`.

    `history` = lista de {role, content} (user/assistant). `on_tool(nome, args)` executa a
    ferramenta e devolve o texto-resultado (que volta ao modelo).
    """
    client = _client()
    messages = _build_messages(context_text, history)

    for _ in range(max_rounds):
        stream = client.chat.completions.create(
            model=IAGON_MODEL,
            messages=messages,
            tools=TOOLS,
            stream=True,
            temperature=0.3,
        )
        text_parts: list[str] = []
        tool_calls: dict[int, dict] = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                text_parts.append(delta.content)
                yield delta.content
            for tc in (delta.tool_calls or []):
                slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        if not tool_calls:
            return

        messages.append(
            {
                "role": "assistant",
                "content": "".join(text_parts) or None,
                "tool_calls": [
                    {
                        "id": t["id"],
                        "type": "function",
                        "function": {"name": t["name"], "arguments": t["args"] or "{}"},
                    }
                    for t in tool_calls.values()
                ],
            }
        )
        for t in tool_calls.values():
            try:
                args = json.loads(t["args"] or "{}")
            except ValueError:
                args = {}
            result = on_tool(t["name"], args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": t["id"], "content": result or "ok"})
    return
