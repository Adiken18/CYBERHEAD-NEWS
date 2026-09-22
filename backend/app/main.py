from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.categories import PRIMARY_CATEGORIES
from app.database import initialise_database, get_articles


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

