"""
Robin REST API - Programmatic access for automation and integrations.
"""
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Lazy imports for core modules (load only when needed)
def _get_llm(model: str):
    from llm import get_llm
    return get_llm(model)

def _run_investigation(query: str, model: str = "gpt4o", threads: int = 5, extract_iocs: bool = False,
                       include_telegram: bool = False, skip_health_check: bool = False):
    from main import _run_single_investigation
    llm = _get_llm(model)
    return _run_single_investigation(
        llm, query, threads, extract_iocs,
        rotate_circuit=False, rotate_interval=None,
        skip_health_check=skip_health_check, telegram=include_telegram
    )


API_KEY = os.getenv("ROBIN_API_KEY")


async def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not API_KEY:
        return True
    if x_api_key and x_api_key == API_KEY:
        return True
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


app = FastAPI(
    title="Robin OSINT API",
    description="AI-Powered Dark Web OSINT Tool - REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SearchRequest(BaseModel):
    query: str
    include_telegram: bool = False
    skip_health_check: bool = False


class InvestigateRequest(BaseModel):
    query: str
    model: str = "gpt4o"
    threads: int = 5
    extract_iocs: bool = False
    include_telegram: bool = False
    skip_health_check: bool = False


class PeopleInvestigateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    model: str = "gpt4o"
    threads: int = 5
    extract_iocs: bool = False
    include_telegram: bool = False
    skip_health_check: bool = False


@app.get("/health", dependencies=[])
async def health():
    """Health check endpoint - no auth required."""
    try:
        from search import verify_tor_connection
        tor_ok = verify_tor_connection()
    except Exception:
        tor_ok = False
    return {"status": "ok", "tor_connected": tor_ok}


@app.post("/search", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def search(req: Request, request: SearchRequest):
    """Run dark web search only (no scrape/summary)."""
    from search import get_search_results
    from llm import get_llm, refine_query
    try:
        llm = _get_llm("gpt4o")
        refined = refine_query(llm, request.query)
        results = get_search_results(
            refined.replace(" ", "+"),
            max_workers=5,
            include_telegram=request.include_telegram,
            skip_health_check=request.skip_health_check,
        )
        return {"refined_query": refined, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/investigate", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def investigate(req: Request, request: InvestigateRequest):
    """Run full investigation pipeline: refine -> search -> filter -> scrape -> summary."""
    try:
        refined, search_res, filtered, scraped, summary, iocs = _run_investigation(
            request.query,
            model=request.model,
            threads=request.threads,
            extract_iocs=request.extract_iocs,
            include_telegram=request.include_telegram,
            skip_health_check=request.skip_health_check,
        )
        return {
            "query": request.query,
            "refined_query": refined,
            "search_results_count": len(search_res),
            "filtered_count": len(filtered),
            "scraped_count": len(scraped),
            "summary": summary,
            "iocs": {k: list(v) for k, v in iocs.items()} if iocs else {},
            "source_urls": list(scraped.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_people_investigation(
    person_input: Dict[str, Any],
    model: str = "gpt4o",
    threads: int = 5,
    extract_iocs: bool = False,
    include_telegram: bool = False,
    skip_health_check: bool = False,
):
    from people_utils import validate_person_input, normalize_person_input
    from people_osint import run_people_investigation
    is_valid, err = validate_person_input(
        name=person_input.get("name"),
        email=person_input.get("email"),
        username=person_input.get("username"),
        phone=person_input.get("phone"),
    )
    if not is_valid:
        raise ValueError(err)
    normalized = normalize_person_input(
        name=person_input.get("name"),
        email=person_input.get("email"),
        username=person_input.get("username"),
        phone=person_input.get("phone"),
    )
    llm = _get_llm(model)
    return run_people_investigation(
        llm,
        normalized,
        threads=threads,
        extract_iocs_flag=extract_iocs,
        include_telegram=include_telegram,
        include_clear_web=True,
        skip_health_check=skip_health_check,
        rotate_circuit=False,
        rotate_interval=None,
    )


@app.post("/investigate/people", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def investigate_people(req: Request, request: PeopleInvestigateRequest):
    """Run People Search (OSINT): at least one of name, email, username, phone required."""
    try:
        person_input = {
            "name": request.name,
            "email": request.email,
            "username": request.username,
            "phone": request.phone,
        }
        person_input, profile, search_res, scraped, summary, iocs = _run_people_investigation(
            person_input,
            model=request.model,
            threads=request.threads,
            extract_iocs=request.extract_iocs,
            include_telegram=request.include_telegram,
            skip_health_check=request.skip_health_check,
        )
        # Serialize profile (lists/sets to list)
        def _ser(v):
            if isinstance(v, (list, set)):
                return list(v)
            return v
        person_profile = {k: _ser(v) for k, v in profile.items()}
        return {
            "person_input": person_input,
            "person_profile": person_profile,
            "summary": summary,
            "search_results_count": len(search_res),
            "scraped_count": len(scraped),
            "source_urls": list(scraped.keys()),
            "iocs": {k: list(v) for k, v in iocs.items()} if iocs else {},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_api(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
