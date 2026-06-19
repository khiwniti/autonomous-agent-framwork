# Cloud Run Deployment Guide

This guide explains how to deploy the Dev Agent A2A Server to Google Cloud Run.

## Prerequisites

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
2. Authenticate and select your project:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```
3. Set your preferred region (e.g., `us-central1` or `asia-east1`):
   ```bash
   gcloud config set run/region us-central1
   ```

## Local Testing

You can build and run the deployment container locally to test it:

```bash
docker build -t agent-platform-a2a -f deploy/Dockerfile .
docker run -p 8080:8080 --env AGENT_PLATFORM_TOKEN=my-secure-token agent-platform-a2a
```

Verify it works:
```bash
curl http://localhost:8080/.well-known/agent.json
```

## Production Deployment to Google Cloud Run

To build and deploy the container directly using Cloud Build:

```bash
# Generate a secure bearer token for authentication
export AGENT_PLATFORM_TOKEN=$(openssl rand -hex 32)

# Deploy to Cloud Run
gcloud run deploy autonomous-agent-a2a \
  --source . \
  --file deploy/Dockerfile \
  --allow-unauthenticated \
  --set-env-vars "AGENT_ENV=production,AGENT_PLATFORM_TOKEN=${AGENT_PLATFORM_TOKEN}"
```

> **Security Note:** `--allow-unauthenticated` allows public ingress to the A2A endpoints, but access to resources and skills is protected by checking the `Authorization: Bearer <AGENT_PLATFORM_TOKEN>` header if `AGENT_PLATFORM_TOKEN` env var is configured.

## Wiring Environment Variables in Next.js Website

Once deployed, copy the Cloud Run Service URL printed by gcloud (e.g. `https://autonomous-agent-a2a-abcde-uc.a.run.app`) and configure it on Vercel/Next.js:

```bash
AGENT_PLATFORM_URL="https://autonomous-agent-a2a-abcde-uc.a.run.app"
AGENT_PLATFORM_TOKEN="<your-generated-agent-platform-token>"
```
