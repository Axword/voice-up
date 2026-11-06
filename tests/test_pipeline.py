"""Routers and executors are swappable behind the typed pipeline contract."""

from app import config, profiles
from app.pipeline import Intent, KeyAction, Pipeline, ProfileRouter, RouteContext, TypeTextAction
from controller.service import VoiceService


def profile(*phrases):
    return profiles.Profile(
        id="p", name="P", commands=[
            profiles.VoiceCommand(id=f"c{i}", phrase=phrase, keys=["r"]) for i, phrase in enumerate(phrases)
        ],
    )


def test_profile_router_returns_key_intent_with_full_confidence():
    intent = ProfileRouter().route("Reload", RouteContext(profile("reload")))
    assert intent.action == KeyAction("c0", ("r",), "click", 3000)
    assert intent.confidence == 1.0 and intent.source == "profile"


def test_first_router_with_an_intent_wins_and_executor_follows_action_type():
    typed = []

    class Dictation:
        name = "dictation"

        def route(self, text, context):
            return Intent(TypeTextAction(text), self.name) if text.startswith("pisz") else None

    class Typer:
        def execute(self, action):
            typed.append(action.text)
            return True

        def release_all(self):
            typed.append("released")

    pipeline = Pipeline([Dictation(), ProfileRouter()], {TypeTextAction: Typer()})
    context = RouteContext(profile("reload"))
    assert pipeline.execute(pipeline.route("pisz cześć", context))
    assert typed == ["cześć"]
    assert pipeline.route("reload", context).source == "profile"
    pipeline.release_all()
    assert typed[-1] == "released"


def test_action_without_executor_is_reported_as_not_executed():
    assert not Pipeline().execute(Intent(TypeTextAction("x"), "test"))


def test_service_runs_a_custom_router_through_its_pipeline():
    service = VoiceService()
    service._settings = config.Settings()
    service._profiles = profiles.ProfilesDocument(active_profile_id="p", profiles=[profile("reload")])
    seen = []

    class Echo:
        def execute(self, action):
            seen.append(action.text)
            return True

        def release_all(self):
            pass

    class Always:
        name = "always"

        def route(self, text, context):
            return Intent(TypeTextAction(text), self.name, 0.5)

    service.pipeline.routers.insert(0, Always())
    service.pipeline.executors[TypeTextAction] = Echo()
    events = []
    service.set_event_sink(events.append)
    service.handle_transcript("cokolwiek")
    heard = next(e for e in events if e["type"] == "heard")
    assert seen == ["cokolwiek"] and heard["executed"] and heard["source"] == "always"
