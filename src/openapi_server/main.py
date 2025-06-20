# coding: utf-8

from fastapi import FastAPI

from openapi_server.apis.default_api import router as DefaultApiRouter

app = FastAPI(
    title="User API",
    description="A simple API to retrieve user data.",
    version="1.0.0",
    servers=[
        {"url": "/", "description": "Root Server"},
    ],
)

app.include_router(DefaultApiRouter)
