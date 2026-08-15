from fastapi import APIRouter

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get("")
def list_repositories() -> list[dict[str, str]]:
    return []
