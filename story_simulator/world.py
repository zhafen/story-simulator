from abc import ABC, abstractmethod

import anthropic

MODEL = "claude-haiku-4-5"


class World(ABC):
    @abstractmethod
    def respond(self, text: str) -> str:
        raise NotImplementedError


class MirrorWorld(World):
    def respond(self, text: str) -> str:
        return text


class AgentWorld(World):
    def __init__(self, model: str = MODEL):
        self.client = anthropic.Anthropic()
        self.model = model

    def respond(self, text: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": text}],
        )
        return next(block.text for block in response.content if block.type == "text")
