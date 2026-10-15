## New Math Data assessment: serverless orders pipeline

### What it does

```
input S3 bucket --(ObjectCreated, *.csv)--> Lambda (Docker, Python/pandas) --> output S3 bucket
```

Upload an orders CSV to the input bucket and the Lambda writes three report CSVs to the output bucket:

| Report | Output prefix |
|--|--|
| Most profitable region (and its profit) | `most_profitable_region/` |
| Most common shipping method per Category | `most_common_ship_method_by_category/` |
| Number of orders per Category and Sub Category | `order_count_by_category_subcategory/` |

### Output partitioning

```
<report_name>/ingest_date=YYYY-MM-DD/<input_key_without_.csv>.csv
```

* One prefix per report, so each report can be crawled/queried as its own table (Hive-style `ingest_date=` partition, compatible with Glue/Athena).
* Partitioned by ingest date (UTC) so repeated uploads over time stay separated and old data is easy to expire or reprocess.
* Files are named after the full input key (slashes become `_`), so `a/orders.csv` and `b/orders.csv` never collide. Re-uploading the same key on the same day overwrites its reports (idempotent).

### Repository layout

| Path | Purpose |
|--|--|
| `terraform/assignment/` | Root config: buckets, hardening, IAM policy, trigger |
| `terraform/modules/ecr-repo`, `modules/lambda` | Reusable modules (ECR repo; Lambda + role + log group) |
| `app/lambda.py` | Lambda handler (S3 event -> read CSV -> write reports) |
| `app/orders_analytics.py` | Pure pandas report logic |
| `Dockerfile`, `app/requirements.txt` | Container image |
| `tests/` | Local unit tests (no AWS needed) |
| `.dockerignore`, `.gitignore` | Keep Terraform files out of the Docker build context / state files out of git |

### Assumptions

* The data has no profit column, so profit per row = `(List Price * (1 - Discount Percent/100) - cost price) * Quantity`, and regional profit is the sum over rows.
* "Number of orders" = distinct `Order Id`s.
* `Ship Mode = "Not Available"` is treated as missing and ignored for the shipping report.
* Ties are broken alphabetically so results are deterministic (e.g. Furniture ties between "Same Day" and "Standard Class" in the sample and resolves to "Same Day").
* Expected result for `sample_orders.csv`: most profitable region is **East (2465.5)**.

### Security / best practices

* Lambda role has only: CloudWatch Logs (AWS managed basic-execution policy), `s3:GetObject` on the input bucket objects, and `s3:PutObject` on the output bucket objects.
* Both buckets: all public access blocked, SSE-S3 encryption, bucket policy denying non-TLS requests.
* The S3 invoke permission is limited to the input bucket's ARN and this AWS account.
* Input and output are separate buckets, so the Lambda can never trigger itself.

### Prerequisites

Terraform, AWS CLI v2, Docker Desktop (running), Python 3.12 (optional, for local tests), and an AWS CLI profile in `us-west-2`:

```powershell
aws configure --profile omahaini
```

### Deploy (PowerShell)

> **State backend note:** `aws.tf` points at the S3 state bucket `nmd-training-tf-states-706146613458`, which does not exist (`NoSuchBucket`), so `terraform init` cannot succeed with it. The backend block is commented out and state is local. Restore it as described in `aws.tf` once a valid bucket is available.

```powershell
$env:AWS_PROFILE = "omahaini"
$REGION     = "us-west-2"
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
$ECR_URI    = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/nmd-assignment-omahaini-ecr"

# 1. Initialise and create ONLY the ECR repo (the Lambda needs an image to exist first)
cd terraform\assignment
terraform init
terraform apply -var-file="vars.tfvars" -target="module.ecr_repo"

# 2. Build and push the image from the repo root (where the Dockerfile lives)
cd ..\..
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
docker build --platform linux/arm64 --provenance=false -t "${ECR_URI}:latest" .
docker push "${ECR_URI}:latest"

# 3. Deploy everything else
cd terraform\assignment
terraform plan  -var-file="vars.tfvars"
terraform apply -var-file="vars.tfvars"
```

* `--provenance=false` stops Docker Desktop from pushing an attestation manifest, which Lambda rejects.
* The image platform must match the Lambda architecture. The default is `arm64` (`variable "lambda_architecture"`). To use x86 instead, set `lambda_architecture = "x86_64"` in `vars.tfvars` and build with `--platform linux/amd64`.

### Test the deployed pipeline

