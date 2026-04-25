"""Exemplo basico de uso do SDK Infomance."""

from infomance import InfomanceClient

# Criar cliente com sua API key
client = InfomanceClient("your-api-key")

# Listar municipios
municipios = client.list_municipalities(state="SP", limit=10)
print(f"Total: {municipios['total']}")
for m in municipios["items"]:
    print(f"- {m['name']} ({m['ibge_code']})")

# Buscar municipio especifico
sp = client.get_municipality("3550308")
print(f"\nSao Paulo - PIB: R$ {sp['pib']:,.2f}")

# Buscar dados economicos
economico = client.get_municipality_economic("3550308")
print(f"Servicos: {economico['services']}%")

# Buscar dados de infraestrutura
infra = client.get_municipality_infrastructure("3550308")
print(f"Cobertura de agua: {infra['water_coverage']}%")

# Fechar conexoes ao terminar
client.close()
