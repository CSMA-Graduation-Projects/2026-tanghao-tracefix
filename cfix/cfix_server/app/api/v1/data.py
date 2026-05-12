from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.data.user_dataset_store import (
    create_dataset,
    create_dataset_item,
    delete_dataset,
    delete_dataset_item,
    get_dataset_item,
    get_dataset_meta_ext,
    list_dataset_items,
    list_dataset_names_all,
    update_dataset_item,
)
from app.schemas.data import DatasetCreateIn, DatasetItemIn

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/set")
def dataset_list(user=Depends(get_current_user)):
    return {"code": 200, "msg": "ok", "data": list_dataset_names_all()}


@router.post("/set")
def dataset_create(payload: DatasetCreateIn, user=Depends(get_current_user)):
    try:
        data = create_dataset(
            name=payload.name,
            display_name=payload.display_name,
            desc=payload.desc,
            initial_item=payload.initial_item.model_dump() if payload.initial_item else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}


@router.delete("/set/{name}")
def dataset_remove(name: str, user=Depends(get_current_user)):
    try:
        delete_dataset(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": True}


@router.get("/set/{name}")
def dataset_detail(name: str, user=Depends(get_current_user)):
    try:
        data = get_dataset_meta_ext(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/set/{name}/items")
def dataset_items(name: str, user=Depends(get_current_user)):
    try:
        data = list_dataset_items(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}


@router.post("/set/{name}/items")
def dataset_item_create(name: str, payload: DatasetItemIn, user=Depends(get_current_user)):
    try:
        data = create_dataset_item(name, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/set/{name}/items/{item_id}")
def dataset_item_detail(name: str, item_id: str, user=Depends(get_current_user)):
    try:
        data = get_dataset_item(name, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}


@router.put("/set/{name}/items/{item_id}")
def dataset_item_update(name: str, item_id: str, payload: DatasetItemIn, user=Depends(get_current_user)):
    try:
        data = update_dataset_item(name, item_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}


@router.delete("/set/{name}/items/{item_id}")
def dataset_item_remove(name: str, item_id: str, user=Depends(get_current_user)):
    try:
        delete_dataset_item(name, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": True}
