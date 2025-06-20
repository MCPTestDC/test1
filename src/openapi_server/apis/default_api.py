from typing import Dict, List, Any

from fastapi import (
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    Security,
    status,
)

from openapi_server.db.database import db_operation_handler

from pydantic import StrictInt
from openapi_server.models.user import User

router = APIRouter()

@router.get(
    "/users/{userId}",
    responses={
        "200": {"model": User, "description": "OK"},
    },
    tags=["default"],
    summary="Returns a user by ID.",
    response_model_by_alias=True
)
async def users_user_id_get(
    response: Response,
    userId: int = Path(..., description=""),
) -> User:

    schema_name = ""
    table_name = ""
    if not schema_name or not table_name:
        raise HTTPException(status_code=501, detail="Schema name and/or Table name not implemented")
    path_params = {
        "user_id": userId
    }
    db_result = db_operation_handler(
        schema_name, 
        table_name,
        "get",
        body_params=None,
        path_params=path_params
    )
    response.status_code = get_status_code("get")
    return return_type_handler("User", db_result)

def get_status_code(http_method):
    status_codes = {
        "get": 200,
        "post": 201,
        "put": 200,
        "delete": 204
    }
    return status_codes.get(http_method.lower(), 500)

def return_type_handler(return_type: str, db_result: Any) -> Any:
    try:
        if return_type.startswith("List"):
            list_key = eval(return_type[5:-1])
            return [list_key.from_dict(item) for item in db_result]
        elif return_type:
            return eval(return_type).from_dict(db_result)
        else:
            return None
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Error: {error}")