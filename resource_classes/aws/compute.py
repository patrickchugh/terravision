from . import _AWS


class _Compute(_AWS):
    _type = "compute"
    _icon_dir = "resource_images/aws/compute"


class ApplicationAutoScaling(_Compute):
    _icon = "application-auto-scaling.png"


class Batch(_Compute):
    _icon = "batch.png"


class Compute(_Compute):
    _icon = "compute.png"


class ElasticContainerRegistry(_Compute):
    _icon = "ec2-container-registry.png"


class EC2(_Compute):
    _icon = "ec2.png"


class EC2Instance(_Compute):
    _icon = "ec2-instance.png"


class EC2Instances(_Compute):
    _icon = "ec2-instances.png"


class ElasticBeanstalk(_Compute):
    _icon = "elastic-beanstalk.png"


class ElasticContainerService(_Compute):
    _icon = "elastic-container-service.png"


class ElasticIP(_Compute):
    _icon = "ec2-elastic-ip-address.png"


class ElasticKubernetesService(_Compute):
    _icon = "elastic-kubernetes-service.png"


## TODO: Requires review as specified as part of ECS task definition
class Fargate(_Compute):
    _icon = "fargate.png"


class Lambda(_Compute):
    _icon = "lambda.png"


class Lightsail(_Compute):
    _icon = "lightsail.png"


class Outposts(_Compute):
    _icon = "outposts.png"


class ServerlessApplicationRepository(_Compute):
    _icon = "serverless-application-repository.png"


class ThinkboxDeadline(_Compute):
    _icon = "thinkbox-deadline.png"


class ThinkboxDraft(_Compute):
    _icon = "thinkbox-draft.png"


class ThinkboxFrost(_Compute):
    _icon = "thinkbox-frost.png"


class ThinkboxKrakatoa(_Compute):
    _icon = "thinkbox-krakatoa.png"


class ThinkboxSequoia(_Compute):
    _icon = "thinkbox-sequoia.png"


class ThinkboxStoke(_Compute):
    _icon = "thinkbox-stoke.png"


class ThinkboxXmesh(_Compute):
    _icon = "thinkbox-xmesh.png"


class VmwareCloudOnAWS(_Compute):
    _icon = "vmware-cloud-on-aws.png"


class Karpenter(_Compute):
    _icon = "karpenter.png"


# Terraform aliases
aws_batch_compute_environment = Batch
aws_ecr_repository = ElasticContainerRegistry
aws_ecrpublic_repository = ElasticContainerRegistry
aws_ecs_service = ElasticContainerService
aws_ecs_cluster = ElasticContainerService
aws_ecs = ElasticContainerService
aws_ecs_fargate = Fargate
aws_eks_fargate_profile = Fargate
aws_fargate = Fargate
aws_ecs_ec2 = EC2Instance
aws_ec2ecs = EC2Instance
aws_eks_service = ElasticKubernetesService
aws_eks_cluster = EC2Instances
aws_eks_cluster_auto = EC2
aws_eks_node_group = EC2Instances
aws_launch_template = EC2

aws_elastic_beanstalk_application = ElasticBeanstalk
aws_instance = EC2Instance
aws_lambda_function = Lambda
aws_lightsail_instance = Lightsail
aws_eip = ElasticIP
tv_karpenter = Karpenter
