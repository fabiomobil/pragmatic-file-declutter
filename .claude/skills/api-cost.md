# Skill: API Cost Estimation

## Pricing (as of 2026-02 — revalidate every 3 months)

### Gemini 2.0 Flash (Primary)
- Input: $0.10 / 1M tokens
- Output: $0.40 / 1M tokens
- Free tier: 15 RPM, 1M tokens/min, 1,500 requests/day
- Average tokens per photo: ~800 input + ~200 output
- **Cost per photo: ~$0.001**

### GPT-4o mini (Fallback)
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens
- Average tokens per photo: ~800 input + ~200 output
- **Cost per photo: ~$0.002**

## Cost Estimation Formula
```python
def estimate_cost(total_photos: int, clip_coverage: float = 0.90) -> dict:
    """Estimate API costs for classification.

    Args:
        total_photos: Total number of photos to classify
        clip_coverage: Fraction handled locally by CLIP (default 90%)

    Returns:
        Dict with cost breakdown
    """
    api_photos = int(total_photos * (1 - clip_coverage))
    gemini_cost = api_photos * 0.001
    gpt_cost = api_photos * 0.002

    return {
        "total_photos": total_photos,
        "local_clip": total_photos - api_photos,
        "api_photos": api_photos,
        "gemini_estimated": f"${gemini_cost:.2f}",
        "gpt_estimated": f"${gpt_cost:.2f}",
        "recommended": "gemini",
    }
```

## UX Requirements
- ALWAYS show cost estimation BEFORE making API calls
- Show Gemini and GPT quotes side by side
- Let user choose which API to use (or cancel)
- Track actual spend during session and show running total
