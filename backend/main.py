"""FastAPI application for the LegalDesk workstation."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import logging
import os
import shutil
from pathlib import Path
import threading
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, ValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from backend.adapters.consultant_plus import ConsultantPlusAdapter, HttpAdapter
from backend.adapters.local_llm import LLMConfig, LocalLLMAdapter
from backend.adapters.registry import AnalysisMode, registry
from backend.core.anonymizer import anonymizer
from backend.core.audit import audit_log
from backend.core.archive import archive
from backend.core.comparison import comparison_service
from backend.core.document_parser import ParseError, SUPPORTED_FILE_SUFFIXES, extractor
from backend.core.exports import report_export_service
from backend.runtime_paths import static_dir, uploads_dir


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

STATIC_DIR = static_dir()
UPLOAD_DIR = uploads_dir()
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
APP_VERSION = "4.0.1"
LOCAL_SHUTDOWN_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _default_api_key() -> str:
    return os.getenv("KP_API_KEY", "DEMO_KEY")


def _default_analysis_mode() -> str:
    return os.getenv("ANALYSIS_MODE", AnalysisMode.AUTO.value).strip().lower() or AnalysisMode.AUTO.value


def _schedule_process_shutdown(delay_seconds: float = 0.35) -> None:
    """Terminate the local desktop server shortly after responding to the client."""

    def _shutdown() -> None:
        time.sleep(delay_seconds)
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True, name="legaldesk-shutdown").start()


def _request_host(request: Request) -> str:
    """Return the normalized client host for local-only control routes."""

    if request.client is None or not request.client.host:
        return ""
    return request.client.host.strip().lower()


def _is_local_shutdown_request(request: Request) -> bool:
    """Allow shutdown only from localhost or in-process test clients."""

    host = _request_host(request)
    return host in LOCAL_SHUTDOWN_HOSTS or host.startswith("127.")


class TextProcessPayload(BaseModel):
    """JSON payload for manual text processing and reviewed preview data."""

    text: str | None = None
    api_key: str | None = None
    source_name: str | None = None
    pre_anonymized_text: str | None = None
    confirmed_replacements: int = 0
    confirmed_entities: dict[str, Any] = Field(default_factory=dict)
    analysis_mode: str = Field(default_factory=_default_analysis_mode)
    llm_url: str | None = None
    llm_model: str | None = None


class LLMConnectionTestPayload(BaseModel):
    """Payload for local LLM connectivity checks."""

    llm_url: str
    llm_model: str | None = None


class KPConnectionTestPayload(BaseModel):
    """Payload for KP API connectivity checks."""

    api_key: str | None = None


class ComparePayload(BaseModel):
    """Payload for comparing two archived cases."""

    left_case_id: int
    right_case_id: int


@dataclass
class FormPayload:
    """Multipart payload that may contain either a file or text."""

    file: UploadFile | StarletteUploadFile | None
    text: str | None
    api_key: str | None
    source_name: str | None
    pre_anonymized_text: str | None
    confirmed_replacements: int
    confirmed_entities: dict[str, Any]
    analysis_mode: str
    llm_url: str | None
    llm_model: str | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up local components once the FastAPI app starts."""

    _ = app
    _ = anonymizer
    logger.info("Anonymizer ready")
    yield


app = FastAPI(
    title="Рабочее место юриста",
    description="Локальная анонимизация и юридический анализ через КонсультантПлюс или локальную LLM",
    version=APP_VERSION,
    lifespan=lifespan,
)
app.state.shutdown_handler = _schedule_process_shutdown

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=FileResponse)
async def root() -> FileResponse:
    """Serve the single-page application."""

    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health() -> dict[str, Any]:
    """Return service health and adapter availability."""

    return {
        "status": "ok",
        **registry.status(),
        "version": APP_VERSION,
    }


@app.post("/api/system/shutdown")
async def shutdown_application(request: Request) -> dict[str, str]:
    """Stop the local desktop server from a localhost-only request."""

    if not _is_local_shutdown_request(request):
        raise HTTPException(403, "Остановка доступна только с локальной машины.")

    audit_log.log_event(
        action="app_shutdown_requested",
        subject="system",
        details={"host": _request_host(request) or "unknown"},
    )
    shutdown_handler = getattr(app.state, "shutdown_handler", _schedule_process_shutdown)
    shutdown_handler()
    return {"status": "stopping"}


