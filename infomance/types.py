"""
Modelos de dados do SDK Infomance.

Utiliza TypedDict para tipagem estatica sem dependencia de runtime.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

# ============================================================================
# Common Types
# ============================================================================


class Pagination(TypedDict, total=False):
    """Parametros de paginacao."""

    limit: int
    offset: int


class StateFilter(TypedDict, total=False):
    """Filtro por estado."""

    state: str


class YearFilter(TypedDict, total=False):
    """Filtro por ano."""

    year: int


class RankingParams(Pagination, StateFilter, YearFilter, total=False):
    """Parametros para ranking."""

    order: Literal["asc", "desc"]


# ============================================================================
# Municipality Types
# ============================================================================


class Municipality(TypedDict):
    """Dados basicos de municipio."""

    ibge_code: str
    name: str
    state: str


class MunicipalityWithRegion(Municipality, total=False):
    """Municipio com regiao."""

    region: str


class MunicipalityIndicators(MunicipalityWithRegion, total=False):
    """Municipio com indicadores."""

    population: int
    pib: float
    pib_per_capita: float
    area_km2: float


class EconomicData(TypedDict, total=False):
    """Dados economicos."""

    pib: float
    pib_per_capita: float
    agriculture: float
    industry: float
    services: float
    taxes: float
    year: int


class InfrastructureData(TypedDict, total=False):
    """Dados de infraestrutura."""

    water_coverage: float
    sewage_collection: float
    sewage_treatment: float
    water_loss: float
    internet_accesses: int
    fiber_coverage: float
    year: int


class IndicatorsMunicipality(MunicipalityIndicators, total=False):
    """Municipio com todos os indicadores."""

    economic: EconomicData
    infrastructure: InfrastructureData


# ============================================================================
# COMEX Types
# ============================================================================


class ComexProduct(TypedDict):
    """Produto de comercio exterior."""

    code_sh4: str
    value_usd: float
    volume_kg: float
    countries: int
    year: int


class ComexOverview(TypedDict):
    """Visao geral do COMEX."""

    total_value_usd: float
    total_volume_kg: float
    total_products: int
    total_countries: int
    top_products: list[ComexProduct]
    years: list[int]


class ComexMunicipality(TypedDict):
    """COMEX por municipio."""

    ibge_code: str
    name: str
    state: str
    total_value_usd: float
    total_volume_kg: float
    products: list[ComexProduct]


class ComexCountry(TypedDict):
    """Pais de destino COMEX."""

    country: str
    value_usd: float


class ComexCountriesResponse(TypedDict):
    """Resposta de paises COMEX."""

    countries: list[ComexCountry]


class ComexProductsResponse(TypedDict):
    """Resposta de produtos COMEX."""

    products: list[ComexProduct]


# ============================================================================
# SICOR Types
# ============================================================================


class SicorByCategory(TypedDict):
    """SICOR por categoria."""

    category: str
    contracts: int
    value_brl: float
    area_ha: float


class SicorOverview(TypedDict):
    """Visao geral do SICOR."""

    total_contracts: int
    total_value_brl: float
    total_area_ha: float
    by_finalidade: list[SicorByCategory]
    by_atividade: list[SicorByCategory]
    years: list[int]


class SicorState(TypedDict):
    """SICOR por estado."""

    uf: str
    contracts: int
    value_brl: float
    area_ha: float
    year: int


# ============================================================================
# Health Types
# ============================================================================


class HealthEstablishment(TypedDict, total=False):
    """Estabelecimento de saude."""

    cnes_code: str
    name: str
    establishment_type: str
    management_type: str
    ibge_code: str
    state: str
    neighborhood: str
    latitude: float
    longitude: float
    total_beds: int
    has_emergency: bool
    is_active: bool


class HealthTypeCount(TypedDict):
    """Contagem por tipo de estabelecimento."""

    type: str
    count: int


class HealthManagementCount(TypedDict):
    """Contagem por tipo de gestao."""

    management: str
    count: int


class HealthStats(TypedDict):
    """Estatisticas de saude."""

    total_establishments: int
    total_beds: int
    by_type: list[HealthTypeCount]
    by_management: list[HealthManagementCount]


# ============================================================================
# Education Types
# ============================================================================


class School(TypedDict, total=False):
    """Escola."""

    inep_code: str
    name: str
    network: str
    ibge_code: str
    state: str
    neighborhood: str
    latitude: float
    longitude: float
    has_internet: bool
    has_library: bool


class IDEBScore(TypedDict, total=False):
    """Nota IDEB."""

    ibge_code: str
    name: str
    ideb_inicial: float
    ideb_final: float
    year: int


class NetworkCount(TypedDict):
    """Contagem por rede de ensino."""

    network: str
    count: int


class EducationOverview(TypedDict):
    """Visao geral da educacao."""

    total_schools: int
    by_network: list[NetworkCount]


class MunicipalityEducation(TypedDict, total=False):
    """Educacao por municipio."""

    schools: int
    ideb: IDEBScore


# ============================================================================
# Security Types
# ============================================================================


class CrimeStats(TypedDict, total=False):
    """Estatisticas de crime."""

    city: str
    state: str
    crime_type: str
    count: int
    rate_per_100k: float
    year: int
    month: int


class CrimeTypeCount(TypedDict):
    """Contagem por tipo de crime."""

    type: str
    count: int


class CityRate(TypedDict):
    """Taxa por cidade."""

    city: str
    rate: float


class CrimeOverview(TypedDict):
    """Visao geral de seguranca."""

    total_crimes: int
    by_type: list[CrimeTypeCount]
    most_dangerous: list[CityRate]
    safest: list[CityRate]


class CrimeTypesResponse(TypedDict):
    """Resposta de tipos de crime."""

    types: list[str]


# ============================================================================
# Employment Types
# ============================================================================


class EmploymentData(TypedDict, total=False):
    """Dados de emprego."""

    ibge_code: str
    name: str
    admissions: int
    dismissals: int
    balance: int
    formal_jobs: int
    average_salary: float
    year: int
    month: int


class EmploymentOverview(TypedDict):
    """Visao geral de emprego."""

    total_jobs: int
    total_admissions: int
    total_dismissals: int


# ============================================================================
# AGRO Types
# ============================================================================


class AgroMunicipality(TypedDict):
    """Dados agro por municipio."""

    ibge_code: str
    name: str
    state: str
    total_estabelecimentos: int
    area_total_ha: float
    efetivo_bovino: int
    valor_producao_mil_brl: float


class AgroTimeseries(TypedDict, total=False):
    """Serie temporal agro."""

    year: int
    product: str
    quantity: float
    value_brl: float
    area_ha: float


class LandUseData(TypedDict):
    """Dados de uso do solo."""

    year: int
    class_: str  # 'class' is reserved word
    area_ha: float
    percentage: float


class EmissionsData(TypedDict, total=False):
    """Dados de emissoes."""

    year: int
    sector: str
    co2_tons: float
    ch4_tons: float
    n2o_tons: float


class AgroStats(TypedDict):
    """Estatisticas agro."""

    total_municipalities: int
    total_area_ha: float


# ============================================================================
# POI Types
# ============================================================================


class POI(TypedDict, total=False):
    """Ponto de interesse."""

    id: str
    name: str
    category: str
    subcategory: str
    city: str
    latitude: float
    longitude: float
    address: str
    brand: str
    opening_hours: str


class POISearchParams(Pagination, total=False):
    """Parametros de busca POI."""

    city: str
    category: str
    lat: float
    lng: float
    radius: float
    q: str


class CategoryCount(TypedDict):
    """Contagem por categoria."""

    category: str
    count: int


class CityPOIStats(TypedDict):
    """Estatisticas de POI por cidade."""

    total: int
    by_category: list[CategoryCount]


class POICategoriesResponse(TypedDict):
    """Resposta de categorias de POI."""

    categories: list[str]


# ============================================================================
# Consolidated Types
# ============================================================================


class ConsolidatedHealth(TypedDict, total=False):
    """Saude consolidada."""

    total_establishments: int
    total_beds: int


class ConsolidatedEducation(TypedDict, total=False):
    """Educacao consolidada."""

    schools: int
    ideb_inicial: float
    ideb_final: float


class ConsolidatedSecurity(TypedDict, total=False):
    """Seguranca consolidada."""

    total_crimes: int
    rate_per_100k: float


class ConsolidatedEmployment(TypedDict, total=False):
    """Emprego consolidado."""

    formal_jobs: int
    average_salary: float


class ConsolidatedCity(TypedDict, total=False):
    """Cidade consolidada."""

    municipality: Municipality
    indicators: IndicatorsMunicipality
    health: HealthStats
    education: ConsolidatedEducation
    security: ConsolidatedSecurity
    employment: ConsolidatedEmployment
    agro: AgroMunicipality


# ============================================================================
# Ranking Types
# ============================================================================


class RankingEntry(TypedDict):
    """Entrada de ranking."""

    position: int
    ibge_code: str
    name: str
    state: str
    value: float


# ============================================================================
# API Response Types
# ============================================================================


class ListResponse(TypedDict, total=False):
    """Resposta de lista paginada."""

    items: list[Any]
    total: int
    limit: int
    offset: int


class RateLimitInfo(TypedDict, total=False):
    """Informacoes de rate limit."""

    limit: int
    remaining: int
    reset: int
    reset_at: datetime


# ============================================================================
# Export Format
# ============================================================================

ExportFormat = Literal["json", "csv", "xlsx"]
