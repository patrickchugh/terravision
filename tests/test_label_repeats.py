"""Labels keep the words the author chose, and drop only echoes of the type.

pretty_name() used to drop every word it had already seen anywhere in the
label. That removed real words from user-chosen names: "site_to_site" lost
its second "Site", and "active_directory" lost "Directory" because the type
"Directory Service" already had it.
"""

import pytest

from modules import helpers


def _label(name):
    return helpers.pretty_name(name, is_group=True)


@pytest.mark.parametrize(
    "name, label",
    [
        # repeats inside the author's own name are kept
        ("aws_vpn_connection.site_to_site", "VPN Connection Site To Site"),
        # the service name ending the author's name completes a phrase
        (
            "aws_directory_service_directory.active_directory",
            "Directory Service Active Directory",
        ),
        (
            "aws_lambda_event_source_mapping.sqs_to_lambda",
            "Lambda Event Source Mapping SQS To Lambda",
        ),
    ],
)
def test_user_chosen_words_survive(name, label):
    assert _label(name) == label


@pytest.mark.parametrize(
    "name, label",
    [
        # the whole name only repeats the type
        ("aws_s3_bucket.bucket", "S3 Bucket"),
        # the type's head noun at the end of the name
        ("aws_s3_bucket.assets_bucket", "S3 Bucket Assets"),
        ("aws_iam_role.lambda_role", "Role Lambda"),
        ("aws_glue_job.etl_job", "Glue Job ETL"),
        # type words elsewhere in the name
        ("aws_nat_gateway.nat_gw", "NAT Gateway Gw"),
        ("aws_kms_key.bucket_kms_key", "KMS Key Bucket"),
        (
            "aws_iam_role_policy_attachment.eks_cluster_policy",
            "IAM Role Policy Attachment EKS Cluster",
        ),
        # the type's own repeat (directory_service_directory)
        ("aws_directory_service_directory.ad", "Directory Service Ad"),
    ],
)
def test_echoes_of_the_type_are_still_dropped(name, label):
    assert _label(name) == label


def test_resource_card_label_wraps_but_keeps_every_word():
    card = helpers.pretty_name("aws_vpn_connection.site_to_site")
    assert card.split() == "VPN Connection Site To Site".split()


def test_vpn_is_an_acronym_on_azure_and_gcp():
    """VPN reads as an acronym on every provider, not "Vpn"."""
    from modules import helpers

    assert helpers.pretty_name("azurerm_vpn_gateway.hub") == "VPN Gateway Hub"
    assert helpers.pretty_name("google_compute_vpn_gateway.onprem") == (
        "VPN Gateway Onprem"
    )


def test_aws_label_width_stays_inside_a_subnet_margin():
    """A label may overhang its icon by less than a subnet box's 50pt margin.

    The budget used the icon's 256px size as if it were a width on the page,
    so labels ran 24 characters wide and spilled over subnet borders.
    """
    from modules import helpers

    chars = helpers._card_chars("aws")
    label_pts = chars * 28 * 0.55
    node_pts = 2.8 * 72
    assert (label_pts - node_pts) / 2 < 50
