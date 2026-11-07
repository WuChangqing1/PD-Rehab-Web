from app.services import integration_knowledge as knowledge


def test_both_hands_question_gets_actual_platform_instructions(monkeypatch):
    monkeypatch.setattr(knowledge.settings, "expert_llm_base_url", "")
    result = knowledge.answer_question("如何进行左右手同时训练", None)

    assert "双手同时敲击" in result["answer"]
    assert "两个高亮键" in result["answer"]
    assert "双手同时敲击" in result["sources"][0]["title"]


def test_alternating_and_simultaneous_questions_retrieve_different_guides(monkeypatch):
    monkeypatch.setattr(knowledge.settings, "expert_llm_base_url", "")
    alternating = knowledge.answer_question("如何进行左右手交替训练", None)
    comparison = knowledge.answer_question("左右手交替和双手同时敲击有什么区别", None)

    assert "左右手交替" in alternating["sources"][0]["title"]
    assert "双手同时敲击" not in alternating["answer"]
    assert {"左右手交替", "双手同时敲击"} <= {
        source["title"].split("：")[-1] for source in comparison["sources"]
    }


def test_question_is_separate_from_reviewed_system_context(monkeypatch):
    monkeypatch.setattr(knowledge.settings, "expert_llm_base_url", "https://example.invalid/v1")
    monkeypatch.setattr(knowledge.settings, "expert_llm_model", "glm-test")
    question = "双手同步怎么练？用户输入标记"

    def provider(system, user):
        assert user == question
        assert question not in system
        assert "双手同时敲击" in system
        return "选择双手同时敲击。"

    result = knowledge.answer_question(question, provider)
    assert result["provider_used"] is True
    assert result["model"] == "glm-test"
