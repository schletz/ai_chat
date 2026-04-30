# Agentic AI showcase using a local LLM

![](agentic_ai_2025.jpg)

This application uses a local LLM to chat with AI characters.
The application provides the LLM with a list of tools to respond to messages.
It dynamically generates this list using special decorators on class methods and reflection.
The LLM autonomously selects the right tool and signals to the application to use it.
The program then invokes the corresponding code via reflection and returns the result.
This allows the AI to get real-time information, like the weather or the current time.

## Features

- Directly loads the model's GGUF file. You do not need other servers or programs like ollama.
- Minimal dependencies. For inference, it only requires the `llama.dll` and the `llama-cpp-python` package.
- Supports all GGUF models, including uncensored versions.
- Privacy through local LLM: all data is processed on your computer, ensuring your chats stay private.
- Maximum performance by using CUDA and the new Blackwell NVIDIA features.

## Prerequisites

### Windows with NVidia GPU

- You must install Visual Studio 2026 with the C++ workload.
- Install the CUDA Toolkit from https://developer.nvidia.com/cuda-downloads?target_os=Windows&target_arch=x86_64&target_version=11&target_type=exe_local
- Add the path to *C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin\x64* to your PATH variable. Adjust the version number if necessary.

```
nvcc --version
set CMAKE_ARGS=-DGGML_CUDA=on
set GGML_CUDA_FA_ALL_QUANTS=1
pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
```

- Afterward, copy *cublas64_13.dll* and *cublasLt64_13.dll* from `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin\x64` to `C:\python\Lib\site-packages\llama_cpp\lib`.

- **Optional:** Compile the llama CLI tool
    - Add *C:\Program Files\Microsoft Visual Studio\18\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin* to the path (for VS2026).
    - You can find instructions at https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#cuda. For safety, also set the environment variable *GGML_CUDA_FA_ALL_QUANTS* here.
    - Documentation is at https://github.com/ggml-org/llama.cpp/tree/master/tools/cli

### macOS

Compile llama-cpp with the following option:

```
CMAKE_ARGS="-DGGML_METAL=on" pip install --upgrade llama-cpp-python
```

## Configure the API

Install the required packages using these commands:

```
pip install --upgrade fastapi 
pip install --upgrade uvicorn
pip install --upgrade pydantic
pip install --upgrade PyJWT
pip install --upgrade python-dotenv
pip install --upgrade cryptography
```

### Creating the Certificates

Run the following command in the */api* directory.
This creates the necessary certificates for HTTPS.

```
python create_cert.py
```

### Download a model

Use a model in GGUF format.
For example, you can download the "Gemma 4 E4B" model from Hugging Face at the following link: https://huggingface.co/lmstudio-community/gemma-4-E4B-it-GGUF/tree/main 
You only need the GGUF file.

If you use LM Studio, go to the Models section.
Use "Show in Explorer" to find the path to the GGUF file. Then, add this path to the .env file as described below.

### Creating the .env File

Create a file named _.env_ in the api directory with the following content:

```
SECRET_KEY="YOUR_SECRET"
MODEL_PATH="YOUR gguf FILE"
CORS_ORIGINS="https://my-name.github.io,http://localhost:5173"
DATA_DIR="data"
TOOLS_DIR="tools"

# Server Configuration
HOST="0.0.0.0"
PORT="8000"
SSL_KEYFILE="key.pem"
SSL_CERTFILE="cert.pem"
```

### Creating the settings.json File

In the directory specified by *DATA_DIR*, you can create a file named *system_config.json*.
This file manages your models.
For example, it might look like this:

```json
{
    "active_model_id": "gemma-4-31B",
    "models": [
        {
            "id": "gemma-4-31B",
            "file_path": "C:\\Users\\Username\\.lmstudio\\models\\lmstudio-community\\gemma-4-31B-it-GGUF\\gemma-4-31B-it-Q4_K_M.gguf",
            "n_ctx": 32768
        },
        {
            "id": "Qwen3.6-27B",
            "file_path": "C:\\Users\\Username\\.lmstudio\\models\\lmstudio-community\\Qwen3.6-27B-GGUF\\Qwen3.6-27B-Q4_K_M.gguf",
            "n_ctx": 32768
        }
    ]
}
```

### Creating a User

You can create a user with the following command:

```
python create_user.py username password
```

## Building the frontend (Vue.js)

Navigate to the */frontend* directory and run these commands:

```
npm install
npm run build
```

This command writes a single `index.html` file to the */docs* folder.
You can host this file on a service like GitHub Pages.

## Extending with Custom Tool Classes

The application automatically loads any Python files (*.py*) you create in the *TOOLS_DIR* as tools.
The API recognizes methods that have the *@llm_tool* decorator and loads them.
The class must inherit from `BaseTool`.
Pay attention to the PyDoc comments (the strings inside triple quotes).
The application passes these comments to the LLM as part of the tool description.
Therefore, write clear instructions for the LLM. Explain when and how to use the tool and its parameters.
The method `_get_random_lines` in `BaseTool` reads a file and returns a specified number of random lines.

```python
from typing import List
from base_tool import BaseTool, llm_tool


class RoleplayTools(BaseTool):
    @llm_tool
    def get_scene_ideas(self, number_of_ideas: int) -> List[str]:
        """
        Retrieve random ideas for a new scene. 
        Use this when a scene change is appropriate or the user requests one.
        Hint: Request multiple ideas to select the one that best fits the current mood and outfit.
        """
        return self._get_random_lines("scene_ideas.txt", number_of_ideas)
```

> [!TIP]
> Your tool class can access the member variables *self.data_dir*, *self.config_manager*, and *self.llm_service* from the base class.
> You can use them when your tools need access to the configuration or the loaded LLM.