"""Absolute-path MCP entrypoint, independent of the user's current project."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.claude_channel import main

if __name__ == '__main__':
    main()
