def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Update expected JSON snapshots with actual output instead of asserting",
    )
