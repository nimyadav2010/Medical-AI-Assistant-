from typing import List, Dict

class SearchTool:
    def search(self, query: str) -> List[Dict[str, str]]:
        # Mock search results for demo
        # In a real application, this would call Bing Search API or similar
        print(f"Searching for: {query}")
        return [
            {"title": "Chronic Kidney Disease Treatment", "snippet": "Treatments include medications to control blood pressure, dialysis, and kidney transplant.", "source": "Medline"},
            {"title": "CKD Diet", "snippet": "A kidney-friendly diet limits sodium, potassium, and phosphorus.", "source": "National Kidney Foundation"},
            {"title": "Nephrologist Appointment", "snippet": "Nephrologists specialize in kidney care and can help manage CKD.", "source": "Healthline"}
        ]
