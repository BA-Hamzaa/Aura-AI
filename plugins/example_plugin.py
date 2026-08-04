"""
example_plugin.py — Sample J.A.R.V.I.S. Plugin.

This demonstrates how to create a plugin for J.A.R.V.I.S.
Drop this file in the /plugins directory and it will be auto-loaded.
"""

import sys
import os

# Allow import of BasePlugin from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from plugins import BasePlugin, PluginMetadata


class JokePlugin(BasePlugin):
    """Returns a random programming joke."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="jokes",
            description="Get programming jokes on demand",
            version="1.0.0",
            author="J.A.R.V.I.S.",
            permissions=[],
        )

    def tools(self):
        return {"get_joke": self.get_joke}

    def on_load(self):
        print("[JokePlugin] Loaded ✅")

    def on_unload(self):
        print("[JokePlugin] Unloaded")

    def get_joke(self) -> str:
        import random
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?'",
            "Why do Java developers wear glasses? Because they don't C#!",
            "There are only 10 types of people in the world: those who understand binary and those who don't.",
            "Why did the programmer quit his job? Because he didn't get arrays.",
        ]
        return random.choice(jokes)
