"""Prompts for the VLM. The classifier's job is strictly semantic: name the garment
and choose the measurement set. It must NEVER emit a number — geometry owns every cm.
"""

GARMENT_TYPES = [
    "t-shirt", "shirt", "jumper", "hoodie", "jacket", "coat", "dress",
    "jeans", "trousers", "shorts", "skirt",
]

# Standard resale measurement sets a buyer needs, by type. The engine measures these.
MEASUREMENT_SETS = {
    "top": ["pit_to_pit", "length", "shoulder_width", "sleeve_length", "hem_width"],
    "bottom": ["waist_flat", "hip_flat", "inseam", "thigh", "leg_opening"],
}

CLASSIFY_PROMPT = f"""You are labelling a single second-hand garment laid flat for resale.

Return ONLY compact JSON, no prose:
{{"garment_type": <one of {GARMENT_TYPES}>, "category": "top" | "bottom"}}

Rules:
- Identify the single main garment in the image.
- Do NOT estimate, guess, or output ANY sizes, measurements, or numbers. Another system
  measures the garment geometrically. Your only job is to name it.
- If unsure between two types, pick the closest and still return valid JSON.
"""
