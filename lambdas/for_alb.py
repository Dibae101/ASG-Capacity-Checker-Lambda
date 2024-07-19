import boto3
import re
import json

# Initialize clients using the IAM role attached to the Lambda function
autoscaling = boto3.client('autoscaling', region_name='us-east-1')
elbv2 = boto3.client('elbv2', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')

# Configuration
ASG_NAME_PATTERN = r'^ASG_NAME.*$'
TARGET_GROUP_ARN = 'TARGET_GROUP_ARN'
SNS_TOPIC_ARN = 'SNS_TOPIC_ARN'
SSM_PARAMETER_NAME = 'ASGAlertState'

def get_matching_asg_names(pattern):
    paginator = autoscaling.get_paginator('describe_auto_scaling_groups')
    page_iterator = paginator.paginate()
    
    matching_asgs = []
    for page in page_iterator:
        matching_asgs.extend(
            [asg['AutoScalingGroupName'] for asg in page['AutoScalingGroups']
             if re.match(pattern, asg['AutoScalingGroupName'])]
        )
    return matching_asgs

def get_max_capacity(asg_name):
    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )
    if not response['AutoScalingGroups']:
        raise Exception(f"No Auto Scaling group found with name {asg_name}")
    return response['AutoScalingGroups'][0]['MaxSize']

def get_registered_targets_count(target_group_arn):
    response = elbv2.describe_target_health(TargetGroupArn=target_group_arn)
    return len(response['TargetHealthDescriptions'])

def send_sns_alert(topic_arn, message):
    sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject="ASG and Target Group Capacity Match Alert"
    )

def get_last_alert_state():
    try:
        response = ssm.get_parameter(Name=SSM_PARAMETER_NAME)
        return json.loads(response['Parameter']['Value'])
    except ssm.exceptions.ParameterNotFound:
        return None

def update_alert_state(state):
    ssm.put_parameter(
        Name=SSM_PARAMETER_NAME,
        Value=json.dumps(state),
        Type='String',
        Overwrite=True
    )

def lambda_handler(event, context):
    try:
        # Get the number of registered targets
        registered_targets_count = get_registered_targets_count(TARGET_GROUP_ARN)
        print(f"Number of registered instances in target group : {registered_targets_count}")

        # Get all matching ASG names
        asg_names = get_matching_asg_names(ASG_NAME_PATTERN)

        # Get the last alert state
        last_alert_state = get_last_alert_state()

        new_alert_state = {
            'asg_name': None,
            'max_capacity': None,
            'registered_targets_count': registered_targets_count
        }

        for asg_name in asg_names:
            # Get the maximum capacity of the ASG
            max_capacity = get_max_capacity(asg_name)
            print(f"Max capacity of ASG '{asg_name}': {max_capacity}")
            
            # Check if the max capacity matches the number of registered targets
            if max_capacity == registered_targets_count:
                new_alert_state['asg_name'] = asg_name
                new_alert_state['max_capacity'] = max_capacity
                message = (f"The Auto Scaling Group '{asg_name}' has reached its maximum capacity, "
                           f"which matches the number of registered targets in the target group. "
                           f"Max capacity: {max_capacity}, Registered targets: {registered_targets_count}.")
                print(message)
                
                # Send an alert only if the state has changed
                if last_alert_state != new_alert_state:
                    send_sns_alert(SNS_TOPIC_ARN, message)
                    update_alert_state(new_alert_state)
                return  # Alert sent, exit the loop
            else:
                print(f"ASG '{asg_name}' max capacity: {max_capacity}, Target group registered targets: {registered_targets_count}. No match.")
        
        # If no match found, clear the state
        if last_alert_state:
            update_alert_state({'asg_name': None, 'max_capacity': None, 'registered_targets_count': registered_targets_count})

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    lambda_handler({}, {})