```powershell
$IN  = terraform output -raw input_bucket_name
$OUT = terraform output -raw output_bucket_name
cd ..\..

aws s3 cp sample_orders.csv "s3://$IN/"
aws s3 ls "s3://$IN/"
aws s3 ls "s3://$OUT/" --recursive          # expect 3 CSVs (give it a few seconds)

# Look at a result (the folder date is the UTC date the Lambda ran)
$D = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
aws s3 cp "s3://$OUT/most_profitable_region/ingest_date=$D/sample_orders.csv" -
aws s3 cp "s3://$OUT/most_common_ship_method_by_category/ingest_date=$D/sample_orders.csv" -
aws s3 cp "s3://$OUT/order_count_by_category_subcategory/ingest_date=$D/sample_orders.csv" -

### Clean up

```powershell
cd terraform\assignment
terraform destroy -var-file="vars.tfvars"
```

### IAM Policy following the principal of least privilege for the Terraform user (in my case, the IAM user "omahaini")

{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EcrLoginToken",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Sid": "EcrRepoManageAndPush",
      "Effect": "Allow",
      "Action": [
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:ListTagsForResource",
        "ecr:TagResource",
        "ecr:SetRepositoryPolicy",
        "ecr:GetRepositoryPolicy",
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "arn:aws:ecr:us-west-2:888577066340:repository/nmd-assignment-omahaini-ecr"
    },
    {
      "Sid": "LogsDescribe",
      "Effect": "Allow",
      "Action": "logs:DescribeLogGroups",
      "Resource": "*"
    },
    {
      "Sid": "LogsLambdaLogGroup",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:PutRetentionPolicy",
        "logs:ListTagsForResource",
        "logs:ListTagsLogGroup"
      ],
      "Resource": [
        "arn:aws:logs:us-west-2:888577066340:log-group:/aws/lambda/nmd-assignment-omahaini-file-processor",
        "arn:aws:logs:us-west-2:888577066340:log-group:/aws/lambda/nmd-assignment-omahaini-file-processor:*"
      ]
    },
    {
      "Sid": "S3BucketConfiguration",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:GetBucketAcl",
        "s3:GetBucketCORS",
        "s3:GetBucketWebsite",
        "s3:GetBucketVersioning",
        "s3:GetAccelerateConfiguration",
        "s3:GetBucketRequestPayment",
        "s3:GetBucketLogging",
        "s3:GetReplicationConfiguration",
        "s3:GetLifecycleConfiguration",
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetBucketNotification",
        "s3:PutBucketNotification",
        "s3:GetBucketTagging",
        "s3:PutBucketTagging"
      ],
      "Resource": "arn:aws:s3:::nmd-assignment-omahaini-*"
    },
    {
      "Sid": "S3TestObjects",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::nmd-assignment-omahaini-*/*"
    },
    {
      "Sid": "LambdaFunctionManage",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:GetFunction",
        "lambda:GetFunctionCodeSigningConfig",
        "lambda:ListVersionsByFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:AddPermission",
        "lambda:GetPolicy",
        "lambda:TagResource",
        "lambda:ListTags"
      ],
      "Resource": "arn:aws:lambda:us-west-2:888577066340:function:nmd-assignment-omahaini-file-processor"
    },
    {
      "Sid": "IamLambdaRoleManage",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:TagRole",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:ListInstanceProfilesForRole",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy"
      ],
      "Resource": "arn:aws:iam::888577066340:role/nmd-assignment-omahaini-file-processor-role"
    },
    {
      "Sid": "IamAttachOnlyBasicExecutionPolicy",
      "Effect": "Allow",
      "Action": [
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy"
      ],
      "Resource": "arn:aws:iam::888577066340:role/nmd-assignment-omahaini-file-processor-role",
      "Condition": {
        "ArnEquals": {
          "iam:PolicyARN": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        }
      }
    },
    {
      "Sid": "IamPassRoleToLambdaOnly",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::888577066340:role/nmd-assignment-omahaini-file-processor-role",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "lambda.amazonaws.com"
        }
      }
    },
    {
      "Sid": "TeardownTerraformDestroy",
      "Effect": "Allow",
      "Action": [
        "s3:DeleteBucket",
        "s3:DeleteBucketPolicy",
        "s3:ListBucketVersions",
        "s3:DeleteObject",
        "s3:DeleteObjectVersion",
        "ecr:DeleteRepository",
        "ecr:DeleteRepositoryPolicy",
        "ecr:BatchDeleteImage",
        "ecr:ListImages",
        "lambda:DeleteFunction",
        "lambda:RemovePermission",
        "logs:DeleteLogGroup",
        "iam:DeleteRole",
        "iam:DeleteRolePolicy",
        "iam:UntagRole"
      ],
      "Resource": [
        "arn:aws:s3:::nmd-assignment-omahaini-*",
        "arn:aws:s3:::nmd-assignment-omahaini-*/*",
        "arn:aws:ecr:us-west-2:888577066340:repository/nmd-assignment-omahaini-ecr",
        "arn:aws:lambda:us-west-2:888577066340:function:nmd-assignment-omahaini-file-processor",
        "arn:aws:logs:us-west-2:888577066340:log-group:/aws/lambda/nmd-assignment-omahaini-file-processor",
        "arn:aws:logs:us-west-2:888577066340:log-group:/aws/lambda/nmd-assignment-omahaini-file-processor:*",
        "arn:aws:iam::888577066340:role/nmd-assignment-omahaini-file-processor-role"
      ]
    },
    {
      "Sid": "OptionalKmsViaAwsServicesOnly",
      "Effect": "Allow",
      "Action": [
        "kms:DescribeKey",
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": [
            "lambda.us-west-2.amazonaws.com",
            "s3.us-west-2.amazonaws.com",
            "ecr.us-west-2.amazonaws.com"
          ]
        }
      }
    }
  ]
}

### I added KMS permissions here at the bottom although they are not neciarrilly needed. I used KMS in my own environment when testing and thought that security best practices would require KMS to be used to encrypt/decyrpt the Lambda/S3 buckets. 