#!/bin/bash
# Helper script to export AWS SSO credentials for Terraform
# Usage: source ./aws-sso.sh

eval "$(aws configure export-credentials --profile default --format env)"
unset AWS_CREDENTIAL_EXPIRATION

if [ -n "$AWS_ACCESS_KEY_ID" ]; then
  echo "✅ AWS credentials exported"
  echo "Credentials valid for SSO session duration"
else
  echo "❌ Failed to export credentials. Run: aws sso login --profile default"
fi
