---

To create an EKS (Elastic Kubernetes Service) cluster and deploy a Python project (e.g., FastAPI)

### ✅ Prerequisites

1. AWS CLI installed and configured (`aws configure`)

   To install AWS CLI:

   ```bash
   # Download the installer
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

   # Unzip the installer
   unzip awscliv2.zip
   # If unzip is not available
   sudo apt install unzip

   # Run the installer
   sudo ./aws/install

   # Verify installation
   aws --version
   ```

2. kubectl installed

   To install `kubectl` on Ubuntu:

   ```bash
   # Download the latest release
   curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

   # Make the binary executable
   chmod +x kubectl

   # Move it to your PATH
   sudo mv kubectl /usr/local/bin/

   # Confirm installation
   kubectl version --client
   ```

3. eksctl installed

   To install `eksctl`:

   ```bash
   curl --silent --location "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
   sudo mv /tmp/eksctl /usr/local/bin

   # Confirm installation
   eksctl version
   ```

4. Docker installed

   To install Docker:

   ```bash
   sudo apt update
   sudo apt install docker.io -y

   # Enable and start Docker
   sudo systemctl enable docker
   sudo systemctl start docker

   # Confirm Docker is running
   docker --version
   ```

5. IAM user/role with required permissions (eks:*, ec2:*, iam:\*)

   Steps:

   * Login to AWS Console → IAM → User groups
   * Create a group named "admin-group" and attach `AdministratorAccess` policy as of now.
   * Create a user named "admin-user" and assign it to "admin-group"
   * Under Security credentials, create an access key
   * Choose CLI as the use case, download/store credentials

   ```bash
   aws configure  # Use the keys from previous step here
   ```

6. Create an EKS Cluster

   ```bash
   eksctl create cluster \
   --name my-python-cluster \
   --region ap-south-1 \
   --nodes 2 \
   --node-type t3.medium \
   --managed  # This creates EKS cluster, VPC and networking, Managed EC2 worker nodes and it will take ~15 minutes

   # Update kubeconfig to interact with EKS
   aws eks --region ap-south-1 update-kubeconfig --name my-python-cluster

   # Confirm cluster access
   kubectl get nodes
   ```

7. Elastic Cloud Kubernetes Integration

   * Log in at [https://cloud.elastic.co](https://cloud.elastic.co)
   * Select or create a deployment and choose Kubernetes monitoring

   Setup OpenTelemetry Collector using Elastic Helm charts:

   ```bash
   # Create a namespace for OpenTelemetry Operator
   kubectl create namespace opentelemetry-operator-system

   # Create a secret for Elastic Cloud OTLP endpoint and API key
   kubectl create secret generic elastic-secret-otel \
   --namespace opentelemetry-operator-system \
   --from-literal=elastic_endpoint='https://<your-elastic-endpoint>:443' \
   --from-literal=elastic_api_key='<your-elastic-api-key>'

   # Install the OpenTelemetry Kubernetes Helm stack from Elastic
   helm install opentelemetry-kube-stack open-telemetry/opentelemetry-kube-stack \
   --namespace opentelemetry-operator-system \
   --values 'https://raw.githubusercontent.com/elastic/elastic-agent/refs/tags/v9.0.2/deploy/helm/edot-collector/kube-stack/values.yaml' \
   --version '0.3.9'

   ```

---

### ✅ FastAPI Project Setup with Elastic OpenTelemetry

#### 1️⃣ Folder Structure

```
fastapi-otel-eks/
├── app/
│   ├── main.py
│   └── __init__.py
├── Dockerfile
├── requirements.txt
├── .env
├── k8s/
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── instrumentation.yaml
```

#### 2️⃣ FastAPI Application Code

`app/main.py`

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on EKS with Elastic OTEL"}
```

#### 3️⃣ `requirements.txt`

```
fastapi
uvicorn
```

#### 4️⃣ Dockerfile

```Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
```

#### 5️⃣ Build Docker Image and Push to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name fastapi-otel-eks

# Authenticate Docker with ECR (use "AWS" as username)
aws ecr get-login-password | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com

# Build Docker image
docker build -t fastapi-otel-eks .

# Tag Docker image for ECR
docker tag fastapi-otel-eks:latest <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com/fastapi-otel-eks:latest

# Push image to ECR
docker push <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com/fastapi-otel-eks:latest
```

#### 6️⃣ Kubernetes YAML Manifests

`k8s/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: fastapi-otel-eks
```

`k8s/instrumentation.yaml`

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: fastapi-instrumentation
  namespace: fastapi-otel-eks
spec:
  exporter:
    endpoint: http://opentelemetry-collector.opentelemetry-operator-system.svc.cluster.local:4317
  python:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:latest
  sampler:
    type: parentbased_traceidratio
    argument: "1.0"
```

`k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi
  namespace: fastapi-otel-eks
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fastapi
  template:
    metadata:
      labels:
        app: fastapi
      annotations:
        instrumentation.opentelemetry.io/inject-python: "true"
    spec:
      containers:
        - name: fastapi
          image: <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com/fastapi-otel-eks:latest
          ports:
            - containerPort: 80
```

`k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
  namespace: fastapi-otel-eks
spec:
  type: LoadBalancer
  selector:
    app: fastapi
  ports:
    - port: 80
      targetPort: 80
```

#### 7️⃣ Apply Kubernetes Configuration

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/instrumentation.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

#### 8️⃣ Validate Deployment

```bash
# Check pod status
kubectl get pods -n fastapi-otel-eks

# Get external IP
kubectl get svc -n fastapi-otel-eks
```

Access in browser:

```
http://<external-ip>/
```

### ✅ Elastic Observability Dashboard – Unified View of Metrics, Traces, and Logs

To view observability data collected via OpenTelemetry and Elastic Agent in **Elastic Cloud**, follow these steps:

#### 🔍 Go to **Discover** in Kibana

You can explore your collected data using the **data views (DDL)**:

* `logs-*` → View **application and infrastructure logs**
* `metrics-*` → Explore **infrastructure and system metrics**
* `APM` → Analyze **application traces and performance data**

#### 📊 What Each Data View Offers:

1. **logs-**\*

   * Shows structured logs from apps and infrastructure
   * Useful for error tracking, request logs, and custom log events

2. **metrics-**\*

   * Displays resource-level metrics (CPU, memory, disk, etc.)
   * Collected from Elastic Agent or OpenTelemetry metrics exporters

3. **APM**

   * Displays distributed traces captured by OpenTelemetry
   * Helps with end-to-end request path analysis and latency insights

---
