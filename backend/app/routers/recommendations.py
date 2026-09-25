from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.recommendations import recommend_for_product, recommend_for_user
from app.db import get_session
from app.models import Product, User
from app.routers.products import build_product_out
from app.schemas import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/products/{product_id}", response_model=list[RecommendationOut])
async def recommend_similar_products(
    product_id: str, limit: int = 5, session: AsyncSession = Depends(get_session)
) -> list[RecommendationOut]:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    recs = await recommend_for_product(session, product, limit=limit)
    return [
        RecommendationOut(product=await build_product_out(session, p), reason=reason, score=round(score, 3))
        for p, score, reason in recs
    ]


@router.get("/for-me", response_model=list[RecommendationOut])
async def recommend_for_me(
    limit: int = 8,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[RecommendationOut]:
    recs = await recommend_for_user(session, user.id, limit=limit)
    return [
        RecommendationOut(product=await build_product_out(session, p), reason=reason, score=round(score, 3))
        for p, score, reason in recs
    ]
