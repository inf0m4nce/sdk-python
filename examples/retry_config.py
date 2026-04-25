"""Exemplo de configuracao de retry."""

from infomance import ClientConfig, InfomanceClient, RetryConfig

# Configuracao padrao de retry
# - max_retries: 3
# - backoff_factor: 1.0 (delays: 1s, 2s, 4s)
# - max_delay: 30s
# - jitter: True (variacao aleatoria no delay)
client_padrao = InfomanceClient("your-api-key")

# Configuracao customizada via RetryConfig direto
retry_agressivo = RetryConfig(
    max_retries=5,  # Mais tentativas
    backoff_factor=2.0,  # Delays maiores: 2s, 4s, 8s, 16s, 30s
    max_delay=60.0,  # Delay maximo de 1 minuto
    jitter=True,  # Variacao aleatoria para evitar thundering herd
)
client_agressivo = InfomanceClient("your-api-key", retry_config=retry_agressivo)

# Configuracao via ClientConfig (mais flexivel)
config = ClientConfig(
    base_url="https://api.infomance.com.br",
    timeout=60.0,  # Timeout de 1 minuto
    verify_ssl=True,
    debug=False,
    retry=RetryConfig(
        max_retries=3,
        backoff_factor=1.5,
        retry_statuses=(429, 500, 502, 503, 504),  # Codigos que ativam retry
        retry_on_timeout=True,  # Retry em timeouts
        retry_on_connection_error=True,  # Retry em erros de conexao
        max_delay=30.0,
        jitter=True,
    ),
)
client_config = InfomanceClient("your-api-key", config=config)

# Desabilitar retry completamente
sem_retry = RetryConfig(max_retries=0)
client_sem_retry = InfomanceClient("your-api-key", retry_config=sem_retry)

# Acessar configuracao de retry atual
print(f"Max retries: {client_config.retry_config.max_retries}")
print(f"Backoff factor: {client_config.retry_config.backoff_factor}")
print(f"Max delay: {client_config.retry_config.max_delay}s")

# Exemplo de uso com retry personalizado
print("\nFazendo requisicao com retry personalizado...")
try:
    result = client_agressivo.list_municipalities(state="SP", limit=5)
    print(f"Sucesso! {len(result['items'])} municipios encontrados")
except Exception as e:
    print(f"Erro apos todas tentativas: {e}")

# Limpar recursos
client_padrao.close()
client_agressivo.close()
client_config.close()
client_sem_retry.close()