@app.post("/api/llm/test")
async def test_llm_connection(body: LLMConnectionTestPayload) -> dict[str, Any]:
    """Test local LLM connectivity and list models when possible."""

    llm_url = body.llm_url.strip()
    if not llm_url:
        raise HTTPException(400, "llm_url обязателен")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{llm_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            models = [str(model.get("name")) for model in response.json().get("models", []) if model.get("name")]
            return {"ok": True, "type": "ollama", "models": models}
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{llm_url.rstrip('/')}/v1/models",
                headers={"Authorization": "Bearer local"},
            )
            response.raise_for_status()
            models = [str(model.get("id")) for model in response.json().get("data", []) if model.get("id")]
            return {"ok": True, "type": "openai-compat", "models": models}
    except Exception as exc:
        raise HTTPException(502, f"LLM недоступна по адресу {llm_url}: {exc}") from exc


@app.post("/api/kp/test")
async def test_kp_connection(body: KPConnectionTestPayload) -> dict[str, Any]:
    """Test whether the supplied KP API key is valid enough for probing."""

    api_key = (body.api_key or "").strip()
    if not api_key or api_key == "DEMO_KEY":
        return {"ok": False, "reason": "Ключ не задан"}

    adapter = HttpAdapter()
    try:
        pattern = await adapter._detect_pattern(api_key)
    except Exception as exc:  # pragma: no cover - network dependent
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "pattern": pattern["name"]}


@app.post("/api/preview-anonymization")
async def preview_anonymization(request: Request) -> dict[str, Any]:
    """Return anonymization preview without saving or calling the analysis backend."""

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await _parse_text_payload(request)
        raw_text = _extract_text_payload(payload)
        return _build_preview_response(
            raw_text=raw_text,
            source_name=_manual_source_name(payload.source_name),
            input_type="manual",
        )

    form_payload = await _parse_form_payload(request)
    has_file = form_payload.file is not None
    has_text = bool(form_payload.text and form_payload.text.strip())
    if has_file == has_text:
        raise HTTPException(422, "Нужно передать либо файл, либо текст")

    if has_file and form_payload.file is not None:
        raw_text = await _extract_text_from_upload(form_payload.file)
        return _build_preview_response(
            raw_text=raw_text,
            source_name=form_payload.file.filename or "Документ",
            input_type="file",
        )

    return _build_preview_response(
        raw_text=_extract_text_payload(
            TextProcessPayload(
                text=form_payload.text,
                source_name=form_payload.source_name,
            )
        ),
        source_name=_manual_source_name(form_payload.source_name),
        input_type="manual",
    )


@app.post("/api/process")
async def process_document(request: Request) -> dict[str, Any]:
    """Process either multipart file upload or text payload."""

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await _parse_text_payload(request)
        return await _process_text_payload(payload)

    form_payload = await _parse_form_payload(request)
    if form_payload.file is not None:
        return await _process_uploaded_file(form_payload)

    if form_payload.text or form_payload.pre_anonymized_text:
        return await _process_text_payload(_text_payload_from_form(form_payload))

    raise HTTPException(422, "Нужно передать файл или текст для обработки")


@app.post("/api/process-text")
async def process_text(request: Request) -> dict[str, Any]:
    """Process manually entered or pre-reviewed text without file parsing."""

    payload = await _parse_text_payload(request)
    return await _process_text_payload(payload)


@app.post("/api/anonymize-only")
async def anonymize_only(request: Request) -> dict[str, Any]:
    """Anonymize file input or manual text input without legal analysis."""

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await _parse_text_payload(request)
        raw_text = _extract_text_payload(payload)
        return _anonymize_response(
            raw_text=raw_text,
            filename=_manual_source_name(payload.source_name),
            input_type="manual",
        )

    form_payload = await _parse_form_payload(request)
    if form_payload.file is not None:
        raw_text = await _extract_text_from_upload(form_payload.file)
        return _anonymize_response(
            raw_text=raw_text,
            filename=form_payload.file.filename or "Документ",
            input_type="file",
        )

    if form_payload.text and form_payload.text.strip():
        return _anonymize_response(
            raw_text=_extract_text_payload(
                TextProcessPayload(
                    text=form_payload.text,
                    source_name=form_payload.source_name,
                )
            ),
            filename=_manual_source_name(form_payload.source_name),
            input_type="manual",
        )

    raise HTTPException(422, "Нужно передать файл или текст")


