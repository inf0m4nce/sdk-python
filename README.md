# Infomance Python SDK

SDK oficial para integracao com a [Infomance API](https://api.infomance.com.br).

Acesse dados de indicadores municipais brasileiros: economia, infraestrutura, saude, educacao, seguranca, emprego, agro e muito mais.

## Instalacao

```bash
pip install infomance
```

## Uso Basico

### Uso Sincrono

```python
from infomance import InfomanceClient

# Inicializar cliente
client = InfomanceClient("sua_api_key")

# Listar municipios
municipios = client.list_municipalities(limit=10, state="SP")
print(municipios)

# Buscar dados de um municipio especifico
sao_paulo = client.get_municipality("3550308")
print(f"PIB: R$ {sao_paulo['economic']['pib']:,.2f}")

# Buscar dados economicos
economicos = client.get_municipality_economic("3550308")
print(f"PIB per capita: R$ {economicos['pib_per_capita']:,.2f}")

# Buscar dados de infraestrutura
infra = client.get_municipality_infrastructure("3550308")
print(f"Cobertura de agua: {infra['water_coverage']}%")

# Fechar conexao
client.close()
```

### Com Context Manager

```python
from infomance import InfomanceClient

with InfomanceClient("sua_api_key") as client:
    municipios = client.list_municipalities(limit=10)
    for m in municipios["items"]:
        print(f"{m['name']} - {m['state']}")
```

### Uso Assincrono

```python
import asyncio
from infomance import InfomanceClient

async def main():
    async with InfomanceClient("sua_api_key") as client:
        # Buscar dados em paralelo
        sao_paulo = await client.get_municipality_async("3550308")
        campinas = await client.get_municipality_async("3509502")

        print(f"Sao Paulo PIB: R$ {sao_paulo['economic']['pib']:,.2f}")
        print(f"Campinas PIB: R$ {campinas['economic']['pib']:,.2f}")

asyncio.run(main())
```

## APIs Disponiveis

### Indicadores Municipais

```python
# Listar municipios
municipios = client.list_municipalities(limit=100, offset=0, state="SP")

# Buscar municipio por codigo IBGE
municipio = client.get_municipality("3550308")

# Dados economicos
economicos = client.get_municipality_economic("3550308")

# Dados de infraestrutura
infra = client.get_municipality_infrastructure("3550308")

# Ranking por indicador
ranking = client.get_indicators_ranking("pib", limit=10, order="desc")
```

### Comercio Exterior (COMEX)

```python
# Visao geral
overview = client.get_comex_overview()

# Dados de um municipio
comex = client.get_comex_municipality("3550308")

# Serie temporal
timeseries = client.get_comex_municipality_timeseries("3550308", year=2023)

# Produtos
produtos = client.get_comex_products(limit=20)

# Paises de destino
paises = client.get_comex_countries(year=2023)
```

### Credito Rural (SICOR)

```python
# Visao geral
overview = client.get_sicor_overview()

# Por estado
sicor_sp = client.get_sicor_state("SP")

# Por categoria
por_finalidade = client.get_sicor_by_finalidade()
por_atividade = client.get_sicor_by_atividade()
por_programa = client.get_sicor_by_programa()
```

### Saude

```python
# Listar estabelecimentos
estabelecimentos = client.list_health_establishments(state="SP", limit=50)

# Buscar por codigo CNES
estabelecimento = client.get_health_establishment("2077485")

# Estatisticas de um municipio
stats = client.get_municipality_health_stats("3550308")

# Busca por nome
resultados = client.search_health_establishments("Hospital das Clinicas")
```

### Educacao

```python
# Listar escolas
escolas = client.list_schools(state="SP", network="federal")

# Visao geral
overview = client.get_education_overview()

# Ranking IDEB
ideb = client.get_ideb_ranking(limit=10, year=2021)

# Dados de um municipio
educacao = client.get_municipality_education("3550308")
```

### Seguranca

```python
# Estatisticas de crimes
crimes = client.list_crime_stats(state="SP", year=2023)

# Visao geral
overview = client.get_security_overview()

# Tipos de crimes disponiveis
tipos = client.get_crime_types()

# Ranking
ranking = client.get_crime_ranking(crime_type="homicidio", limit=10)

# Crimes de uma cidade
crimes_sp = client.get_municipality_crime_stats("3550308")
```

### Emprego

```python
# Listar municipios
emprego = client.list_employment_municipalities(state="SP")

# Dados de um municipio
emp_sp = client.get_municipality_employment("3550308")

# Serie temporal
timeseries = client.get_employment_timeseries("3550308")

# Visao geral
overview = client.get_employment_overview()
```

### Agropecuaria (AGRO)

```python
# Listar municipios
agro = client.list_agro_municipalities(state="MT")

# Dados de um municipio
agro_mun = client.get_agro_municipality("5103403")

# Serie temporal de producao
timeseries = client.get_agro_timeseries("5103403")

# Uso do solo
land_use = client.get_agro_land_use("5103403")

# Emissoes de GEE
emissoes = client.get_agro_emissions("5103403")

# Estatisticas gerais
stats = client.get_agro_stats()
```

### Pontos de Interesse (POI)

```python
# Buscar POIs
pois = client.search_pois(city="Sao Paulo", category="hospital", limit=20)

# POIs proximos a uma localizacao
nearby = client.search_nearby_pois(lat=-23.5505, lng=-46.6333, radius=1000)

# Categorias disponiveis
categorias = client.get_poi_categories()

# Estatisticas de uma cidade
stats = client.get_city_poi_stats("Sao Paulo")
```

### Dados Consolidados

```python
# Todos os dados de uma cidade
consolidado = client.get_consolidated_city("3550308")

# Resumo
resumo = client.get_consolidated_city_summary("3550308")
```

### Exportacao

```python
# Exportar para CSV
csv_data = client.export_to_csv("/api/v1/indicators/municipalities", state="SP")
with open("municipios.csv", "w") as f:
    f.write(csv_data)

# Exportar para Excel
excel_data = client.export_to_excel("/api/v1/indicators/municipalities", state="SP")
with open("municipios.xlsx", "wb") as f:
    f.write(excel_data)
```

## Tratamento de Erros

```python
from infomance import (
    InfomanceClient,
    InfomanceError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

client = InfomanceClient("sua_api_key")

try:
    municipio = client.get_municipality("0000000")
except AuthenticationError:
    print("API Key invalida")
except NotFoundError:
    print("Municipio nao encontrado")
except RateLimitError as e:
    print(f"Rate limit excedido. Tente novamente em {e.retry_after} segundos")
except ValidationError as e:
    print(f"Parametros invalidos: {e.errors}")
except InfomanceError as e:
    print(f"Erro na API: {e.message} [HTTP {e.status_code}]")
```

## Rate Limiting

O SDK rastreia automaticamente os limites de requisicao:

```python
client = InfomanceClient("sua_api_key")

# Fazer uma requisicao
municipios = client.list_municipalities()

# Verificar rate limit
if client.rate_limit:
    print(f"Limite: {client.rate_limit['limit']}")
    print(f"Restantes: {client.rate_limit['remaining']}")
    print(f"Reset em: {client.rate_limit['reset']}")

# ID da ultima requisicao (util para suporte)
print(f"Request ID: {client.last_request_id}")
```

## Configuracao

```python
from infomance import InfomanceClient

# URL customizada (para staging/dev)
client = InfomanceClient(
    api_key="sua_api_key",
    base_url="https://staging-api.infomance.com.br",
    timeout=60.0,  # timeout em segundos
)
```

## Debugging

O SDK inclui logging integrado para ajudar na depuracao. Ative o modo debug para ver detalhes das requisicoes:

### Ativando Debug no Cliente

```python
from infomance import InfomanceClient

# Modo simples - ativa logging automaticamente
client = InfomanceClient("sua_api_key", debug=True)

# Logs serao exibidos automaticamente:
# 2026-04-25 10:30:00 - infomance - DEBUG - Request started: GET https://api.infomance.com.br/api/v1/indicators/municipalities
# 2026-04-25 10:30:01 - infomance - DEBUG - Request completed: GET https://api.infomance.com.br/api/v1/indicators/municipalities - status=200, elapsed=150.25ms
```

### Configuracao Manual de Logging

Para controle mais fino do logging, configure o logger diretamente:

```python
import logging
from infomance import InfomanceClient, logger

# Configurar nivel e formato
logging.basicConfig(level=logging.DEBUG)

# Ou configurar apenas o logger do SDK
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
))
logger.addHandler(handler)

# Usar o cliente normalmente
client = InfomanceClient("sua_api_key")
```

### Niveis de Log

O SDK usa os seguintes niveis de log:

| Nivel | Descricao |
|-------|-----------|
| DEBUG | Request iniciado (metodo, URL) e completado (status, tempo) |
| WARNING | Retry acontecendo (tentativa, delay, motivo) |
| ERROR | Erros de timeout, rede ou HTTP 4xx/5xx |

### Exemplo de Saida

```
2026-04-25 10:30:00 - infomance - DEBUG - Request started: GET https://api.infomance.com.br/api/v1/indicators/municipalities/3550308
2026-04-25 10:30:01 - infomance - DEBUG - Request completed: GET https://api.infomance.com.br/api/v1/indicators/municipalities/3550308 - status=200, elapsed=150.25ms
```

Em caso de retry:

```
2026-04-25 10:30:00 - infomance - DEBUG - Request started: GET https://api.infomance.com.br/api/v1/indicators/municipalities
2026-04-25 10:30:01 - infomance - ERROR - Request error: GET https://api.infomance.com.br/api/v1/indicators/municipalities - status=503, detail=Service Unavailable
2026-04-25 10:30:01 - infomance - WARNING - Retry attempt 1: ServerError - waiting 1.05s before next attempt
2026-04-25 10:30:02 - infomance - DEBUG - Request started: GET https://api.infomance.com.br/api/v1/indicators/municipalities
2026-04-25 10:30:03 - infomance - DEBUG - Request completed: GET https://api.infomance.com.br/api/v1/indicators/municipalities - status=200, elapsed=145.30ms
```

## Seguranca / Security

### Verificacao SSL / SSL Verification

Por padrao, o SDK verifica certificados SSL em todas as conexoes. **Nunca desabilite a verificacao SSL em producao.**

By default, the SDK verifies SSL certificates on all connections. **Never disable SSL verification in production.**

```python
# CORRETO - Producao (padrao) / CORRECT - Production (default)
client = InfomanceClient("your_api_key")

# APENAS para desenvolvimento local com certificados auto-assinados
# ONLY for local development with self-signed certificates
# NUNCA use em producao! / NEVER use in production!
from infomance import InfomanceClient, ClientConfig

config = ClientConfig(verify_ssl=False)  # DEVELOPMENT ONLY
client = InfomanceClient("your_api_key", config=config)
```

> **Aviso / Warning**: Desabilitar a verificacao SSL expoe sua aplicacao a ataques man-in-the-middle. Use apenas em ambientes de desenvolvimento controlados. / Disabling SSL verification exposes your application to man-in-the-middle attacks. Use only in controlled development environments.

### Armazenamento de Credenciais / Credential Storage

Nunca hardcode sua API key no codigo. Use variaveis de ambiente:

Never hardcode your API key in source code. Use environment variables:

```python
import os
from infomance import InfomanceClient

api_key = os.environ.get("INFOMANCE_API_KEY")
if not api_key:
    raise ValueError("INFOMANCE_API_KEY not set")

client = InfomanceClient(api_key)
```

### Logging Seguro / Secure Logging

O SDK **nunca** loga sua API key. Os logs incluem apenas:

The SDK **never** logs your API key. Logs only include:

- Metodo HTTP e URL / HTTP method and URL
- Status code e tempo de resposta / Status code and response time
- Mensagens de erro (sem credenciais) / Error messages (without credentials)

## Requisitos

- Python 3.9+
- httpx >= 0.25.0

## Licenca

Proprietario. Veja [infomance.com.br](https://infomance.com.br) para mais detalhes.

## Suporte

- Email: contato@infomance.com.br
- Documentacao: https://api.infomance.com.br/docs
