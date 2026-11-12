import json

from worker.workflows.veille import SourceOutcome, VeilleItem, synthesize_report


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeChat:
    def __init__(self, content):
        self._content = content

    def complete(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def test_synthesize_report_without_items(monkeypatch):
    import worker.workflows.veille as veille

    monkeypatch.setattr(veille.config, "AGENT_TITLE", "Test")
    report = _run(veille, [])
    assert "Aucune nouveaute" in report


def _run(veille, outcomes):
    import asyncio

    return asyncio.run(veille.synthesize_report(outcomes, 7))


def test_synthesize_report_builds_prompt(monkeypatch):
    import worker.workflows.veille as veille

    captured = {}

    def fake_complete(**kwargs):
        captured.update(kwargs)
        return _FakeResponse("# Rapport\n\nContenu.")

    class FakeChat:
        complete = staticmethod(fake_complete)

    class FakeClient:
        chat = FakeChat()

    import mistralai.workflows.client as client_module

    monkeypatch.setattr(client_module, "get_mistral_client", lambda **kw: FakeClient())

    outcome = SourceOutcome(
        name="Source test",
        ok=True,
        items=[
            VeilleItem(
                source="Source test",
                title="Loi de finances sociales",
                url="https://example.gouv.fr/loi",
                published="2026-11-09",
                excerpt="Dispositions sociales",
            )
        ],
    )
    report = _run(veille, [outcome])
    assert report.startswith("# Rapport")
    assert "EXCLUSIVEMENT" in captured["messages"][0]["content"]
    payload = json.loads(
        captured["messages"][1]["content"].split("Donnees collectees (JSON) :\n")[1]
    )
    assert payload["elements_collectes"][0]["title"] == "Loi de finances sociales"
