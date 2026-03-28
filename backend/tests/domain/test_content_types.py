"""
Domain Tests — Content Types Feature

完整测试 content_type 功能的 user flow：
- Persona 创建时设置 content_types
- 自动产出图文范例
- 发文时使用/覆盖 content_type
- AI 生成结果符合类型风格
"""
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.persona import PersonaCard, ExamplePost
from app.services import genesis_service
from app.services import life_stream_service


# ---------------------------------------------------------------------------
# Domain: Persona Creation
# ---------------------------------------------------------------------------

class TestPersonaCreationWithContentTypes:
    """测试 Persona 建立时的 content_types 功能"""

    @pytest.mark.asyncio
    async def test_create_persona_with_single_content_type(self):
        """建立 Persona 时可设置单个 content_type"""
        with patch('app.services.genesis_service.client_anthropic') as mock_client:
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"name":"测试","occupation":"工程师","personality_tags":["技术"],"speech_pattern":"简洁","values":["创新"],"weekly_lifestyle":"忙碌"}')]
            ))

            result = await genesis_service.create_persona(
                description="一个技术博主",
                persona_id="test-001",
                content_types=["educational"]
            )

            assert result["persona_id"] == "test-001"
            assert result["persona"].content_types == ["educational"]

    @pytest.mark.asyncio
    async def test_create_persona_with_multiple_content_types(self):
        """建立 Persona 时可设置 1-3 个 content_types"""
        with patch('app.services.genesis_service.client_anthropic') as mock_client:
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"name":"测试","occupation":"网红","personality_tags":["活泼"],"speech_pattern":"可爱","values":["快乐"],"weekly_lifestyle":"多彩"}')]
            ))

            result = await genesis_service.create_persona(
                description="一个生活博主",
                persona_id="test-002",
                content_types=["entertainment", "personal_story", "engagement"]
            )

            assert len(result["persona"].content_types) == 3
            assert set(result["persona"].content_types) == {"entertainment", "personal_story", "engagement"}

    @pytest.mark.asyncio
    async def test_create_persona_without_content_types(self):
        """建立 Persona 时 content_types 可为空（向后相容）"""
        with patch('app.services.genesis_service.client_anthropic') as mock_client:
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"name":"测试","occupation":"博主","personality_tags":["随性"],"speech_pattern":"自然","values":["真实"],"weekly_lifestyle":"随性"}')]
            ))

            result = await genesis_service.create_persona(
                description="一个随性博主",
                persona_id="test-003",
                content_types=None
            )

            assert result["persona"].content_types is None


# ---------------------------------------------------------------------------
# Domain: Example Post Generation
# ---------------------------------------------------------------------------

class TestExamplePostGeneration:
    """测试人设卡建立后自动产出图文范例"""

    @pytest.mark.asyncio
    async def test_confirm_persona_generates_example_post(self):
        """confirm_persona 应该自动产出图文范例"""
        from datetime import datetime
        from app.models.persona import AppearanceFeatures

        # 模拟 Persona
        persona_id = str(uuid.uuid4())
        persona = PersonaCard(
            id=persona_id,
            name="测试",
            occupation="博主",
            personality_tags=["活泼"],
            speech_pattern="可爱",
            values=["快乐"],
            weekly_lifestyle="充实",
            content_types=["entertainment"],
            reference_face_url="https://example.com/face.jpg",
            appearance=AppearanceFeatures(
                facial_features="friendly",
                skin_tone="fair",
                hair="long",
                body="athletic",
                style="casual",
                image_prompt="casual person"
            ),
            created_at=datetime.utcnow().isoformat() + "Z"
        )

        with patch('app.services.genesis_service.client_anthropic') as mock_client, \
             patch('app.services.comfyui_service.generate_image', new_callable=AsyncMock) as mock_gen_image, \
             patch('app.services.comfyui_service.build_realism_prompt', return_value="mocked full prompt") as mock_build, \
             patch('app.services.cloudinary_service.upload_from_url', new_callable=AsyncMock) as mock_upload:

            # 模拟 Claude 生成文案
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"scene":"公园散步","caption":"今天天气真好 ☀️","scene_prompt":"walking in park","hashtags":["#公园","#散步"]}')]
            ))

            # 模拟图片生成
            mock_gen_image.return_value = "https://replicate.com/img.png"
            mock_upload.return_value = "https://cloudinary.com/img.png"

            # 执行 confirm_persona
            result = await genesis_service.confirm_persona(persona)

            # 验证 example_post 已生成
            assert result["persona"].example_post is not None
            assert result["persona"].example_post.scene == "公园散步"
            assert result["persona"].example_post.caption == "今天天气真好 ☀️"
            assert result["persona"].example_post.image_url == "https://cloudinary.com/img.png"

    @pytest.mark.asyncio
    async def test_example_post_matches_first_content_type(self):
        """图文范例应该符合 content_types[0] 的风格"""
        persona_id = str(uuid.uuid4())
        persona = PersonaCard(
            id=persona_id,
            name="测试",
            occupation="老师",
            personality_tags=["专业"],
            speech_pattern="严谨",
            values=["教育"],
            weekly_lifestyle="规律",
            content_types=["educational", "engagement"],  # 第一个是 educational
        )

        with patch('app.services.genesis_service.client_anthropic') as mock_client:
            # 验证 prompt 包含 "知识分享"
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"scene":"教室","caption":"今天教大家...","scene_prompt":"classroom","hashtags":["#学习"]}')]
            ))

            result = await genesis_service.generate_example_post(persona)

            # 检查 LLM 调用的 system prompt 是否包含 educational 的描述
            call_args = mock_client.messages.create.call_args
            system_prompt = call_args.kwargs.get('system', '')
            assert "知識分享" in system_prompt


