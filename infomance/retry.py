"""
Retry logic com backoff exponencial para o SDK Infomance.

Suporta retry automatico em erros retryaveis (429, 5xx, timeout, conexao).
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class RetryConfig:
    """
    Configuracao de retry com backoff exponencial.

    Attributes:
        max_retries: Numero maximo de tentativas (default: 3)
        backoff_factor: Fator multiplicador do delay (default: 1.0)
        retry_statuses: Codigos HTTP que ativam retry (default: 429, 5xx)
        retry_on_timeout: Fazer retry em timeouts (default: True)
        retry_on_connection_error: Fazer retry em erros de conexao (default: True)
        max_delay: Delay maximo em segundos (default: 30.0)
        jitter: Adicionar variacao aleatoria ao delay (default: True)

    Exemplo:
        >>> config = RetryConfig(max_retries=5, backoff_factor=2.0)
        >>> # Delays: 2s, 4s, 8s, 16s, 30s (capped)
    """

    max_retries: int = 3
    backoff_factor: float = 1.0
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True
    max_delay: float = 30.0
    jitter: bool = True

    def calculate_delay(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """
        Calcula o delay para a proxima tentativa.

        Args:
            attempt: Numero da tentativa (0-indexed)
            retry_after: Valor do header Retry-After (se presente)

        Returns:
            Delay em segundos
        """
        # Respeitar Retry-After se presente
        if retry_after is not None and retry_after > 0:
            return min(float(retry_after), self.max_delay)

        # Backoff exponencial: factor * 2^attempt
        delay = self.backoff_factor * (2**attempt)

        # Adicionar jitter (0-25% do delay)
        if self.jitter:
            jitter_amount = delay * 0.25 * random.random()
            delay += jitter_amount

        return min(delay, self.max_delay)

    def should_retry(
        self,
        status_code: Optional[int] = None,
        is_timeout: bool = False,
        is_connection_error: bool = False,
    ) -> bool:
        """
        Verifica se deve fazer retry baseado no erro.

        Args:
            status_code: Codigo HTTP da resposta
            is_timeout: Se foi um timeout
            is_connection_error: Se foi um erro de conexao

        Returns:
            True se deve fazer retry
        """
        if is_timeout and self.retry_on_timeout:
            return True
        if is_connection_error and self.retry_on_connection_error:
            return True
        if status_code is not None and status_code in self.retry_statuses:
            return True
        return False


class RetryHandler:
    """
    Handler para executar funcoes com retry.

    Uso:
        >>> handler = RetryHandler(RetryConfig(max_retries=3))
        >>> result = handler.execute(my_function, arg1, arg2)
    """

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self.config = config or RetryConfig()

    def execute(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        **kwargs,
    ) -> T:
        """
        Executa funcao com retry sincrono.

        Args:
            func: Funcao a executar
            *args: Argumentos posicionais
            on_retry: Callback chamado antes de cada retry (attempt, error, delay)
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da funcao

        Raises:
            A ultima excecao se max_retries for excedido
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e

                # Verificar se deve fazer retry
                should_retry = self._should_retry_exception(e)
                if not should_retry or attempt >= self.config.max_retries:
                    raise

                # Calcular delay
                retry_after = self._get_retry_after(e)
                delay = self.config.calculate_delay(attempt, retry_after)

                # Callback opcional
                if on_retry:
                    on_retry(attempt, e, delay)

                time.sleep(delay)

        # Nunca deveria chegar aqui, mas por seguranca
        if last_error:
            raise last_error
        raise RuntimeError("Retry loop exited unexpectedly")

    async def execute_async(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        **kwargs,
    ) -> T:
        """
        Executa funcao com retry assincrono.

        Args:
            func: Funcao async a executar
            *args: Argumentos posicionais
            on_retry: Callback chamado antes de cada retry
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da funcao

        Raises:
            A ultima excecao se max_retries for excedido
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                # Verificar se deve fazer retry
                should_retry = self._should_retry_exception(e)
                if not should_retry or attempt >= self.config.max_retries:
                    raise

                # Calcular delay
                retry_after = self._get_retry_after(e)
                delay = self.config.calculate_delay(attempt, retry_after)

                # Callback opcional
                if on_retry:
                    on_retry(attempt, e, delay)

                await asyncio.sleep(delay)

        # Nunca deveria chegar aqui, mas por seguranca
        if last_error:
            raise last_error
        raise RuntimeError("Retry loop exited unexpectedly")

    def _should_retry_exception(self, error: Exception) -> bool:
        """Verifica se a excecao e retryavel."""
        # Import local para evitar circular import
        from .exceptions import InfomanceError, NetworkError, TimeoutError

        if isinstance(error, TimeoutError):
            return self.config.retry_on_timeout
        if isinstance(error, NetworkError):
            return self.config.retry_on_connection_error
        if isinstance(error, InfomanceError):
            if error.status_code and error.status_code in self.config.retry_statuses:
                return True
            return getattr(error, "is_retryable", False)

        return False

    def _get_retry_after(self, error: Exception) -> Optional[int]:
        """Extrai retry_after da excecao se disponivel."""
        from .exceptions import InfomanceError

        if isinstance(error, InfomanceError):
            return error.retry_after
        return None


# Default config para uso direto
DEFAULT_RETRY_CONFIG = RetryConfig()
