"""
Testes para o InfomanceClient.
"""

import logging
from datetime import datetime, timezone

import pytest
import respx
from httpx import Response

from infomance import (
    InfomanceClient,
    ClientConfig,
    RetryConfig,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError,
    logger,
)


class TestClientInitialization:
    """Testes de inicializacao do cliente."""

    def test_create_client_with_api_key(self, api_key: str):
        """Teste de criacao do cliente com API key."""
        client = InfomanceClient(api_key)
        assert client.api_key == api_key
        assert client.base_url == "https://api.infomance.com.br"

    def test_create_client_with_custom_config(self, api_key: str):
        """Teste de criacao do cliente com configuracao customizada."""
        client = InfomanceClient(
            api_key,
            base_url="https://custom.api.com",
            timeout=60.0,
        )
        assert client.base_url == "https://custom.api.com"
        assert client.timeout == 60.0

    def test_create_client_without_api_key_raises_error(self):
        """Teste de erro quando API key nao e fornecida."""
        with pytest.raises(ValueError, match="API Key"):
            InfomanceClient("")

    def test_client_context_manager(self, api_key: str):
        """Teste do cliente como context manager."""
        with InfomanceClient(api_key) as client:
            assert client.api_key == api_key

    def test_client_repr(self, api_key: str):
        """Teste da representacao em string do cliente."""
        client = InfomanceClient(api_key)
        assert "InfomanceClient" in repr(client)
        assert "api.infomance.com.br" in repr(client)

    def test_client_with_config(self, api_key: str):
        """Teste de criacao do cliente com ClientConfig."""
        retry = RetryConfig(max_retries=5, backoff_factor=2.0)
        config = ClientConfig(
            base_url="https://custom.api.com",
            timeout=60.0,
            retry=retry,
        )
        client = InfomanceClient(api_key, config=config)

        assert client.base_url == "https://custom.api.com"
        assert client.timeout == 60.0
        assert client.retry_config.max_retries == 5

    def test_client_with_retry_config(self, api_key: str):
        """Teste de criacao do cliente com RetryConfig direto."""
        retry = RetryConfig(max_retries=10)
        client = InfomanceClient(api_key, retry_config=retry)

        assert client.retry_config.max_retries == 10

    def test_client_user_agent_header(self, api_key: str):
        """Teste de User-Agent header."""
        client = InfomanceClient(api_key)
        headers = client._get_headers()

        assert "User-Agent" in headers
        assert headers["User-Agent"].startswith("infomance-python/")
        assert headers["X-API-Key"] == api_key


