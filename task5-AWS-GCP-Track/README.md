# Task 5 — AWS/GCP Cloud Task

## Objective

Design a  cloud-based application deployment using AWS IAM Roles instead of hardcoded credentials.


# Solution Overview

This solution demonstrates how an application running on an EC2 instance can securely access AWS services such as S3 using IAM Roles. Temporary credentials are automatically provided by AWS through an attached IAM Role.

# Architecture

```text
                +------------------+
                |     IAM Role     |
                +------------------+
                         |
                         v
+------------------------------------------------+
|                EC2 Instance                    |
|                                                |
|   Python Application                           |
|   - Uses boto3 SDK                             |
|   - No hardcoded credentials                   |
+------------------------------------------------+
                         |
                         v
              AWS Temporary Credentials
                         |
                         +
                        S3 
```

---

# How IAM Roles Work

1. An IAM Role is created with specific permissions that are attached as JSOn policies.
2. The IAM Role is attached to the EC2 instance.
3. AWS automatically provides temporary credentials to the EC2 instance through the Instance Metadata Service (IMDS).
4. Applications use AWS SDKs such as boto3 to access AWS services.
5. Credentials are automatically rotated by AWS.

This way the application never needs to sotre AWS credentials.

---

# Why IAM Roles Are Preferred Over Static Secrets

## Problems with Static Credentials

Hardcoded AWS credentials are insecure because:

* secrets may leak into GitHub repositories if not careful
* credentials are long-lived
* manual rotation is difficult


## Benefits of IAM Roles

IAM Roles provide:

* temporary credentials
* automatic credential rotation
* easy permission management

This is the recommended AWS security practice.

# Security Controls Explanation

## 1. Least Privilege

The application should only receive permissions required for its functionality.

Example:

* allow reading objects from one S3 bucket
* deny all unnecessary actions

---

## 2. Credential Rotation

IAM Roles use temporary AWS STS credentials that are automatically rotated.

This reduces the impact of credential compromise.


# Sample IAM Policy to attach to EC2

File: `iam-policy.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::my-app-bucket/*"
      ]
    }
  ]
}
```

This policy allows reading objects from a specific S3 bucket only and follows the principle of least privilege

---

# Example Deployment Steps

1. Launch an EC2 instance.
2. Create S3 bucket and upload an object.
3. Create an IAM Role with required permissions as provided in the sample JSON
4. Attach the IAM Role to the EC2 instance.
5. Install dependencies and build the application.
6. Run the application.
7. Verify that AWS S3 bucket objects are accessible without access keys.

---

# Expected Outcome

The application successfully accesses the object using temporary IAM Role credentials without storing AWS access keys in code or configuration files.

---

# Security Best Practices Followed

* No hardcoded credentials
* Least privilege IAM policy
* Temporary credentials via IAM Role
* Automatic credential rotation
* Restricted permissions
* Secure metadata access using IMDSv2

