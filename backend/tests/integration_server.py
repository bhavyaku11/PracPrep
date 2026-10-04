"""Controlled Local Integration Test Server for PracPrep.

Runs FastAPI with dependency overrides (in-memory stateful database mock,
deterministic DemonstrationAIProvider, sandboxed temporary filesystem storage)
to enable complete cross-module verification between frontend and backend.
"""

import shutil
from pathlib import Path
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import create_app
from app.core.database import get_db
from app.modules.documents.extractor import DocumentExtractorService, get_extractor_service
from app.modules.documents.parser import DocumentSectionParserService, get_section_parser_service
from app.modules.documents.storage import DocumentStorageService, get_storage_service
from app.modules.ai.factory import DemonstrationAIProvider
from app.modules.viva.router import get_viva_ai_provider
from tests.test_e2e_workflow import E2EWorkflowState

TEST_STORAGE_DIR = Path("/tmp/pracprep_verification_storage")
if TEST_STORAGE_DIR.exists():
    shutil.rmtree(TEST_STORAGE_DIR, ignore_errors=True)
TEST_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

storage_service = DocumentStorageService(base_dir=TEST_STORAGE_DIR)
demo_ai_provider = DemonstrationAIProvider()
extractor_service = DocumentExtractorService(storage_service=storage_service)
state = E2EWorkflowState(storage_service=storage_service)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    session = state.make_mock_session()
    yield session


def override_get_storage_service() -> DocumentStorageService:
    return storage_service


def override_get_viva_ai_provider() -> DemonstrationAIProvider:
    return demo_ai_provider


def override_get_section_parser_service() -> DocumentSectionParserService:
    return DocumentSectionParserService(ai_provider=demo_ai_provider)


def override_get_extractor_service() -> DocumentExtractorService:
    return extractor_service


def create_integration_app():
    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_storage_service] = override_get_storage_service
    application.dependency_overrides[get_viva_ai_provider] = override_get_viva_ai_provider
    application.dependency_overrides[get_section_parser_service] = override_get_section_parser_service
    application.dependency_overrides[get_extractor_service] = override_get_extractor_service
    return application


app = create_integration_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