class TestIndicatorsAPI:
    """Testes da API de Indicadores."""

    @respx.mock
    def test_list_municipalities_success(
        self, client: InfomanceClient, base_url: str, sample_list_response: dict
    ):
        """Teste de listagem de municipios com sucesso."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(
                200,
                json=sample_list_response,
                headers={
                    "X-RateLimit-Limit": "1000",
                    "X-RateLimit-Remaining": "999",
                    "X-RateLimit-Reset": "1704067200",
                    "X-Request-ID": "req_123abc",
                },
            )
        )

        result = client.list_municipalities()

        assert len(result["items"]) == 2
        assert result["total"] == 5570
        assert client.rate_limit is not None
        assert client.rate_limit["limit"] == 1000
        assert client.last_request_id == "req_123abc"

    @respx.mock
    def test_list_municipalities_with_params(
        self, client: InfomanceClient, base_url: str, sample_list_response: dict
    ):
        """Teste de listagem de municipios com parametros."""
        route = respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, json=sample_list_response)
        )

        result = client.list_municipalities(limit=10, offset=20, state="SP")

        assert route.called
        assert route.calls[0].request.url.params["limit"] == "10"
        assert route.calls[0].request.url.params["offset"] == "20"
        assert route.calls[0].request.url.params["state"] == "SP"

    @respx.mock
    def test_get_municipality_success(
        self, client: InfomanceClient, base_url: str, sample_municipality_response: dict
    ):
        """Teste de busca de municipio com sucesso."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities/3550308").mock(
            return_value=Response(200, json=sample_municipality_response)
        )

        result = client.get_municipality("3550308")

        assert result["ibge_code"] == "3550308"
        assert result["name"] == "Sao Paulo"
        assert result["economic"]["pib"] == 699288090000.0

    @respx.mock
    def test_get_municipality_not_found(self, client: InfomanceClient, base_url: str):
        """Teste de erro 404 para municipio nao encontrado."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities/0000000").mock(
            return_value=Response(404, json={"detail": "Municipio nao encontrado"})
        )

        with pytest.raises(NotFoundError) as exc_info:
            client.get_municipality("0000000")

        assert exc_info.value.status_code == 404

    @respx.mock
    def test_get_indicators_ranking(
        self, client: InfomanceClient, base_url: str, sample_ranking_response: list
    ):
        """Teste de busca de ranking."""
        respx.get(f"{base_url}/api/v1/indicators/ranking/pib").mock(
            return_value=Response(200, json=sample_ranking_response)
        )

        result = client.get_indicators_ranking("pib", limit=10, order="desc")

        assert len(result) == 2
        assert result[0]["position"] == 1
        assert result[0]["name"] == "Sao Paulo"


class TestHealthAPI:
    """Testes da API de Saude."""

    @respx.mock
    def test_get_municipality_health_stats(
        self, client: InfomanceClient, base_url: str, sample_health_stats: dict
    ):
        """Teste de estatisticas de saude de um municipio."""
        respx.get(f"{base_url}/api/v1/health/municipalities/3550308").mock(
            return_value=Response(200, json=sample_health_stats)
        )

        result = client.get_municipality_health_stats("3550308")

        assert result["total_establishments"] == 15234
        assert result["total_beds"] == 45678


class TestErrorHandling:
    """Testes de tratamento de erros."""

    @respx.mock
    def test_authentication_error(self, client: InfomanceClient, base_url: str):
        """Teste de erro 401."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(401, json={"detail": "API Key invalida"})
        )

        with pytest.raises(AuthenticationError) as exc_info:
            client.list_municipalities()

        assert exc_info.value.status_code == 401
        assert exc_info.value.is_retryable is False

    @respx.mock
    def test_forbidden_error(self, client: InfomanceClient, base_url: str):
        """Teste de erro 403."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(403, json={"detail": "Acesso negado"})
        )

        with pytest.raises(ForbiddenError) as exc_info:
            client.list_municipalities()

        assert exc_info.value.status_code == 403

    @respx.mock
    def test_validation_error(self, client: InfomanceClient, base_url: str):
        """Teste de erro 400."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(
                400,
                json={
                    "detail": "Parametros invalidos",
                    "errors": [{"field": "state", "message": "UF invalida"}],
                },
            )
        )

        with pytest.raises(ValidationError) as exc_info:
            client.list_municipalities(state="XX")

        assert exc_info.value.status_code == 400
        assert len(exc_info.value.errors) == 1

    @respx.mock
    def test_rate_limit_error(self, client: InfomanceClient, base_url: str):
        """Teste de erro 429 com retry_after."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(
                429,
                json={"detail": "Rate limit excedido"},
                headers={"Retry-After": "60"},
            )
        )

        with pytest.raises(RateLimitError) as exc_info:
            client.list_municipalities()

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 60
        assert exc_info.value.is_retryable is True

    @respx.mock
    def test_server_error(self, client: InfomanceClient, base_url: str):
        """Teste de erro 500."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(500, json={"detail": "Erro interno"})
        )

        with pytest.raises(ServerError) as exc_info:
            client.list_municipalities()

        assert exc_info.value.status_code == 500
        assert exc_info.value.is_retryable is True


