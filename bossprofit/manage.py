#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bossprofit_project.settings")
    # Windows 콘솔(cp949)에서 ✓·이모지·한글 출력 시 UnicodeEncodeError가 나는 것을 방지
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django를 import할 수 없습니다. 가상환경이 활성화되어 있는지, "
            "PYTHONPATH에 Django가 설치되어 있는지 확인해주세요."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
