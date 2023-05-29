from . import _AWS


class _Integration(_AWS):
    _type = "integration"
    _icon_dir = "resource_images/aws/integration"


class ApplicationIntegration(_Integration):
    _icon = "application-integration.png"


class Appsync(_Integration):
    _icon = "appsync.png"


class ConsoleMobileApplication(_Integration):
    _icon = "console-mobile-application.png"


class Eventbridge(_Integration):
    _icon = "eventbridge.png"


class MQ(_Integration):
    _icon = "mq.png"


class SimpleNotificationServiceSns(_Integration):
    _icon = "simple-notification-service-sns.png"


class SimpleQueueServiceSqs(_Integration):
    _icon = "simple-queue-service-sqs.png"


class StepFunctions(_Integration):
    _icon = "step-functions.png"


# Aliases

SNS = SimpleNotificationServiceSns
SQS = SimpleQueueServiceSqs
SF = StepFunctions

# Terraform Resource Mappings

aws_appsync_function = Appsync
aws_cloudwatch_event_rule = Eventbridge
aws_cloudwatch_event = Eventbridge
aws_mq_broker = MQ
aws_mq_configuration = MQ
aws_sns_topic = SimpleNotificationServiceSns
aws_sns_topic_subscription = SimpleNotificationServiceSns
aws_sns_platform_application = SimpleNotificationServiceSns
aws_sqs_queue = SimpleQueueServiceSqs
aws_sfn_state_machine = StepFunctions
