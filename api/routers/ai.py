import os
import time
import requests
from google import genai
from google.genai import errors as genai_errors
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from core.auth.deps import current_user, CurrentUser
from api.models import AISummaryOut, ChatRequest

router = APIRouter(prefix="/api/ai", tags=["ai"])

_summary_cache: dict[str, tuple[str, float]] = {}
_SUMMARY_TTL = 600.0  # 10분


def _get_client() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "your_gemini_key_here":
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured")
    return genai.Client(api_key=key)


def _get_recent_news_titles(ticker: str, limit: int = 3) -> list[str]:
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key or api_key == "your_fmp_key_here":
        return []
    url = (
        f"https://financialmodelingprep.com/api/v3/stock_news"
        f"?tickers={ticker.upper()}&limit={limit}&apikey={api_key}"
    )
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            return [item.get("title", "") for item in resp.json()]
    except Exception:
        pass
    return []


@router.get("/summary", response_model=AISummaryOut)
def get_summary(
    ticker: str = Query(..., description="티커 심볼 (예: SPY)"),
    user: CurrentUser = Depends(current_user),
) -> AISummaryOut:
    client = _get_client()

    now = time.time()
    if ticker.upper() in _summary_cache:
        cached_text, expires_at = _summary_cache[ticker.upper()]
        if now < expires_at:
            return AISummaryOut(ticker=ticker.upper(), summary=cached_text)

    news_titles = _get_recent_news_titles(ticker, 3)
    news_text = "\n".join(f"- {t}" for t in news_titles) if news_titles else "뉴스 없음"

    prompt = (
        f"다음은 {ticker.upper()} 종목의 최근 뉴스입니다:\n{news_text}\n\n"
        f"3문장 이내의 간결한 한국어로 현재 시장 동향을 요약해주세요."
    )
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        summary = response.text.strip()
    except genai_errors.ClientError as e:
        raise HTTPException(status_code=503, detail=f"Gemini API 오류: {e.code}") from e

    _summary_cache[ticker.upper()] = (summary, now + _SUMMARY_TTL)
    return AISummaryOut(ticker=ticker.upper(), summary=summary)


@router.post("/chat")
def chat(
    req: ChatRequest,
    user: CurrentUser = Depends(current_user),
):
    client = _get_client()

    ticker = req.ticker.upper() if req.ticker else None
    news_titles = _get_recent_news_titles(ticker, 3) if ticker else []
    news_text = "\n".join(f"- {t}" for t in news_titles) if news_titles else ""

    system_parts = ["당신은 주식 분석 어시스턴트입니다. 간결하고 객관적인 한국어로 답하세요."]
    if ticker:
        system_parts.append(f"현재 {ticker} 종목에 대해 논의 중입니다.")
    if news_text:
        system_parts.append(f"최근 뉴스:\n{news_text}")
    system_prompt = "\n".join(system_parts)

    last_user_content = req.messages[-1].content if req.messages else ""
    full_prompt = f"{system_prompt}\n\n{last_user_content}"

    def generate():
        try:
            for chunk in client.models.generate_content_stream(
                model="gemini-2.5-flash", contents=full_prompt
            ):
                if chunk.text:
                    yield f"data: {chunk.text}\n\n"
        except genai_errors.ClientError as e:
            yield f"data: [오류: Gemini API {e.code}]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
