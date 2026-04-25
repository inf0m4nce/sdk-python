"""
Testes para o modulo de retry.
"""

import pytest
import time
from unittest.mock import Mock, patch

from infomance import RetryConfig, RetryHandler
from infomance.exceptions import (
    InfomanceError,
    NetworkError,
    RateLimitError,
    ServerError,
    TimeoutError,
)


class TestRetryConfig:
    """Testes para RetryConfig."""

    def test_default_config(self):
        """Teste de configuracao padrao."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.backoff_factor == 1.0
        assert config.retry_statuses == (429, 500, 502, 503, 504)
        assert config.retry_on_timeout is True
        assert config.retry_on_connection_error is True
        assert config.max_delay == 30.0
        assert config.jitter is True

    def test_custom_config(self):
        """Teste de configuracao customizada."""
        config = RetryConfig(
            max_retries=5,
            backoff_factor=2.0,
            retry_statuses=(429, 503),
            retry_on_timeout=False,
            max_delay=60.0,
        )
        assert config.max_retries == 5
        assert config.backoff_factor == 2.0
        assert config.retry_statuses == (429, 503)
        assert config.retry_on_timeout is False
        assert config.max_delay == 60.0

    def test_calculate_delay_exponential_backoff(self):
        """Teste de calculo de delay com backoff exponencial."""
        config = RetryConfig(backoff_factor=1.0, jitter=False)

        # Sem jitter, delays sao: 1s, 2s, 4s, 8s...
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_calculate_delay_respects_max_delay(self):
        """Teste de delay maximo."""
        config = RetryConfig(backoff_factor=10.0, max_delay=15.0, jitter=False)

        # 10 * 2^2 = 40, mas max_delay = 15
        assert config.calculate_delay(2) == 15.0

    def test_calculate_delay_respects_retry_after(self):
        """Teste de Retry-After header."""
        config = RetryConfig(jitter=False)

        # Retry-After tem prioridade sobre backoff
        assert config.calculate_delay(0, retry_after=10) == 10.0
        assert config.calculate_delay(0, retry_after=60) == 30.0  # capped

    def test_calculate_delay_with_jitter(self):
        """Teste de jitter no delay."""
        config = RetryConfig(backoff_factor=1.0, jitter=True)

        # Com jitter, delay varia ate 25% a mais
        delays = [config.calculate_delay(0) for _ in range(100)]

        # Todos devem estar entre 1.0 e 1.25
        assert all(1.0 <= d <= 1.25 for d in delays)
        # Deve haver variacao (nao todos iguais)
        assert len(set(delays)) > 1

    def test_should_retry_on_timeout(self):
        """Teste de retry em timeout."""
        config = RetryConfig(retry_on_timeout=True)
        assert config.should_retry(is_timeout=True) is True

        config = RetryConfig(retry_on_timeout=False)
        assert config.should_retry(is_timeout=True) is False

    def test_should_retry_on_connection_error(self):
        """Teste de retry em erro de conexao."""
        config = RetryConfig(retry_on_connection_error=True)
        assert config.should_retry(is_connection_error=True) is True

        config = RetryConfig(retry_on_connection_error=False)
        assert config.should_retry(is_connection_error=True) is False

    def test_should_retry_on_status_code(self):
        """Teste de retry em status codes especificos."""
        config = RetryConfig(retry_statuses=(429, 503))

        assert config.should_retry(status_code=429) is True
        assert config.should_retry(status_code=503) is True
        assert config.should_retry(status_code=500) is False
        assert config.should_retry(status_code=400) is False


class TestRetryHandler:
    """Testes para RetryHandler."""

    def test_successful_first_attempt(self):
        """Teste de sucesso na primeira tentativa."""
        handler = RetryHandler(RetryConfig(max_retries=3))
        mock_func = Mock(return_value="success")

        result = handler.execute(mock_func, "arg1", kwarg1="value")

        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_with("arg1", kwarg1="value")

    def test_retry_on_retryable_error(self):
        """Teste de retry em erro retryavel."""
        config = RetryConfig(max_retries=3, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        # Falha 2x, sucesso na 3a
        mock_func = Mock(side_effect=[
            ServerError("Erro 500", status_code=500),
            ServerError("Erro 500", status_code=500),
            "success",
        ])

        result = handler.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_retries_exceeded(self):
        """Teste de max retries excedido."""
        config = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        mock_func = Mock(side_effect=ServerError("Erro 500", status_code=500))

        with pytest.raises(ServerError):
            handler.execute(mock_func)

        # 1 tentativa inicial + 2 retries = 3
        assert mock_func.call_count == 3

    def test_no_retry_on_non_retryable_error(self):
        """Teste de nao retry em erro nao retryavel."""
        handler = RetryHandler(RetryConfig(max_retries=3))

        # 400 nao e retryavel por padrao
        mock_func = Mock(side_effect=InfomanceError("Bad Request", status_code=400))

        with pytest.raises(InfomanceError):
            handler.execute(mock_func)

        assert mock_func.call_count == 1

    def test_retry_on_timeout(self):
        """Teste de retry em timeout."""
        config = RetryConfig(max_retries=2, retry_on_timeout=True, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        mock_func = Mock(side_effect=[
            TimeoutError("Timeout", timeout_seconds=30),
            "success",
        ])

        result = handler.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_on_network_error(self):
        """Teste de retry em erro de rede."""
        config = RetryConfig(max_retries=2, retry_on_connection_error=True, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        mock_func = Mock(side_effect=[
            NetworkError("Connection refused"),
            "success",
        ])

        result = handler.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_with_rate_limit_error(self):
        """Teste de retry com RateLimitError."""
        config = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        # RateLimitError com retry_after deve ser respeitado
        mock_func = Mock(side_effect=[
            RateLimitError("Rate limit", retry_after=1),
            "success",
        ])

        result = handler.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_on_retry_callback(self):
        """Teste de callback on_retry."""
        config = RetryConfig(max_retries=3, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        callback = Mock()
        mock_func = Mock(side_effect=[
            ServerError("Erro 500", status_code=500),
            ServerError("Erro 500", status_code=500),
            "success",
        ])

        result = handler.execute(mock_func, on_retry=callback)

        assert result == "success"
        assert callback.call_count == 2
        # Verificar argumentos do callback
        call_args = callback.call_args_list
        assert call_args[0][0][0] == 0  # attempt 0
        assert isinstance(call_args[0][0][1], ServerError)
        assert call_args[1][0][0] == 1  # attempt 1


@pytest.mark.asyncio
class TestRetryHandlerAsync:
    """Testes assincronos para RetryHandler."""

    async def test_async_successful_first_attempt(self):
        """Teste async de sucesso na primeira tentativa."""
        handler = RetryHandler(RetryConfig(max_retries=3))

        async def mock_func():
            return "success"

        result = await handler.execute_async(mock_func)
        assert result == "success"

    async def test_async_retry_on_error(self):
        """Teste async de retry em erro."""
        config = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ServerError("Erro 500", status_code=500)
            return "success"

        result = await handler.execute_async(mock_func)

        assert result == "success"
        assert call_count == 2

    async def test_async_max_retries_exceeded(self):
        """Teste async de max retries excedido."""
        config = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        handler = RetryHandler(config)

        async def mock_func():
            raise ServerError("Erro 500", status_code=500)

        with pytest.raises(ServerError):
            await handler.execute_async(mock_func)
