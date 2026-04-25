"""
Excepcoes do SDK Infomance.

Hierarquia de excecoes para tratamento granular de erros.
"""

from __future__ import annotations

from typing import Any, Optional


class InfomanceError(Exception):
    """
    Excecao base para erros da Infomance API.

    Attributes:
        message: Mensagem de erro
        status_code: Codigo HTTP da resposta
        response_body: Corpo da resposta de erro
        request_id: ID da requisicao para suporte
        retry_after: Segundos para retry (se aplicavel)
    """

    def __init__(
        self,
        message: str = "Erro na API Infomance",
        status_code: Optional[int] = None,
        response_body: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response_body = response_body or {}
        self.request_id = request_id
        self.retry_after = retry_after
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"[HTTP {self.status_code}]")
        if self.request_id:
            parts.append(f"[Request ID: {self.request_id}]")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"request_id={self.request_id!r})"
        )

    @property
    def is_retryable(self) -> bool:
        """Indica se o erro pode ser recuperavel via retry."""
        return self.status_code in (429, 500, 502, 503, 504)


class AuthenticationError(InfomanceError):
    """Erro de autenticacao (HTTP 401)."""

    def __init__(
        self,
        message: str = "API Key invalida ou nao fornecida",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, status_code=401, **kwargs)


class ForbiddenError(InfomanceError):
    """Erro de autorizacao (HTTP 403)."""

    def __init__(
        self,
        message: str = "Acesso negado. Verifique se seu plano permite este recurso.",
        required_plan: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.required_plan = required_plan
        if required_plan:
            message = f"{message} Plano necessario: {required_plan}"
        super().__init__(message=message, status_code=403, **kwargs)


class NotFoundError(InfomanceError):
    """Recurso nao encontrado (HTTP 404)."""

    def __init__(
        self,
        message: str = "Recurso nao encontrado",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, status_code=404, **kwargs)


class RateLimitError(InfomanceError):
    """Limite de requisicoes excedido (HTTP 429)."""

    def __init__(
        self,
        message: str = "Limite de requisicoes excedido",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        remaining: int = 0,
        **kwargs: Any,
    ) -> None:
        self.limit = limit
        self.remaining = remaining
        if retry_after:
            message = f"{message}. Tente novamente em {retry_after} segundos."
        super().__init__(message=message, status_code=429, retry_after=retry_after, **kwargs)

    @property
    def is_retryable(self) -> bool:
        return True


class ValidationError(InfomanceError):
    """Erro de validacao (HTTP 400/422)."""

    def __init__(
        self,
        message: str = "Parametros invalidos",
        errors: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        self.errors = errors or []
        if errors:
            error_details = "; ".join(
                f"{e.get('field', 'unknown')}: {e.get('message', e.get('msg', 'erro'))}"
                for e in errors
            )
            message = f"{message}: {error_details}"
        super().__init__(message=message, status_code=400, **kwargs)


class ServerError(InfomanceError):
    """Erro interno do servidor (HTTP 5xx)."""

    def __init__(
        self,
        message: str = "Erro interno do servidor",
        **kwargs: Any,
    ) -> None:
        status_code = kwargs.pop("status_code", 500)
        super().__init__(message=message, status_code=status_code, **kwargs)

    @property
    def is_retryable(self) -> bool:
        return True


class TimeoutError(InfomanceError):
    """Timeout na requisicao."""

    def __init__(
        self,
        message: str = "Timeout na requisicao",
        timeout_seconds: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            message = f"{message} (limite: {timeout_seconds}s)"
        super().__init__(message=message, **kwargs)

    @property
    def is_retryable(self) -> bool:
        return True


class NetworkError(InfomanceError):
    """Erro de rede/conexao."""

    def __init__(
        self,
        message: str = "Erro de conexao com a API",
        original_error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        self.original_error = original_error
        if original_error:
            message = f"{message}: {str(original_error)}"
        super().__init__(message=message, **kwargs)

    @property
    def is_retryable(self) -> bool:
        return True


# Mapeamento de status code para excecao
STATUS_CODE_EXCEPTIONS: dict[int, type[InfomanceError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
    500: ServerError,
    502: ServerError,
    503: ServerError,
    504: ServerError,
}


def raise_for_status(
    status_code: int,
    response_body: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
    retry_after: Optional[int] = None,
) -> None:
    """Levanta a excecao apropriada baseada no status code."""
    if 200 <= status_code < 300:
        return

    response_body = response_body or {}
    detail = response_body.get("detail", "") or response_body.get("error", "")

    # Handle detail being a dict
    if isinstance(detail, dict):
        message = (
            detail.get("error") or detail.get("detail") or detail.get("message") or str(detail)
        )
    else:
        message = str(detail) if detail else ""

    exception_class = STATUS_CODE_EXCEPTIONS.get(status_code, InfomanceError)

    kwargs: dict[str, Any] = {
        "response_body": response_body,
        "request_id": request_id,
    }

    if status_code == 429:
        kwargs["retry_after"] = retry_after

    if status_code in (400, 422) and "errors" in response_body:
        kwargs["errors"] = response_body["errors"]

    if message:
        kwargs["message"] = message

    raise exception_class(**kwargs)
