"""
Cliente principal do SDK Infomance.

Suporta operacoes sincronas e assincronas com retry automatico.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

# Logger do SDK
logger = logging.getLogger("infomance")

from .exceptions import (
    NetworkError,
    TimeoutError,
    raise_for_status,
)
from .retry import RetryConfig, RetryHandler
from .types import (
    AgroMunicipality,
    AgroStats,
    AgroTimeseries,
    CityPOIStats,
    ComexCountriesResponse,
    ComexMunicipality,
    ComexOverview,
    ComexProduct,
    ComexProductsResponse,
    ConsolidatedCity,
    CrimeOverview,
    CrimeStats,
    CrimeTypesResponse,
    EconomicData,
    EducationOverview,
    EmissionsData,
    EmploymentData,
    EmploymentOverview,
    ExportFormat,
    HealthEstablishment,
    HealthStats,
    IDEBScore,
    IndicatorsMunicipality,
    InfrastructureData,
    LandUseData,
    ListResponse,
    MunicipalityEducation,
    POICategoriesResponse,
    RankingEntry,
    RateLimitInfo,
    SicorByCategory,
    SicorOverview,
    SicorState,
)

DEFAULT_BASE_URL = "https://api.infomance.com.br"
DEFAULT_TIMEOUT = 30.0
VERSION = "1.0.0"


@dataclass
class ClientConfig:
    """
    Client configuration. / Configuração do cliente.

    Attributes:
        base_url: Base API URL / URL base da API
        timeout: Timeout in seconds / Timeout em segundos
        retry: Retry configuration / Configuração de retry
        verify_ssl: Verify SSL certificates. **NEVER disable in production.**
            Disabling exposes your application to man-in-the-middle attacks.
            Use False only in development environments with self-signed certificates.
            ---
            Verificar certificados SSL. **NUNCA desabilite em produção.**
            Desabilitar expõe sua aplicação a ataques man-in-the-middle.
            Use False apenas em ambientes de desenvolvimento com certificados
            auto-assinados.
        debug: Enable DEBUG level logging / Ativa logging em nível DEBUG

    Warning:
        Setting verify_ssl=False disables SSL certificate verification.
        This is a security risk and should ONLY be used in development.
        ---
        Definir verify_ssl=False desabilita a verificação de certificados SSL.
        Isso é um risco de segurança e deve ser usado APENAS em desenvolvimento.
    """

    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    retry: RetryConfig = field(default_factory=RetryConfig)
    verify_ssl: bool = True
    debug: bool = False


class InfomanceClient:
    """
    Cliente para a Infomance API.

    Suporta operacoes sincronas e assincronas com retry automatico.

    Args:
        api_key: Sua chave de API (obrigatoria)
        config: Configuracoes do cliente (opcional)
        base_url: URL base da API (shortcut para config.base_url)
        timeout: Timeout em segundos (shortcut para config.timeout)
        retry_config: Configuracao de retry (shortcut para config.retry)

    Exemplo sincrono:
        >>> client = InfomanceClient("sua_api_key")
        >>> municipios = client.list_municipalities()
        >>> print(municipios)

        >>> # Com context manager
        >>> with InfomanceClient("sua_api_key") as client:
        ...     municipio = client.get_municipality("3550308")

    Exemplo assincrono:
        >>> import asyncio
        >>> async def main():
        ...     async with InfomanceClient("sua_api_key") as client:
        ...         municipios = await client.list_municipalities_async()
        >>> asyncio.run(main())

    Exemplo com retry customizado:
        >>> from infomance import RetryConfig
        >>> retry = RetryConfig(max_retries=5, backoff_factor=2.0)
        >>> client = InfomanceClient("sua_api_key", retry_config=retry)
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[ClientConfig] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        retry_config: Optional[RetryConfig] = None,
        debug: bool = False,
    ) -> None:
        if not api_key:
            raise ValueError("API Key e obrigatoria")

        self.api_key = api_key
        self.config = config or ClientConfig()

        # Sobrescreve com parametros diretos se fornecidos
        if base_url:
            self.config.base_url = base_url.rstrip("/")
        if timeout:
            self.config.timeout = timeout
        if retry_config:
            self.config.retry = retry_config
        if debug:
            self.config.debug = debug

        self.base_url = self.config.base_url.rstrip("/")
        self.timeout = self.config.timeout

        # Configurar logging se debug habilitado
        if self.config.debug:
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)

        # Rate limit tracking
        self._rate_limit: Optional[RateLimitInfo] = None
        self._last_request_id: Optional[str] = None

        # Retry handler com callback de logging
        self._retry_handler = RetryHandler(self.config.retry)

        # HTTP clients (lazy initialization)
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict[str, str]:
        """Retorna headers padrao para requisicoes."""
        return {
            "User-Agent": f"infomance-python/{VERSION}",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_sync_client(self) -> httpx.Client:
        """Retorna ou cria o cliente HTTP sincrono."""
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers(),
                verify=self.config.verify_ssl,
            )
        return self._sync_client

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Retorna ou cria o cliente HTTP assincrono."""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers(),
                verify=self.config.verify_ssl,
            )
        return self._async_client

    def _extract_rate_limit(self, response: httpx.Response) -> None:
        """Extrai informacoes de rate limit dos headers."""
        try:
            limit = response.headers.get("X-RateLimit-Limit")
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")

            if limit and remaining and reset:
                reset_timestamp = int(reset)
                self._rate_limit = {
                    "limit": int(limit),
                    "remaining": int(remaining),
                    "reset": reset_timestamp,
                    "reset_at": datetime.fromtimestamp(reset_timestamp, tz=timezone.utc),
                }
            else:
                self._rate_limit = None
        except (ValueError, TypeError):
            self._rate_limit = None

        self._last_request_id = response.headers.get("X-Request-ID")

    def _build_query(self, params: Optional[dict[str, Any]]) -> dict[str, Any]:
        """Constroi query params filtrando valores None."""
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    def _build_url(self, path: str, format_: Optional[ExportFormat] = None) -> str:
        """Constroi URL completa."""
        url = f"{self.base_url}{path}"
        if format_ and format_ != "json":
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}format={format_}"
        return url

    # =========================================================================
    # Sync Request Methods (with retry)
    # =========================================================================

    def _do_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        format_: Optional[ExportFormat] = None,
    ) -> Any:
        """Executa requisicao HTTP sincrona (sem retry)."""
        client = self._get_sync_client()
        url = self._build_url(path, format_)
        query_params = self._build_query(params)

        logger.debug("Request started: %s %s", method, url)
        start_time = time.monotonic()

        try:
            response = client.request(
                method=method,
                url=url,
                params=query_params,
                json=json,
            )
        except httpx.TimeoutException as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Request timeout: %s %s after %.2fms - %s",
                method, url, elapsed_ms, str(e)
            )
            raise TimeoutError(timeout_seconds=self.timeout) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Request network error: %s %s after %.2fms - %s: %s",
                method, url, elapsed_ms, type(e).__name__, str(e)
            )
            raise NetworkError(original_error=e) from e

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "Request completed: %s %s - status=%d, elapsed=%.2fms",
            method, url, response.status_code, elapsed_ms
        )

        self._extract_rate_limit(response)

        if response.status_code >= 400:
            retry_after = None
            if response.status_code == 429:
                retry_after_header = response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        retry_after = int(retry_after_header)
                    except ValueError:
                        pass

            try:
                body = response.json()
            except Exception:
                body = {"detail": response.text}

            logger.error(
                "Request error: %s %s - status=%d, detail=%s",
                method, url, response.status_code, body.get("detail", "Unknown error")
            )

            raise_for_status(
                response.status_code,
                body,
                self._last_request_id,
                retry_after,
            )

        if format_ == "csv":
            return response.text
        if format_ == "xlsx":
            return response.content

        return response.json()

    def _log_retry(self, attempt: int, error: Exception, delay: float) -> None:
        """Callback de logging para retries."""
        logger.warning(
            "Retry attempt %d: %s - waiting %.2fs before next attempt",
            attempt + 1, str(error), delay
        )

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        format_: Optional[ExportFormat] = None,
    ) -> Any:
        """Executa requisicao HTTP sincrona com retry."""
        return self._retry_handler.execute(
            self._do_request,
            method,
            path,
            params,
            json,
            format_,
            on_retry=self._log_retry,
        )

    # =========================================================================
    # Async Request Methods (with retry)
    # =========================================================================

    async def _do_request_async(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        format_: Optional[ExportFormat] = None,
    ) -> Any:
        """Executa requisicao HTTP assincrona (sem retry)."""
        client = await self._get_async_client()
        url = self._build_url(path, format_)
        query_params = self._build_query(params)

        logger.debug("Request started (async): %s %s", method, url)
        start_time = time.monotonic()

        try:
            response = await client.request(
                method=method,
                url=url,
                params=query_params,
                json=json,
            )
        except httpx.TimeoutException as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Request timeout (async): %s %s after %.2fms - %s",
                method, url, elapsed_ms, str(e)
            )
            raise TimeoutError(timeout_seconds=self.timeout) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Request network error (async): %s %s after %.2fms - %s: %s",
                method, url, elapsed_ms, type(e).__name__, str(e)
            )
            raise NetworkError(original_error=e) from e

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "Request completed (async): %s %s - status=%d, elapsed=%.2fms",
            method, url, response.status_code, elapsed_ms
        )

        self._extract_rate_limit(response)

        if response.status_code >= 400:
            retry_after = None
            if response.status_code == 429:
                retry_after_header = response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        retry_after = int(retry_after_header)
                    except ValueError:
                        pass

            try:
                body = response.json()
            except Exception:
                body = {"detail": response.text}

            logger.error(
                "Request error (async): %s %s - status=%d, detail=%s",
                method, url, response.status_code, body.get("detail", "Unknown error")
            )

            raise_for_status(
                response.status_code,
                body,
                self._last_request_id,
                retry_after,
            )

        if format_ == "csv":
            return response.text
        if format_ == "xlsx":
            return response.content

        return response.json()

    async def _request_async(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        format_: Optional[ExportFormat] = None,
    ) -> Any:
        """Executa requisicao HTTP assincrona com retry."""
        return await self._retry_handler.execute_async(
            self._do_request_async,
            method,
            path,
            params,
            json,
            format_,
            on_retry=self._log_retry,
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def rate_limit(self) -> Optional[RateLimitInfo]:
        """Informacoes de rate limit da ultima requisicao."""
        return self._rate_limit

    @property
    def last_request_id(self) -> Optional[str]:
        """ID da ultima requisicao (util para suporte)."""
        return self._last_request_id

    @property
    def retry_config(self) -> RetryConfig:
        """Configuracao de retry atual."""
        return self.config.retry

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def close(self) -> None:
        """Fecha as conexoes HTTP sincronas."""
        if self._sync_client and not self._sync_client.is_closed:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self) -> None:
        """Fecha as conexoes HTTP assincronas."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self) -> InfomanceClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    async def __aenter__(self) -> InfomanceClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close_async()

    def __repr__(self) -> str:
        return f"InfomanceClient(base_url={self.base_url!r})"

    # =========================================================================
    # Indicators API - Sync
    # =========================================================================

    def list_municipalities(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> ListResponse:
        """Lista municipios com indicadores socioeconomicos.

        Args:
            limit: Numero maximo de resultados (default: 100, max: 1000).
            offset: Offset para paginacao.
            state: UF para filtrar (ex: "SP"). Se None, retorna todos.

        Returns:
            ListResponse com items (lista de municipios) e total.

        Raises:
            AuthenticationError: Se a API key for invalida.
            RateLimitError: Se o limite de requests for atingido.
            ValidationError: Se os parametros forem invalidos.

        Example:
            >>> client = InfomanceClient("api-key")
            >>> result = client.list_municipalities(state="SP", limit=10)
            >>> print(result["total"])
            645
            >>> for m in result["items"]:
            ...     print(f"{m['name']} - {m['ibge_code']}")
        """
        params = {"limit": limit, "offset": offset, "state": state}
        return self._request("GET", "/api/v1/indicators/municipalities", params=params)

    def get_municipality(self, ibge_code: str) -> IndicatorsMunicipality:
        """Busca dados completos de um municipio.

        Retorna informacoes detalhadas incluindo dados demograficos,
        economicos e de infraestrutura.

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos, ex: "3550308").

        Returns:
            IndicatorsMunicipality com nome, populacao, PIB, area,
            dados economicos e de infraestrutura.

        Raises:
            NotFoundError: Se o municipio nao existir.
            AuthenticationError: Se a API key for invalida.
            ValidationError: Se o codigo IBGE for invalido.

        Example:
            >>> client = InfomanceClient("api-key")
            >>> sp = client.get_municipality("3550308")
            >>> print(f"{sp['name']} - PIB: R$ {sp['pib']:,.2f}")
            Sao Paulo - PIB: R$ 699,288,090,000.00
        """
        return self._request("GET", f"/api/v1/indicators/municipalities/{ibge_code}")

    def get_municipality_economic(self, ibge_code: str) -> EconomicData:
        """Busca dados economicos de um municipio.

        Retorna a composicao do PIB por setor (agricultura, industria,
        servicos, impostos) e PIB per capita.

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos).

        Returns:
            EconomicData com PIB total, PIB per capita e participacao
            de cada setor economico.

        Raises:
            NotFoundError: Se o municipio nao existir.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> economic = client.get_municipality_economic("3550308")
            >>> print(f"PIB: R$ {economic['pib']:,.2f}")
            >>> print(f"Servicos: {economic['services']}%")
        """
        return self._request("GET", f"/api/v1/indicators/municipalities/{ibge_code}/economic")

    def get_municipality_infrastructure(self, ibge_code: str) -> InfrastructureData:
        """Busca dados de infraestrutura de um municipio.

        Retorna indicadores de saneamento basico (agua, esgoto),
        perdas de agua e cobertura de internet/fibra.

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos).

        Returns:
            InfrastructureData com cobertura de agua, coleta e tratamento
            de esgoto, perdas de agua, acessos a internet e cobertura de fibra.

        Raises:
            NotFoundError: Se o municipio nao existir.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> infra = client.get_municipality_infrastructure("3550308")
            >>> print(f"Cobertura de agua: {infra['water_coverage']}%")
            >>> print(f"Coleta de esgoto: {infra['sewage_collection']}%")
        """
        return self._request(
            "GET", f"/api/v1/indicators/municipalities/{ibge_code}/infrastructure"
        )

    def get_indicators_ranking(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking de municipios por indicador.

        Retorna municipios ordenados por um indicador especifico,
        util para comparacoes e analises competitivas.

        Args:
            indicator: Nome do indicador (pib, population, pib_per_capita,
                area_km2, etc.).
            limit: Numero maximo de resultados (default: 100, max: 1000).
            offset: Offset para paginacao.
            state: UF para filtrar (ex: "SP").
            year: Ano de referencia dos dados.
            order: Ordenacao "asc" (menor para maior) ou "desc" (maior para menor).

        Returns:
            Lista de RankingEntry com position, ibge_code, name, state e value.

        Raises:
            ValidationError: Se o indicador nao existir ou parametros invalidos.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> ranking = client.get_indicators_ranking("pib", limit=5, order="desc")
            >>> for r in ranking:
            ...     print(f"{r['position']}. {r['name']}: R$ {r['value']:,.2f}")
            1. Sao Paulo: R$ 699,288,090,000.00
            2. Rio de Janeiro: R$ 364,052,740,000.00
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return self._request("GET", f"/api/v1/indicators/ranking/{indicator}", params=params)

    # =========================================================================
    # COMEX API - Sync
    # =========================================================================

    def get_comex_overview(self) -> ComexOverview:
        """Retorna visao geral do comercio exterior agropecuario.

        Fornece estatisticas agregadas de exportacoes brasileiras,
        incluindo produtos mais exportados e paises de destino.

        Returns:
            ComexOverview com total_value_usd, total_volume_kg, total_products,
            total_countries, top_products e anos disponiveis.

        Raises:
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> overview = client.get_comex_overview()
            >>> print(f"Total exportado: US$ {overview['total_value_usd']:,.2f}")
            >>> for p in overview['top_products'][:3]:
            ...     print(f"  {p['code_sh4']}: US$ {p['value_usd']:,.2f}")
        """
        return self._request("GET", "/api/v1/comex/overview")

    def get_comex_municipality(self, ibge_code: str) -> ComexMunicipality:
        """Busca dados de comercio exterior de um municipio.

        Retorna exportacoes do municipio incluindo produtos,
        valores em USD e volume em kg.

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos).

        Returns:
            ComexMunicipality com total_value_usd, total_volume_kg
            e lista de produtos exportados.

        Raises:
            NotFoundError: Se o municipio nao existir ou nao tiver dados.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> comex = client.get_comex_municipality("3550308")
            >>> print(f"{comex['name']}: US$ {comex['total_value_usd']:,.2f}")
        """
        return self._request("GET", f"/api/v1/comex/municipalities/{ibge_code}")

    def get_comex_municipality_timeseries(
        self,
        ibge_code: str,
        year: Optional[int] = None,
    ) -> list[ComexProduct]:
        """
        Busca serie temporal de COMEX de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio
            year: Filtrar por ano

        Returns:
            Lista de produtos por ano
        """
        params = {"year": year}
        return self._request(
            "GET", f"/api/v1/comex/municipalities/{ibge_code}/timeseries", params=params
        )

    def get_comex_products(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        year: Optional[int] = None,
    ) -> ComexProductsResponse:
        """
        Lista produtos de exportacao.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            year: Filtrar por ano

        Returns:
            Lista de produtos
        """
        params = {"limit": limit, "offset": offset, "year": year}
        return self._request("GET", "/api/v1/comex/products", params=params)

    def get_comex_countries(self, year: Optional[int] = None) -> ComexCountriesResponse:
        """
        Lista paises de destino das exportacoes.

        Args:
            year: Filtrar por ano

        Returns:
            Lista de paises com valores
        """
        params = {"year": year}
        return self._request("GET", "/api/v1/comex/countries", params=params)

    def get_comex_ranking(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """
        Busca ranking de COMEX por indicador.

        Args:
            indicator: Nome do indicador
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano
            order: Ordenacao (asc ou desc)

        Returns:
            Lista de municipios ordenados
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return self._request("GET", f"/api/v1/comex/ranking/{indicator}", params=params)

    # =========================================================================
    # SICOR API - Sync
    # =========================================================================

    def get_sicor_overview(self) -> SicorOverview:
        """
        Retorna visao geral do credito rural.

        Returns:
            Totais, categorias e anos disponiveis
        """
        return self._request("GET", "/api/v1/sicor/overview")

    def get_sicor_state(self, uf: str) -> list[SicorState]:
        """
        Busca dados de SICOR de um estado.

        Args:
            uf: Sigla do estado (ex: SP, MG)

        Returns:
            Dados de credito rural do estado
        """
        return self._request("GET", f"/api/v1/sicor/states/{uf}")

    def get_sicor_state_timeseries(self, uf: str) -> list[SicorState]:
        """
        Busca serie temporal de SICOR de um estado.

        Args:
            uf: Sigla do estado

        Returns:
            Serie temporal de credito rural
        """
        return self._request("GET", f"/api/v1/sicor/states/{uf}/timeseries")

    def get_sicor_by_finalidade(self) -> list[SicorByCategory]:
        """
        Busca SICOR agrupado por finalidade.

        Returns:
            Dados agrupados por finalidade (custeio, investimento, etc)
        """
        return self._request("GET", "/api/v1/sicor/by-finalidade")

    def get_sicor_by_atividade(self) -> list[SicorByCategory]:
        """
        Busca SICOR agrupado por atividade.

        Returns:
            Dados agrupados por atividade (agricola, pecuaria, etc)
        """
        return self._request("GET", "/api/v1/sicor/by-atividade")

    def get_sicor_by_programa(self) -> list[SicorByCategory]:
        """
        Busca SICOR agrupado por programa.

        Returns:
            Dados agrupados por programa (PRONAF, PRONAMP, etc)
        """
        return self._request("GET", "/api/v1/sicor/by-programa")

    def get_sicor_ranking(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """
        Busca ranking de SICOR por indicador.

        Args:
            indicator: Nome do indicador
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano
            order: Ordenacao (asc ou desc)

        Returns:
            Lista de municipios/estados ordenados
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return self._request("GET", f"/api/v1/sicor/ranking/{indicator}", params=params)

    # =========================================================================
    # Health API - Sync
    # =========================================================================

    def list_health_establishments(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        type_: Optional[str] = None,
    ) -> ListResponse:
        """Lista estabelecimentos de saude do SUS.

        Retorna hospitais, UBS, clinicas e outros estabelecimentos
        de saude com dados do CNES (Cadastro Nacional de Estabelecimentos de Saude).

        Args:
            limit: Numero maximo de resultados (default: 100, max: 1000).
            offset: Offset para paginacao.
            state: UF para filtrar (ex: "SP").
            type_: Tipo de estabelecimento (ex: "Hospital Geral", "UBS").

        Returns:
            ListResponse com items (lista de HealthEstablishment) e total.

        Raises:
            AuthenticationError: Se a API key for invalida.
            ValidationError: Se os parametros forem invalidos.

        Example:
            >>> result = client.list_health_establishments(state="SP", limit=10)
            >>> for e in result["items"]:
            ...     print(f"{e['name']} - {e['establishment_type']}")
        """
        params = {"limit": limit, "offset": offset, "state": state, "type": type_}
        return self._request("GET", "/api/v1/health/establishments", params=params)

    def get_health_establishment(self, cnes_code: str) -> HealthEstablishment:
        """Busca dados de um estabelecimento de saude pelo codigo CNES.

        Retorna informacoes detalhadas incluindo tipo, gestao,
        localizacao, leitos e servicos disponiveis.

        Args:
            cnes_code: Codigo CNES do estabelecimento (7 digitos).

        Returns:
            HealthEstablishment com nome, tipo, gestao, endereco,
            coordenadas, leitos e flags de servicos.

        Raises:
            NotFoundError: Se o estabelecimento nao existir.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> hospital = client.get_health_establishment("2077485")
            >>> print(f"{hospital['name']} - {hospital['total_beds']} leitos")
        """
        return self._request("GET", f"/api/v1/health/establishments/{cnes_code}")

    def get_municipality_health_stats(self, ibge_code: str) -> HealthStats:
        """Busca estatisticas de saude de um municipio.

        Retorna agregados de estabelecimentos e leitos do municipio,
        agrupados por tipo de estabelecimento e tipo de gestao.

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos).

        Returns:
            HealthStats com total_establishments, total_beds e
            distribuicao por tipo e gestao.

        Raises:
            NotFoundError: Se o municipio nao existir.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> stats = client.get_municipality_health_stats("3550308")
            >>> print(f"Total: {stats['total_establishments']} estabelecimentos")
            >>> print(f"Leitos: {stats['total_beds']}")
        """
        return self._request("GET", f"/api/v1/health/municipalities/{ibge_code}")

    def get_health_stats(self) -> HealthStats:
        """
        Retorna estatisticas gerais de saude.

        Returns:
            Estatisticas agregadas de saude
        """
        return self._request("GET", "/api/v1/health/stats")

    def search_health_establishments(
        self,
        query: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListResponse:
        """
        Busca estabelecimentos de saude por nome.

        Args:
            query: Termo de busca
            limit: Numero maximo de resultados
            offset: Offset para paginacao

        Returns:
            Lista paginada de estabelecimentos
        """
        params = {"q": query, "limit": limit, "offset": offset}
        return self._request("GET", "/api/v1/health/search", params=params)

    # =========================================================================
    # Education API - Sync
    # =========================================================================

    def list_schools(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        network: Optional[str] = None,
    ) -> ListResponse:
        """
        Lista escolas.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            network: Filtrar por rede (municipal, estadual, federal, privada)

        Returns:
            Lista paginada de escolas
        """
        params = {"limit": limit, "offset": offset, "state": state, "network": network}
        return self._request("GET", "/api/v1/education/schools", params=params)

    def get_education_overview(self) -> EducationOverview:
        """
        Retorna visao geral da educacao.

        Returns:
            Total de escolas e distribuicao por rede
        """
        return self._request("GET", "/api/v1/education/overview")

    def get_ideb_ranking(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[IDEBScore]:
        """
        Busca ranking do IDEB.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano
            order: Ordenacao (asc ou desc)

        Returns:
            Lista de municipios ordenados pelo IDEB
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return self._request("GET", "/api/v1/education/ideb/ranking", params=params)

    def get_municipality_education(self, ibge_code: str) -> MunicipalityEducation:
        """
        Busca dados de educacao de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Dados de educacao do municipio
        """
        return self._request("GET", f"/api/v1/education/municipalities/{ibge_code}")

    # =========================================================================
    # Security API - Sync
    # =========================================================================

    def list_crime_stats(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
    ) -> ListResponse:
        """
        Lista estatisticas de crimes.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano

        Returns:
            Lista paginada de estatisticas
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year}
        return self._request("GET", "/api/v1/security/stats", params=params)

    def get_security_overview(self) -> CrimeOverview:
        """
        Retorna visao geral de seguranca.

        Returns:
            Totais e rankings de seguranca
        """
        return self._request("GET", "/api/v1/security/overview")

    def get_crime_types(self) -> CrimeTypesResponse:
        """
        Lista tipos de crimes.

        Returns:
            Lista de tipos de crimes disponiveis
        """
        return self._request("GET", "/api/v1/security/types")

    def get_crime_ranking(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
        crime_type: Optional[str] = None,
    ) -> list[RankingEntry]:
        """
        Busca ranking de crimes.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano
            order: Ordenacao (asc ou desc)
            crime_type: Filtrar por tipo de crime

        Returns:
            Lista de cidades ordenadas
        """
        params = {
            "limit": limit,
            "offset": offset,
            "state": state,
            "year": year,
            "order": order,
            "crime_type": crime_type,
        }
        return self._request("GET", "/api/v1/security/ranking", params=params)

    def get_municipality_crime_stats(self, city: str) -> list[CrimeStats]:
        """
        Busca estatisticas de crimes de uma cidade.

        Args:
            city: Nome ou codigo da cidade

        Returns:
            Lista de estatisticas de crimes
        """
        return self._request("GET", f"/api/v1/security/municipalities/{city}")

    # =========================================================================
    # Employment API - Sync
    # =========================================================================

    def list_employment_municipalities(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> ListResponse:
        """
        Lista municipios com dados de emprego.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado

        Returns:
            Lista paginada de municipios
        """
        params = {"limit": limit, "offset": offset, "state": state}
        return self._request("GET", "/api/v1/employment/municipalities", params=params)

    def get_municipality_employment(self, ibge_code: str) -> EmploymentData:
        """
        Busca dados de emprego de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Dados de emprego do municipio
        """
        return self._request("GET", f"/api/v1/employment/municipalities/{ibge_code}")

    def get_employment_timeseries(self, ibge_code: str) -> list[EmploymentData]:
        """
        Busca serie temporal de emprego de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Serie temporal de emprego
        """
        return self._request("GET", f"/api/v1/employment/municipalities/{ibge_code}/timeseries")

    def get_employment_ranking(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """
        Busca ranking de emprego por indicador.

        Args:
            indicator: Nome do indicador
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano
            order: Ordenacao (asc ou desc)

        Returns:
            Lista de municipios ordenados
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return self._request("GET", f"/api/v1/employment/ranking/{indicator}", params=params)

    def get_employment_overview(self) -> EmploymentOverview:
        """
        Retorna visao geral de emprego.

        Returns:
            Totais de emprego
        """
        return self._request("GET", "/api/v1/employment/overview")

    # =========================================================================
    # AGRO API - Sync
    # =========================================================================

    def list_agro_municipalities(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> ListResponse:
        """
        Lista municipios com dados agropecuarios.

        Args:
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado

        Returns:
            Lista paginada de municipios
        """
        params = {"limit": limit, "offset": offset, "state": state}
        return self._request("GET", "/api/v1/agro/municipalities", params=params)

    def get_agro_municipality(self, ibge_code: str) -> AgroMunicipality:
        """
        Busca dados agropecuarios de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Dados agropecuarios do municipio
        """
        return self._request("GET", f"/api/v1/agro/municipalities/{ibge_code}")

    def get_agro_timeseries(self, ibge_code: str) -> list[AgroTimeseries]:
        """
        Busca serie temporal agropecuaria de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Serie temporal de producao
        """
        return self._request("GET", f"/api/v1/agro/municipalities/{ibge_code}/timeseries")

    def get_agro_land_use(self, ibge_code: str) -> list[LandUseData]:
        """
        Busca dados de uso do solo de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Dados de uso do solo
        """
        return self._request("GET", f"/api/v1/agro/municipalities/{ibge_code}/land-use")

    def get_agro_emissions(self, ibge_code: str) -> list[EmissionsData]:
        """
        Busca dados de emissoes de um municipio.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Dados de emissoes de GEE
        """
        return self._request("GET", f"/api/v1/agro/municipalities/{ibge_code}/emissions")

    def get_agro_ranking(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """
        Busca ranking agropecuario por indicador.

        Args:
            indicator: Nome do indicador
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            state: Filtrar por estado
            year: Filtrar por ano
            order: Ordenacao (asc ou desc)

        Returns:
            Lista de municipios ordenados
        """
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return self._request("GET", f"/api/v1/agro/ranking/{indicator}", params=params)

    def get_agro_stats(self) -> AgroStats:
        """
        Retorna estatisticas agropecuarias gerais.

        Returns:
            Estatisticas agregadas
        """
        return self._request("GET", "/api/v1/agro/stats")

    # =========================================================================
    # POI API - Sync
    # =========================================================================

    def search_pois(
        self,
        city: Optional[str] = None,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius: Optional[float] = None,
        q: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListResponse:
        """Busca pontos de interesse (POIs).

        Permite buscar estabelecimentos comerciais, servicos e locais
        de interesse com filtros por cidade, categoria, localizacao
        e termo de busca textual.

        Args:
            city: Nome ou codigo IBGE da cidade.
            category: Categoria do POI (ex: "restaurante", "farmacia").
            lat: Latitude para busca por proximidade.
            lng: Longitude para busca por proximidade.
            radius: Raio em metros para busca por proximidade (default: 1000).
            q: Termo de busca textual (nome, endereco, etc.).
            limit: Numero maximo de resultados (default: 100, max: 1000).
            offset: Offset para paginacao.

        Returns:
            ListResponse com items (lista de POI) e total.

        Raises:
            ValidationError: Se os parametros forem invalidos.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> pois = client.search_pois(city="Sao Paulo", category="farmacia", limit=10)
            >>> for p in pois["items"]:
            ...     print(f"{p['name']} - {p['address']}")
        """
        params = {
            "city": city,
            "category": category,
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "q": q,
            "limit": limit,
            "offset": offset,
        }
        return self._request("GET", "/api/v1/pois", params=params)

    def search_nearby_pois(
        self,
        lat: float,
        lng: float,
        radius: Optional[float] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListResponse:
        """
        Busca POIs proximos a uma localizacao.

        Args:
            lat: Latitude do ponto central
            lng: Longitude do ponto central
            radius: Raio em metros (default: 1000)
            city: Filtrar por cidade
            category: Filtrar por categoria
            limit: Numero maximo de resultados
            offset: Offset para paginacao

        Returns:
            Lista paginada de POIs
        """
        params = {
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "city": city,
            "category": category,
            "limit": limit,
            "offset": offset,
        }
        return self._request("GET", "/api/v1/pois/nearby", params=params)

    def get_poi_categories(self) -> POICategoriesResponse:
        """
        Lista categorias de POIs disponiveis.

        Returns:
            Lista de categorias
        """
        return self._request("GET", "/api/v1/pois/categories")

    def get_city_poi_stats(self, city: str) -> CityPOIStats:
        """
        Busca estatisticas de POIs de uma cidade.

        Args:
            city: Nome ou codigo da cidade

        Returns:
            Estatisticas de POIs da cidade
        """
        return self._request("GET", f"/api/v1/pois/cities/{city}/stats")

    # =========================================================================
    # Consolidated API - Sync
    # =========================================================================

    def get_consolidated_city(self, ibge_code: str) -> ConsolidatedCity:
        """Busca dados consolidados de uma cidade.

        Retorna todos os indicadores disponiveis em uma unica chamada:
        demograficos, economicos, saude, educacao, seguranca e emprego.
        Ideal para dashboards e visoes gerais.

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos).

        Returns:
            ConsolidatedCity com municipality, indicators, health,
            education, security, employment e agro.

        Raises:
            NotFoundError: Se o municipio nao existir.
            AuthenticationError: Se a API key for invalida.

        Example:
            >>> city = client.get_consolidated_city("3550308")
            >>> print(f"{city['municipality']['name']}")
            >>> print(f"PIB: R$ {city['indicators']['pib']:,.2f}")
            >>> print(f"Hospitais: {city['health']['total_establishments']}")
        """
        return self._request("GET", f"/api/v1/consolidated/cities/{ibge_code}")

    def get_consolidated_city_summary(self, ibge_code: str) -> ConsolidatedCity:
        """
        Busca resumo consolidado de uma cidade.

        Args:
            ibge_code: Codigo IBGE do municipio

        Returns:
            Resumo consolidado com principais indicadores
        """
        return self._request("GET", f"/api/v1/consolidated/cities/{ibge_code}/summary")

    # =========================================================================
    # Export Methods - Sync
    # =========================================================================

    def export_to_csv(self, path: str, **params: Any) -> str:
        """Exporta dados em formato CSV.

        Permite baixar os dados de qualquer endpoint em formato CSV
        para analise em planilhas ou processamento posterior.

        Args:
            path: Caminho do endpoint (ex: "/api/v1/indicators/municipalities").
            **params: Parametros de query (state, limit, etc.).

        Returns:
            Conteudo CSV como string com cabecalho e dados.

        Raises:
            AuthenticationError: Se a API key for invalida.
            ValidationError: Se os parametros forem invalidos.

        Example:
            >>> csv_data = client.export_to_csv(
            ...     "/api/v1/indicators/municipalities",
            ...     state="SP",
            ...     limit=100
            ... )
            >>> with open("municipios_sp.csv", "w") as f:
            ...     f.write(csv_data)
        """
        return self._request("GET", path, params=params, format_="csv")

    def export_to_excel(self, path: str, **params: Any) -> bytes:
        """Exporta dados em formato Excel (XLSX).

        Permite baixar os dados de qualquer endpoint em formato Excel
        para analise em planilhas.

        Args:
            path: Caminho do endpoint (ex: "/api/v1/indicators/municipalities").
            **params: Parametros de query (state, limit, etc.).

        Returns:
            Conteudo Excel como bytes (arquivo XLSX).

        Raises:
            AuthenticationError: Se a API key for invalida.
            ValidationError: Se os parametros forem invalidos.

        Example:
            >>> excel_data = client.export_to_excel(
            ...     "/api/v1/indicators/municipalities",
            ...     state="SP"
            ... )
            >>> with open("municipios_sp.xlsx", "wb") as f:
            ...     f.write(excel_data)
        """
        return self._request("GET", path, params=params, format_="xlsx")

    # =========================================================================
    # Indicators API - Async
    # =========================================================================

    async def list_municipalities_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> ListResponse:
        """Lista municipios com indicadores socioeconomicos (assincrono).

        Versao assincrona de list_municipalities(). Use com await ou
        asyncio.gather() para buscar multiplos recursos em paralelo.

        Args:
            limit: Numero maximo de resultados (default: 100, max: 1000).
            offset: Offset para paginacao.
            state: UF para filtrar (ex: "SP").

        Returns:
            ListResponse com items (lista de municipios) e total.

        Example:
            >>> async with InfomanceClient("api-key") as client:
            ...     result = await client.list_municipalities_async(state="SP")
        """
        params = {"limit": limit, "offset": offset, "state": state}
        return await self._request_async("GET", "/api/v1/indicators/municipalities", params=params)

    async def get_municipality_async(self, ibge_code: str) -> IndicatorsMunicipality:
        """Busca dados completos de um municipio (assincrono).

        Versao assincrona de get_municipality(). Ideal para buscar
        multiplos municipios em paralelo com asyncio.gather().

        Args:
            ibge_code: Codigo IBGE do municipio (7 digitos).

        Returns:
            IndicatorsMunicipality com dados completos.

        Raises:
            NotFoundError: Se o municipio nao existir.

        Example:
            >>> async with InfomanceClient("api-key") as client:
            ...     sp, rj = await asyncio.gather(
            ...         client.get_municipality_async("3550308"),
            ...         client.get_municipality_async("3304557"),
            ...     )
        """
        return await self._request_async("GET", f"/api/v1/indicators/municipalities/{ibge_code}")

    async def get_municipality_economic_async(self, ibge_code: str) -> EconomicData:
        """Busca dados economicos de um municipio (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/indicators/municipalities/{ibge_code}/economic"
        )

    async def get_municipality_infrastructure_async(self, ibge_code: str) -> InfrastructureData:
        """Busca dados de infraestrutura de um municipio (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/indicators/municipalities/{ibge_code}/infrastructure"
        )

    async def get_indicators_ranking_async(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking de municipios por indicador (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return await self._request_async(
            "GET", f"/api/v1/indicators/ranking/{indicator}", params=params
        )

    # =========================================================================
    # COMEX API - Async
    # =========================================================================

    async def get_comex_overview_async(self) -> ComexOverview:
        """Retorna visao geral do comercio exterior (assincrono)."""
        return await self._request_async("GET", "/api/v1/comex/overview")

    async def get_comex_municipality_async(self, ibge_code: str) -> ComexMunicipality:
        """Busca dados de COMEX de um municipio (assincrono)."""
        return await self._request_async("GET", f"/api/v1/comex/municipalities/{ibge_code}")

    async def get_comex_municipality_timeseries_async(
        self,
        ibge_code: str,
        year: Optional[int] = None,
    ) -> list[ComexProduct]:
        """Busca serie temporal de COMEX de um municipio (assincrono)."""
        params = {"year": year}
        return await self._request_async(
            "GET", f"/api/v1/comex/municipalities/{ibge_code}/timeseries", params=params
        )

    async def get_comex_products_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        year: Optional[int] = None,
    ) -> ComexProductsResponse:
        """Lista produtos de exportacao (assincrono)."""
        params = {"limit": limit, "offset": offset, "year": year}
        return await self._request_async("GET", "/api/v1/comex/products", params=params)

    async def get_comex_countries_async(self, year: Optional[int] = None) -> ComexCountriesResponse:
        """Lista paises de destino das exportacoes (assincrono)."""
        params = {"year": year}
        return await self._request_async("GET", "/api/v1/comex/countries", params=params)

    async def get_comex_ranking_async(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking de COMEX por indicador (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return await self._request_async(
            "GET", f"/api/v1/comex/ranking/{indicator}", params=params
        )

    # =========================================================================
    # SICOR API - Async
    # =========================================================================

    async def get_sicor_overview_async(self) -> SicorOverview:
        """Retorna visao geral do credito rural (assincrono)."""
        return await self._request_async("GET", "/api/v1/sicor/overview")

    async def get_sicor_state_async(self, uf: str) -> list[SicorState]:
        """Busca dados de SICOR de um estado (assincrono)."""
        return await self._request_async("GET", f"/api/v1/sicor/states/{uf}")

    async def get_sicor_state_timeseries_async(self, uf: str) -> list[SicorState]:
        """Busca serie temporal de SICOR de um estado (assincrono)."""
        return await self._request_async("GET", f"/api/v1/sicor/states/{uf}/timeseries")

    async def get_sicor_by_finalidade_async(self) -> list[SicorByCategory]:
        """Busca SICOR agrupado por finalidade (assincrono)."""
        return await self._request_async("GET", "/api/v1/sicor/by-finalidade")

    async def get_sicor_by_atividade_async(self) -> list[SicorByCategory]:
        """Busca SICOR agrupado por atividade (assincrono)."""
        return await self._request_async("GET", "/api/v1/sicor/by-atividade")

    async def get_sicor_by_programa_async(self) -> list[SicorByCategory]:
        """Busca SICOR agrupado por programa (assincrono)."""
        return await self._request_async("GET", "/api/v1/sicor/by-programa")

    async def get_sicor_ranking_async(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking de SICOR por indicador (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return await self._request_async(
            "GET", f"/api/v1/sicor/ranking/{indicator}", params=params
        )

    # =========================================================================
    # Health API - Async
    # =========================================================================

    async def list_health_establishments_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        type_: Optional[str] = None,
    ) -> ListResponse:
        """Lista estabelecimentos de saude (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "type": type_}
        return await self._request_async("GET", "/api/v1/health/establishments", params=params)

    async def get_health_establishment_async(self, cnes_code: str) -> HealthEstablishment:
        """Busca dados de um estabelecimento de saude (assincrono)."""
        return await self._request_async("GET", f"/api/v1/health/establishments/{cnes_code}")

    async def get_municipality_health_stats_async(self, ibge_code: str) -> HealthStats:
        """Busca estatisticas de saude de um municipio (assincrono)."""
        return await self._request_async("GET", f"/api/v1/health/municipalities/{ibge_code}")

    async def get_health_stats_async(self) -> HealthStats:
        """Retorna estatisticas gerais de saude (assincrono)."""
        return await self._request_async("GET", "/api/v1/health/stats")

    async def search_health_establishments_async(
        self,
        query: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListResponse:
        """Busca estabelecimentos de saude por nome (assincrono)."""
        params = {"q": query, "limit": limit, "offset": offset}
        return await self._request_async("GET", "/api/v1/health/search", params=params)

    # =========================================================================
    # Education API - Async
    # =========================================================================

    async def list_schools_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        network: Optional[str] = None,
    ) -> ListResponse:
        """Lista escolas (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "network": network}
        return await self._request_async("GET", "/api/v1/education/schools", params=params)

    async def get_education_overview_async(self) -> EducationOverview:
        """Retorna visao geral da educacao (assincrono)."""
        return await self._request_async("GET", "/api/v1/education/overview")

    async def get_ideb_ranking_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[IDEBScore]:
        """Busca ranking do IDEB (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return await self._request_async("GET", "/api/v1/education/ideb/ranking", params=params)

    async def get_municipality_education_async(self, ibge_code: str) -> MunicipalityEducation:
        """Busca dados de educacao de um municipio (assincrono)."""
        return await self._request_async("GET", f"/api/v1/education/municipalities/{ibge_code}")

    # =========================================================================
    # Security API - Async
    # =========================================================================

    async def list_crime_stats_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
    ) -> ListResponse:
        """Lista estatisticas de crimes (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year}
        return await self._request_async("GET", "/api/v1/security/stats", params=params)

    async def get_security_overview_async(self) -> CrimeOverview:
        """Retorna visao geral de seguranca (assincrono)."""
        return await self._request_async("GET", "/api/v1/security/overview")

    async def get_crime_types_async(self) -> CrimeTypesResponse:
        """Lista tipos de crimes (assincrono)."""
        return await self._request_async("GET", "/api/v1/security/types")

    async def get_crime_ranking_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
        crime_type: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking de crimes (assincrono)."""
        params = {
            "limit": limit,
            "offset": offset,
            "state": state,
            "year": year,
            "order": order,
            "crime_type": crime_type,
        }
        return await self._request_async("GET", "/api/v1/security/ranking", params=params)

    async def get_municipality_crime_stats_async(self, city: str) -> list[CrimeStats]:
        """Busca estatisticas de crimes de uma cidade (assincrono)."""
        return await self._request_async("GET", f"/api/v1/security/municipalities/{city}")

    # =========================================================================
    # Employment API - Async
    # =========================================================================

    async def list_employment_municipalities_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> ListResponse:
        """Lista municipios com dados de emprego (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state}
        return await self._request_async("GET", "/api/v1/employment/municipalities", params=params)

    async def get_municipality_employment_async(self, ibge_code: str) -> EmploymentData:
        """Busca dados de emprego de um municipio (assincrono)."""
        return await self._request_async("GET", f"/api/v1/employment/municipalities/{ibge_code}")

    async def get_employment_timeseries_async(self, ibge_code: str) -> list[EmploymentData]:
        """Busca serie temporal de emprego de um municipio (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/employment/municipalities/{ibge_code}/timeseries"
        )

    async def get_employment_ranking_async(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking de emprego por indicador (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return await self._request_async(
            "GET", f"/api/v1/employment/ranking/{indicator}", params=params
        )

    async def get_employment_overview_async(self) -> EmploymentOverview:
        """Retorna visao geral de emprego (assincrono)."""
        return await self._request_async("GET", "/api/v1/employment/overview")

    # =========================================================================
    # AGRO API - Async
    # =========================================================================

    async def list_agro_municipalities_async(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> ListResponse:
        """Lista municipios com dados agropecuarios (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state}
        return await self._request_async("GET", "/api/v1/agro/municipalities", params=params)

    async def get_agro_municipality_async(self, ibge_code: str) -> AgroMunicipality:
        """Busca dados agropecuarios de um municipio (assincrono)."""
        return await self._request_async("GET", f"/api/v1/agro/municipalities/{ibge_code}")

    async def get_agro_timeseries_async(self, ibge_code: str) -> list[AgroTimeseries]:
        """Busca serie temporal agropecuaria de um municipio (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/agro/municipalities/{ibge_code}/timeseries"
        )

    async def get_agro_land_use_async(self, ibge_code: str) -> list[LandUseData]:
        """Busca dados de uso do solo de um municipio (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/agro/municipalities/{ibge_code}/land-use"
        )

    async def get_agro_emissions_async(self, ibge_code: str) -> list[EmissionsData]:
        """Busca dados de emissoes de um municipio (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/agro/municipalities/{ibge_code}/emissions"
        )

    async def get_agro_ranking_async(
        self,
        indicator: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        order: Optional[str] = None,
    ) -> list[RankingEntry]:
        """Busca ranking agropecuario por indicador (assincrono)."""
        params = {"limit": limit, "offset": offset, "state": state, "year": year, "order": order}
        return await self._request_async(
            "GET", f"/api/v1/agro/ranking/{indicator}", params=params
        )

    async def get_agro_stats_async(self) -> AgroStats:
        """Retorna estatisticas agropecuarias gerais (assincrono)."""
        return await self._request_async("GET", "/api/v1/agro/stats")

    # =========================================================================
    # POI API - Async
    # =========================================================================

    async def search_pois_async(
        self,
        city: Optional[str] = None,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius: Optional[float] = None,
        q: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListResponse:
        """Busca pontos de interesse (assincrono)."""
        params = {
            "city": city,
            "category": category,
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "q": q,
            "limit": limit,
            "offset": offset,
        }
        return await self._request_async("GET", "/api/v1/pois", params=params)

    async def search_nearby_pois_async(
        self,
        lat: float,
        lng: float,
        radius: Optional[float] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> ListResponse:
        """Busca POIs proximos a uma localizacao (assincrono)."""
        params = {
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "city": city,
            "category": category,
            "limit": limit,
            "offset": offset,
        }
        return await self._request_async("GET", "/api/v1/pois/nearby", params=params)

    async def get_poi_categories_async(self) -> POICategoriesResponse:
        """Lista categorias de POIs disponiveis (assincrono)."""
        return await self._request_async("GET", "/api/v1/pois/categories")

    async def get_city_poi_stats_async(self, city: str) -> CityPOIStats:
        """Busca estatisticas de POIs de uma cidade (assincrono)."""
        return await self._request_async("GET", f"/api/v1/pois/cities/{city}/stats")

    # =========================================================================
    # Consolidated API - Async
    # =========================================================================

    async def get_consolidated_city_async(self, ibge_code: str) -> ConsolidatedCity:
        """Busca dados consolidados de uma cidade (assincrono)."""
        return await self._request_async("GET", f"/api/v1/consolidated/cities/{ibge_code}")

    async def get_consolidated_city_summary_async(self, ibge_code: str) -> ConsolidatedCity:
        """Busca resumo consolidado de uma cidade (assincrono)."""
        return await self._request_async(
            "GET", f"/api/v1/consolidated/cities/{ibge_code}/summary"
        )

    # =========================================================================
    # Export Methods - Async
    # =========================================================================

    async def export_to_csv_async(self, path: str, **params: Any) -> str:
        """Exporta dados em formato CSV (assincrono)."""
        return await self._request_async("GET", path, params=params, format_="csv")

    async def export_to_excel_async(self, path: str, **params: Any) -> bytes:
        """Exporta dados em formato Excel (assincrono)."""
        return await self._request_async("GET", path, params=params, format_="xlsx")
