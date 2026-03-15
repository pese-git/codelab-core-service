#!/bin/bash
set -e

# MinIO initialization script for bucket creation
# This script runs as a separate init container and creates required buckets

MINIO_HOST="${MINIO_HOST:-minio}"
MINIO_PORT="${MINIO_PORT:-9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minio}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-miniosecret}"
MINIO_BUCKET="${MINIO_BUCKET:-langfuse}"

# Endpoint for mc (MinIO Client)
MINIO_ENDPOINT="http://${MINIO_HOST}:${MINIO_PORT}"

echo "MinIO initialization script started"
echo "Endpoint: $MINIO_ENDPOINT"
echo "Bucket name: $MINIO_BUCKET"

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
max_retries=30
retry_count=0
while ! mc alias set local "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; do
  retry_count=$((retry_count + 1))
  if [ $retry_count -ge $max_retries ]; then
    echo "Failed to connect to MinIO after $max_retries attempts"
    exit 1
  fi
  echo "Attempt $retry_count/$max_retries: Waiting for MinIO..."
  sleep 2
done

echo "MinIO is ready!"

# Create buckets with error handling
echo "Creating bucket: $MINIO_BUCKET"
if mc mb "local/$MINIO_BUCKET" 2>&1; then
  echo "✓ Bucket '$MINIO_BUCKET' created successfully"
else
  if mc ls "local/$MINIO_BUCKET" >/dev/null 2>&1; then
    echo "✓ Bucket '$MINIO_BUCKET' already exists"
  else
    echo "✗ Failed to create bucket '$MINIO_BUCKET'"
    exit 1
  fi
fi

# Create additional bucket for OTEL data
MINIO_BUCKET_OTEL="${MINIO_BUCKET}-otel"
echo "Creating bucket: $MINIO_BUCKET_OTEL"
if mc mb "local/$MINIO_BUCKET_OTEL" 2>&1; then
  echo "✓ Bucket '$MINIO_BUCKET_OTEL' created successfully"
else
  if mc ls "local/$MINIO_BUCKET_OTEL" >/dev/null 2>&1; then
    echo "✓ Bucket '$MINIO_BUCKET_OTEL' already exists"
  else
    echo "✗ Failed to create bucket '$MINIO_BUCKET_OTEL'"
    exit 1
  fi
fi

# Enable versioning for data protection
echo "Enabling versioning..."
mc version enable "local/$MINIO_BUCKET" 2>/dev/null || echo "Versioning already enabled or not supported"
mc version enable "local/$MINIO_BUCKET_OTEL" 2>/dev/null || echo "Versioning already enabled or not supported"

echo "✓ MinIO initialization completed successfully"
echo "Buckets ready:"
mc ls local/
