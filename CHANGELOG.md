# Changelog

All notable changes to the Infomance Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-24

### Added

- Initial release
- Full support for all Infomance API endpoints:
  - Indicators (municipalities, economic, infrastructure, ranking)
  - COMEX (comercio exterior agropecuario)
  - SICOR (credito rural)
  - Health (estabelecimentos de saude)
  - Education (escolas, IDEB)
  - Security (estatisticas de crimes)
  - Employment (emprego formal, CAGED)
  - Agro (producao agropecuaria, uso do solo, emissoes)
  - POIs (pontos de interesse)
  - Consolidated (dados consolidados por cidade)
- Retry automatico com backoff exponencial:
  - Configuravel via `RetryConfig`
  - Retry em 429, 5xx, timeout e erros de conexao
  - Respeita header `Retry-After`
  - Jitter aleatorio para evitar thundering herd
- Rate limit tracking:
  - `client.rate_limit` retorna limite, remaining e reset
  - `reset_at` como datetime (UTC) para facil manipulacao
- Suporte sincrono e assincrono:
  - Metodos sync: `client.get_municipality("3550308")`
  - Metodos async: `await client.get_municipality_async("3550308")`
- Export para CSV e Excel
- Context manager para gerenciamento de conexoes
- Tipagem completa com TypedDict
- User-Agent padronizado
- Tratamento de erros granular:
  - `AuthenticationError` (401)
  - `ForbiddenError` (403)
  - `NotFoundError` (404)
  - `RateLimitError` (429)
  - `ValidationError` (400, 422)
  - `ServerError` (5xx)
  - `TimeoutError`
  - `NetworkError`

### Dependencies

- `httpx>=0.25.0` - HTTP client com suporte async
