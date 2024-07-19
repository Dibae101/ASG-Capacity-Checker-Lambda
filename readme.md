The ASG Capacity Checker is a serverless application designed to monitor Auto Scaling Groups (ASGs) and ensure that they do not exceed their maximum capacity. This application automatically checks the maximum capacity of ASGs and compares it with the number of registered instances in a specified Load Balancer. If an ASG reaches its maximum capacity, it sends an alert via Amazon SNS to notify the operations team.

Key Features:

	•	Automatic Monitoring: Continuously monitors the ASGs and Load Balancer to check for capacity limits.
	•	Real-Time Alerts: Sends notifications through Amazon SNS when an ASG reaches its maximum capacity.
	•	State Management: Maintains the state of the last alert to prevent duplicate notifications.
	•	Easy Deployment: Uses AWS SAM for simple and straightforward deployment.
	•	Scalable: Built on serverless architecture, ensuring scalability and low maintenance.

This application is ideal for ensuring high availability and preventing service disruption by proactively managing ASG capacities.