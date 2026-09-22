from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.categories import PRIMARY_CATEGORIES
from app.database import initialise_database, get_articles

from app.database import get_article_cves

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialise_database()
    yield


app = FastAPI(
    title="CYBERHEAD News API",
    lifespan=lifespan
)


@app.get("/")
def home():
    return {
        "message": "CYBERHEAD News backend is running",
        "status": "ok"
    }


@app.get("/articles")
def list_articles():
    articles = get_articles()

    return {
        "count": len(articles),
        "articles": articles
    }


@app.get("/categories")
def list_categories():
    return {"categories": list(PRIMARY_CATEGORIES)}

@app.get("/article-cves")
def list_article_cves():
    links = get_article_cves()

    return {
        "count": len(links),
        "article_cves": links
    }

from app.database import get_cve_details
@app.get("/cves")
def list_cve_details():
    details = get_cve_details()

    return {
        "count": len(details),
        "cves": details
    }