@app.get("/api/archive")
async def get_archive(limit: int = 50, offset: int = 0) -> dict[str, list[dict[str, Any]]]:
    """List archived cases."""

    return {"cases": archive.get_all(limit=limit, offset=offset)}


@app.get("/api/audit")
async def get_audit_log(
    limit: int = 100,
    offset: int = 0,
    case_id: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return the local compliance audit trail."""

    return {"entries": audit_log.list_entries(limit=limit, offset=offset, case_id=case_id)}


@app.get("/api/archive/{case_id}")
async def get_case(case_id: int) -> dict[str, Any]:
    """Return full archived case data."""

    case = archive.get_case(case_id)
    if case is None:
        raise HTTPException(404, "Дело не найдено")
    audit_log.log_event(
        action="case_opened",
        subject=case.get("filename") or f"case:{case_id}",
        case_id=case_id,
        details={"status": case.get("status"), "input_type": case.get("input_type")},
    )
    return case


@app.get("/api/archive/{case_id}/export")
async def export_case(case_id: int, format: str = "docx") -> Response:
    """Export an archived case as a branded report."""

    case = archive.get_case(case_id)
    if case is None:
        raise HTTPException(404, "Р”РµР»Рѕ РЅРµ РЅР°Р№РґРµРЅРѕ")

    export_format = format.strip().lower()
    filename_stem = _safe_filename(case.get("filename") or f"case-{case_id}")
    if export_format == "docx":
        payload = report_export_service.export_docx(case)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        download_name = f"{filename_stem}.docx"
        action = "export_docx"
    elif export_format == "pdf":
        payload = report_export_service.export_pdf(case)
        media_type = "application/pdf"
        download_name = f"{filename_stem}.pdf"
        action = "export_pdf"
    else:
        raise HTTPException(400, "Поддерживаются только форматы docx и pdf")

    audit_log.log_event(
        action=action,
        subject=case.get("filename") or download_name,
        case_id=case_id,
        details={"format": export_format, "source": case.get("source")},
    )
    headers = {"Content-Disposition": f'attachment; filename=\"{download_name}\"'}
    return Response(content=payload, media_type=media_type, headers=headers)


@app.patch("/api/archive/{case_id}/review")
async def mark_reviewed(case_id: int) -> dict[str, str]:
    """Mark an archived case as reviewed."""

    if not archive.mark_reviewed(case_id):
        raise HTTPException(404, "Дело не найдено")
    audit_log.log_event(
        action="case_reviewed",
        subject=f"case:{case_id}",
        case_id=case_id,
        details={"status": "reviewed"},
    )
    return {"status": "reviewed"}


@app.delete("/api/archive/{case_id}")
async def delete_case(case_id: int) -> dict[str, str]:
    """Delete an archived case."""

    existing = archive.get_case(case_id)
    if not archive.delete_case(case_id):
        raise HTTPException(404, "Дело не найдено")
    audit_log.log_event(
        action="case_deleted",
        subject=(existing or {}).get("filename") or f"case:{case_id}",
        case_id=case_id,
        details={"status": "deleted"},
    )
    return {"status": "deleted"}


@app.post("/api/compare")
async def compare_cases(body: ComparePayload) -> dict[str, Any]:
    """Compare two archived cases and return structured differences."""

    left_case = archive.get_case(body.left_case_id)
    right_case = archive.get_case(body.right_case_id)
    if left_case is None or right_case is None:
        raise HTTPException(404, "Одно из дел не найдено")

    result = comparison_service.compare_cases(left_case, right_case)
    audit_log.log_event(
        action="cases_compared",
        subject=f"{left_case.get('filename') or body.left_case_id} ↔ {right_case.get('filename') or body.right_case_id}",
        case_id=body.left_case_id,
        details={"right_case_id": body.right_case_id},
    )
    return result


async def _parse_text_payload(request: Request) -> TextProcessPayload:
    try:
        body = await request.json()
    except Exception as exc:  # pragma: no cover - malformed request path
        raise HTTPException(400, "Некорректный JSON в запросе") from exc

    try:
        return TextProcessPayload(**body)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()[0]["msg"]) from exc


async def _parse_form_payload(request: Request) -> FormPayload:
    form = await request.form()
    upload = form.get("file")
    file = upload if isinstance(upload, (UploadFile, StarletteUploadFile)) else None

    return FormPayload(
        file=file,
        text=_optional_string(form.get("text")),
        api_key=_optional_string(form.get("api_key")),
        source_name=_optional_string(form.get("source_name")),
        pre_anonymized_text=_optional_string(form.get("pre_anonymized_text")),
        confirmed_replacements=_parse_confirmed_replacements(form.get("confirmed_replacements")),
        confirmed_entities=_parse_confirmed_entities(form.get("confirmed_entities")),
        analysis_mode=_optional_string(form.get("analysis_mode")) or _default_analysis_mode(),
        llm_url=_optional_string(form.get("llm_url")),
        llm_model=_optional_string(form.get("llm_model")),
    )


async def _process_text_payload(payload: TextProcessPayload) -> dict[str, Any]:
    source_name = _manual_source_name(payload.source_name)
    reviewed_text = _validated_pre_anonymized_text(payload.pre_anonymized_text)
    raw_text = _extract_archive_text(payload) if reviewed_text is not None else _extract_text_payload(payload)
    return await _run_full_pipeline(
        raw_text=raw_text,
        source_name=source_name,
        api_key=payload.api_key or _default_api_key(),
        input_type="manual",
        pre_anonymized_text=reviewed_text,
        confirmed_replacements=max(0, int(payload.confirmed_replacements or 0)),
        confirmed_entities=_sanitize_entities(payload.confirmed_entities),
        analysis_mode=payload.analysis_mode,
        llm_url=payload.llm_url,
        llm_model=payload.llm_model,
    )


async def _process_uploaded_file(form_payload: FormPayload) -> dict[str, Any]:
    if form_payload.file is None:
        raise HTTPException(422, "Не найден файл для обработки")

    raw_text = await _extract_text_from_upload(form_payload.file)
    filename = form_payload.file.filename or "Документ"
    reviewed_text = _validated_pre_anonymized_text(form_payload.pre_anonymized_text)
    return await _run_full_pipeline(
        raw_text=raw_text,
        source_name=filename,
        api_key=form_payload.api_key or _default_api_key(),
        input_type="file",
        pre_anonymized_text=reviewed_text,
        confirmed_replacements=form_payload.confirmed_replacements,
        confirmed_entities=_sanitize_entities(form_payload.confirmed_entities),
        analysis_mode=form_payload.analysis_mode,
        llm_url=form_payload.llm_url,
        llm_model=form_payload.llm_model,
    )


def _extract_text_payload(payload: TextProcessPayload) -> str:
    if payload.text and len(payload.text) > 500_000:
        raise HTTPException(422, "Текст слишком длинный для анализа (максимум 500 000 символов)")
    try:
        return extractor.extract_from_text(payload.text or "")
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc


def _extract_archive_text(payload: TextProcessPayload) -> str:
    if payload.text and payload.text.strip():
        return payload.text.strip()
    reviewed_text = _validated_pre_anonymized_text(payload.pre_anonymized_text)
    if reviewed_text:
        return reviewed_text
    raise HTTPException(422, "Текст не может быть пустым")


def _validated_pre_anonymized_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise HTTPException(422, "Предпросмотр анонимизации не может быть пустым")
    if len(trimmed) > 500_000:
        raise HTTPException(422, "Текст слишком длинный для анализа (максимум 500 000 символов)")
    return trimmed


async def _extract_text_from_upload(file: UploadFile | StarletteUploadFile) -> str:
    filename = file.filename or "Документ"
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_FILE_SUFFIXES:
        raise HTTPException(400, f"Формат '{suffix}' не поддерживается")

    tmp_path = UPLOAD_DIR / filename
    try:
        with tmp_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        if tmp_path.stat().st_size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Файл слишком большой. Максимум: 50 МБ.")
        return extractor.extract(tmp_path)
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - filesystem/parsing failure path
        logger.exception("Document parsing failed")
        raise HTTPException(500, f"Ошибка парсинга документа: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)


async def _run_full_pipeline(
    *,
    raw_text: str,
    source_name: str,
    api_key: str,
    input_type: str,
    pre_anonymized_text: str | None = None,
    confirmed_replacements: int = 0,
    confirmed_entities: dict[str, Any] | None = None,
    analysis_mode: str,
    llm_url: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    if pre_anonymized_text is not None:
        anonymized_text = pre_anonymized_text
        entities_found = _sanitize_entities(confirmed_entities or {})
        total_replacements = max(0, confirmed_replacements)
        warnings: list[str] = []
    else:
        try:
            anonymized = anonymizer.anonymize(raw_text)
        except Exception as exc:  # pragma: no cover - anonymizer runtime failure
            logger.exception("Anonymization failed")
            raise HTTPException(500, f"Ошибка анонимизации: {exc}") from exc

        anonymized_text = anonymized.anonymized_text
        entities_found = anonymized.entities_found
        total_replacements = anonymized.total_replacements
        warnings = anonymized.warnings

    adapter = _select_adapter(
        analysis_mode=analysis_mode,
        api_key=api_key,
        llm_url=llm_url,
        llm_model=llm_model,
    )

    try:
        legal_result = await adapter.analyze(anonymized_text, api_key)
    except RuntimeError as exc:
        logger.warning("Legal analysis backend error: %s", exc)
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - adapter runtime failure
        logger.exception("Legal analysis request failed")
        raise HTTPException(502, f"Ошибка юридического анализа: {exc}") from exc

    case_id = archive.save_case(
        filename=source_name,
        original_text=raw_text,
        anonymized_text=anonymized_text,
        entities_found=entities_found,
        legal_result=legal_result,
        total_replacements=total_replacements,
        input_type=input_type,
    )
    audit_log.log_event(
        action="analysis_completed",
        subject=source_name,
        case_id=case_id,
        details={
            "input_type": input_type,
            "analysis_mode": _resolve_analysis_mode(analysis_mode).value,
            "source": legal_result.source,
            "total_replacements": total_replacements,
        },
    )

    return {
        "case_id": case_id,
        "filename": source_name,
        "input_type": input_type,
        "original_text": raw_text,
        "anonymization": {
            "total_replacements": total_replacements,
            "entities_found": entities_found,
            "anonymized_text": anonymized_text,
            "warnings": warnings,
        },
        "legal_analysis": {
            "summary": legal_result.summary,
            "relevant_laws": legal_result.relevant_laws,
            "court_practice": legal_result.court_practice,
            "recommendations": legal_result.recommendations,
            "source": legal_result.source,
            "raw_response": legal_result.raw_response or {},
        },
    }


def _build_preview_response(*, raw_text: str, source_name: str, input_type: str) -> dict[str, Any]:
    try:
        anonymized = anonymizer.anonymize(raw_text)
    except Exception as exc:  # pragma: no cover - anonymizer runtime failure
        logger.exception("Anonymization preview failed")
        raise HTTPException(500, f"Ошибка анонимизации: {exc}") from exc

    preview = {
        "filename": source_name,
        "input_type": input_type,
        "original_text": raw_text,
        "anonymized_text": anonymized.anonymized_text,
        "replacements": [asdict(record) for record in anonymized.replacements],
        "review_candidates": [asdict(record) for record in anonymized.review_candidates],
        "total_replacements": anonymized.total_replacements,
        "entities_found": anonymized.entities_found,
        "whitelist_skipped": anonymized.whitelist_skipped,
        "warnings": anonymized.warnings,
    }
    audit_log.log_event(
        action="preview_created",
        subject=source_name,
        details={
            "input_type": input_type,
            "total_replacements": anonymized.total_replacements,
            "whitelist_skipped": len(anonymized.whitelist_skipped),
        },
    )
    return preview


def _anonymize_response(*, raw_text: str, filename: str, input_type: str) -> dict[str, Any]:
    try:
        anonymized = anonymizer.anonymize(raw_text)
    except Exception as exc:  # pragma: no cover - anonymizer runtime failure
        logger.exception("Anonymization failed")
        raise HTTPException(500, f"Ошибка анонимизации: {exc}") from exc

    return {
        "filename": filename,
        "input_type": input_type,
        "original_text": raw_text,
        "anonymized_text": anonymized.anonymized_text,
        "total_replacements": anonymized.total_replacements,
        "entities_found": anonymized.entities_found,
        "warnings": anonymized.warnings,
    }


def _text_payload_from_form(form_payload: FormPayload) -> TextProcessPayload:
    return TextProcessPayload(
        text=form_payload.text,
        api_key=form_payload.api_key,
        source_name=form_payload.source_name,
        pre_anonymized_text=form_payload.pre_anonymized_text,
        confirmed_replacements=form_payload.confirmed_replacements,
        confirmed_entities=form_payload.confirmed_entities,
        analysis_mode=form_payload.analysis_mode,
        llm_url=form_payload.llm_url,
        llm_model=form_payload.llm_model,
    )


def _manual_source_name(source_name: str | None) -> str:
    if source_name and source_name.strip():
        return source_name.strip()
    return f"Ручной ввод {datetime.now().strftime('%H:%M %d.%m.%Y')}"


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    string_value = str(value).strip()
    return string_value or None


def _parse_confirmed_replacements(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "confirmed_replacements должен быть целым числом") from exc


def _parse_confirmed_entities(value: object) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "confirmed_entities должен быть JSON-объектом") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(422, "confirmed_entities должен быть JSON-объектом")
    return parsed


def _sanitize_entities(value: dict[str, Any]) -> dict[str, list[str]]:
    sanitized: dict[str, list[str]] = {}
    for key, raw_items in (value or {}).items():
        if isinstance(raw_items, list):
            sanitized[str(key)] = [str(item) for item in raw_items]
        else:
            sanitized[str(key)] = [str(raw_items)]
    return sanitized


def _safe_filename(value: str) -> str:
    cleaned = "".join(
        char if char.isascii() and (char.isalnum() or char in ("-", "_", ".")) else "_"
        for char in value.strip()
    )
    return cleaned.strip("._") or "legaldesk-report"


def _resolve_analysis_mode(value: str | None) -> AnalysisMode:
    try:
        return AnalysisMode((value or _default_analysis_mode()).strip().lower())
    except ValueError:
        return AnalysisMode.AUTO


def _has_real_kp_key(api_key: str | None) -> bool:
    return bool(api_key) and api_key != "DEMO_KEY" and len(api_key) > 10


def _build_llm_config(llm_url: str | None, llm_model: str | None) -> LLMConfig:
    base_url = (llm_url or os.getenv("LLM_BASE_URL", "")).strip()
    model = (llm_model or os.getenv("LLM_MODEL", "llama3")).strip() or "llama3"
    if not base_url:
        raise HTTPException(422, "Режим LLM выбран, но LLM URL не задан.")
    return LLMConfig(
        base_url=base_url,
        model=model,
        timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
    )


def _select_adapter(
    *,
    analysis_mode: str,
    api_key: str,
    llm_url: str | None,
    llm_model: str | None,
) -> ConsultantPlusAdapter:
    mode = _resolve_analysis_mode(analysis_mode)

    if mode == AnalysisMode.DEMO:
        return registry.get(AnalysisMode.DEMO)

    if mode == AnalysisMode.KP:
        if _has_real_kp_key(api_key):
            return HttpAdapter()
        try:
            return registry.get(AnalysisMode.KP)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    if mode == AnalysisMode.LLM:
        return LocalLLMAdapter(config=_build_llm_config(llm_url, llm_model))

    if _has_real_kp_key(api_key):
        return HttpAdapter()
    if (llm_url or os.getenv("LLM_BASE_URL", "")).strip():
        return LocalLLMAdapter(config=_build_llm_config(llm_url, llm_model))
    return registry.get(AnalysisMode.AUTO)