class TestRateLimitTracking:
    """Testes de rastreamento de rate limit."""

    @respx.mock
    def test_rate_limit_extracted_from_headers(
        self, client: InfomanceClient, base_url: str, sample_list_response: dict
    ):
        """Teste de extracao de rate limit dos headers."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(
                200,
                json=sample_list_response,
                headers={
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Remaining": "4999",
                    "X-RateLimit-Reset": "1704067200",
                },
            )
        )

        assert client.rate_limit is None

        client.list_municipalities()

        assert client.rate_limit is not None
        assert client.rate_limit["limit"] == 5000
        assert client.rate_limit["remaining"] == 4999
        assert client.rate_limit["reset"] == 1704067200

    @respx.mock
    def test_rate_limit_includes_reset_at_datetime(
        self, client: InfomanceClient, base_url: str, sample_list_response: dict
    ):
        """Teste de reset_at como datetime."""
        reset_timestamp = 1704067200
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(
                200,
                json=sample_list_response,
                headers={
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Remaining": "4999",
                    "X-RateLimit-Reset": str(reset_timestamp),
                },
            )
        )

        client.list_municipalities()

        assert client.rate_limit is not None
        assert "reset_at" in client.rate_limit
        reset_at = client.rate_limit["reset_at"]
        assert isinstance(reset_at, datetime)
        assert reset_at.tzinfo == timezone.utc
        assert reset_at.timestamp() == reset_timestamp

    @respx.mock
    def test_rate_limit_none_when_headers_missing(
        self, client: InfomanceClient, base_url: str, sample_list_response: dict
    ):
        """Teste de rate limit None quando headers estao ausentes."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, json=sample_list_response)
        )

        client.list_municipalities()

        assert client.rate_limit is None


class TestRetryBehavior:
    """Testes de comportamento de retry."""

    @respx.mock
    def test_retry_on_server_error(self, api_key: str, base_url: str, sample_list_response: dict):
        """Teste de retry em erro 500."""
        retry = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        client = InfomanceClient(api_key, base_url=base_url, retry_config=retry)

        # Mock: 2 erros 500, depois sucesso
        route = respx.get(f"{base_url}/api/v1/indicators/municipalities")
        route.side_effect = [
            Response(500, json={"detail": "Internal Server Error"}),
            Response(500, json={"detail": "Internal Server Error"}),
            Response(200, json=sample_list_response),
        ]

        result = client.list_municipalities()

        assert len(result["items"]) == 2
        assert route.call_count == 3

    @respx.mock
    def test_retry_on_rate_limit(self, api_key: str, base_url: str, sample_list_response: dict):
        """Teste de retry em erro 429."""
        retry = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        client = InfomanceClient(api_key, base_url=base_url, retry_config=retry)

        route = respx.get(f"{base_url}/api/v1/indicators/municipalities")
        route.side_effect = [
            Response(429, json={"detail": "Rate limit"}, headers={"Retry-After": "1"}),
            Response(200, json=sample_list_response),
        ]

        result = client.list_municipalities()

        assert len(result["items"]) == 2
        assert route.call_count == 2

    @respx.mock
    def test_no_retry_on_client_error(self, api_key: str, base_url: str):
        """Teste de nao retry em erro 400."""
        retry = RetryConfig(max_retries=3)
        client = InfomanceClient(api_key, base_url=base_url, retry_config=retry)

        route = respx.get(f"{base_url}/api/v1/indicators/municipalities")
        route.mock(return_value=Response(400, json={"detail": "Bad Request"}))

        with pytest.raises(Exception):  # ValidationError
            client.list_municipalities()

        # Apenas 1 tentativa (sem retry)
        assert route.call_count == 1

    @respx.mock
    def test_max_retries_exceeded(self, api_key: str, base_url: str):
        """Teste de max retries excedido."""
        retry = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)
        client = InfomanceClient(api_key, base_url=base_url, retry_config=retry)

        route = respx.get(f"{base_url}/api/v1/indicators/municipalities")
        route.mock(return_value=Response(503, json={"detail": "Service Unavailable"}))

        with pytest.raises(ServerError):
            client.list_municipalities()

        # 1 tentativa inicial + 2 retries = 3
        assert route.call_count == 3


class TestExportMethods:
    """Testes dos metodos de exportacao."""

    @respx.mock
    def test_export_to_csv(self, client: InfomanceClient, base_url: str):
        """Teste de exportacao para CSV."""
        csv_content = "ibge_code,name,state\n3550308,Sao Paulo,SP"
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, text=csv_content)
        )

        result = client.export_to_csv("/api/v1/indicators/municipalities", state="SP")

        assert result == csv_content
        assert "ibge_code,name,state" in result

    @respx.mock
    def test_export_to_excel(self, client: InfomanceClient, base_url: str):
        """Teste de exportacao para Excel."""
        excel_content = b"PK\x03\x04..."  # Excel file magic bytes
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, content=excel_content)
        )

        result = client.export_to_excel("/api/v1/indicators/municipalities", state="SP")

        assert isinstance(result, bytes)
        assert result == excel_content


