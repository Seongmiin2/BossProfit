"""
BOSSPROFIT LLM Service
OpenAI API를 사용해 매장 데이터 기반 분석을 제공합니다.
"""
import os


def _get_client():
    try:
        import openai
    except ImportError:
        raise ImportError("pip install openai 를 실행하세요.")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
    return openai.OpenAI(api_key=api_key)


def build_store_context(report):
    sa = report.get('sales_analysis', {})
    period = report.get('data_period', {})
    summary = report.get('summary', '')
    top_menus = sa.get('top_menus', [])[:5]
    market_risks = report.get('market_risks', [])

    lines = [
        f"=== 매장 분석 ({period.get('from', '?')} ~ {period.get('to', '?')}) ===",
        "",
        f"[판매 요약] {summary}",
        "",
    ]

    if top_menus:
        lines.append("[판매 상위 메뉴]")
        for m in top_menus:
            trend = f", 최근 추이 {m['trend_rate']:+.1f}%" if m.get('trend_rate') is not None else ""
            lines.append(
                f"  {m['rank']}위 {m['name']}: {m['quantity']:,}개 판매"
                f", 실매출 {int(m['net_revenue']):,}원{trend}"
            )
            if m.get('profitability_message'):
                lines.append(f"    → {m['profitability_message']}")

    lines.append("")

    if market_risks:
        lines.append("[재료 가격 위험]")
        for risk in market_risks:
            item = risk.get('item', {})
            menus = ', '.join(m['name'] for m in risk.get('affected_menus', []))
            forecasts = risk.get('forecasts', [])
            fc_parts = [
                f"{fc['horizon_days']}일후 {fc['change_rate']:+.1f}%"
                for fc in sorted(forecasts, key=lambda f: f['horizon_days'])
            ]
            fc_str = ', '.join(fc_parts) if fc_parts else '예측 없음'
            lines.append(f"  {item.get('name', '?')}: {fc_str}")
            if menus:
                lines.append(f"    → 영향 메뉴: {menus}")
    else:
        lines.append("[재료 가격 위험] 연결된 재료 없음 (레시피 미연결)")

    limitations = report.get('limitations', [])
    if limitations:
        lines.append("")
        lines.append("[분석 한계]")
        for limit in limitations[:4]:
            lines.append(f"  - {limit}")

    return "\n".join(lines)


SYSTEM_PROMPT = """\
당신은 한국 외식 자영업자 전문 수익성 어시스턴트입니다.
아래는 이 사장님 매장의 실제 POS 판매 데이터와 재료 가격 위험 분석입니다.

{context}

답변 규칙:
1. 위 데이터에 근거해서 구체적이고 실용적으로 답하세요.
2. 친근하고 명확한 한국어 존댓말로 답하세요.
3. 데이터에 없는 내용은 "현재 데이터로는 알 수 없습니다"라고 솔직히 말하세요.
4. 핵심 결론을 먼저, 수치 근거를 2~3개 이하로 뒤에 제시하세요.
5. 답변은 3~5문장으로 간결하게 하세요.\
"""


def call_openai_follow_up(question, store_context):
    """Returns (answer_text: str, engine_name: str)."""
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(context=store_context)},
            {"role": "user", "content": question},
        ],
        max_tokens=600,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip(), "gpt-4o-mini"


def generate_report_summary(report):
    """
    LLM으로 핵심 인사이트 2문장 생성.
    Returns (summary: str, used_llm: bool).
    API 키 없거나 실패 시 (None, False) 반환.
    """
    try:
        client = _get_client()
    except (ValueError, ImportError):
        return None, False

    sa = report.get('sales_analysis', {})
    top_menus = sa.get('top_menus', [])[:3]
    summary_data = sa.get('summary', {})
    market_risks = report.get('market_risks', [])
    period = report.get('data_period', {})

    lines = [
        f"분석기간: {period.get('from', '?')} ~ {period.get('to', '?')}",
        f"총 판매량: {summary_data.get('food_quantity', 0):,}개",
        f"총 실매출: {int(summary_data.get('food_net_revenue', 0)):,}원",
    ]
    for m in top_menus:
        trend = f" (최근 30일 {m['trend_rate']:+.1f}%)" if m.get('trend_rate') is not None else ""
        lines.append(f"판매 {m['rank']}위 {m['name']}: {m['quantity']:,}개{trend}")
    for r in market_risks[:2]:
        rate = r.get('headline_change_rate')
        if rate is not None:
            lines.append(f"{r['item']['name']} 30일 예측: {rate:+.1f}%")

    prompt = (
        "아래 매장 데이터를 보고 사장님께 핵심 인사이트를 정확히 2문장으로 알려주세요.\n"
        "첫 문장: 현재 판매 상황 요약 (핵심 수치 포함).\n"
        "둘째 문장: 지금 가장 주목할 기회나 위험.\n"
        "각 문장 50자 이내, 존댓말.\n\n"
        + "\n".join(lines)
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip(), True
    except Exception:
        return None, False
