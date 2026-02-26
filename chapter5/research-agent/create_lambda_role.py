import boto3
import json

# This script creates and configures an IAM role used by the research Lambda.
# It is intended for one-time bootstrap of IAM resources.

# AWSクライアント初期化
iam = boto3.client('iam')
sts = boto3.client('sts')
# 現在のAWSアカウントID取得
account_id = sts.get_caller_identity().get('Account')

# 設定
ROLE_NAME = 'ResearchAgentExecutionRole'
REGION = 'us-west-2'
FUNCTION_NAME = 'research-agent'

# 信頼ポリシー
trust_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
}


# 実行ポリシー（CloudWatch Logs + Bedrock）
execution_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "logs:CreateLogGroup",
            "Resource": f"arn:aws:logs:{REGION}:{account_id}:*"
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": f"arn:aws:logs:{REGION}:{account_id}:log-group:/aws/lambda/{FUNCTION_NAME}:*"
        },
        {
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            "Resource": "*"
        }
    ]
}

# ロール作成
# Create the role with a trust policy that allows Lambda service to assume it.
role = iam.create_role(
    RoleName=ROLE_NAME,
    AssumeRolePolicyDocument=json.dumps(trust_policy),
    Description='Lambda execution role with CloudWatch Logs and Bedrock'
)

# ポリシーアタッチ
# Attach runtime permissions (logs + Bedrock invoke) as an inline policy.
iam.put_role_policy(
    RoleName=ROLE_NAME,
    PolicyName=f'{ROLE_NAME}-Policy',
    PolicyDocument=json.dumps(execution_policy)
)

# 結果出力
print(f"✓ ロール作成完了\nARN: {role['Role']['Arn']}")
