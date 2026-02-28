"""
AI Detector Service - Hive AI Detection Integration

Uses Hive Moderation API to detect AI-generated images.
Docs: https://docs.thehive.ai/docs/ai-generated-content
"""

import os
import httpx
from typing import Optional


class AIDetectorService:
    """Service for detecting AI-generated images using Hive API."""
    
    def __init__(self):
        self.api_key = os.getenv("HIVE_API_KEY")
        self.api_url = "https://api.thehive.ai/api/v2/task/sync"
        
    async def detect_ai_image(self, image_url: str) -> float:
        """
        Detect if an image is AI-generated using Hive AI Detector.
        
        Args:
            image_url: Public URL of the image to analyze
            
        Returns:
            float: AI detection score (0-1)
                  0.0 = definitely real
                  1.0 = definitely AI-generated
                  -1.0 = error occurred
        """
        if not self.api_key:
            print("⚠️ HIVE_API_KEY not set in .env - returning error score")
            return -1.0
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "url": image_url,
                        "classes": ["ai_generated"]
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract AI detection score from response
                # Hive API returns: status[0].response.output[0].classes[0].score
                try:
                    ai_score = (
                        data["status"][0]
                        ["response"]["output"][0]
                        ["classes"][0]["score"]
                    )
                    return float(ai_score)
                except (KeyError, IndexError, TypeError) as e:
                    print(f"⚠️ Unexpected Hive API response format: {e}")
                    print(f"Response: {data}")
                    return -1.0
                    
        except httpx.HTTPStatusError as e:
            print(f"❌ Hive API HTTP error: {e.response.status_code}")
            print(f"Response: {e.response.text}")
            return -1.0
        except httpx.RequestError as e:
            print(f"❌ Hive API request error: {e}")
            return -1.0
        except Exception as e:
            print(f"❌ Unexpected error in AI detection: {e}")
            return -1.0


# Singleton instance
_ai_detector = AIDetectorService()


async def detect_ai_image(image_url: str) -> float:
    """
    Convenience function for AI detection.
    
    Args:
        image_url: Public URL of the image to analyze
        
    Returns:
        float: AI detection score (0-1, or -1 for error)
    """
    return await _ai_detector.detect_ai_image(image_url)
