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
KAMIS_ITEM_MAP = {}
