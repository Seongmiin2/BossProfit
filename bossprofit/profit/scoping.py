"""매장(Store) 스코프 유틸리티.

모든 매장 데이터 조회·쓰기는 반드시 현재 사용자의 store로 한정해야 한다.
view에서 직접 user를 store로 환원하지 않고 이 모듈의 함수를 거친다.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from .models import Store, StoreMember


def get_active_store(user) -> Optional[Store]:
    """인증 사용자의 현재 매장을 반환. 없으면 None.

    MVP는 사용자당 1매장이므로 소유 매장 또는 멤버십 매장 중 첫 번째를 사용한다.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    store = user.owned_stores.order_by("id").first()
    if store is not None:
        return store
    membership = (
        StoreMember.objects.filter(user=user)
        .select_related("store")
        .order_by("id")
        .first()
    )
    return membership.store if membership else None


@transaction.atomic
def ensure_store_for_user(user, name: str = "내 매장") -> Store:
    """사용자에게 매장이 없으면 생성하고 OWNER 멤버십을 보장한다."""
    store = get_active_store(user)
    if store is None:
        store = Store.objects.create(owner=user, name=name)
    StoreMember.objects.get_or_create(
        store=store, user=user, defaults={"role": "OWNER"}
    )
    return store
