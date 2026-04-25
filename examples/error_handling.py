"""Exemplo de tratamento de erros."""

from infomance import InfomanceClient
from infomance.exceptions import (
    AuthenticationError,
    ForbiddenError,
    InfomanceError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)

client = InfomanceClient("your-api-key")


def buscar_municipio_seguro(ibge_code: str) -> dict | None:
    """Busca um municipio com tratamento completo de erros."""
    try:
        return client.get_municipality(ibge_code)

    except NotFoundError:
        print(f"Municipio {ibge_code} nao encontrado")
        return None

    except AuthenticationError:
        print("API key invalida. Verifique suas credenciais.")
        return None

    except ForbiddenError as e:
        print(f"Acesso negado: {e.message}")
        if e.required_plan:
            print(f"Plano necessario: {e.required_plan}")
        return None

    except ValidationError as e:
        print(f"Parametros invalidos: {e.message}")
        for error in e.errors:
            print(f"  - {error.get('field')}: {error.get('message')}")
        return None

    except RateLimitError as e:
        print(f"Rate limit atingido. Tente em {e.retry_after}s")
        print(f"Limite: {e.limit}, Restante: {e.remaining}")
        return None

    except TimeoutError as e:
        print(f"Timeout na requisicao ({e.timeout_seconds}s)")
        return None

    except NetworkError as e:
        print(f"Erro de conexao: {e.message}")
        return None

    except ServerError as e:
        print(f"Erro do servidor (HTTP {e.status_code})")
        if e.request_id:
            print(f"Request ID para suporte: {e.request_id}")
        return None

    except InfomanceError as e:
        # Captura qualquer outro erro da API
        print(f"Erro inesperado: {e.message}")
        return None


# Testar com diferentes cenarios
print("Buscando Sao Paulo...")
sp = buscar_municipio_seguro("3550308")
if sp:
    print(f"Encontrado: {sp['name']}")

print("\nBuscando codigo invalido...")
invalido = buscar_municipio_seguro("0000000")

# Usando propriedade is_retryable para decidir se vale tentar novamente
try:
    data = client.get_municipality("3550308")
except InfomanceError as e:
    if e.is_retryable:
        print(f"Erro temporario, pode tentar novamente: {e.message}")
    else:
        print(f"Erro permanente, nao adianta tentar novamente: {e.message}")

client.close()
