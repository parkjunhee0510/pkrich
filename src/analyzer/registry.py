from __future__ import annotations

from dataclasses import dataclass, field

from src.analyzer.base import AnalysisModule, sort_modules


@dataclass
class ModuleRegistry:
    _modules: list[AnalysisModule] = field(default_factory=list)
    _registration_order: dict[str, int] = field(default_factory=dict)

    def register(self, module: AnalysisModule) -> None:
        if module.name in self._registration_order:
            raise ValueError(f"Duplicate analysis module name: {module.name}")
        self._registration_order[module.name] = len(self._modules)
        self._modules.append(module)

    def register_many(self, modules: list[AnalysisModule]) -> None:
        for module in modules:
            self.register(module)

    def modules(self) -> list[AnalysisModule]:
        return sort_modules(list(self._modules))

    def resolve_order(self, base_inputs: set[str]) -> list[AnalysisModule]:
        modules = self.modules()
        produced_by: dict[str, set[str]] = {}
        for module in modules:
            for output_key in module.produces:
                produced_by.setdefault(output_key, set()).add(module.name)

        edges: dict[str, set[str]] = {module.name: set() for module in modules}
        indegree: dict[str, int] = {module.name: 0 for module in modules}

        for module in modules:
            missing = set()
            for requirement in module.requires:
                if requirement in base_inputs:
                    continue
                producers = produced_by.get(requirement, set()) - {module.name}
                if not producers:
                    missing.add(requirement)
                    continue
                for producer_name in producers:
                    if module.name not in edges[producer_name]:
                        edges[producer_name].add(module.name)
                        indegree[module.name] += 1
            if missing:
                missing_text = ", ".join(sorted(missing))
                raise ValueError(f"Unresolved requires for module {module.name}: {missing_text}")

        module_by_name = {module.name: module for module in modules}
        ready = [
            module
            for module in modules
            if indegree[module.name] == 0
        ]
        ordered: list[AnalysisModule] = []

        while ready:
            ready.sort(key=lambda module: (module.priority, self._registration_order[module.name]))
            current = ready.pop(0)
            ordered.append(current)
            for neighbor_name in sorted(edges[current.name]):
                indegree[neighbor_name] -= 1
                if indegree[neighbor_name] == 0:
                    ready.append(module_by_name[neighbor_name])

        if len(ordered) != len(modules):
            unresolved = sorted(name for name, degree in indegree.items() if degree > 0)
            raise ValueError(f"Cycle detected in analysis modules: {', '.join(unresolved)}")

        return ordered


AnalysisRegistry = ModuleRegistry

