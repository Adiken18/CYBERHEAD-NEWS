from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.source_manager import (
    DuplicateSourceError,
    SourceNotFoundError,
    SourceValidationError,
    add_source,
    get_sources,
    set_source_enabled,
    test_feed_url,
)


router = APIRouter(

    prefix="/api/sources",

    tags=[
        "Sources"
    ],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class SourceTestRequest(
    BaseModel
):

    url: str = Field(
        min_length=8,
        max_length=2048,
    )


class SourceCreateRequest(
    BaseModel
):

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    url: str = Field(
        min_length=8,
        max_length=2048,
    )


class SourceEnabledRequest(
    BaseModel
):

    enabled: bool


# =========================================================
# LIST SOURCES
# =========================================================

@router.get("")
def api_sources():

    sources = (
        get_sources()
    )


    return {

        "count":
            len(
                sources
            ),

        "active_count":
            sum(
                1
                for source
                in sources

                if source[
                    "enabled"
                ]
            ),

        "sources":
            sources,
    }


# =========================================================
# TEST FEED
# =========================================================

@router.post("/test")
def api_test_source(
    request:
        SourceTestRequest
):

    try:

        return (
            test_feed_url(
                request.url
            )
        )


    except SourceValidationError as error:

        raise HTTPException(

            status_code=400,

            detail=str(
                error
            ),
        ) from error


# =========================================================
# ADD SOURCE
# =========================================================

@router.post(
    "",
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def api_add_source(
    request:
        SourceCreateRequest
):

    try:

        return (
            add_source(
                request.name,
                request.url,
            )
        )


    except DuplicateSourceError as error:

        raise HTTPException(

            status_code=409,

            detail=str(
                error
            ),
        ) from error


    except SourceValidationError as error:

        raise HTTPException(

            status_code=400,

            detail=str(
                error
            ),
        ) from error


# =========================================================
# ENABLE / DISABLE SOURCE
# =========================================================

@router.patch(
    "/{source_id}/enabled"
)
def api_set_source_enabled(
    source_id: int,

    request:
        SourceEnabledRequest,
):

    try:

        source = (
            set_source_enabled(
                source_id,
                request.enabled,
            )
        )


    except SourceNotFoundError as error:

        raise HTTPException(

            status_code=404,

            detail=str(
                error
            ),
        ) from error


    return {
        "source":
            source
    }