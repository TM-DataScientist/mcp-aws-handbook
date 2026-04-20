#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
IMAGE_NAME="research-agent"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo ".env not found: ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required in .env}"

AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${IMAGE_NAME}:latest"

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

docker build \
  -t "${IMAGE_NAME}" \
  -f "${REPO_ROOT}/chapter5/research-agent/Dockerfile" \
  "${REPO_ROOT}/chapter5/research-agent"

docker tag "${IMAGE_NAME}:latest" "${IMAGE_URI}"
docker push "${IMAGE_URI}"

echo "Pushed: ${IMAGE_URI}"
