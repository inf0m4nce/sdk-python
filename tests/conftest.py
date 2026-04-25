"""
Pytest fixtures para os testes do SDK Infomance.
"""

import pytest

from infomance import InfomanceClient


@pytest.fixture
def api_key() -> str:
    """API key para testes."""
    return "test_api_key_123"


@pytest.fixture
def base_url() -> str:
    """URL base para testes."""
    return "https://api.infomance.com.br"


@pytest.fixture
def client(api_key: str, base_url: str) -> InfomanceClient:
    """Cliente configurado para testes."""
    return InfomanceClient(api_key, base_url=base_url)


@pytest.fixture
def sample_municipality_response() -> dict:
    """Resposta de exemplo de municipio."""
    return {
        "ibge_code": "3550308",
        "name": "Sao Paulo",
        "state": "SP",
        "region": "Sudeste",
        "population": 12325232,
        "pib": 699288090000.0,
        "pib_per_capita": 56700.0,
        "area_km2": 1521.11,
        "economic": {
            "pib": 699288090000.0,
            "pib_per_capita": 56700.0,
            "agriculture": 0.01,
            "industry": 11.3,
            "services": 73.8,
            "taxes": 14.9,
            "year": 2021,
        },
        "infrastructure": {
            "water_coverage": 99.1,
            "sewage_collection": 92.3,
            "sewage_treatment": 78.5,
            "water_loss": 33.2,
            "internet_accesses": 5234567,
            "fiber_coverage": 85.0,
            "year": 2022,
        },
    }


@pytest.fixture
def sample_list_response() -> dict:
    """Resposta de exemplo de lista paginada."""
    return {
        "items": [
            {
                "ibge_code": "3550308",
                "name": "Sao Paulo",
                "state": "SP",
                "population": 12325232,
            },
            {
                "ibge_code": "3304557",
                "name": "Rio de Janeiro",
                "state": "RJ",
                "population": 6747815,
            },
        ],
        "total": 5570,
        "limit": 10,
        "offset": 0,
    }


@pytest.fixture
def sample_ranking_response() -> list:
    """Resposta de exemplo de ranking."""
    return [
        {
            "position": 1,
            "ibge_code": "3550308",
            "name": "Sao Paulo",
            "state": "SP",
            "value": 699288090000.0,
        },
        {
            "position": 2,
            "ibge_code": "3304557",
            "name": "Rio de Janeiro",
            "state": "RJ",
            "value": 364052740000.0,
        },
    ]


@pytest.fixture
def sample_health_stats() -> dict:
    """Resposta de exemplo de estatisticas de saude."""
    return {
        "total_establishments": 15234,
        "total_beds": 45678,
        "by_type": [
            {"type": "Hospital Geral", "count": 234},
            {"type": "UBS", "count": 4567},
        ],
        "by_management": [
            {"management": "Municipal", "count": 8765},
            {"management": "Estadual", "count": 2345},
        ],
    }
