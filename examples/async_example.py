"""Exemplo de uso assincrono do SDK Infomance."""

import asyncio

from infomance import InfomanceClient


async def main():
    """Demonstra uso assincrono do SDK."""
    async with InfomanceClient("your-api-key") as client:
        # Buscar multiplos municipios em paralelo
        tasks = [
            client.get_municipality_async("3550308"),  # Sao Paulo
            client.get_municipality_async("3304557"),  # Rio de Janeiro
            client.get_municipality_async("3106200"),  # Belo Horizonte
        ]
        results = await asyncio.gather(*tasks)

        for city in results:
            print(f"{city['name']}: PIB R$ {city['pib']:,.2f}")

        # Buscar dados economicos e infraestrutura em paralelo
        sp_code = "3550308"
        economic, infra = await asyncio.gather(
            client.get_municipality_economic_async(sp_code),
            client.get_municipality_infrastructure_async(sp_code),
        )

        print(f"\nSao Paulo - Economia:")
        print(f"  Servicos: {economic['services']}%")
        print(f"  Industria: {economic['industry']}%")

        print(f"\nSao Paulo - Infraestrutura:")
        print(f"  Agua: {infra['water_coverage']}%")
        print(f"  Esgoto: {infra['sewage_collection']}%")


if __name__ == "__main__":
    asyncio.run(main())
