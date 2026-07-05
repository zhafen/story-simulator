from abc import ABC, abstractmethod


class World(ABC):
    @abstractmethod
    def respond(self, text: str) -> str:
        raise NotImplementedError


class MirrorWorld(World):
    def respond(self, text: str) -> str:
        return text
