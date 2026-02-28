import importlib
import pkgutil
from core.base_strategy import BaseStrategy

class StrategyRegistry:
    def __init__(self):
        self._strategies = {}

    def register(self, strategy):
        self._strategies[strategy.name] = strategy

    def get(self, name):
        return self._strategies.get(name)

    def get_all(self):
        return list(self._strategies.values())

    def get_by_tier(self, tier):
        return [s for s in self._strategies.values() if s.tier == tier]

    def discover(self, package_name="strategies"):
        package = importlib.import_module(package_name)
        for importer, modname, ispkg in pkgutil.walk_packages(package.__path__, prefix=package.__name__ + "."):
            if ispkg:
                continue
            try:
                module = importlib.import_module(modname)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
                        instance = attr()
                        self.register(instance)
            except Exception:
                continue
