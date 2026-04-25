"""
Infomance Python SDK
~~~~~~~~~~~~~~~~~~~~

SDK oficial para integracao com a Infomance API.
Dados de indicadores municipais, saude, educacao, seguranca, emprego e agro.

Uso basico (sincrono):

    from infomance import InfomanceClient

    client = InfomanceClient("sua_api_key")
    municipios = client.list_municipalities()
    print(municipios)

Com context manager:

    from infomance import InfomanceClient

    with InfomanceClient("sua_api_key") as client:
        municipio = client.get_municipality("3550308")
        print(municipio)

Uso assincrono:

    import asyncio
    from infomance import InfomanceClient

    async def main():
        async with InfomanceClient("sua_api_key") as client:
            municipios = await client.list_municipalities_async()
            print(municipios)

    asyncio.run(main())

:copyright: (c) 2024-2026 Infomance
:license: Proprietary
"""

from .client import ClientConfig, InfomanceClient, logger
from .exceptions import (
    AuthenticationError,
    ForbiddenError,
    InfomanceError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
    raise_for_status,
)
from .retry import RetryConfig, RetryHandler
from .types import (
    POI,
    AgroMunicipality,
    AgroStats,
    AgroTimeseries,
    CategoryCount,
    CityPOIStats,
    CityRate,
    ComexCountriesResponse,
    ComexCountry,
    ComexMunicipality,
    ComexOverview,
    ComexProduct,
    ComexProductsResponse,
    ConsolidatedCity,
    ConsolidatedEducation,
    ConsolidatedEmployment,
    ConsolidatedHealth,
    ConsolidatedSecurity,
    CrimeOverview,
    CrimeStats,
    CrimeTypeCount,
    CrimeTypesResponse,
    EconomicData,
    EducationOverview,
    EmissionsData,
    EmploymentData,
    EmploymentOverview,
    ExportFormat,
    HealthEstablishment,
    HealthManagementCount,
    HealthStats,
    HealthTypeCount,
    IDEBScore,
    IndicatorsMunicipality,
    InfrastructureData,
    LandUseData,
    ListResponse,
    Municipality,
    MunicipalityEducation,
    MunicipalityIndicators,
    MunicipalityWithRegion,
    NetworkCount,
    Pagination,
    POICategoriesResponse,
    POISearchParams,
    RankingEntry,
    RankingParams,
    RateLimitInfo,
    School,
    SicorByCategory,
    SicorOverview,
    SicorState,
    StateFilter,
    YearFilter,
)

__version__ = "1.0.0"
__all__ = [
    # Client
    "InfomanceClient",
    "ClientConfig",
    "logger",
    # Retry
    "RetryConfig",
    "RetryHandler",
    # Exceptions
    "InfomanceError",
    "AuthenticationError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "ServerError",
    "TimeoutError",
    "NetworkError",
    "raise_for_status",
    # Common Types
    "Pagination",
    "StateFilter",
    "YearFilter",
    "RankingParams",
    "ListResponse",
    "RateLimitInfo",
    "ExportFormat",
    # Municipality Types
    "Municipality",
    "MunicipalityWithRegion",
    "MunicipalityIndicators",
    "IndicatorsMunicipality",
    "EconomicData",
    "InfrastructureData",
    # COMEX Types
    "ComexProduct",
    "ComexOverview",
    "ComexMunicipality",
    "ComexCountry",
    "ComexCountriesResponse",
    "ComexProductsResponse",
    # SICOR Types
    "SicorByCategory",
    "SicorOverview",
    "SicorState",
    # Health Types
    "HealthEstablishment",
    "HealthStats",
    "HealthTypeCount",
    "HealthManagementCount",
    # Education Types
    "School",
    "IDEBScore",
    "NetworkCount",
    "EducationOverview",
    "MunicipalityEducation",
    # Security Types
    "CrimeStats",
    "CrimeOverview",
    "CrimeTypeCount",
    "CityRate",
    "CrimeTypesResponse",
    # Employment Types
    "EmploymentData",
    "EmploymentOverview",
    # AGRO Types
    "AgroMunicipality",
    "AgroTimeseries",
    "LandUseData",
    "EmissionsData",
    "AgroStats",
    # POI Types
    "POI",
    "POISearchParams",
    "CategoryCount",
    "CityPOIStats",
    "POICategoriesResponse",
    # Consolidated Types
    "ConsolidatedCity",
    "ConsolidatedHealth",
    "ConsolidatedEducation",
    "ConsolidatedSecurity",
    "ConsolidatedEmployment",
    # Ranking Types
    "RankingEntry",
]
