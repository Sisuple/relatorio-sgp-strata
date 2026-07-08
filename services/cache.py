"""Cache distribuído via Redis com fallback para `lru_cache` em memória.

Uso:
    from services.cache import cached

    @cached(ttl=600)
    def funcao_pesada(arg1, arg2):
        ...

Características:
- Cache **compartilhado entre workers** quando Redis está disponível.
- **Fallback automático** para in-memory (`functools.lru_cache`) se Redis cai.
- Serializa retornos (DataFrames, dicts, listas) via `pickle`.
- TTL configurável por chave.
- `cache_clear(funcao_pesada)` invalida todas as chaves daquela função.
- `cache_flush_all()` zera tudo (use com cuidado).

Variáveis de ambiente:
    REDIS_URL — ex.: 'redis://localhost:6379/0'. Se ausente ou inválido,
                cai no fallback in-memory.
    CACHE_PREFIX — prefixo das chaves no Redis (default: 'sgp:').
"""
from __future__ import annotations

import hashlib
import logging
import os
import pickle
from functools import lru_cache, wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Garante que o .env (com MYSQL_DB) esteja carregado antes de montar o prefixo.
# Necessário porque este módulo é importado antes do src.database (que também
# chama load_dotenv) na cadeia de imports do v1. Idempotente.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Prefixo isolado por banco: v1 (sigma_dnitro) e v2/gestao (sigma_dnitro_backup)
# dividem o mesmo Redis. Sem o nome do banco no prefixo, os caches (chaveados
# só pelos argumentos) colidiriam e um serviço serviria dados do outro, além de
# o flush de um zerar o cache do outro. CACHE_PREFIX explícito tem precedência.
_CACHE_PREFIX = os.getenv("CACHE_PREFIX") or f"sgp:{os.getenv('MYSQL_DB', '')}:"
_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "1800"))  # 30 min

_redis_client = None
_redis_alive = False


def _connect_redis():
    """Conecta no Redis uma vez. Em falha, marca `_redis_alive = False`."""
    global _redis_client, _redis_alive
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        client = redis.Redis.from_url(
            _REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=False,
        )
        client.ping()
        _redis_client = client
        _redis_alive = True
        logger.info(f"Cache: conectado ao Redis em {_REDIS_URL}")
    except Exception as exc:
        logger.warning(f"Cache: Redis indisponível ({exc!r}), usando lru_cache local")
        _redis_alive = False
        _redis_client = None
    return _redis_client


def is_redis_alive() -> bool:
    """Retorna True se o Redis está respondendo."""
    if _redis_client is None:
        _connect_redis()
    return _redis_alive


def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Chave determinística para args/kwargs.

    Os kwargs são ordenados para a chave independer da ordem de chamada; o
    ``repr`` é reduzido a um sha1 de 24 hex para manter a chave do Redis curta.
    Formato final: ``{prefixo_do_app}{prefix}:{digest}``.
    """
    raw = repr((args, tuple(sorted(kwargs.items()))))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"{_CACHE_PREFIX}{prefix}:{digest}"


def cached(ttl: int | None = None, key_prefix: str | None = None) -> Callable:
    """Decorador. Use TTL em segundos (default 1800 = 30 min).

    Args:
        ttl: tempo de vida em segundos. Default: env CACHE_DEFAULT_TTL.
        key_prefix: prefixo customizado (default: nome da função).
    """
    ttl_val = ttl if ttl is not None else _DEFAULT_TTL

    def decorator(func: Callable) -> Callable:
        prefix = key_prefix or f"{func.__module__}.{func.__name__}"
        # Fallback in-memory: lru_cache armazena por (args, kwargs).
        _memory_cache: dict[str, Any] = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Ordem de resolução: Redis (se vivo) -> cache local -> executa func.
            cli = _connect_redis()
            key = _make_key(prefix, args, kwargs)

            # Redis path.
            if cli is not None and _redis_alive:
                try:
                    raw = cli.get(key)
                    if raw is not None:
                        return pickle.loads(raw)
                    result = func(*args, **kwargs)
                    try:
                        cli.setex(key, ttl_val, pickle.dumps(result))
                    except Exception as exc:
                        logger.warning(f"Cache: falha ao gravar {key}: {exc!r}")
                    return result
                except Exception as exc:
                    logger.warning(f"Cache: erro Redis em {key} ({exc!r}), caindo no memory")
                    # cai pro path local sem retornar — segue abaixo.

            # Fallback in-memory.
            if key in _memory_cache:
                return _memory_cache[key]
            result = func(*args, **kwargs)
            # Limita memory cache a 256 entradas (LRU rude — descarta arbitrário).
            if len(_memory_cache) >= 256:
                _memory_cache.pop(next(iter(_memory_cache)))
            _memory_cache[key] = result
            return result

        def cache_clear():
            """Limpa todas as chaves desta função (Redis + memória)."""
            _memory_cache.clear()
            cli = _connect_redis()
            if cli is not None and _redis_alive:
                pattern = f"{_CACHE_PREFIX}{prefix}:*"
                try:
                    keys = list(cli.scan_iter(pattern, count=500))
                    if keys:
                        cli.delete(*keys)
                except Exception as exc:
                    logger.warning(f"Cache: cache_clear falhou para {prefix}: {exc!r}")

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        wrapper._cache_prefix = prefix  # type: ignore[attr-defined]
        return wrapper

    return decorator


def cache_flush_all() -> int:
    """Apaga TODAS as chaves com o prefixo do app. Devolve quantas chaves apagou."""
    cli = _connect_redis()
    if cli is None or not _redis_alive:
        return 0
    try:
        keys = list(cli.scan_iter(f"{_CACHE_PREFIX}*", count=500))
        if keys:
            cli.delete(*keys)
        return len(keys)
    except Exception as exc:
        logger.warning(f"Cache: flush_all falhou: {exc!r}")
        return 0


def get_meta(key: str) -> str | None:
    """Lê um valor de metadados (string) do Redis. Sem pickle, sem TTL.

    Usado para guardar a assinatura dos cenários e detectar mudanças no banco.
    Chave real: ``{prefix}meta:{key}``.
    """
    cli = _connect_redis()
    if cli is None or not _redis_alive:
        return None
    try:
        raw = cli.get(f"{_CACHE_PREFIX}meta:{key}")
        return raw.decode("utf-8") if raw is not None else None
    except Exception as exc:
        logger.warning(f"Cache: get_meta falhou para {key}: {exc!r}")
        return None


def set_meta(key: str, value: str) -> None:
    """Grava um valor de metadados (string) no Redis, sem TTL."""
    cli = _connect_redis()
    if cli is None or not _redis_alive:
        return
    try:
        cli.set(f"{_CACHE_PREFIX}meta:{key}", value.encode("utf-8"))
    except Exception as exc:
        logger.warning(f"Cache: set_meta falhou para {key}: {exc!r}")


def cache_stats() -> dict:
    """Resumo do cache atual (debug)."""
    cli = _connect_redis()
    out = {"redis_alive": _redis_alive, "redis_url": _REDIS_URL, "prefix": _CACHE_PREFIX, "ttl_default": _DEFAULT_TTL}
    if cli is not None and _redis_alive:
        try:
            info = cli.info("memory")
            keys = sum(1 for _ in cli.scan_iter(f"{_CACHE_PREFIX}*", count=500))
            out["keys"] = keys
            out["used_memory_mb"] = round(int(info.get("used_memory", 0)) / 1024 / 1024, 2)
        except Exception:
            pass
    return out
