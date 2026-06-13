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
from pathlib import Path
from typing import Any, Callable, Iterator

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_BASE = Path(__file__).resolve().parent.parent
_PROMPT_PATH = _BASE / "prompts" / "iagon_system_prompt.md"
_METHODOLOGY_PATH = _BASE / "prompts" / "metodologia_paragon_base_conhecimento.md"
_MEMORY_PATH = _BASE / "data" / "iagon_memory.json"

IAGON_MODEL = os.getenv("IAGON_MODEL", "gpt-4.1")


def system_prompt() -> str:
    """Lê o prompt principal a cada chamada — permite editar sem reiniciar o servidor."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return "Você é o IAGON, assistente de pavimentos do DNIT. Responda em português."


def methodology_notes() -> str:
    """Lê o arquivo editável `paragon_methodology.md` (conhecimento de domínio do usuário).
    Atualizações no arquivo refletem na próxima conversa, sem reiniciar."""
    try:
        return _METHODOLOGY_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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
                        "description": "'rede' para toda a malha, ou o código/nome de uma rodovia (ex.: 'BR-421', '429').",
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
            "name": "gerar_mapa",
            "description": (
                "Renderiza o MAPA INTERATIVO (Leaflet + Satélite) da rodovia no chat, "
                "exatamente o mesmo componente das telas Diagnóstico/Soluções do painel. "
                "Aceita FILTROS opcionais: 'classes' (IAP Paragon), 'solucoes' (intervenção Paragon), "
                "'faixas_iri' (IRI DNIT). SEM filtro = mostra todos os segmentos. "
                "É sua RESPONSABILIDADE decidir quais filtros aplicar baseado no pedido do usuário "
                "(ex.: 'só péssimos' = classes=['Péssimo'])."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rodovia": {
                        "type": "string",
                        "description": "Código/nome da rodovia (ex.: 'BR-421', 'BR-429', 'BR-435').",
                    },
                    "metodologia": {
                        "type": "string",
                        "enum": ["paragon", "dnit"],
                        "description": "Qual matriz colorir o mapa. Default: paragon.",
                    },
                    "classes": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["Excelente", "Bom", "++ Regular", "+ Regular", "- Regular", "Mau", "Péssimo"],
                        },
                        "description": (
                            "Filtra Paragon por classes IAP. Ex.: ['Péssimo'] mostra só os trechos péssimos, "
                            "['Mau', 'Péssimo'] mostra os críticos. Vazio = todos."
                        ),
                    },
                    "solucoes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filtra Paragon por tipo de solução. Use os nomes exatos: "
                            "'Reconstrução', 'Fresagem e recomposição', 'Recarga Superficial + Reparo localizado', "
                            "'Sem intervenção'. Ex.: ['Reconstrução'] mostra só trechos que precisam Reconstrução."
                        ),
                    },
                    "faixas_iri": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["IRI ≤ 3", "3 < IRI ≤ 4", "4 < IRI ≤ 5,5", "IRI > 5,5"],
                        },
                        "description": (
                            "Filtra DNIT por faixa IRI. Ex.: ['IRI > 5,5'] mostra só trechos críticos."
                        ),
                    },
                    "snvs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filtra por código(s) de SNV/SRE específico(s). "
                            "Ex.: ['421BRO0040'] mostra SÓ esse trecho. "
                            "Use sempre que o usuário pedir 'só o SNV X' ou 'apenas o trecho 421BRO0040'."
                        ),
                    },
                },
                "required": ["rodovia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_plano_trabalho",
            "description": (
                "Gera um PLANO DE TRABALHO real (PDF/Excel/CSV) com a LISTA segmento a segmento "
                "dos trechos a serem intervindos: SNV, km inicial/final, extensão, IAP/IRI, classe, "
                "intervenção recomendada e custo, além de resumo por solução. "
                "Aceita os MESMOS filtros do mapa (classes, soluções, faixas IRI) — use os mesmos "
                "que foram aplicados na última chamada de gerar_mapa para manter coerência. "
                "Sempre que o usuário pedir 'plano de trabalho', 'plano de obras', 'lista de trechos', "
                "'plano de intervenções', use esta tool — NUNCA `exportar_relatorio` para isso."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rodovia": {"type": "string", "description": "Ex.: 'BR-421'."},
                    "metodologia": {
                        "type": "string",
                        "enum": ["paragon", "dnit"],
                        "description": "Default: paragon.",
                    },
                    "classes": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["Excelente", "Bom", "++ Regular", "+ Regular", "- Regular", "Mau", "Péssimo"],
                        },
                        "description": "Paragon: filtra por classes IAP. Use os mesmos do mapa.",
                    },
                    "solucoes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paragon: filtra por solução (ex.: ['Reconstrução']).",
                    },
                    "faixas_iri": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["IRI ≤ 3", "3 < IRI ≤ 4", "4 < IRI ≤ 5,5", "IRI > 5,5"],
                        },
                        "description": "DNIT: filtra por faixa IRI.",
                    },
                    "snvs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtra por código(s) de SNV/SRE (ex.: ['421BRO0040']).",
                    },
                    "formato": {
                        "type": "string",
                        "enum": ["pdf", "excel", "csv"],
                        "description": "Default: pdf.",
                    },
                },
                "required": ["rodovia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simular_cenario_economico",
            "description": (
                "Roda o MESMO pipeline da página Cenário Econômico do painel e devolve os "
                "NÚMEROS EXATOS: cobertura anual, km atendidos, orçamento faltante, lista "
                "de SNVs atendidos vs fora do orçamento, custo por ano. "
                "USE SEMPRE QUE O USUÁRIO MENCIONAR UM ORÇAMENTO ESPECÍFICO "
                "(ex.: 'com 20 mi', 'se eu tiver R$ 50 mi por ano', 'quanto cubro com X mi'). "
                "Se o usuário pedir um relatório, passe formato='pdf' (ou 'excel') para também "
                "gerar o arquivo de download."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rodovia": {"type": "string", "description": "Ex.: 'BR-421'."},
                    "orcamento_anual_mi": {
                        "type": "integer",
                        "description": "Orçamento anual em R$ milhões. Ex.: 20 para R$ 20 mi/ano.",
                    },
                    "horizonte_anos": {
                        "type": "integer",
                        "description": "Horizonte em anos. Default = 8 anos.",
                    },
                    "metodologia": {
                        "type": "string",
                        "enum": ["paragon", "dnit"],
                        "description": "Default: paragon.",
                    },
                    "formato": {
                        "type": "string",
                        "enum": ["pdf", "excel", "csv"],
                        "description": "Opcional. Se informado, também gera o arquivo do cenário.",
                    },
                },
                "required": ["rodovia", "orcamento_anual_mi"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_metodologias",
            "description": (
                "Compara Paragon × DNIT para uma rodovia: necessidade, cobertura anual, km atendidos "
                "e delta. Use quando o usuário pedir 'compare as duas metodologias', 'qual mais cara', "
                "'qual cobre mais km'. Devolve um dicionário JSON-like que você deve interpretar e "
                "apresentar em uma resposta executiva (tabela)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rodovia": {"type": "string", "description": "Ex.: 'BR-421'."},
                    "orcamento_anual_mi": {
                        "type": "integer",
                        "description": "Orçamento anual em R$ milhões (default 50).",
                    },
                    "horizonte_anos": {
                        "type": "integer",
                        "description": "Horizonte de planejamento em anos (default 8).",
                    },
                },
                "required": ["rodovia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_grafico",
            "description": (
                "Renderiza um gráfico PNG (matplotlib) e exibe inline no chat. "
                "Use quando o usuário pedir um GRÁFICO, COMPARATIVO VISUAL, DISTRIBUIÇÃO, "
                "PROJEÇÃO ou EVOLUÇÃO. É sua responsabilidade escolher o 'tipo' adequado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": [
                            "distribuicao_iap",
                            "distribuicao_solucoes",
                            "custo_por_ano",
                            "comparativo_rodovias",
                            "projecao_iap",
                        ],
                        "description": (
                            "Tipo do gráfico: "
                            "distribuicao_iap (pie/donut % por classe IAP de 1 rodovia); "
                            "distribuicao_solucoes (bar km por solução, Paragon ou DNIT); "
                            "custo_por_ano (bar R$/ano, Paragon ou DNIT); "
                            "comparativo_rodovias (IAP médio + necessidade entre rodovias); "
                            "projecao_iap (line chart evolução IAP de um SRE)."
                        ),
                    },
                    "rodovia": {
                        "type": "string",
                        "description": "Rodovia (ex.: 'BR-421'). Obrigatório para todos os tipos exceto 'comparativo_rodovias'.",
                    },
                    "rodovias": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Para 'comparativo_rodovias': lista de rodovias. Omitir = todas.",
                    },
                    "metodologia": {
                        "type": "string",
                        "enum": ["paragon", "dnit"],
                        "description": "Para distribuicao_solucoes/custo_por_ano. Default: paragon.",
                    },
                    "sre": {
                        "type": "string",
                        "description": "Para 'projecao_iap': código do SRE (ex.: '421BRO0040').",
                    },
                },
                "required": ["tipo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lembrar",
            "description": (
                "Salva um aprendizado ou preferência na memória de longo prazo do IAGON, para reusar em "
                "conversas futuras (ex.: 'o diretor foca na BR-429', 'prefere relatórios em PDF'). Use só o útil."
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
    messages = [{"role": "system", "content": sys}]

    metodologia = methodology_notes()
    if metodologia:
        messages.append({
            "role": "system",
            "content": (
                "═══ BASE DE CONHECIMENTO — METODOLOGIA PARAGON ═══\n"
                "(notas editáveis do engenheiro responsável — leia antes de responder "
                "perguntas sobre a metodologia)\n\n" + metodologia
            ),
        })

    messages.append({
        "role": "system",
        "content": "DADOS DO RELATÓRIO — use SOMENTE estes números, não invente:\n\n" + context_text,
    })
    messages.extend(history)
    return messages


def analisar(context_text: str, pergunta: str, *, temperature: float = 0.3) -> str:
    """Análise one-shot (sem tools, sem streaming) usando o mesmo system prompt,
    base de conhecimento e MEMÓRIA de longo prazo da IAGON. Devolve o texto."""
    if not is_configured():
        return ""
    client = _client()
    messages = _build_messages(context_text, [{"role": "user", "content": pergunta}])
    resp = client.chat.completions.create(
        model=IAGON_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


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
