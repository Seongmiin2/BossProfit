from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from profit.scoping import ensure_store_for_user
from .serializers import RegisterSerializer, UserSerializer


@api_view(['POST'])
def register(request):
    """회원가입 + 매장 자동 생성"""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        store = ensure_store_for_user(user, name=f"{user.username}님의 매장")
        return Response(
            {
                'id': user.id,
                'username': user.username,
                'store_id': store.id,
                'message': '회원가입 성공',
            },
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """현재 사용자 정보"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)
