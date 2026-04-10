from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.knowledge_base import router as knowledge_base_router
from app.routers.notes import router as notes_router

__all__ = ["auth_router", "chat_router", "knowledge_base_router", "notes_router"]
