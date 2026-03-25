"""
Tests for Persona models, specifically content_types field validation.
"""
import pytest
from pydantic import ValidationError
from app.models.persona import PersonaCard, AppearanceFeatures


class TestPersonaCardContentTypes:
    """Tests for PersonaCard.content_types field validation"""
    
    def test_content_types_none_is_valid(self):
        """None should be accepted (backward compatibility)"""
        persona = PersonaCard(
            name="Test",
            occupation="Developer",
            personality_tags=["creative"],
            speech_pattern="casual",
            values=["innovation"],
            weekly_lifestyle="coding",
            content_types=None
        )
        assert persona.content_types is None
    
    def test_content_types_empty_list_is_valid(self):
        """Empty list should be accepted (backward compatibility)"""
        persona = PersonaCard(
            name="Test",
            occupation="Developer",
            personality_tags=["creative"],
            speech_pattern="casual",
            values=["innovation"],
            weekly_lifestyle="coding",
            content_types=[]
        )
        assert persona.content_types == []
    
    def test_content_types_single_valid_type(self):
        """Single valid content type should be accepted"""
        persona = PersonaCard(
            name="Test",
            occupation="Developer",
            personality_tags=["creative"],
            speech_pattern="casual",
            values=["innovation"],
            weekly_lifestyle="coding",
            content_types=["educational"]
        )
        assert persona.content_types == ["educational"]
    
    def test_content_types_multiple_valid_types(self):
        """Multiple valid content types (up to 3) should be accepted"""
        persona = PersonaCard(
            name="Test",
            occupation="Developer",
            personality_tags=["creative"],
            speech_pattern="casual",
            values=["innovation"],
            weekly_lifestyle="coding",
            content_types=["educational", "entertainment", "engagement"]
        )
        assert len(persona.content_types) == 3
        assert "educational" in persona.content_types
    
    def test_content_types_all_allowed_values(self):
        """Test all allowed content type values"""
        allowed = ["educational", "entertainment", "promotional", "engagement", "personal_story"]
        for content_type in allowed:
            persona = PersonaCard(
                name="Test",
                occupation="Developer",
                personality_tags=["creative"],
                speech_pattern="casual",
                values=["innovation"],
                weekly_lifestyle="coding",
                content_types=[content_type]
            )
            assert persona.content_types == [content_type]
    
    def test_content_types_too_many_raises_error(self):
        """More than 3 content types should raise ValidationError"""
        with pytest.raises(ValidationError) as excinfo:
            PersonaCard(
                name="Test",
                occupation="Developer",
                personality_tags=["creative"],
                speech_pattern="casual",
                values=["innovation"],
                weekly_lifestyle="coding",
                content_types=["educational", "entertainment", "promotional", "engagement"]
            )
        assert "at most 3 items" in str(excinfo.value)
    
    def test_content_types_invalid_value_raises_error(self):
        """Invalid content type value should raise ValidationError"""
        with pytest.raises(ValidationError) as excinfo:
            PersonaCard(
                name="Test",
                occupation="Developer",
                personality_tags=["creative"],
                speech_pattern="casual",
                values=["innovation"],
                weekly_lifestyle="coding",
                content_types=["invalid_type"]
            )
        assert "Invalid content_type" in str(excinfo.value)
    
    def test_content_types_duplicate_values_raises_error(self):
        """Duplicate content types should raise ValidationError"""
        with pytest.raises(ValidationError) as excinfo:
            PersonaCard(
                name="Test",
                occupation="Developer",
                personality_tags=["creative"],
                speech_pattern="casual",
                values=["innovation"],
                weekly_lifestyle="coding",
                content_types=["educational", "educational"]
            )
        assert "must not contain duplicates" in str(excinfo.value)
    
    def test_content_types_default_value(self):
        """When not provided, content_types should default to None"""
        persona = PersonaCard(
            name="Test",
            occupation="Developer",
            personality_tags=["creative"],
            speech_pattern="casual",
            values=["innovation"],
            weekly_lifestyle="coding"
        )
        assert persona.content_types is None
