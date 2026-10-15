## Objective
Design and implement an end-to-end serverless data processing pipeline using AWS resources, provisioned through Terraform. This pipeline should ingest new order files delivered to an input S3 bucket, process them to generate analytics reports, and write the results to a separate output S3 bucket. 

## Assignment Description

You are tasked with building a data processing pipeline using the following AWS services:

* S3: Two buckets will be used—one for incoming order files and another for processed analytics reports.
* AWS Lambda (Dockerized): Processes new order files from S3 and generates analytics reports.


## Requirements:

1. Terraform Resources

We have provided some terraform modules to get you started but some configuration is required. Update the Terraform code to provision the following resources:

* S3 Buckets:
  * An input bucket to store incoming order files.
  * An output bucket to store the generated analytics reports.
* AWS Lambda Function:
  * Use a Docker container for the Lambda function runtime.
  * The function should process new files uploaded to the input S3 bucket and generate the analytics reports.

2. Lambda Function Logic

Write the Python code for the Lambda function to:

* Read the order data from newly uploaded CSV files in the input S3 bucket.
* Compute the required analytics reports and write them to the output S3 bucket. Describe any partitioning you used in the readme:
  * Most profitable region.
  * Most common shipping method for each product category.
  * Number of orders by category and sub-category.
  * Write the output as CSV files to the output S3 bucket.


Deliverables:

1.	Terraform Code:
  * A complete set of Terraform scripts to provision all required AWS resources.
  * Clear comments and modular design (use of modules is a plus).
2.	Lambda Code:
  * The Python code for the Lambda function, with clear documentation and structure.
  * Include a Dockerfile to package the Lambda function as a Docker image.
3.	Testing and Deployment Instructions:
  * Provide instructions to deploy and test the infrastructure and code.
  * Include commands for running Terraform, building the Docker image, and deploying the Lambda function.
4.  Readme file for the application.
5.	Bonus:
    * Add IAM policies that follow the principle of least privilege.

Evaluation Criteria:

* Correctness: Does the pipeline meet the requirements and generate the expected outputs?
* Code Quality: Is the Terraform code modular and well-structured? Is the Lambda function code readable and efficient?
* Documentation: Are the deployment and testing instructions clear? Are resources and configurations well-documented?
* Best Practices: Are AWS resources secured and follow best practices (e.g., IAM roles, S3 bucket policies)?
* Discussion question responses.

Good luck, and feel free to ask any clarifying questions!

### Terraform

#### Deploying the assignment

Before deploying, ensure that you have configured an AWS CLI profile with the necessary credentials. You can create a new profile using:

```sh
aws configure --profile <YOUR_PROFILE>
```

Follow the prompts to input your AWS access key, secret key, region (us-west-2), and output format.

Modify the [terraform vars](terraform/assignment/vars.tfvars) file. Ensure the username matches your aws username as it is used in resource controls. 
Then proceed with the following commands to initialize and deploy the infrastructure:

```sh
cd terraform/assignment
terraform init -backend-config="key=nmd-assignment-<candidate-name>.tfstate"
```

Your inital terraform apply will fail unless you deploy just the ecr repo and then build and push an image.

Terraform commands:
```sh
terraform plan -var-file="vars.tfvars"
terraform apply -var-file="vars.tfvars"
```

Example code to Build and push an image to the ecr repo
```sh
docker build --platform linux/arm64 --no-cache -t "$LOCAL_IMAGE_NAME" ./app
aws ecr get-login-password | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
docker tag "$LOCAL_IMAGE_NAME" "$ECR_URI"
docker push "$ECR_URI"
```

If you push a new image to an existing lambda, you will have to force update the lambda:
```sh
aws lambda update-function-code \
--function-name "$LAMBDA_FUNCTION_NAME" \
--image-uri "$ECR_URI:latest" > /dev/null
```

### Testing with Sample Orders

A sample file `sample_orders.csv` is provided in the repository to help you validate your Lambda function locally or in the deployed AWS environment.

To test your deployed pipeline:

**Upload the sample file to the input S3 bucket:**

```sh
aws s3 cp assessment_assets/sample_orders.csv s3://<your-input-bucket-name>/ --profile <YOUR_PROFILE>
```

Replace `<your-input-bucket-name>` and `<YOUR_PROFILE>` with your actual S3 bucket name and AWS CLI profile.

**Check for uploaded files:**

```sh
aws s3 ls s3://<your-input-bucket-name>/ --profile <YOUR_PROFILE>
```

**Check for processed analytics output files in the output bucket:**

```sh
aws s3 ls s3://<your-output-bucket-name>/ --recursive --profile <YOUR_PROFILE>
```

You should see CSV files corresponding to each of the required analytics reports.
