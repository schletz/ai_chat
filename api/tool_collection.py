import os
import importlib.util
import inspect
from typing import List, Any
from llama_cpp import ChatCompletionTool
from base_tool import BaseTool
from config_manager import ConfigManager
from llm_service import LLMService


class LLMToolCollection:
    """
    Verwaltet die dynamisch geladenen Werkzeuge (Tools) für das LLM.
    Zeigt im Unterricht die Konzepte von Reflection (Code, der eigenen Code analysiert)
    und dynamischem Modul-Laden in Python (Plugin-Architektur).
    """
    def __init__(self, tools_dir: str, data_dir: str, config_manager: ConfigManager, llm_service: LLMService):
        self.tools_dir = tools_dir
        self.data_dir = data_dir
        self.config_manager = config_manager
        self.llm_service = llm_service
        self.plugins: List[BaseTool] = []
        self._load_plugins()

    def _load_plugins(self):
        if not os.path.exists(self.tools_dir):
            os.makedirs(self.tools_dir)

        # 1. Scanne das Verzeichnis nach Python-Dateien
        for filename in os.listdir(self.tools_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                file_path = os.path.join(self.tools_dir, filename)

                # 2. Dynamisches Laden (Plugin-System): Lädt Module zur Laufzeit statt statisch mit "import".
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # 3. Reflection: Durchsucht das Modul nach Klassen, die von `BaseTool` erben.
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseTool) and obj is not BaseTool:
                            # 4. Instanziiert das Plugin und reicht die Abhängigkeiten weiter.
                            self.plugins.append(obj(self.data_dir, self.config_manager, self.llm_service))

    def generate_tools_array(self) -> List[ChatCompletionTool]:
        tools = []
        type_mapping = {int: "integer", float: "number", str: "string", bool: "boolean"}

        # Iteriere über alle aktiven Plugins
        for plugin in self.plugins:
            # Reflection: Finde alle Methoden, die an dieses Objekt gebunden sind.
            for name, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
                # Prüfe, ob die Methode unseren speziellen `@llm_tool` Decorator hat.
                if getattr(method, "_is_llm_tool", False):
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
                            "description": inspect.getdoc(method).strip()
                            if inspect.getdoc(method)
                            else "",
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
        for plugin in self.plugins:
            if hasattr(plugin, func_name):
                method = getattr(plugin, func_name)
                # Wichtiger Sicherheitscheck: Das LLM darf nur Methoden ausführen,
                # die explizit vom Entwickler mit `@llm_tool` markiert wurden.
                if getattr(method, "_is_llm_tool", False):
                    return method(**kwargs)

        raise ValueError(f"Die Methode '{func_name}' existiert nicht in den geladenen Plugins.")
