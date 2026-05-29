from src.backend.classes.top_module import TopModule
from src.utils import sort_signals_hierarchically


class TopModuleManager:
    """Main project class that manages all top modules and their associated operations.
    Also used to store information about warnings and errors during elaboration."""

    def __init__(self, top_modules: dict[str, TopModule], diagnosis: tuple[int, int, str]):
        """
        Args:
            top_modules: Top module objects
            diagnosis: Diagnostic data from compiling the files
        """
        self.__diagnosis: tuple[int, int, str] = diagnosis
        self.__top_modules: dict[str, TopModule] = top_modules

    def get_top_modules(self) -> dict[str, TopModule]:
        return self.__top_modules

    def get_top_module_names(self) -> list[str]:
        return sort_signals_hierarchically(self.__top_modules)

    def get_top_module_by_name(self, top_module_name: str) -> TopModule:
        return self.__top_modules[top_module_name]

    def get_diagnostic_data(self) -> tuple[int, int, str]:
        return self.__diagnosis
