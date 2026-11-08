"""Labor-rules explainer. Stage 1: ungrounded baseline on the raw Anthropic SDK."""


def main() -> int:
    """Entry point for the `labor-rules-assistant` script that uv init created."""
    from .cli import main as _main

    return _main()
