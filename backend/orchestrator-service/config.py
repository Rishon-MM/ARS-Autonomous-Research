"""
config.py — Centralized configuration for the orchestrator service.

All environment variables, model names, and tuning parameters in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    # Gemini
    gemini_api_key: str = ""
    gemini_fast: str = "gemini-2.5-flash"
    gemini_strong: str = "gemini-2.5-flash"

    # OpenAI
    openai_api_key: str = ""
    openai_fast: str = "gpt-4o-mini"
    openai_strong: str = "gpt-4o"

    # Local LLaMA
    local_llama_url: str = "http://host.docker.internal:8080/v1"
    local_llama_model: str = "local-model"


@dataclass
class DatabaseConfig:
    """PostgreSQL connection configuration."""

    url: str = "postgresql://ars_user:ars_password@postgres:5432/ars_memory"


@dataclass
class SearchConfig:
    """Knowledge acquisition settings."""

    max_search_queries: int = 3
    max_papers_per_query: int = 15
    final_select_count: int = 5
    min_relevant_papers: int = 10
    max_agent_steps: int = 80
    pdf_storage_dir: str = "/app/pdfs"
    max_pdf_size_mb: int = 50
    chunk_size: int = 500
    chunk_overlap: int = 100


@dataclass
class GraphConfig:
    """Execution engine settings."""

    max_parallel_workers: int = 3
    default_timeout_seconds: int = 120
    max_retries: int = 3
    retry_backoff: str = "exponential"  # exponential | linear | fixed
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    checkpoint_after_every_node: bool = True


@dataclass
class ObservabilityConfig:
    """Tracing and logging settings."""

    otel_endpoint: str = "http://jaeger:4317"
    otel_service_name: str = "ars-orchestrator"
    log_level: str = "INFO"
    log_format: str = "json"  # json | console


@dataclass
class EmbeddingConfig:
    """Embedding model settings."""

    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384


@dataclass
class Settings:
    """Root configuration — constructed from environment variables."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    # Service identity
    service_name: str = "ars-orchestrator"
    host: str = "0.0.0.0"
    port: int = 8001


def load_settings() -> Settings:
    """Build settings from environment variables with sensible defaults."""
    return Settings(
        llm=LLMConfig(
            gemini_api_key=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")),
            gemini_fast=os.getenv("GEMINI_FAST_MODEL", "gemini-2.5-flash"),
            gemini_strong=os.getenv("GEMINI_STRONG_MODEL", "gemini-2.5-flash"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_fast=os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
            openai_strong=os.getenv("OPENAI_STRONG_MODEL", "gpt-4o"),
            local_llama_url=os.getenv("LOCAL_LLAMA_URL", "http://host.docker.internal:8080/v1"),
            local_llama_model=os.getenv("LOCAL_LLAMA_MODEL", "local-model"),
        ),
        database=DatabaseConfig(
            url=os.getenv(
                "DATABASE_URL",
                "postgresql://ars_user:ars_password@postgres:5432/ars_memory",
            ),
        ),
        search=SearchConfig(
            pdf_storage_dir=os.getenv("PDF_STORAGE_DIR", "/app/pdfs"),
        ),
        graph=GraphConfig(
            max_parallel_workers=int(os.getenv("MAX_PARALLEL_WORKERS", "3")),
            default_timeout_seconds=int(os.getenv("WORKER_TIMEOUT", "120")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
        ),
        observability=ObservabilityConfig(
            otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json"),
        ),
    )
