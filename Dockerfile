# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.12

# Copy the application code into the Lambda task root (/var/task)
COPY ./app ${LAMBDA_TASK_ROOT}

# Install Python dependencies
RUN pip3 install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Handler: <file name>.<function name>  ->  app/lambda.py : lambda_handler
CMD ["lambda.lambda_handler"]
