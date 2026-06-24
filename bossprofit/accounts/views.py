from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.db import transaction
from .models import StoreMember, OnboardingProgress
from .serializers import (
    PasswordChangeSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
    StoreCreateSerializer,
    StoreSerializer,
    StoreUpdateSerializer,
    OnboardingProgressSerializer,
)


@api_view(['POST'])
def register(request):
    """회원가입"""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {'id': user.id, 'username': user.username, 'message': '회원가입 성공'},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """현재 사용자 정보"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    serializer = ProfileUpdateSerializer(
        request.user,
        data=request.data,
        partial=True,
    )
    if serializer.is_valid():
        serializer.save()
        return Response(UserSerializer(request.user).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_store(request):
    membership = (
        StoreMember.objects.filter(user=request.user, is_active=True)
        .select_related("store")
        .first()
    )
    if not membership:
        return Response(
            {"detail": "연결된 매장이 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if membership.role != "OWNER":
        return Response(
            {"detail": "매장 소유자만 매장 정보를 수정할 수 있습니다."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = StoreUpdateSerializer(
        membership.store,
        data=request.data,
        partial=True,
    )
    if serializer.is_valid():
        serializer.save()
        return Response(UserSerializer(request.user).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(
        data=request.data,
        context={"request": request},
    )
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "비밀번호가 변경되었습니다."})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_store(request):
    """최초 온보딩에서 사용자 매장을 생성한다."""
    serializer = StoreCreateSerializer(
        data=request.data,
        context={"request": request},
    )
    if serializer.is_valid():
        store = serializer.save()
        return Response(StoreSerializer(store).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def onboarding_status(request):
    membership = (
        StoreMember.objects.filter(user=request.user, is_active=True)
        .select_related("store")
        .first()
    )
    if not membership:
        return Response({
            "has_store": False,
            "current_step": "STORE",
            "is_complete": False,
            "completed_steps": 0,
            "total_steps": 5,
        })
    progress, _ = OnboardingProgress.objects.get_or_create(store=membership.store)
    return Response(OnboardingProgressSerializer(progress).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """refresh token을 폐기해 서버 측 로그아웃을 완료한다."""
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response(
            {"refresh": ["refresh token이 필요합니다."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError:
        return Response(
            {"detail": "유효하지 않거나 이미 폐기된 토큰입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(status=status.HTTP_204_NO_CONTENT)
