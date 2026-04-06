from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar

from life_world_model.types import RawEvent

COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {}


def register_collector(cls: type[BaseCollector]) -> type[BaseCollector]:
    COLLECTOR_REGISTRY[cls.source_name] = cls
    return cls


class BaseCollector(ABC):
    source_name: ClassVar[str]

    @abstractmethod
    def collect_for_date(self, target_date: date) -> list[RawEvent]: ...

    @abstractmethod
    def is_available(self) -> bool: ...
