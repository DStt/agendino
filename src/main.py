import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
from app.router import router

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


app.include_router(router)