# ---------------------------------------------------------------------------
# Domain: Content Generation
# ---------------------------------------------------------------------------

class TestContentGenerationWithContentType:
    """测试发文时 content_type 的使用"""

    @pytest.mark.asyncio
    async def test_generate_post_uses_persona_default_content_type(self):
        """未指定 content_type 时应使用 Persona 预设值"""
        from app.services.persona_storage import save_persona, delete_persona
        from app.models.persona import AppearanceFeatures
        from datetime import datetime

        # 准备测试 Persona
        persona_id = str(uuid.uuid4())
        persona = PersonaCard(
            id=persona_id,
            name="测试",
            occupation="博主",
            personality_tags=["活泼"],
            speech_pattern="可爱",
            values=["快乐"],
            weekly_lifestyle="充实",
            content_types=["entertainment", "engagement"],  # 预设
            reference_face_url="https://example.com/face.jpg",
            appearance=AppearanceFeatures(
                facial_features="friendly", skin_tone="fair", hair="long",
                body="athletic", style="casual", image_prompt="test prompt"
            ),
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        save_persona(persona_id, persona)

        try:
            with patch('app.services.life_stream_service.client') as mock_client, \
                 patch('app.services.life_stream_service._generate_and_upload_image', new_callable=AsyncMock) as mock_gen:

                mock_client.messages.create = AsyncMock(return_value=MagicMock(
                    content=[MagicMock(text='{"scene":"测试","caption":"测试文案","scene_prompt":"test","hashtags":["#测试"]}')]
                ))
                mock_gen.return_value = "https://example.com/img.png"

                # 未传入 content_type
                await life_stream_service.generate_single_post(
                    persona_id=persona_id,
                    date="2026-04-01",
                    content_type=None  # 未指定
                )

                # 验证使用了 entertainment（第一个预设类型）
                call_args = mock_client.messages.create.call_args
                system_prompt = call_args.kwargs.get('system', '')
                assert "娛樂互動" in system_prompt  # entertainment 对应的标签
        finally:
            delete_persona(persona_id)

    @pytest.mark.asyncio
    async def test_generate_post_can_override_content_type(self):
        """用户可覆盖 Persona 预设，选择其他 content_type"""
        from app.services.persona_storage import save_persona, delete_persona
        from app.models.persona import AppearanceFeatures
        from datetime import datetime

        persona_id = str(uuid.uuid4())
        persona = PersonaCard(
            id=persona_id,
            name="测试",
            occupation="博主",
            personality_tags=["活泼"],
            speech_pattern="可爱",
            values=["快乐"],
            weekly_lifestyle="充实",
            content_types=["entertainment"],  # 预设
            reference_face_url="https://example.com/face.jpg",
            appearance=AppearanceFeatures(
                facial_features="friendly", skin_tone="fair", hair="long",
                body="athletic", style="casual", image_prompt="test prompt"
            ),
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        save_persona(persona_id, persona)

        try:
            with patch('app.services.life_stream_service.client') as mock_client, \
                 patch('app.services.life_stream_service._generate_and_upload_image', new_callable=AsyncMock) as mock_gen:

                mock_client.messages.create = AsyncMock(return_value=MagicMock(
                    content=[MagicMock(text='{"scene":"测试","caption":"测试文案","scene_prompt":"test","hashtags":["#测试"]}')]
                ))
                mock_gen.return_value = "https://example.com/img.png"

                # 覆盖为 educational
                await life_stream_service.generate_single_post(
                    persona_id=persona_id,
                    date="2026-04-01",
                    content_type="educational"  # 覆盖
                )

                # 验证使用了 educational
                call_args = mock_client.messages.create.call_args
                system_prompt = call_args.kwargs.get('system', '')
                assert "知識分享" in system_prompt
        finally:
            delete_persona(persona_id)


class TestContentTypeStyles:
    """测试 5 种 content_type 各自的风格定义"""

    def test_all_five_content_types_have_style_definitions(self):
        """验证 5 种类型都有风格定义"""
        from app.services.life_stream_service import CONTENT_TYPE_STYLES

        required_types = ["educational", "entertainment", "promotional", "engagement", "personal_story"]
        for content_type in required_types:
            assert content_type in CONTENT_TYPE_STYLES, f"{content_type} missing style definition"

    def test_educational_style_emphasizes_clarity(self):
        """educational 应强调清晰解说"""
        from app.services.life_stream_service import CONTENT_TYPE_STYLES

        assert "清晰解說" in CONTENT_TYPE_STYLES["educational"] or "清晰" in CONTENT_TYPE_STYLES["educational"]

    def test_entertainment_style_emphasizes_fun(self):
        """entertainment 应强调轻松幽默"""
        from app.services.life_stream_service import CONTENT_TYPE_STYLES

        assert "輕鬆" in CONTENT_TYPE_STYLES["entertainment"] or "幽默" in CONTENT_TYPE_STYLES["entertainment"]

    def test_promotional_style_emphasizes_cta(self):
        """promotional 应强调 CTA"""
        from app.services.life_stream_service import CONTENT_TYPE_STYLES

        assert "CTA" in CONTENT_TYPE_STYLES["promotional"] or "吸睛" in CONTENT_TYPE_STYLES["promotional"]

    def test_engagement_style_emphasizes_interaction(self):
        """engagement 应强调互动"""
        from app.services.life_stream_service import CONTENT_TYPE_STYLES

        assert "互動" in CONTENT_TYPE_STYLES["engagement"] or "討論" in CONTENT_TYPE_STYLES["engagement"]

    def test_personal_story_style_emphasizes_emotion(self):
        """personal_story 应强调情感共鸣"""
        from app.services.life_stream_service import CONTENT_TYPE_STYLES

        assert "情感" in CONTENT_TYPE_STYLES["personal_story"] or "故事" in CONTENT_TYPE_STYLES["personal_story"]


# ---------------------------------------------------------------------------
# Domain: Integration Flow
# ---------------------------------------------------------------------------

class TestContentTypeEndToEndFlow:
    """测试完整 content_type 功能流程"""

    @pytest.mark.asyncio
    async def test_full_persona_creation_to_post_generation_flow(self):
        """完整流程：建立 Persona（含 content_types）→ 产出范例 → 发文"""
        from app.services.persona_storage import save_persona, delete_persona
        from datetime import datetime

        persona_id = str(uuid.uuid4())

        try:
            # Step 1: 建立 Persona（含 content_types）
            with patch('app.services.genesis_service.client_anthropic') as mock_client:
                mock_client.messages.create = AsyncMock(return_value=MagicMock(
                    content=[MagicMock(text='{"name":"完整测试","occupation":"博主","personality_tags":["专业"],"speech_pattern":"清晰","values":["教育"],"weekly_lifestyle":"忙碌"}')]
                ))

                persona_result = await genesis_service.create_persona(
                    description="一个专业博主",
                    persona_id=persona_id,
                    content_types=["educational", "engagement"]
                )

                assert persona_result["persona"].content_types == ["educational", "engagement"]

            # Step 2: confirm_persona 应产出范例（模拟）
            from app.models.persona import AppearanceFeatures
            persona = persona_result["persona"]
            persona.reference_face_url = "https://example.com/face.jpg"
            persona.appearance = AppearanceFeatures(
                facial_features="friendly", skin_tone="fair", hair="long",
                body="athletic", style="casual", image_prompt="test person"
            )

            with patch('app.services.genesis_service.client_anthropic') as mock_client, \
                 patch('app.services.comfyui_service.generate_image', new_callable=AsyncMock) as mock_gen_image, \
                 patch('app.services.comfyui_service.build_realism_prompt', return_value="mocked full prompt"), \
                 patch('app.services.cloudinary_service.upload_from_url', new_callable=AsyncMock) as mock_upload:

                mock_client.messages.create = AsyncMock(return_value=MagicMock(
                    content=[MagicMock(text='{"scene":"测试","caption":"测试","scene_prompt":"test","hashtags":["#测试"]}')]
                ))
                mock_gen_image.return_value = "https://replicate.com/img.png"
                mock_upload.return_value = "https://cloudinary.com/img.png"

                confirmed = await genesis_service.confirm_persona(persona)

                assert confirmed["persona"].example_post is not None

            # Step 3: 发文时使用 content_type
            save_persona(persona_id, confirmed["persona"])

            with patch('app.services.life_stream_service.client') as mock_client, \
                 patch('app.services.life_stream_service._generate_and_upload_image', new_callable=AsyncMock) as mock_gen:

                mock_client.messages.create = AsyncMock(return_value=MagicMock(
                    content=[MagicMock(text='{"scene":"测试","caption":"测试","scene_prompt":"test","hashtags":["#测试"]}')]
                ))
                mock_gen.return_value = "https://example.com/img.png"

                post = await life_stream_service.generate_single_post(
                    persona_id=persona_id,
                    date="2026-04-01",
                    content_type="educational"  # 明确指定
                )

                assert post["scene"] == "测试"

        finally:
            # 清理测试数据
            delete_persona(persona_id)
