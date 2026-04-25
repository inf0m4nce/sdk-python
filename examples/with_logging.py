"""Exemplo com logging habilitado."""

import logging

from infomance import InfomanceClient, logger

# Configurar logging para ver todas as mensagens
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Criar cliente com debug mode
# Isso automaticamente configura o logger do SDK para DEBUG
client = InfomanceClient("your-api-key", debug=True)

# Todas as requests serao logadas com detalhes:
# - Inicio da requisicao (URL, metodo)
# - Conclusao (status, tempo de resposta)
# - Erros (codigo, mensagem)
# - Retries (tentativa, delay)
print("Buscando municipios (veja os logs abaixo)...")
result = client.list_municipalities(state="SP", limit=5)

print(f"\nResultado: {len(result['items'])} municipios encontrados")

# Voce tambem pode configurar o logger diretamente
logger.setLevel(logging.WARNING)  # Reduzir verbosidade

print("\nAgora com menos logs...")
result2 = client.list_municipalities(state="RJ", limit=5)

# Ou adicionar seu proprio handler
file_handler = logging.FileHandler("infomance_sdk.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

print("\nAgora tambem logando para arquivo...")
result3 = client.list_municipalities(state="MG", limit=5)

client.close()
