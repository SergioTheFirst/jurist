"""
FastAPI — главное приложение рабочего места юриста.
Запуск: uvicorn backend.main:app --reload --port 8000
"""

import logging
import os
import shutil
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.adapters.consultant_plus import consultant_adapter
from backend.core.anonymizer import anonymizer
from backend.core.archive import archive
from backend.core.document_parser import extractor, ParseError

# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("KP_API_KEY", "DEMO_KEY")

# ──────────────────────────────────────────────
app = FastAPI(
    title="Рабочее место юриста",
    description="Локальная анонимизация + анализ через КонсультантПлюс",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика (frontend)
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ══════════════════════════════════════════════
# МАРШРУТЫ
# ══════════════════════════════════════════════

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "kp_mode": "demo" if API_KEY == "DEMO_KEY" else "live",
        "kp_adapter": type(consultant_adapter).__name__,
    }


# ── Загрузка и полная обработка документа ────────────────────────────────────

@app.post("/api/process")
async def process_document(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
):
    """
    Основной эндпоинт:
    1. Принимает файл (PDF / DOCX / TXT)
    2. Извлекает текст локально
    3. Анонимизирует локально (никаких внешних запросов на этом этапе)
    4. Отправляет ТОЛЬКО очищенный текст в КП
    5. Возвращает полный результат + сохраняет в архив
    """
    key = api_key or API_KEY

    # ── Сохраняем файл временно ──────────────────────
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(400, f"Формат '{suffix}' не поддерживается")

    tmp_path = UPLOAD_DIR / file.filename
    try:
        with tmp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(500, f"Ошибка сохранения файла: {e}")

    # ── Этап 1: Извлечение текста ─────────────────────
    try:
        raw_text = extractor.extract(tmp_path)
    except ParseError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Ошибка парсинга документа: {e}")

    # ── Этап 2: Анонимизация (100% локально) ─────────
    try:
        anon_result = anonymizer.anonymize(raw_text)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Ошибка анонимизации: {e}")

    # ── Этап 3: КонсультантПлюс (только очищенный текст) ─
    try:
        legal_result = await consultant_adapter.analyze(
            anon_result.anonymized_text, key
        )
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error(traceback.format_exc())
        raise HTTPException(502, f"Ошибка запроса к КонсультантПлюс: {e}")

    # ── Сохранение в архив ────────────────────────────
    case_id = archive.save_case(
        filename=file.filename,
        anonymized_text=anon_result.anonymized_text,
        entities_found=anon_result.entities_found,
        legal_result=legal_result,
        total_replacements=anon_result.total_replacements,
    )

    tmp_path.unlink(missing_ok=True)

    return {
        "case_id": case_id,
        "filename": file.filename,
        "anonymization": {
            "total_replacements": anon_result.total_replacements,
            "entities_found": anon_result.entities_found,
            "anonymized_text": anon_result.anonymized_text,
            "warnings": anon_result.warnings,
        },
        "legal_analysis": {
            "summary": legal_result.summary,
            "relevant_laws": legal_result.relevant_laws,
            "court_practice": legal_result.court_practice,
            "recommendations": legal_result.recommendations,
            "source": legal_result.source,
        },
    }


# ── Только анонимизация (без КП) ─────────────────────────────────────────────

@app.post("/api/anonymize-only")
async def anonymize_only(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(400, f"Формат '{suffix}' не поддерживается")

    tmp_path = UPLOAD_DIR / f"tmp_{file.filename}"
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        raw_text = extractor.extract(tmp_path)
        anon_result = anonymizer.anonymize(raw_text)
    except ParseError as e:
        raise HTTPException(422, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "anonymized_text": anon_result.anonymized_text,
        "total_replacements": anon_result.total_replacements,
        "entities_found": anon_result.entities_found,
        "warnings": anon_result.warnings,
    }


# ── Архив ─────────────────────────────────────────────────────────────────────

@app.get("/api/archive")
async def get_archive(limit: int = 50, offset: int = 0):
    return {"cases": archive.get_all(limit=limit, offset=offset)}


@app.get("/api/archive/{case_id}")
async def get_case(case_id: int):
    case = archive.get_case(case_id)
    if not case:
        raise HTTPException(404, "Дело не найдено")
    return case


@app.patch("/api/archive/{case_id}/review")
async def mark_reviewed(case_id: int):
    ok = archive.mark_reviewed(case_id)
    if not ok:
        raise HTTPException(404, "Дело не найдено")
    return {"status": "reviewed"}


@app.delete("/api/archive/{case_id}")
async def delete_case(case_id: int):
    ok = archive.delete_case(case_id)
    if not ok:
        raise HTTPException(404, "Дело не найдено")
    return {"status": "deleted"}
