from companion.http_api import build_parser


def test_http_api_parser_supports_host_and_port_flags():
    parser = build_parser()

    args = parser.parse_args(["--host", "127.0.0.1", "--port", "8010"])

    assert args.host == "127.0.0.1"
    assert args.port == 8010
