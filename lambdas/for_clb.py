import boto3
import re
import json

# Initialize clients using the IAM role attached to the Lambda function
autoscaling = boto3.client('autoscaling', region_name='us-west-2')
elb = boto3.client('elb', region_name='us-west-2')
sns = boto3.client('sns', region_name='us-west-2')
ssm = boto3.client('ssm', region_name='us-west-2')

# Configuration
ASG_NAME_PATTERN = r'^ASG_NAME_PATTERN-\d+$'
LOAD_BALANCER_NAME = 'LOAD_BALANCER_NAME'
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

def get_registered_instances_count(load_balancer_name):
    response = elb.describe_load_balancers(
        LoadBalancerNames=[load_balancer_name]
    )
    if not response['LoadBalancerDescriptions']:
        raise Exception(f"No load balancer found with name {load_balancer_name}")
    return len(response['LoadBalancerDescriptions'][0]['Instances'])

def send_sns_alert(topic_arn, message):
    sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject="syncservice-production-idata ASG has reached the maximum capacity"
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
        # Get the number of registered instances
        registered_instances_count = get_registered_instances_count(LOAD_BALANCER_NAME)
        print(f"Number of registered instances in load balancer '{LOAD_BALANCER_NAME}': {registered_instances_count}")

        # Get all matching ASG names
        asg_names = get_matching_asg_names(ASG_NAME_PATTERN)

        # Get the last alert state
        last_alert_state = get_last_alert_state()

        new_alert_state = {
            'asg_name': None,
            'max_capacity': None,
            'registered_instances_count': registered_instances_count
        }

        for asg_name in asg_names:
            # Get the maximum capacity of the ASG
            max_capacity = get_max_capacity(asg_name)
            print(f"Max capacity of ASG '{asg_name}': {max_capacity}")
            
            # Check if the max capacity matches the number of registered instances
            if max_capacity == registered_instances_count:
                new_alert_state['asg_name'] = asg_name
                new_alert_state['max_capacity'] = max_capacity
                message = (f"The Auto Scaling Group '{asg_name}' has reached its maximum capacity, "
                           f"which matches the number of registered instances in the load balancer '{LOAD_BALANCER_NAME}'. "
                           f"Max capacity: {max_capacity}, Registered instances: {registered_instances_count}.")
                print(message)
                
                # Send an alert only if the state has changed
                if last_alert_state != new_alert_state:
                    send_sns_alert(SNS_TOPIC_ARN, message)
                    update_alert_state(new_alert_state)
                return  # Alert sent, exit the loop
            else:
                print(f"ASG '{asg_name}' max capacity: {max_capacity}, Load balancer '{LOAD_BALANCER_NAME}' registered instances: {registered_instances_count}. No match.")
        
        # If no match found, clear the state
        if last_alert_state:
            update_alert_state({'asg_name': None, 'max_capacity': None, 'registered_instances_count': registered_instances_count})

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    lambda_handler({}, {})