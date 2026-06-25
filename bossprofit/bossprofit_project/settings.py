"""
BOSSPROFIT Django settings (MVP)
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-bossprofit-mvp-week1-replace-in-prod"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "accounts",
    "profit",
    "market",
    "weather",
    "forecast",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bossprofit_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bossprofit_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF 설정
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# CORS 설정 (로컬 개발용)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# JWT 설정
from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Media 파일 설정
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# ===== 외부 식재료 시세 연동 (Phase 4) =====
# KAMIS(농수산물유통정보) Open API 인증값. 둘 다 설정돼야 실제 API를 사용하고,
# 비어 있으면 모의 시세(MockMarketPriceProvider)로 동작한다.
# 키 발급: https://www.kamis.or.kr/customer/reference/openapi_list.do
import os
KAMIS_CERT_KEY = os.environ.get("KAMIS_CERT_KEY", "")
KAMIS_CERT_ID = os.environ.get("KAMIS_CERT_ID", "")

# 공공데이터포털(data.go.kr) 통합 인증키. 기상청 ASOS/단기·중기예보, 농업기상,
# 전국 공영도매시장 경매 등 data.go.kr 계열 서비스가 공유한다.
# 비어 있으면 해당 ingestion은 fixture로 동작한다.
DATA_GO_KR_API_KEY = os.environ.get("DATA_GO_KR_API_KEY", "")

# 식자재(ingredient_id 또는 name) → KAMIS 품목 매핑.
#   category_code: 부류코드 (100 식량작물 / 200 채소류 / 300 특용작물 /
#                  400 과일류 / 500 축산물 / 600 수산물)  -- 필수
#   item_code:     품목코드 (부류 내 품목, kamis_check 명령으로 조회)
#   kind_code:     품종코드 (선택)
#   product_cls_code: "01" 소매(기본) / "02" 도매
#   convert_kg_yn:    "Y" 1kg 환산가(기본) / "N" 조사단위
#   unit_factor:      KAMIS 가격 → 식자재 purchase_quantity 기준 환산 계수(기본 1.0)
# 품목/품종 코드는 `python manage.py kamis_check --category 200` 으로 조회 후 채운다.
# 예:
#   KAMIS_ITEM_MAP = {
#       "PORK_LOIN_G": {"category_code": "500", "item_code": "514",
#                       "kind_code": "01", "unit_factor": 1.0},
#   }
# 우동·돈까스 매장 채소 품목 매핑(KAMIS 채소 부류 200). convert_kg_yn=Y → 1kg 환산가.
# unit_factor = 식자재 구매수량(g)/1000 (1kg 단가를 구매수량 기준 금액으로 환산).
KAMIS_ITEM_MAP = {
    # 양파: 구매 3000g → 1kg 단가 × 3
    "ONION_G": {"category_code": "200", "item_code": "245", "unit_factor": 3.0},
    # 양배추: 구매 1000g → 1kg(≈1포기) 단가 × 1
    "CABBAGE_G": {"category_code": "200", "item_code": "212", "unit_factor": 1.0},
}

# 로컬 비밀값(인증키 등)은 gitignore된 local_settings.py 에서 덮어쓴다.
try:
    from .local_settings import *  # noqa: F401,F403
except ImportError:
    pass
