#!/bin/bash
# LocalStack init hook: creates the DynamoDB tables, GSIs and S3 bucket that
# the backend expects. Mirrors infra/terraform/modules/dynamodb/main.tf.
# Runs automatically when LocalStack becomes ready.
set -euo pipefail

REGION=us-east-1

echo "[init-aws] creating DynamoDB main table..."
awslocal dynamodb create-table \
  --region "$REGION" \
  --table-name OpenRepoWikiMain \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
      AttributeName=parent_path,AttributeType=S \
  --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes '[{
      "IndexName": "ParentPathIndex",
      "KeySchema": [
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "parent_path", "KeyType": "RANGE"}
      ],
      "Projection": {"ProjectionType": "ALL"}
  }]' >/dev/null

echo "[init-aws] creating DynamoDB jobs table..."
awslocal dynamodb create-table \
  --region "$REGION" \
  --table-name OpenRepoWikiJobs \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
      AttributeName=status,AttributeType=S \
  --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes '[{
      "IndexName": "StatusIndex",
      "KeySchema": [
        {"AttributeName": "status", "KeyType": "HASH"}
      ],
      "Projection": {"ProjectionType": "ALL"}
  }]' >/dev/null

echo "[init-aws] creating S3 bucket..."
awslocal s3 mb s3://openrepowiki-artifacts-dev --region "$REGION" >/dev/null

echo "[init-aws] done."
