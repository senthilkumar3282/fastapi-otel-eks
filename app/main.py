import os
from dotenv import load_dotenv
from fastapi import FastAPI
from elasticapm.contrib.starlette import make_apm_client, ElasticAPM


# Load environment variables from .env
load_dotenv()

apm_config = {
    "SERVICE_NAME": os.getenv("APM_SERVICE_NAME"),
    "SERVER_URL": os.getenv("APM_SERVER_URL"),
    "SECRET_TOKEN": os.getenv("APM_SECRET_TOKEN"),
    "ENVIRONMENT": os.getenv("APM_ENVIRONMENT"),
}

apm = make_apm_client(apm_config)

app = FastAPI()
app.add_middleware(ElasticAPM, client=apm)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on EKS with Elastic OTEL"}
