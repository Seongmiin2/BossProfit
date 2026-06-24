from .models import StoreMember


def get_user_store(user):
    """현재 사용자의 기본 활성 매장을 반환한다."""
    if not user or not user.is_authenticated:
        return None
    membership = (
        StoreMember.objects.filter(user=user, is_active=True)
        .select_related("store")
        .first()
    )
    return membership.store if membership else None