@pytest.mark.asyncio
class TestAsyncClient:
    """Testes do cliente assincrono."""

    @respx.mock
    async def test_list_municipalities_async(
        self, api_key: str, base_url: str, sample_list_response: dict
    ):
        """Teste de listagem assincrona de municipios."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, json=sample_list_response)
        )

        async with InfomanceClient(api_key, base_url=base_url) as client:
            result = await client.list_municipalities_async()

        assert len(result["items"]) == 2

    @respx.mock
    async def test_get_municipality_async(
        self, api_key: str, base_url: str, sample_municipality_response: dict
    ):
        """Teste de busca assincrona de municipio."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities/3550308").mock(
            return_value=Response(200, json=sample_municipality_response)
        )

        async with InfomanceClient(api_key, base_url=base_url) as client:
            result = await client.get_municipality_async("3550308")

        assert result["name"] == "Sao Paulo"

    @respx.mock
    async def test_error_handling_async(self, api_key: str, base_url: str):
        """Teste de tratamento de erros assincrono."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities/0000000").mock(
            return_value=Response(404, json={"detail": "Nao encontrado"})
        )

        async with InfomanceClient(api_key, base_url=base_url) as client:
            with pytest.raises(NotFoundError):
                await client.get_municipality_async("0000000")


class TestLogging:
    """Testes de logging do SDK."""

    def test_logger_is_exported(self):
        """Teste de exportacao do logger."""
        assert logger is not None
        assert logger.name == "infomance"

    def test_debug_mode_sets_log_level(self, api_key: str):
        """Teste de que debug=True configura o nivel de log."""
        # Resetar handlers para evitar interferencia entre testes
        logger.handlers = []
        logger.setLevel(logging.WARNING)

        client = InfomanceClient(api_key, debug=True)

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) > 0

        client.close()

    def test_debug_mode_via_config(self, api_key: str):
        """Teste de que debug=True via ClientConfig funciona."""
        # Resetar handlers
        logger.handlers = []
        logger.setLevel(logging.WARNING)

        config = ClientConfig(debug=True)
        client = InfomanceClient(api_key, config=config)

        assert logger.level == logging.DEBUG

        client.close()

    @respx.mock
    def test_logging_request_started(
        self, api_key: str, base_url: str, sample_list_response: dict, caplog
    ):
        """Teste de log de request iniciado."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, json=sample_list_response)
        )

        with caplog.at_level(logging.DEBUG, logger="infomance"):
            client = InfomanceClient(api_key, base_url=base_url, debug=True)
            client.list_municipalities()
            client.close()

        assert any("Request started" in record.message for record in caplog.records)
        assert any("GET" in record.message for record in caplog.records)

    @respx.mock
    def test_logging_request_completed(
        self, api_key: str, base_url: str, sample_list_response: dict, caplog
    ):
        """Teste de log de request completado."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(200, json=sample_list_response)
        )

        with caplog.at_level(logging.DEBUG, logger="infomance"):
            client = InfomanceClient(api_key, base_url=base_url, debug=True)
            client.list_municipalities()
            client.close()

        assert any("Request completed" in record.message for record in caplog.records)
        assert any("status=200" in record.message for record in caplog.records)
        assert any("elapsed=" in record.message for record in caplog.records)

    @respx.mock
    def test_logging_request_error(self, api_key: str, base_url: str, caplog):
        """Teste de log de erro HTTP."""
        respx.get(f"{base_url}/api/v1/indicators/municipalities").mock(
            return_value=Response(404, json={"detail": "Nao encontrado"})
        )

        with caplog.at_level(logging.ERROR, logger="infomance"):
            client = InfomanceClient(api_key, base_url=base_url, debug=True)
            with pytest.raises(NotFoundError):
                client.list_municipalities()
            client.close()

        assert any("Request error" in record.message for record in caplog.records)
        assert any("status=404" in record.message for record in caplog.records)

    @respx.mock
    def test_logging_retry(self, api_key: str, base_url: str, sample_list_response: dict, caplog):
        """Teste de log de retry."""
        retry = RetryConfig(max_retries=2, backoff_factor=0.01, jitter=False)

        route = respx.get(f"{base_url}/api/v1/indicators/municipalities")
        route.side_effect = [
            Response(503, json={"detail": "Service Unavailable"}),
            Response(200, json=sample_list_response),
        ]

        with caplog.at_level(logging.WARNING, logger="infomance"):
            client = InfomanceClient(api_key, base_url=base_url, retry_config=retry, debug=True)
            result = client.list_municipalities()
            client.close()

        assert len(result["items"]) == 2
        assert any("Retry attempt" in record.message for record in caplog.records)
        assert any("waiting" in record.message for record in caplog.records)


class TestAdditionalAPIs:
    """Testes adicionais para outras APIs do SDK."""

    @respx.mock
    def test_get_municipality_economic(
        self, client: InfomanceClient, base_url: str
    ):
        """Teste de busca de dados economicos."""
        economic_data = {
            "pib": 699288090000.0,
            "pib_per_capita": 56700.0,
            "agriculture": 0.01,
            "industry": 11.3,
            "services": 73.8,
            "taxes": 14.9,
            "year": 2021,
        }
        respx.get(f"{base_url}/api/v1/indicators/municipalities/3550308/economic").mock(
            return_value=Response(200, json=economic_data)
        )

        result = client.get_municipality_economic("3550308")
        assert result["pib"] == 699288090000.0
        assert result["services"] == 73.8

    @respx.mock
    def test_get_municipality_infrastructure(
        self, client: InfomanceClient, base_url: str
    ):
        """Teste de busca de dados de infraestrutura."""
        infra_data = {
            "water_coverage": 99.1,
            "sewage_collection": 92.3,
            "year": 2022,
        }
        respx.get(f"{base_url}/api/v1/indicators/municipalities/3550308/infrastructure").mock(
            return_value=Response(200, json=infra_data)
        )

        result = client.get_municipality_infrastructure("3550308")
        assert result["water_coverage"] == 99.1

    @respx.mock
    def test_get_comex_overview(self, client: InfomanceClient, base_url: str):
        """Teste de visao geral do COMEX."""
        overview = {
            "total_value_usd": 1000000000.0,
            "total_products": 500,
            "years": [2022, 2023],
        }
        respx.get(f"{base_url}/api/v1/comex/overview").mock(
            return_value=Response(200, json=overview)
        )

        result = client.get_comex_overview()
        assert result["total_value_usd"] == 1000000000.0

    @respx.mock
    def test_get_comex_municipality(self, client: InfomanceClient, base_url: str):
        """Teste de COMEX por municipio."""
        comex_data = {
            "ibge_code": "3550308",
            "name": "Sao Paulo",
            "total_value_usd": 500000000.0,
        }
        respx.get(f"{base_url}/api/v1/comex/municipalities/3550308").mock(
            return_value=Response(200, json=comex_data)
        )

        result = client.get_comex_municipality("3550308")
        assert result["name"] == "Sao Paulo"

    @respx.mock
    def test_search_pois(self, client: InfomanceClient, base_url: str):
        """Teste de busca de POIs."""
        pois_response = {
            "items": [{"name": "Farmacia Teste", "category": "farmacia"}],
            "total": 1,
        }
        respx.get(f"{base_url}/api/v1/pois").mock(
            return_value=Response(200, json=pois_response)
        )

        result = client.search_pois(city="Sao Paulo", category="farmacia")
        assert result["total"] == 1
        assert result["items"][0]["category"] == "farmacia"

    @respx.mock
    def test_get_consolidated_city(self, client: InfomanceClient, base_url: str):
        """Teste de dados consolidados."""
        consolidated = {
            "municipality": {"ibge_code": "3550308", "name": "Sao Paulo"},
            "indicators": {"pib": 699288090000.0},
        }
        respx.get(f"{base_url}/api/v1/consolidated/cities/3550308").mock(
            return_value=Response(200, json=consolidated)
        )

        result = client.get_consolidated_city("3550308")
        assert result["municipality"]["name"] == "Sao Paulo"

    @respx.mock
    def test_get_sicor_overview(self, client: InfomanceClient, base_url: str):
        """Teste de visao geral do SICOR."""
        overview = {"total_contracts": 1000, "total_value_brl": 5000000.0}
        respx.get(f"{base_url}/api/v1/sicor/overview").mock(
            return_value=Response(200, json=overview)
        )

        result = client.get_sicor_overview()
        assert result["total_contracts"] == 1000

    @respx.mock
    def test_get_education_overview(self, client: InfomanceClient, base_url: str):
        """Teste de visao geral de educacao."""
        overview = {"total_schools": 50000, "by_network": []}
        respx.get(f"{base_url}/api/v1/education/overview").mock(
            return_value=Response(200, json=overview)
        )

        result = client.get_education_overview()
        assert result["total_schools"] == 50000

    @respx.mock
    def test_get_security_overview(self, client: InfomanceClient, base_url: str):
        """Teste de visao geral de seguranca."""
        overview = {"total_crimes": 100000, "by_type": []}
        respx.get(f"{base_url}/api/v1/security/overview").mock(
            return_value=Response(200, json=overview)
        )

        result = client.get_security_overview()
        assert result["total_crimes"] == 100000

    @respx.mock
    def test_get_employment_overview(self, client: InfomanceClient, base_url: str):
        """Teste de visao geral de emprego."""
        overview = {"total_jobs": 20000000, "total_admissions": 500000}
        respx.get(f"{base_url}/api/v1/employment/overview").mock(
            return_value=Response(200, json=overview)
        )

        result = client.get_employment_overview()
        assert result["total_jobs"] == 20000000

    @respx.mock
    def test_get_agro_stats(self, client: InfomanceClient, base_url: str):
        """Teste de estatisticas agro."""
        stats = {"total_municipalities": 5000, "total_area_ha": 350000000.0}
        respx.get(f"{base_url}/api/v1/agro/stats").mock(
            return_value=Response(200, json=stats)
        )

        result = client.get_agro_stats()
        assert result["total_municipalities"] == 5000


@pytest.mark.asyncio
class TestAsyncAdditionalAPIs:
    """Testes assincronos adicionais."""

    @respx.mock
    async def test_get_municipality_economic_async(
        self, api_key: str, base_url: str
    ):
        """Teste assincrono de dados economicos."""
        economic_data = {"pib": 699288090000.0, "services": 73.8}
        respx.get(f"{base_url}/api/v1/indicators/municipalities/3550308/economic").mock(
            return_value=Response(200, json=economic_data)
        )

        async with InfomanceClient(api_key, base_url=base_url) as client:
            result = await client.get_municipality_economic_async("3550308")

        assert result["pib"] == 699288090000.0

    @respx.mock
    async def test_get_consolidated_city_async(
        self, api_key: str, base_url: str
    ):
        """Teste assincrono de dados consolidados."""
        consolidated = {"municipality": {"name": "Sao Paulo"}}
        respx.get(f"{base_url}/api/v1/consolidated/cities/3550308").mock(
            return_value=Response(200, json=consolidated)
        )

        async with InfomanceClient(api_key, base_url=base_url) as client:
            result = await client.get_consolidated_city_async("3550308")

        assert result["municipality"]["name"] == "Sao Paulo"


class TestExceptionDetails:
    """Testes de detalhes de excecoes."""

    def test_infomance_error_str_representation(self):
        """Teste da representacao em string do erro."""
        from infomance.exceptions import InfomanceError

        error = InfomanceError(
            message="Test error",
            status_code=500,
            request_id="req_123"
        )
        error_str = str(error)
        assert "Test error" in error_str
        assert "HTTP 500" in error_str
        assert "req_123" in error_str

    def test_infomance_error_repr(self):
        """Teste da representacao repr do erro."""
        from infomance.exceptions import InfomanceError

        error = InfomanceError(message="Test", status_code=500, request_id="req_1")
        error_repr = repr(error)
        assert "InfomanceError" in error_repr
        assert "Test" in error_repr

    def test_forbidden_error_with_required_plan(self):
        """Teste de ForbiddenError com plano requerido."""
        error = ForbiddenError(required_plan="Pro")
        assert "Pro" in error.message
        assert error.required_plan == "Pro"

    def test_validation_error_with_errors_list(self):
        """Teste de ValidationError com lista de erros."""
        errors = [{"field": "state", "message": "UF invalida"}]
        error = ValidationError(errors=errors)
        assert "state" in error.message
        assert "UF invalida" in error.message
        assert len(error.errors) == 1
