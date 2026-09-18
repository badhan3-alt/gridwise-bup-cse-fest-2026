from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gridwise_app.guardrails import InterpretationError
from gridwise_app.models import OptimizeRequest, OptimizeResponse
from gridwise_app.optimizer import OptimizationError
from gridwise_app.service import optimize_energy
from gridwise_app.validator import PlanValidationError

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("gridwise")

app = FastAPI(title="GridWise API", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": "Invalid request structure", "errors": exc.errors()})


@app.exception_handler(InterpretationError)
async def interpretation_error_handler(_: Request, exc: InterpretationError):
    logger.warning("Controlled interpretation failure: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Operator-note interpretation failed"})


@app.exception_handler(OptimizationError)
async def optimization_error_handler(_: Request, exc: OptimizationError):
    logger.error("Controlled optimization failure: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Optimization pipeline failed"})


@app.exception_handler(PlanValidationError)
async def plan_validation_error_handler(_: Request, exc: PlanValidationError):
    logger.error("Controlled final-validation failure: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Optimization pipeline failed"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy_endpoint(payload: OptimizeRequest):
    return optimize_energy(payload)
