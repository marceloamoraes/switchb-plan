"""JSON schema + prompt for the Gemini structured-extraction call."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "component": {"type": "STRING", "description": "Component / part number"},
        "Product": {"type": "STRING", "description": "Product / material description"},
        "Vendor": {"type": "STRING", "description": "Vendor / supplier name"},
        "Ampacity": {"type": "STRING", "description": "e.g. 3000A, 800A, 1200A"},
        "Voltage": {"type": "STRING", "description": "e.g. 220V, 110V, 480/277V"},
        "Enclosure type": {"type": "STRING", "description": "e.g. NEMA3R, Type1, Type 3R, Steel"},
        "Options": {"type": "STRING", "description": "Options / accessories, e.g. Humidistat, Thermostat"},
        "Circuit Breaker Details": {"type": "STRING", "description": "e.g. LCB 1 Right: 3000A Electronic LSIG (100kA @ 480V)"},
        "Total Price": {"type": "STRING"},
    },
    "required": [
        "component", "Product", "Vendor", "Ampacity", "Voltage",
        "Enclosure type", "Options", "Circuit Breaker Details", "Total Price",
    ],
}

PROMPT_TEMPLATE = """Extract the following fields from this switchgear/switchboard \
document text. If a field is not present in the text, use an empty string.

- component: Component / part number
- Product: Product / material description
- Vendor: Vendor / supplier name
- Ampacity: value ending in "A", e.g. 3000A, 800A, 1200A
- Voltage: value ending in "V", e.g. 220V, 110V, 480/277V
- Enclosure type: e.g. NEMA3R, Type1, Type 3R, Level 1 Acoustic Enclosure, Steel
- Options: options/accessories, e.g. Humidistat, Thermostat, Internal heaters, \
Automatic shutters, Meter Compartment, Solid State Trip
- Circuit Breaker Details: e.g. "LCB 1 Right: 3000A Electronic LSIG (100kA @ 480V)"
- Total Price

Text:
{text}
"""

MAX_INPUT_CHARS = 8000  # ~2k tokens


def build_prompt(text: str) -> str:
    return PROMPT_TEMPLATE.format(text=text[:MAX_INPUT_CHARS])
