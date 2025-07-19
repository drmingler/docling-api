import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from document_converter.route import router as document_converter_router

app = FastAPI(
    title="Document to Markdown API",
    description="Convert PDF, DOCX, PPTX, HTML, images, AsciiDoc, Markdown, and CSV to Markdown.",
    version="0.1.0",
)


# Browsers reject `Access-Control-Allow-Origin: *` when credentials are included,
# so keep the two consistent. Origins can be overridden via CORS_ALLOW_ORIGINS.
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
_cors_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
_allow_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=_allow_credentials,
)


@app.get("/health", tags=["health"], summary="Liveness probe")
def health():
    return {"status": "ok"}


app.include_router(document_converter_router, prefix="", tags=["document-converter"])
