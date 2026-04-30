import os
import importlib.util
import inspect
from typing import List, Any
from llama_cpp import ChatCompletionTool
from base_tool import BaseTool
from config_manager import ConfigManager
from llm_service import LLMService


class LLMToolCollection:
    """Manages dynamically loaded tools for the LLM.

    Demonstrates reflection and dynamic module loading concepts
    to implement a plugin architecture.

    @param tools_dir Directory path containing tool modules.
    @param data_dir Directory path for application data.
    @param config_manager Configuration management instance.
    @param llm_service LLM service integration instance.
    """

    def __init__(self, tools_dir: str, data_dir: str, config_manager: ConfigManager, llm_service: LLMService) -> None:
        self.tools_dir = tools_dir
        self.data_dir = data_dir
        self.config_manager = config_manager
        self.llm_service = llm_service
        self.plugins: List[BaseTool] = []
        self._load_plugins()

    def _load_plugins(self) -> None:
        """Scans the tools directory and dynamically loads plugin modules."""
        if not os.path.exists(self.tools_dir):
            os.makedirs(self.tools_dir)

        for filename in os.listdir(self.tools_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                file_path = os.path.join(self.tools_dir, filename)

                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Instantiate classes inheriting from BaseTool
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseTool) and obj is not BaseTool:
                            self.plugins.append(
                                obj(self.data_dir, self.config_manager, self.llm_service)
                            )

    def generate_tools_array(self) -> List[ChatCompletionTool]:
        """Generates a list of tool definitions for the LLM API.

        @returns Formatted tool specifications.
        """
        tools = []
        type_mapping = {int: "integer", float: "number", str: "string", bool: "boolean"}

        for plugin in self.plugins:
            # Inspect bound methods to find decorated functions
            for name, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
                if getattr(method, "is_llm_tool", False):
                    sig = inspect.signature(method)
                    properties = {}
                    required = []

                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue

                        param_type = type_mapping.get(param.annotation, "string")
                        properties[param_name] = {"type": param_type}

                        if param.default == inspect.Parameter.empty:
                            required.append(param_name)

                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": (
                                str(inspect.getdoc(method)).strip()
                                if inspect.getdoc(method) else ""
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required,
                            },
                        },
                    }
                    tools.append(tool_def)

        return tools

    def execute_tool(self, func_name: str, **kwargs) -> Any:
        """Executes a loaded tool by name.

        @param func_name Name of the method to execute.
        @returns Result from the executed tool method.
        @raises ValueError If the specified function is not found or lacks the decorator.
        """
        for plugin in self.plugins:
            if hasattr(plugin, func_name):
                method = getattr(plugin, func_name)
                # Verify explicit developer marking before execution
                if getattr(method, "is_llm_tool", False):
                    return method(**kwargs)

        raise ValueError(f"The method '{func_name}' does not exist in the loaded plugins.")