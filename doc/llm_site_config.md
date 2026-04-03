# Site LLM Configuration Guide

This guide explains how to customize your LLM configuration. For most use cases,
the YAML-based `site_config.yml` is sufficient. For advanced scenarios requiring
custom API logic, you can use a Python-based `site_config.py` instead.

## Table of Contents

- [Overview](#overview)
- [Quick Start Examples](#quick-start-examples)
  - [Select Which Models to Enable](#select-which-models-to-enable)
  - [Enable or Disable Individual Models](#enable-or-disable-individual-models)
  - [Add a New OpenAI Model](#add-a-new-openai-model)
  - [Add a Local Ollama Model](#add-a-local-ollama-model)
  - [Connect to a Custom OpenAI-Compatible API](#connect-to-a-custom-openai-compatible-api)
  - [Change Global Defaults](#change-global-defaults)
  - [Override Model-Specific Settings](#override-model-specific-settings)
- [Common Use Cases](#common-use-cases)
  - [Enterprise Deployment with Internal API](#enterprise-deployment-with-internal-api)
  - [Multiple Ollama Models](#multiple-ollama-models)
  - [Using Docker with Ollama](#using-docker-with-ollama)
- [Default Models](#default-models)
  - [OpenAI Models](#openai-models)
  - [Anthropic Models](#anthropic-models)
- [Available Templates](#available-templates)
- [Available Credential Types (Built-in)](#available-credential-types-built-in)
- [Configuration Reference](#configuration-reference)
  - [Top-Level Structure](#top-level-structure)
  - [Enabled Models List](#enabled-models-list)
  - [Credentials Configuration](#credentials-configuration)
  - [Global Defaults](#global-defaults)
  - [Provider Configuration](#provider-configuration)
  - [Model Configuration](#model-configuration)
  - [Templates (Advanced)](#templates-advanced)
  - [Authentication Types (Advanced)](#authentication-types-advanced)
- [Troubleshooting](#troubleshooting)
- [File Location](#file-location)
- [Advanced: Python Configuration](#advanced-python-configuration)
  - [When to Use Python Configuration](#when-to-use-python-configuration)
  - [Setup](#setup-1)
  - [Writing a Callback Function](#writing-a-callback-function)
  - [Defining the Model in YAML](#defining-the-model-in-yaml)
  - [Complete Example](#complete-example)

## Overview

Rocketgraph Mission Control comes with a default configuration (`config.yml`) that defines available LLM providers, models, and credentials. You can customize this configuration without modifying the default file by creating a `site_config.yml` file.

### Setup

1. Create a `site_config.yml` file on your host machine.
1. Set the `MC_SITE_CONFIG_YML` environment variable to point to your file.
1. Start the compose project.
1. The file is automatically mounted into the container at `/app/site_config/site_config.yml`.

The settings in `site_config.yml` are deep-merged with the base configuration.
You only need to specify the settings you want to change or add.
Any setting you specify will override the corresponding setting in the base config.

For advanced setups that require custom API logic or non-standard authentication, see [Advanced: Python Configuration](#advanced-python-configuration) below.

## Quick Start Examples

### Select Which Models to Enable

The simplest way to configure which models are available is to use the `enabled_models`
list. This is a whitelist - only models in this list will be enabled:

```yaml
llms:
  enabled_models:
    - openai_gpt_5_4
    - anthropic_claude_sonnet_4_6
```

This is simpler than setting `enabled: true/false` on individual models and is
the recommended approach for most deployments.

### Enable or Disable Individual Models

Alternatively, you can enable or disable models individually using the `enabled`
property. To enable a model that is disabled by default:

```yaml
llms:
  providers:
    openai:
      models:
        openai_gpt_4o:
          enabled: true
```

To disable a model that is enabled by default:

```yaml
llms:
  providers:
    anthropic:
      models:
        anthropic_claude_opus_4_6:
          enabled: false
```

**Note:** If `enabled_models` is present, it takes precedence over individual
`enabled` properties.

### Add a New OpenAI Model

To add a new model using the existing OpenAI provider:

```yaml
llms:
  providers:
    openai:
      models:
        my_custom_gpt:
          display_name: "My Custom GPT"
          model: "gpt-4-turbo-preview"
          enabled: true
```

This model automatically inherits OpenAI's defaults (endpoint URL, credentials, template).

### Add a Local Ollama Model

To add a locally-running Ollama model:

```yaml
llms:
  providers:
    local_ollama:
      models:
        local_llama3:
          display_name: "Local Llama 3"
          model: "llama3:8b"
          template: "ollama_chat"
          endpoint_url: "http://localhost:11434"
          credentials: "none"
          enabled: true
```

### Connect to a Custom OpenAI-Compatible API

Many LLM services offer OpenAI-compatible APIs. To connect to one:

```yaml
llms:
  # First, add credentials if needed
  credentials:
    my_service:
      display_name: "My Service"
      fields:
        api_key:
          display_name: "API Key"
          name: "api_key"
          type: "text"
          mask: true
          required: true

  providers:
    my_service:
      models:
        my_model:
          display_name: "My Service Model"
          model: "model-name"
          template: "openai_compatible"
          endpoint_url: "https://api.my-service.com"
          credentials: "my_service"
          enabled: true
```

### Change Global Defaults

To change settings that apply to all models:

```yaml
llms:
  defaults:
    timeout: 120          # Increase timeout to 2 minutes
    temperature: 0.1      # Lower temperature for more consistent responses
    max_tokens: 8192      # Increase max response length
```

### Override Model-Specific Settings

To change settings for a specific model:

```yaml
llms:
  providers:
    anthropic:
      models:
        anthropic_claude_opus_4_6:
          temperature: 0.2
          max_tokens: 16384
          timeout: 180
```

## Common Use Cases

### Enterprise Deployment with Internal API

For organizations running their own LLM infrastructure:

```yaml
llms:
  credentials:
    internal_llm:
      display_name: "Internal LLM Service"
      fields:
        api_key:
          display_name: "Service Token"
          name: "api_key"
          type: "text"
          mask: true
          required: true

  providers:
    internal:
      defaults:
        endpoint_url: "https://llm.internal.company.com"
        credentials: "internal_llm"
        template: "openai_compatible"
      models:
        company_gpt:
          display_name: "Company GPT"
          model: "company-gpt-v2"
          enabled: true
        company_gpt_fast:
          display_name: "Company GPT Fast"
          model: "company-gpt-fast"
          enabled: true
```

### Multiple Ollama Models

Running multiple models on a local Ollama instance:

```yaml
llms:
  providers:
    ollama:
      defaults:
        endpoint_url: "http://localhost:11434"
        credentials: "none"
        template: "ollama_chat"
      models:
        ollama_llama3:
          display_name: "Llama 3 (8B)"
          model: "llama3:8b"
          enabled: true
        ollama_codellama:
          display_name: "Code Llama (13B)"
          model: "codellama:13b"
          enabled: true
        ollama_mistral:
          display_name: "Mistral (7B)"
          model: "mistral:7b"
          enabled: true
```

### Using Docker with Ollama

When running in Docker and connecting to Ollama on the host:

```yaml
llms:
  providers:
    ollama:
      defaults:
        # Use Docker's host gateway to reach Ollama on the host machine
        endpoint_url: "http://host.docker.internal:11434"
        credentials: "none"
        template: "ollama_chat"
      models:
        ollama_llama3:
          display_name: "Llama 3"
          model: "llama3:8b"
          enabled: true
```

## Available Models

The following models are pre-configured in the base configuration. Models marked as
enabled are available immediately once credentials are configured.

### OpenAI Models

| Model Name | Display Name | API Model ID | Enabled | Description |
|------------|--------------|--------------|---------|-------------|
| `openai_gpt_5_4` | GPT-5.4 | gpt-5.4 | Yes | OpenAI's most capable model. Best for multi-step problems and detailed analysis. |
| `openai_gpt_5_4_mini` | GPT-5.4 Mini | gpt-5.4-mini | Yes | Smaller, faster GPT-5.4 variant. Good balance of capability and speed for everyday tasks. |
| `openai_gpt_5_4_nano` | GPT-5.4 Nano | gpt-5.4-nano | No | Smallest GPT-5.4 variant. Most cost-effective option for simpler tasks where speed matters. |
| `openai_gpt_5_3_chat` | GPT-5.3 Chat | gpt-5.3-chat-latest | Yes | Fast GPT-5.3 chat variant optimized for quick, conversational responses. |
| `openai_gpt_5_2` | GPT-5.2 | gpt-5.2 | No | Previous generation GPT-5.2 model. Still highly capable for complex reasoning tasks. |
| `openai_gpt_5_2_chat` | GPT-5.2 Chat | gpt-5.2-chat-latest | No | Previous generation GPT-5.2 chat variant optimized for quick responses. |
| `openai_o3` | o3 | o3 | No | OpenAI's advanced reasoning model using chain-of-thought. Excels at math, science, and coding problems. |
| `openai_o3_mini` | o3 Mini | o3-mini | No | Smaller o3 reasoning model. Faster and cheaper while retaining strong reasoning capabilities. |
| `openai_gpt_4_1` | GPT-4.1 | gpt-4.1 | No | Updated GPT-4 with improved instruction following and coding abilities. Reliable general-purpose model. |
| `openai_gpt_4o` | GPT-4o | gpt-4o | No | Multimodal GPT-4 model capable of processing text and images. Faster and more efficient than earlier GPT-4 versions. |
| `openai_gpt_4o_mini` | GPT-4o Mini | gpt-4o-mini | No | Smaller, faster, and more cost-effective GPT-4o variant. Good for simpler tasks where speed matters. |

### Anthropic Models

| Model Name | Display Name | API Model ID | Enabled | Description |
|------------|--------------|--------------|---------|-------------|
| `anthropic_claude_opus_4_6` | Claude Opus 4.6 | claude-opus-4-6 | Yes | Anthropic's most capable model. Excels at complex analysis, nuanced writing, and difficult reasoning tasks. |
| `anthropic_claude_sonnet_4_6` | Claude Sonnet 4.6 | claude-sonnet-4-6 | Yes | Balanced performance and speed. Excellent for most tasks including coding, analysis, and content generation. |
| `anthropic_claude_haiku_4_5` | Claude Haiku 4.5 | claude-haiku-4-5-20251001 | Yes | Fast and efficient for straightforward tasks. Best for high-volume, lower-complexity workloads. |
| `anthropic_claude_opus_4_5` | Claude Opus 4.5 | claude-opus-4-5-20251101 | No | Previous Opus generation. Still highly capable for complex tasks. |
| `anthropic_claude_sonnet_4_5` | Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 | No | Previous Sonnet generation. Good general-purpose model with balanced capabilities. |
| `anthropic_claude_opus_4_1` | Claude Opus 4.1 | claude-opus-4-1-20250805 | No | Earlier Opus release. Strong reasoning and analysis capabilities. |

## Available Templates

The following templates are available for use with the `template` field:

| Template | Description | Use Case |
|----------|-------------|----------|
| `openai_compatible` | OpenAI chat completions API format | OpenAI, Azure OpenAI, and compatible services |
| `anthropic_messages` | Anthropic Messages API format | Anthropic Claude models |
| `ollama_chat` | Ollama chat API format | Local Ollama instances |
| `huggingface_tgi` | Hugging Face Text Generation Inference | HuggingFace TGI deployments |
| `simple_completion` | Legacy completion API format | Older APIs using /v1/completions |

## Available Credential Types (Built-in)

| Credential | Provider | Fields |
|------------|----------|--------|
| `openai` | OpenAI | `api_key` (pattern: sk-... or sk-proj-...) |
| `anthropic` | Anthropic | `api_key` (pattern: sk-ant-...) |
| `aws_bedrock` | AWS Bedrock | `aws_region`, `aws_access_key`, `aws_secret_access_key` |
| `none` | No auth | (no fields) |

---

## Configuration Reference

This section provides a complete reference of all configuration options.

### Top-Level Structure

```yaml
llms:
  enabled_models: # List of model names to enable (optional, recommended)
    # ...
  credentials:    # Credential type definitions
    # ...
  defaults:       # Global defaults for all models
    # ...
  templates:      # Request/response templates (rarely needed to customize)
    # ...
  auth_types:     # Authentication methods (rarely needed to customize)
    # ...
  providers:      # Provider and model definitions
    # ...
```

### Enabled Models List

The `enabled_models` list provides a simple way to specify exactly which models should
be available. When present, it acts as a whitelist - only models in this list are
enabled, regardless of their individual `enabled` property.

```yaml
llms:
  enabled_models:
    - openai_gpt_5_4
    - openai_gpt_5_4_mini
    - anthropic_claude_sonnet_4_6
    - anthropic_claude_haiku_4_5
```

**Precedence rules:**

1. `config.yml` per-model `enabled` property (lowest priority)
2. `site_config.yml` per-model `enabled` property
3. `site_config.yml` `enabled_models` list (overrides all per-model settings)

**Key behaviors:**

- If `enabled_models` is not present, the per-model `enabled` properties are used
- If `enabled_models` is present but empty (`enabled_models: []`), no models are enabled

### Credentials Configuration

Credentials define how users authenticate with LLM providers.

```yaml
llms:
  credentials:
    <credential_name>:
      display_name: "Human Readable Name"
      fields:
        <field_name>:
          display_name: "Field Label"
          name: "internal_name"        # Key used in API calls
          type: "text" | "dropdown"
          mask: true | false           # Hide value in UI (for secrets)
          required: true | false
          pattern: "regex_pattern"     # Validation regex (optional)
          options: ["opt1", "opt2"]    # For dropdown type only
```

**Field Types:**
- `text`: Free-form text input
- `dropdown`: Selection from predefined options

### Global Defaults

Settings that apply to all models unless overridden:

```yaml
llms:
  defaults:
    timeout: 60           # Request timeout in seconds
    max_retries: 3        # Number of retry attempts
    temperature: 0.05     # Response randomness (0.0-1.0)
    max_tokens: 4096      # Maximum response tokens
    enabled: false        # Whether models are enabled by default
```

### Provider Configuration

Providers group related models together and can define shared defaults:

```yaml
llms:
  providers:
    <provider_name>:
      defaults:
        endpoint_url: "https://api.example.com"
        credentials: "credential_name"
        template: "template_name"
        # Any model setting can be a default
      models:
        <model_name>:
          # Model-specific settings
```

### Model Configuration

Complete model configuration options:

```yaml
llms:
  providers:
    <provider_name>:
      models:
        <model_name>:
          # Required
          model: "api-model-id"         # Model ID sent to the API
          enabled: true | false         # Whether model is available

          # Display
          display_name: "Friendly Name" # Name shown in UI

          # Connection (use template OR callback, not both)
          endpoint_url: "https://..."   # API base URL
          template: "template_name"     # Request/response template
          callback: "function_name"     # Python callback in site_config.py
          credentials: "cred_name"      # Which credentials to use

          # Request parameters
          timeout: 60                   # Request timeout (seconds)
          max_retries: 3                # Retry attempts
          temperature: 0.05             # Response randomness
          max_tokens: 4096              # Max response tokens

          # Optional metadata
          description: "Model info"     # Description (not displayed)
```

### Templates (Advanced)

Templates define how requests are formatted and responses are parsed. The built-in templates cover most use cases, but you can define custom templates:

```yaml
llms:
  templates:
    <template_name>:
      description: "Template description"
      auth_type: "bearer_token" | "api_key_header" | "hf_token" | "none"
      endpoint_suffix: "/v1/chat/completions"

      request_format:
        model: "{model}"
        messages: "{messages}"
        max_tokens: "{max_tokens}"
        temperature: "{temperature}"
        # Structure depends on the API

      response_parser:
        type: "json_path"
        text_path: "choices[0].message.content"
        usage_path: "usage"             # Optional

      headers:
        Content-Type: "application/json"
        # Additional headers as needed

      # Optional: Parameter name mappings
      parameter_mappings:
        max_tokens: "max_completion_tokens"

      # Optional: Model-specific parameter mappings
      model_specific_mappings:
        <model_name>:
          max_tokens: "max_tokens"

      # Optional: Model-specific fixed values
      model_specific_value_mappings:
        <model_name>:
          temperature:
            fixed_value: 1.0
```

**Template Variables:**
- `{model}` - The model ID
- `{messages}` - Chat messages array
- `{prompt}` - Combined prompt string
- `{system_prompt}` - System message content
- `{question}` - User question
- `{max_tokens}` - Maximum tokens setting
- `{temperature}` - Temperature setting
- `{top_p}` - Top-p setting (if applicable)

### Authentication Types (Advanced)

Authentication types define how credentials are sent in API requests:

```yaml
llms:
  auth_types:
    <auth_type_name>:
      header: "Authorization"           # HTTP header name
      format: "Bearer {api_key}"        # Header value format
      credential_field: "api_key"       # Field from credentials
```

**Built-in auth types:**
- `bearer_token` - Authorization: Bearer {api_key}
- `api_key_header` - x-api-key: {api_key}
- `hf_token` - Authorization: Bearer {token}
- `none` - No authentication

## Troubleshooting

### Model not appearing in the UI

1. Check that `enabled: true` is set
2. Verify the YAML syntax is correct (proper indentation)
3. Check the application logs for configuration errors

### API connection errors

1. Verify the `endpoint_url` is correct and accessible
2. Check that credentials are properly configured
3. For Docker deployments, ensure network access to external APIs

### Credential validation errors

1. Check that the credential `name` field matches what the API expects
2. Verify any `pattern` regex matches your credential format
3. Ensure required fields are marked correctly

## File Location

Create your `site_config.yml` file anywhere on your host machine, then set the
`MC_SITE_CONFIG_YML` environment variable to point to it. The Docker Compose
configuration will mount it into the container automatically.

Example:

```bash
# Create your config file
mkdir -p ~/.rocketgraph
vi ~/.rocketgraph/site_config.yml

# Set the environment variable (add to your shell profile or .env file)
export MC_SITE_CONFIG_YML=~/.rocketgraph/site_config.yml
```

The file will be mounted into the container at `/app/site_config/site_config.yml`.

## Advanced: Python Configuration

For advanced use cases where the built-in templates are not sufficient, you can
create a Python-based `site_config.py` that defines custom callback functions
to handle LLM API calls. The model itself is still defined in `site_config.yml`
and references the callback function by name.

### When to Use Python Configuration

Use `site_config.py` in addition to `site_config.yml` when you need to:

- Connect to an LLM API that doesn't follow standard patterns (OpenAI-compatible,
  Anthropic, or Ollama)
- Implement custom authentication logic (e.g., token refresh, signed requests)
- Add custom pre/post-processing of requests or responses
- Handle non-standard response formats
- Integrate with internal services that require custom logic

For standard LLM providers, the YAML configuration alone is sufficient and
recommended.

### Setup

1. Define your callback function(s) in a `site_config.py` file on your host machine.
1. Define your model in `site_config.yml` with a `callback` field referencing the
   function name.
1. Set the `MC_SITE_CONFIG_PY` environment variable to point to your Python file.
1. Set the `MC_SITE_CONFIG_YML` environment variable to point to your YAML file.
1. Start the compose project.

```bash
# Create your config files
mkdir -p ~/.rocketgraph
vi ~/.rocketgraph/site_config.py
vi ~/.rocketgraph/site_config.yml

# Set the environment variables (add to your shell profile or .env file)
export MC_SITE_CONFIG_PY=~/.rocketgraph/site_config.py
export MC_SITE_CONFIG_YML=~/.rocketgraph/site_config.yml
```

The files will be mounted into the container at `/app/site_config/`.

## API Details for an LLM

To write a Python callback that calls your LLM and returns its response to
Mission Control, you need to understand the LLM's API details. The most
important piece is the response JSON structure, which tells your code where
to find the LLM's answer.

Sample LLM API Structure:

  - **URL**: https://my.local.llm:6502/api/v1/query
  - **Method**: POST
  - **Headers**:
    - Authorization: Bearer <API_KEY>
    - Content-Type: application/json
  - **Request Payload**:
    - model: The model identifier (e.g., "gpt-3")
    - prompt: The input text or question
    - max_tokens: Maximum number of tokens to generate
    - temperature: Sampling temperature (range 0.0 to 1.0)
    - history: List of previous interactions (optional)
  - **Response**:
    ```json
    {
        "id": "cmpl-5b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8",
        "object": "text_completion",
        "created": 1612304000,
        "model": "gpt-3",
        "choices": [
            {
            "text": "The capital of France is Paris.",
            "index": 0,
            "logprobs": null,
            "finish_reason": "length"
            }
        ]
    }
    ```

### Writing a Callback Function

Define a function in your `site_config.py` that handles the API call. The
function signature is:

```python
def my_callback(llm_config, llm_credentials, question, prompt,
                history, **kwargs):
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `llm_config` | `dict` | Model configuration dictionary |
| `llm_credentials` | `dict` | User's credential values for this model |
| `question` | `str` | The user's question |
| `prompt` | `str` | System prompt |
| `history` | `list` | Conversation history as list of `{ "role": ..., "content": ... }` |
| `**kwargs` | `dict` | Additional parameters |

The function must return a string containing the LLM's response.

**Accessing model config:**

The `llm_config` dictionary contains the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `model` | `str` | Model ID sent to the API (e.g., `'gpt-4o-mini'`) |
| `credentials` | `str` | Credential type name (e.g., `'openai'`) |
| `display_name` | `str` | Human-readable model name |
| `endpoint_url` | `str` | API base URL |
| `temperature` | `float` | Temperature setting (default: 0.05) |
| `max_tokens` | `int` | Maximum response tokens (default: 4096) |
| `timeout` | `int` | Request timeout in seconds (default: 60) |
| `max_retries` | `int` | Number of retry attempts (default: 3) |

For example:

```python
model = llm_config['model']              # 'gpt-4o-mini'
temperature = llm_config['temperature']  # 0.05
```

**Accessing credentials:**

The `llm_credentials` dictionary contains the credential values entered by the
user. The keys are the `name` property of each credential field (not the YAML
field key). For example:

```python
api_key = llm_credentials.get('api_key', '')
```

Credential values by credential type:

| Credential Type | Keys | Values |
|-----------------|------|--------|
| `openai` | `api_key` | `{ "api_key": "sk-proj-..." }` |
| `anthropic` | `api_key` | `{ "api_key": "sk-ant-..." }` |
| `aws_bedrock` | `aws_region`, `aws_access_key`, `aws_secret_access_key` | `{ "aws_region": "us-east-1", "aws_access_key": "AKIA...", "aws_secret_access_key": "..." }` |

### Defining the Model in YAML

The model that uses the callback is defined in `site_config.yml`, not in
`site_config.py`. Use the `callback` field instead of `template` to reference
the Python function by name:

```yaml
llms:
  providers:
    my_provider:
      models:
        my_custom_model:
          display_name: "My Custom Model"
          model: "model-id"
          callback: "my_callback"        # Function name in site_config.py
          credentials: "openai"          # Credential type for user auth
          temperature: 0.1
          max_tokens: 4096
          timeout: 60
          enabled: true
```

The `callback` field replaces `template`.  A model should have one or the
other, not both. All other model fields (credentials, temperature, etc.) work
the same as for template-based models and are accessible via the `llm_config`
parameter in the callback function.

### Complete Example

This example adds a custom OpenAI model using a callback. It requires two
files: `site_config.py` for the callback function and `site_config.yml` for
the model and credential definitions.

**site_config.py** -- callback function only:

```python
def call_openai(llm_config, llm_credentials, question, prompt,
                history, **kwargs):
  """Call OpenAI Chat Completions API."""
  import requests

  # Get API key from credentials.
  api_key = llm_credentials.get('api_key', '')
  if not api_key:
    return "Error: OpenAI API key not provided"

  # Build messages.
  messages = []
  if prompt:
    messages.append({ "role": "system", "content": prompt })
  if history:
    for msg in history:
      if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
        messages.append(msg)
  messages.append({ "role": "user", "content": question })

  headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
  }

  payload = {
    "model": llm_config['model'],
    "messages": messages,
    "max_tokens": llm_config['max_tokens'],
    "temperature": llm_config['temperature'],
  }

  try:
    response = requests.post(
      "https://api.openai.com/v1/chat/completions",
      json = payload,
      headers = headers,
      timeout = llm_config['timeout']
    )
    response.raise_for_status()
    result = response.json()

    return (result.get('choices', [{}])[0]
                  .get('message', {})
                  .get('content', str(result)))
  except requests.exceptions.RequestException as e:
    return f"Error calling OpenAI API: {str(e)}"
```

**site_config.yml** -- model and credential definitions:

```yaml
llms:
  credentials:
    custom_openai:
      display_name: "Custom OpenAI"
      fields:
        custom_openai_api_key:
          display_name: "OpenAI API Key"
          name: "api_key"
          type: "text"
          mask: true
          required: true

  providers:
    custom_openai:
      models:
        custom_openai_gpt_4o_mini:
          display_name: "Custom GPT-4o Mini"
          model: "gpt-4o-mini"
          callback: "call_openai"
          credentials: "custom_openai"
          temperature: 0.1
          max_tokens: 4096
          timeout: 60
          enabled: true
```
