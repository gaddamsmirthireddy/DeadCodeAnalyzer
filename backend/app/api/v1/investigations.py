from fastapi import APIRouter

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get("")
def list_investigations() -> list[dict[str, str]]:
    return []
