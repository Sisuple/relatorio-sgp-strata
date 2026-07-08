"""IAGON — assistente de IA do painel de pavimentos.

Orquestra a conversa com a OpenAI (streaming + function calling), mantém memória
de longo prazo em arquivo e expõe as ferramentas que a UI executa (exportar/lembrar).
A geração de arquivos e o contexto de dados ficam na app (onde vivem os helpers);
aqui é só a camada de IA.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_BASE = Path(__file__).resolve().parent.parent
_PROMPT_PATH = _BASE / "prompts" / "iagon_system_prompt.md"
_METHODOLOGY_PATH = _BASE / "prompts" / "metodologia_paragon_base_conhecimento.md"
_MEMORY_PATH = _BASE / "data" / "iagon_memory.json"          # legado (curados) — migrado p/ SQLite
_MEMORY_DB_PATH = _BASE / "data" / "iagon_memory.db"         # memória RAG (conversa + fatos)

IAGON_MODEL = os.getenv("IAGON_MODEL", "gpt-4.1")
_EMBED_MODEL = os.getenv("IAGON_EMBED_MODEL", "text-embedding-3-small")
_DISTILL_MODEL = os.getenv("IAGON_DISTILL_MODEL", IAGON_MODEL)
_RAG_TOP_K = int(os.getenv("IAGON_RAG_TOP_K", "6"))


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


# ──────────────────────────── memória de longo prazo (RAG) ────────────────────────────
# SQLite local + embeddings OpenAI. Guarda (a) a conversa crua e (b) fatos destilados
# (★ priorizados). A recuperação é por similaridade de cosseno (top-K) sobre a pergunta.

def _db() -> sqlite3.Connection:
    _MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_MEMORY_DB_PATH), timeout=5)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL DEFAULT 'conversa', "
        "texto TEXT NOT NULL, categoria TEXT DEFAULT 'geral', ts TEXT NOT NULL, embedding BLOB)"
    )
    conn.commit()
    _migrate_json_once(conn)
    return conn


def _migrate_json_once(conn: sqlite3.Connection) -> None:
    """Importa uma vez os fatos curados do antigo iagon_memory.json e arquiva o arquivo."""
    if not _MEMORY_PATH.exists():
        return
    try:
        data = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for m in data:
                fato = (m.get("fato") or "").strip()
                if not fato:
                    continue
                emb = _embed([fato])
                conn.execute(
                    "INSERT INTO memories (tipo, texto, categoria, ts, embedding) VALUES (?,?,?,?,?)",
                    ("fato", fato, m.get("categoria", "geral"),
                     m.get("ts") or time.strftime("%Y-%m-%d %H:%M"),
                     emb[0].tobytes() if emb else None),
                )
            conn.commit()
        _MEMORY_PATH.rename(_MEMORY_PATH.with_name("iagon_memory.json.migrated"))
    except Exception:
        pass


def _embed(texts: list[str]) -> list:
    """Embeddings OpenAI (np.float32). Lista vazia em falha/sem chave."""
    texts = [t for t in texts if t and t.strip()]
    if not texts or not is_configured():
        return []
    try:
        resp = _client().embeddings.create(model=_EMBED_MODEL, input=texts)
        return [np.asarray(d.embedding, dtype=np.float32) for d in resp.data]
    except Exception:
        return []


def add_memory(texto: str, tipo: str = "conversa", categoria: str = "geral") -> None:
    """Insere uma memória (com embedding). Dedupe por (texto, tipo). Best-effort."""
    texto = (texto or "").strip()
    if not texto:
        return
    try:
        conn = _db()
        if conn.execute("SELECT 1 FROM memories WHERE texto=? AND tipo=? LIMIT 1", (texto, tipo)).fetchone():
            conn.close()
            return
        emb = _embed([texto])
        conn.execute(
            "INSERT INTO memories (tipo, texto, categoria, ts, embedding) VALUES (?,?,?,?,?)",
            (tipo, texto, categoria, time.strftime("%Y-%m-%d %H:%M"), emb[0].tobytes() if emb else None),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _recent_memories(k: int) -> list[dict]:
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT tipo, texto, categoria, ts FROM memories ORDER BY id DESC LIMIT ?", (int(k),)
        ).fetchall()
        conn.close()
        return [{"tipo": t, "texto": tx, "categoria": c, "ts": ts} for t, tx, c, ts in rows]
    except Exception:
        return []


def search_memories(query: str, k: int = _RAG_TOP_K) -> list[dict]:
    """Top-K memórias por similaridade de cosseno; fatos curados (★) recebem leve boost."""
    query = (query or "").strip()
    if not query:
        return _recent_memories(k)
    try:
        qe = _embed([query])
        if not qe:
            return _recent_memories(k)
        q = qe[0]
        qn = float(np.linalg.norm(q)) + 1e-9
        conn = _db()
        rows = conn.execute(
            "SELECT tipo, texto, categoria, ts, embedding FROM memories WHERE embedding IS NOT NULL"
        ).fetchall()
        conn.close()
        scored = []
        for tipo, texto, cat, ts, blob in rows:
            v = np.frombuffer(blob, dtype=np.float32)
            if v.shape != q.shape:
                continue
            sim = float(np.dot(v, q) / ((float(np.linalg.norm(v)) + 1e-9) * qn))
            if tipo == "fato":
                sim += 0.05  # prioriza fatos curados sobre conversa crua
            scored.append((sim, tipo, texto, cat, ts))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"tipo": t, "texto": tx, "categoria": c, "ts": ts, "score": round(s, 3)}
                for s, t, tx, c, ts in scored[:k]]
    except Exception:
        return _recent_memories(k)


def distill_facts(pergunta: str, resposta: str) -> list[str]:
    """1 chamada ao modelo: 0–3 fatos DURÁVEIS da troca (prefs, decisões, foco, achados)."""
    if not is_configured():
        return []
    try:
        resp = _client().chat.completions.create(
            model=_DISTILL_MODEL, temperature=0.1, response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content":
                    "Você destila MEMÓRIA de longo prazo de um assistente de pavimentos (DNIT/RO). "
                    "Extraia de 0 a 3 fatos DURÁVEIS e úteis para conversas futuras: preferências do "
                    "usuário, decisões, foco (rodovia/sentido prioritário) e achados específicos com "
                    "números. IGNORE saudações, perguntas triviais e dados que já vêm do relatório "
                    "(são recalculados a cada conversa). Responda SÓ em JSON: "
                    "{\"fatos\": [\"frase curta e objetiva\"]}. Nada a guardar => {\"fatos\": []}."},
                {"role": "user", "content": f"PERGUNTA:\n{pergunta}\n\nRESPOSTA:\n{resposta}"},
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return [str(f).strip() for f in (data.get("fatos") or []) if str(f).strip()][:3]
    except Exception:
        return []


def capture_exchange(pergunta: str, resposta: str) -> None:
    """Captura automática HÍBRIDA: guarda a troca crua + destila fatos-chave. Best-effort."""
    pergunta = (pergunta or "").strip()
    resposta = (resposta or "").strip()
    if not pergunta or not resposta or resposta.startswith("⚠️"):
        return
    add_memory(f"Pergunta: {pergunta}\nResposta: {resposta}"[:4000], tipo="conversa")
    for fato in distill_facts(pergunta, resposta):
        add_memory(fato, tipo="fato")


def remember(fato: str, categoria: str = "geral") -> dict:
    """Ferramenta `lembrar`: grava um fato curado (★) na memória RAG."""
    fato = (fato or "").strip()
    if fato:
        add_memory(fato, tipo="fato", categoria=(categoria or "geral").strip())
    return {"fato": fato, "categoria": (categoria or "geral").strip(), "ts": time.strftime("%Y-%m-%d %H:%M")}


def forget_all() -> None:
    try:
        conn = _db()
        conn.execute("DELETE FROM memories")
        conn.commit()
        conn.close()
    except Exception:
        pass


def memory_count() -> dict:
    """Contagem por tipo (diagnóstico/UI)."""
    try:
        conn = _db()
        rows = conn.execute("SELECT tipo, COUNT(*) FROM memories GROUP BY tipo").fetchall()
        conn.close()
        return {t: c for t, c in rows}
    except Exception:
        return {}


def memory_text(k: int = 12) -> str:
    """Compat: memórias recentes em texto (fallback; o caminho principal é search_memories)."""
    mems = _recent_memories(k)
    if not mems:
        return "(ainda sem memórias)"
    return "\n".join(f"- [{m['tipo']}] {m['texto'][:200]}" for m in mems)


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
    # RAG: recupera memórias relevantes pela última pergunta do usuário (cosseno top-K).
    query = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
    mems = search_memories(query)
    if mems:
        mem_txt = "\n".join(
            f"- {'★ ' if m['tipo'] == 'fato' else ''}[{m.get('ts', '')}] {m['texto'][:400]}"
            for m in mems
        )
    else:
        mem_txt = "(ainda sem memórias relevantes — aprenda com a conversa)"
    sys = (
        system_prompt()
        + "\n\n═══ MEMÓRIA DE LONGO PRAZO (recuperada por relevância; ★ = fato curado) ═══\n"
        + mem_txt
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
