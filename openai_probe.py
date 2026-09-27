"""Live CI preflight for the shared OpenAI provider contract."""
import json

import openai_models
import openai_runtime


model = openai_models.model_for("classification")
key = openai_runtime.require_live()
result = openai_runtime.preflight(model, key=key)
print("probe_status=success")
print(json.dumps(result, sort_keys=True))
