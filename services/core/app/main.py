from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Headroom API")


class LiveStatus(BaseModel):
    status: Literal["ok"]


@app.get("/healthz/live", response_model=LiveStatus)
def live() -> LiveStatus:
    return LiveStatus(status="ok")
