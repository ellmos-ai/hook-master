from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_library_module(name: str, filename: str):
    path = REPO / "library" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_skill(skills_root: Path, name: str) -> None:
    skill_dir = skills_root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: " + name + "\n---\nbody\n", encoding="utf-8")


def _write_profile(profiles_dir: Path, name: str, data: dict) -> None:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def _basic_setup(tmp_path, monkeypatch):
    hook = _load_library_module("starter_pack_hook_test", "starter_pack_hook.py")
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "starter-pack-hook-creator"
    profiles_dir = skill_dir / "profiles"
    skills_root.mkdir(parents=True)
    skill_dir.mkdir(parents=True)

    monkeypatch.setattr(hook, "SKILLS_ROOT", str(skills_root))
    monkeypatch.setattr(hook, "SKILL_DIR", str(skill_dir))
    monkeypatch.setattr(hook, "PROFILES_DIR", str(profiles_dir))
    monkeypatch.setattr(hook, "PROFILE_FILE", str(tmp_path / "starter-pack.profile"))
    monkeypatch.delenv("STARTER_PACK_PROFILE", raising=False)

    (skill_dir / "recipe.md").write_text("1. Testrezept-Zeile.\n", encoding="utf-8")
    return hook, skills_root, profiles_dir


def test_no_profile_returns_empty_and_exit_0(tmp_path, monkeypatch):
    hook, _skills_root, _profiles_dir = _basic_setup(tmp_path, monkeypatch)
    assert hook.build_message() == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert hook.main() == 0


def test_single_profile_lists_installed_entries_only(tmp_path, monkeypatch, capsys):
    hook, skills_root, profiles_dir = _basic_setup(tmp_path, monkeypatch)
    _make_skill(skills_root, "skill-finder")
    _write_profile(
        profiles_dir,
        "ellmos",
        {
            "name": "ellmos",
            "extends": [],
            "recipe": "recipe.md",
            "categories": [
                {
                    "id": "skill-routing",
                    "title": "Skill-Routing",
                    "when": "Faehigkeit fehlt?",
                    "entry": ["skill-finder", "not-installed-skill"],
                    "more": [],
                },
                {
                    "id": "nutzerassistenz",
                    "title": "Nutzerassistenz",
                    "when": "Alltagsaufgabe?",
                    "entry": [],
                    "more": [],
                },
            ],
        },
    )

    message = hook.build_message()
    assert "Testrezept-Zeile" in message
    assert "skill-finder" in message
    assert "not-installed-skill" not in message
    assert "-> skill-finder" in message.splitlines()[-1] or "Nutzerassistenz" in message

    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"s"}'))
    assert hook.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "skill-finder" in out["hookSpecificOutput"]["additionalContext"]


def test_second_profile_overrides_category_without_duplicating(tmp_path, monkeypatch):
    hook, skills_root, profiles_dir = _basic_setup(tmp_path, monkeypatch)
    _make_skill(skills_root, "skill-finder")
    _make_skill(skills_root, "code-skill-index")
    base = {
        "name": "ellmos",
        "extends": [],
        "recipe": "recipe.md",
        "categories": [
            {
                "id": "skill-routing",
                "title": "Skill-Routing",
                "when": "Public-Variante",
                "entry": ["skill-finder"],
                "more": [],
            }
        ],
    }
    overlay = {
        "name": "private",
        "extends": ["ellmos"],
        "categories": [
            {
                "id": "skill-routing",
                "title": "Skill-Routing",
                "when": "Private-Variante",
                "entry": ["code-skill-index"],
                "more": [],
            }
        ],
    }
    _write_profile(profiles_dir, "ellmos", base)
    _write_profile(profiles_dir, "private", overlay)

    monkeypatch.setenv("STARTER_PACK_PROFILE", "ellmos,private")
    message = hook.build_message()

    assert message.count("Skill-Routing") == 1  # Kategorie nicht doppelt, voll ersetzt
    assert "code-skill-index" in message
    assert "skill-finder" not in message  # Public-Eintrag wurde vollstaendig ersetzt


def test_profile_chain_from_env_and_file(tmp_path, monkeypatch):
    hook, _skills_root, profiles_dir = _basic_setup(tmp_path, monkeypatch)
    _write_profile(profiles_dir, "a", {"name": "a", "categories": []})
    _write_profile(profiles_dir, "b", {"name": "b", "categories": []})

    monkeypatch.setenv("STARTER_PACK_PROFILE", "a,b")
    assert hook._profile_chain() == ["a", "b"]

    monkeypatch.delenv("STARTER_PACK_PROFILE", raising=False)
    Path(hook.PROFILE_FILE).write_text("a, b  # Kommentar\n", encoding="utf-8")
    assert hook._profile_chain() == ["a", "b"]


def test_missing_profile_in_chain_is_skipped_fail_open(tmp_path, monkeypatch):
    hook, skills_root, profiles_dir = _basic_setup(tmp_path, monkeypatch)
    _make_skill(skills_root, "skill-finder")
    _write_profile(
        profiles_dir,
        "ellmos",
        {
            "name": "ellmos",
            "categories": [
                {
                    "id": "skill-routing",
                    "title": "Skill-Routing",
                    "when": "x",
                    "entry": ["skill-finder"],
                    "more": [],
                }
            ],
        },
    )
    monkeypatch.setenv("STARTER_PACK_PROFILE", "ellmos,nonexistent-host-profile")
    message = hook.build_message()
    assert "skill-finder" in message


def test_broken_profile_json_is_fail_open(tmp_path, monkeypatch):
    hook, _skills_root, profiles_dir = _basic_setup(tmp_path, monkeypatch)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / "ellmos.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("STARTER_PACK_PROFILE", "ellmos")
    assert hook.build_message() == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert hook.main() == 0


def test_corrupt_stdin_does_not_crash_main(tmp_path, monkeypatch):
    hook, skills_root, profiles_dir = _basic_setup(tmp_path, monkeypatch)
    _make_skill(skills_root, "skill-finder")
    _write_profile(
        profiles_dir,
        "ellmos",
        {
            "name": "ellmos",
            "categories": [
                {
                    "id": "skill-routing",
                    "title": "Skill-Routing",
                    "when": "x",
                    "entry": ["skill-finder"],
                    "more": [],
                }
            ],
        },
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json at all"))
    assert hook.main() == 0
